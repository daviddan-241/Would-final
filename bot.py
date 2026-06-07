"""
Telegram Coin Scanner & SMM Raid Engine Bot
Fresh coins only + Multi-Platform Auto-Post, Mirroring, Ad Scheduling & Auto-Raid Engine.
"""
import logging
import asyncio
import aiohttp
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from server import start_health_server
from formatter import format_caption, build_keyboard
from scanners.base import TokenInfo
from scanners.dexscreener import scan_dexscreener
from scanners.geckoterminal import scan_geckoterminal
from scanners.pumpfun import scan_pumpfun
from scanners.birdeye import scan_extra_sources
import seen_db

logger = logging.getLogger(__name__)

scan_count = 0
total_posted = 0


# --- SMM Telegram Handlers ---

async def mirror_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets up a target account to clone, rewrite and post content."""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: <code>/mirror [platform] [handle]</code>\n"
            "Example: <code>/mirror twitter @elonmusk</code>\n"
            "Platforms: twitter, tiktok, instagram, facebook",
            parse_mode=ParseMode.HTML
        )
        return
        
    platform = args[0].lower()
    handle = args[1]
    
    if platform not in ["twitter", "tiktok", "instagram", "facebook"]:
        await update.message.reply_text("❌ Invalid platform. Supported: twitter, tiktok, instagram, facebook.")
        return
        
    import marketing_db
    marketing_db.add_target(platform, handle, "TG_GROUP")
    await update.message.reply_text(
        f"✅ Registered <b>{platform.title()}</b> mirror stream for <code>{handle}</code>!\n"
        f"New posts will be copied, rewritten by AI, and automatically posted.",
        parse_mode=ParseMode.HTML
    )


async def raid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Launches a multi-platform community raid with deep action links and executes auto-raiding."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Usage: <code>/raid [url] [optional_caption]</code>\n"
            "Example: <code>/raid https://x.com/elonmusk/status/... Bullish!</code>",
            parse_mode=ParseMode.HTML
        )
        return
        
    url = args[0]
    caption = " ".join(args[1:]) if len(args) > 1 else ""
    
    platform = "twitter"
    if "tiktok.com" in url:
        platform = "tiktok"
    elif "instagram.com" in url:
        platform = "instagram"
    elif "facebook.com" in url:
        platform = "facebook"
        
    import marketing_db
    import raid_engine
    
    # 1. Register active raid in DB (triggers automated self-bots fleet)
    marketing_db.add_raid(platform, url, caption)
    
    # 2. Build community interactive post
    msg = raid_engine.build_raid_message(platform, url, caption)
    kbd = raid_engine.generate_raid_keyboard(platform, url)
    
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=kbd)


async def schedule_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedules recurrent ads at regular intervals (in minutes)."""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: <code>/schedule_ad [interval_min] [text_content]</code>\n"
            "Example: <code>/schedule_ad 30 🚀 Secure your entry!</code>",
            parse_mode=ParseMode.HTML
        )
        return
        
    try:
        interval = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Interval must be a number representing minutes.")
        return
        
    content = " ".join(args[1:])
    
    import marketing_db
    marketing_db.add_ad("telegram", content, interval)
    await update.message.reply_text(
        f"✅ Scheduled recurring promotional ad! Running every <b>{interval}</b> minutes.",
        parse_mode=ParseMode.HTML
    )


async def accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists connected automated self-bots."""
    import marketing_db
    accs = marketing_db.get_accounts()
    if not accs:
        await update.message.reply_text(
            "⚠️ No automated SMM accounts linked yet.\n"
            "Open the Web Dashboard at port 10000 to add credentials and tokens!",
            parse_mode=ParseMode.HTML
        )
        return
        
    text = "👤 <b>SMM Automated Account Fleet:</b>\n\n"
    for acc in accs:
        text += f"• <b>{acc['platform'].title()}</b>: <code>{acc['username']}</code> ({acc['status']})\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# --- Core Scanner Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 <b>Coin Scanner & SMM Master Bot</b>\n\n"
        f"Group/Chat ID: <code>{cid}</code>\n\n"
        "🟢 <b>Scanner Commands:</b>\n"
        "/status — View system health\n"
        "/scan — Perform manual coin check\n"
        "/stats — View scan counters\n"
        "/clear — Empty coin database cache\n\n"
        "🔥 <b>SMM & Marketing Commands:</b>\n"
        "/raid <code>[url] [caption]</code> — Detonate multi-platform raid\n"
        "/mirror <code>[platform] [handle]</code> — Clone & rewrite content\n"
        "/schedule_ad <code>[minutes] [text]</code> — Run recurrent ads\n"
        "/accounts — Show automated account fleet",
        parse_mode=ParseMode.HTML,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import marketing_db
    db = marketing_db.load_db()
    targets_count = len(db.get("targets", []))
    completed_raids = len([r for r in db.get("raids", []) if r.get("status") == "Completed"])
    ads_count = len(db.get("ads", []))
    accounts_count = len(db.get("accounts", []))

    await update.message.reply_text(
        f"📊 <b>System status report:</b>\n\n"
        f"⏱ <b>Coin Scan Interval:</b> {config.SCAN_INTERVAL}s\n"
        f"📁 <b>Cached Tokens:</b> {seen_db.seen_count()}\n"
        f"📈 <b>Token Scans:</b> {scan_count} | Posted: {total_posted}\n\n"
        f"🎯 <b>SMM Marketing Engine:</b>\n"
        f"• Clone targets: <b>{targets_count}</b>\n"
        f"• Connected automated accounts: <b>{accounts_count}</b>\n"
        f"• Active ad rotations: <b>{ads_count}</b>\n"
        f"• Automated raids executed: <b>{completed_raids}</b>",
        parse_mode=ParseMode.HTML
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📈 Scans: {scan_count} | Posted: {total_posted} | Cached: {seen_db.seen_count()}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = seen_db.seen_count()
    seen_db.clear_all()
    await update.message.reply_text(f"🧹 Cleared {c} tokens.")


async def manual_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning...")
    count = await run_scan_cycle(context.bot)
    await update.message.reply_text(f"✅ Found {count} new tokens.")


async def send_token(bot: Bot, token: TokenInfo) -> bool:
    """Send token as photo + caption + inline buttons."""
    caption = format_caption(token)
    keyboard = build_keyboard(token)

    # Try photo
    if token.image_url:
        try:
            await bot.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=token.image_url, caption=caption,
                parse_mode=ParseMode.HTML, reply_markup=keyboard,
            )
            return True
        except:
            pass

    # Fallback: text
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=caption, parse_mode=ParseMode.HTML,
            reply_markup=keyboard, disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        logger.error(f"Send failed for {token.name}: {e}")
        return False


async def run_scan_cycle(bot: Bot) -> int:
    global scan_count, total_posted
    scan_count += 1

    all_tokens: list[TokenInfo] = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        if config.ENABLE_PUMPFUN:
            tasks.append(scan_pumpfun(session))
        if config.ENABLE_DEXSCREENER:
            tasks.append(scan_dexscreener(session))
        if config.ENABLE_GECKOTERMINAL:
            tasks.append(scan_geckoterminal(session))
        tasks.append(scan_extra_sources(session))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_tokens.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"Scanner error: {r}")

    # Dedup by contract address within this cycle
    unique: dict[str, TokenInfo] = {}
    for token in all_tokens:
        addr = token.contract_address.lower()
        if addr not in unique:
            unique[addr] = token

    # Filter already-posted (by address, TG link, AND name+symbol)
    new_tokens = []
    for addr, token in unique.items():
        if not seen_db.is_seen(addr, token.telegram_link, token.name, token.symbol):
            new_tokens.append(token)

    # Post
    posted = 0
    for token in new_tokens:
        ok = await send_token(bot, token)
        if ok:
            seen_db.mark_seen(token.contract_address, token.telegram_link, token.name, token.symbol)
            posted += 1
            total_posted += 1
            logger.info(f"✅ {token.name} (${token.symbol}) [{token.chain}] {token.telegram_link}")
        await asyncio.sleep(2)

    return posted


async def periodic_scan(bot: Bot):
    logger.info(f"Scanner started — every {config.SCAN_INTERVAL}s")
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="🤖 <b>Coin Scanner Started</b>\n\n"
                 f"⏱ Every {config.SCAN_INTERVAL}s\n"
                 "📡 Pump.fun + DexScreener + GeckoTerminal\n"
                 "🔗 Fresh coins with Telegram links only",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Startup msg error: {e}")

    while True:
        try:
            count = await run_scan_cycle(bot)
            if count > 0:
                logger.info(f"Cycle #{scan_count}: {count} new")
        except Exception as e:
            logger.error(f"Cycle error: {e}")
        await asyncio.sleep(config.SCAN_INTERVAL)


async def post_init(app: Application):
    # Start the core token scanner loop
    asyncio.create_task(periodic_scan(app.bot))
    
    # Start the SMM automated marketing & cloning engine
    from engine_coordinator import start_all_smm_services
    start_all_smm_services(app.bot)


async def start_smm_offline():
    from engine_coordinator import start_all_smm_services
    start_all_smm_services()
    while True:
        await asyncio.sleep(3600)


def main():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    )
    for noisy in ("httpx", "httpcore", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Start Health check & fully interactive Admin Dashboard Server
    start_health_server()
    print("🚀 Starting SMM-Upgraded Coin Scanner Bot...")

    # Start Telegram bot polling ONLY if tokens are provided
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        print("🤖 Initializing Telegram Coin Scanner...")
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Core commands
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("scan", manual_scan_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("clear", clear_command))
        
        # SMM commands
        app.add_handler(CommandHandler("mirror", mirror_command))
        app.add_handler(CommandHandler("raid", raid_command))
        app.add_handler(CommandHandler("schedule_ad", schedule_ad_command))
        app.add_handler(CommandHandler("accounts", accounts_command))
        
        app.post_init = post_init
        app.run_polling(drop_pending_updates=True)
    else:
        print("⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing!")
        print("💡 The Telegram Coin Scanner will remain inactive, but the SMM Marketing Engines, DMs Inbox, and Web Dashboard are fully operational on port 10000.")
        
        # Start background SMM services directly in a clean active asyncio loop
        try:
            asyncio.run(start_smm_offline())
        except KeyboardInterrupt:
            pass



if __name__ == "__main__":
    main()
