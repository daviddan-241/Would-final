"""
Telegram Coin Scanner & SMM Raid Engine Bot
Fresh coins + Discord link scanner + Multi-Platform Auto-Post.
"""
import logging
import asyncio
import aiohttp
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import config
from server import start_health_server
from formatter import format_caption, build_keyboard
from scanners.base import TokenInfo
from scanners.dexscreener import scan_dexscreener
from scanners.geckoterminal import scan_geckoterminal
from scanners.pumpfun import scan_pumpfun
from scanners.birdeye import scan_extra_sources
import seen_db
import marketing_db
import dm_manager
import humanizer

logger = logging.getLogger(__name__)

scan_count = 0
total_posted = 0


async def handle_private_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    sender_handle = f"@{user.username}" if user.username else f"{user.first_name or 'User'}_{user.id}"
    message_text = update.message.text or ""
    if not message_text:
        return
    logger.info(f"📬 [REAL-TG-DM] Incoming DM from {sender_handle}: '{message_text}'")
    profiles = marketing_db.get_profiles()
    active_profiles = [p for p in profiles if p.get("active", True)]
    profile = active_profiles[0] if active_profiles else None
    profile_id = profile["id"] if profile else None
    conv, _ = marketing_db.add_incoming_message(
        platform="telegram", sender_handle=sender_handle,
        text=message_text, avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={sender_handle}",
        profile_id=profile_id
    )
    if not profile:
        await update.message.reply_text("hey! give me a sec 👀")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    raw_body, raw_followup = await dm_manager.generate_ai_or_rule_reply(message_text, profile)
    human_body = humanizer.humanize_text(raw_body)
    human_followup = humanizer.humanize_text(raw_followup) if raw_followup else ""
    delay = humanizer.calculate_typing_delay(human_body)
    await asyncio.sleep(delay)
    await update.message.reply_text(human_body)
    marketing_db.add_outgoing_reply(conv["id"], human_body)
    if human_followup:
        await asyncio.sleep(3.5)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        await asyncio.sleep(2.5)
        await update.message.reply_text(human_followup)
        marketing_db.add_outgoing_reply(conv["id"], human_followup)
    marketing_db.increment_analytics(leads=1)


async def mirror_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: <code>/mirror [platform] [handle]</code>\n"
            "Example: <code>/mirror twitter @elonmusk</code>",
            parse_mode=ParseMode.HTML
        )
        return
    platform = args[0].lower()
    handle = args[1]
    if platform not in ["twitter", "tiktok", "instagram", "facebook"]:
        await update.message.reply_text("❌ Invalid platform. Supported: twitter, tiktok, instagram, facebook.")
        return
    marketing_db.add_target(platform, handle, "TG_GROUP")
    await update.message.reply_text(
        f"✅ Mirror started for <b>{platform.title()}</b>: <code>{handle}</code>",
        parse_mode=ParseMode.HTML
    )


async def raid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Usage: <code>/raid [url] [optional_caption]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    url = args[0]
    caption = " ".join(args[1:]) if len(args) > 1 else ""
    platform = "twitter"
    if "tiktok.com" in url: platform = "tiktok"
    elif "instagram.com" in url: platform = "instagram"
    elif "facebook.com" in url: platform = "facebook"
    import raid_engine
    marketing_db.add_raid(platform, url, caption)
    msg = raid_engine.build_raid_message(platform, url, caption)
    kbd = raid_engine.generate_raid_keyboard(platform, url)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=kbd)


async def schedule_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: <code>/schedule_ad [interval_min] [text]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        interval = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Interval must be a number.")
        return
    content = " ".join(args[1:])
    marketing_db.add_ad("telegram", content, interval)
    await update.message.reply_text(
        f"✅ Ad scheduled every <b>{interval}</b> minutes.",
        parse_mode=ParseMode.HTML
    )


async def accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accs = marketing_db.get_accounts()
    if not accs:
        await update.message.reply_text("⚠️ No accounts linked. Open the dashboard at port 5000.")
        return
    text = "👤 <b>SMM Account Fleet:</b>\n\n"
    for acc in accs:
        text += f"• <b>{acc['platform'].title()}</b>: <code>{acc['username']}</code> ({acc['status']})\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 <b>Coin Scanner + Discord Hunter + SMM Bot</b>\n\n"
        f"Group/Chat ID: <code>{cid}</code>\n\n"
        "🟢 <b>Scanner Commands:</b>\n"
        "/status — System health\n"
        "/scan — Manual coin scan\n"
        "/stats — Scan counters\n"
        "/clear — Clear cache\n\n"
        "🎮 <b>Discord Scanner:</b>\n"
        "Auto-scans all new pump.fun coins for Discord links\n\n"
        "🔥 <b>SMM Commands:</b>\n"
        "/raid <code>[url]</code> — Multi-platform raid\n"
        "/mirror <code>[platform] [handle]</code> — Clone content\n"
        "/schedule_ad <code>[min] [text]</code> — Recurring ads",
        parse_mode=ParseMode.HTML,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = marketing_db.load_db()
    discord_count = len(db.get("discord_coins", []))
    await update.message.reply_text(
        f"📊 <b>System Status:</b>\n\n"
        f"⏱ Scan interval: {config.SCAN_INTERVAL}s\n"
        f"📁 Cached tokens: {seen_db.seen_count()}\n"
        f"📈 Total scans: {scan_count} | Posted: {total_posted}\n"
        f"🎮 Discord coins found: <b>{discord_count}</b>",
        parse_mode=ParseMode.HTML
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = marketing_db.load_db()
    discord_count = len(db.get("discord_coins", []))
    await update.message.reply_text(
        f"📈 Scans: {scan_count} | Posted: {total_posted} | Cached: {seen_db.seen_count()} | Discord: {discord_count}"
    )


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


def _save_discord_coin_UNUSED(token: TokenInfo):
    """Persist Discord-link coins to the marketing DB for the dashboard."""
    try:
        db = marketing_db.load_db()
        if "discord_coins" not in db:
            db["discord_coins"] = []
        import time as _time
        entry = {
            "name": token.name,
            "symbol": token.symbol,
            "mint": token.contract_address,
            "chain": token.chain,
            "discord_link": token.discord_link,
            "telegram_link": token.telegram_link or "",
            "twitter": token.twitter or "",
            "website": token.website or "",
            "image_url": token.image_url or "",
            "pair_url": token.pair_url or "",
            "source": token.source,
            "found_at": _time.time(),
        }
        # Avoid duplicates
        existing_mints = {c.get("mint", "") for c in db["discord_coins"]}
        if token.contract_address not in existing_mints:
            db["discord_coins"].append(entry)
            # Keep last 500
            if len(db["discord_coins"]) > 500:
                db["discord_coins"] = db["discord_coins"][-500:]
            marketing_db.save_db(db)
    except Exception as e:
        logger.debug(f"Failed to save discord coin: {e}")


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

    # Dedup by contract address
    unique: dict[str, TokenInfo] = {}
    for token in all_tokens:
        addr = token.contract_address.lower()
        if addr not in unique:
            unique[addr] = token

    # Filter already-posted
    new_tokens = []
    for addr, token in unique.items():
        if not seen_db.is_seen(addr, token.telegram_link, token.name, token.symbol):
            new_tokens.append(token)

    # Save Discord coins to DB (for dashboard display) - even if not posting to TG
    discord_new = 0
    for token in new_tokens:
        if token.discord_link:
            marketing_db.add_discord_coin(token.name, token.symbol, token.contract_address, token.chain, token.discord_link, token.telegram_link or "", token.twitter or "", token.website or "", token.image_url or "", token.pair_url or "", token.source)
            discord_new += 1

    if discord_new:
        logger.info(f"Discord coins found this cycle: {discord_new}")

    # Post tokens that have Telegram links (existing behavior)
    # Also post Discord-only coins with a special format
    posted = 0
    for token in new_tokens:
        # Only send to Telegram if it has a TG link (or if it's Discord-only, still send it)
        if not token.telegram_link and not token.discord_link:
            continue

        ok = await send_token(bot, token)
        if ok:
            seen_db.mark_seen(token.contract_address, token.telegram_link, token.name, token.symbol)
            posted += 1
            total_posted += 1
            social_info = f"TG:{bool(token.telegram_link)} Discord:{bool(token.discord_link)}"
            logger.info(f"✅ {token.name} (${token.symbol}) [{token.chain}] {social_info}")
        await asyncio.sleep(2)

    return posted


async def periodic_scan(bot: Bot):
    logger.info(f"Scanner started — every {config.SCAN_INTERVAL}s")
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="🤖 <b>Coin Scanner + Discord Hunter Started</b>\n\n"
                 f"⏱ Every {config.SCAN_INTERVAL}s\n"
                 "📡 Pump.fun + DexScreener + GeckoTerminal\n"
                 "🔗 Fresh coins with TG or Discord links\n"
                 "🎮 Discord links tracked in dashboard",
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
    asyncio.create_task(periodic_scan(app.bot))
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

    start_health_server()
    print("🚀 Starting Coin Scanner + Discord Hunter + SMM Bot...")

    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        print("🤖 Initializing Telegram Bot...")
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("scan", manual_scan_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(CommandHandler("mirror", mirror_command))
        app.add_handler(CommandHandler("raid", raid_command))
        app.add_handler(CommandHandler("schedule_ad", schedule_ad_command))
        app.add_handler(CommandHandler("accounts", accounts_command))
        app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_dm))
        app.post_init = post_init
        app.run_polling(drop_pending_updates=True)
    else:
        print("⚠️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing.")
        print("💡 Dashboard is live on port 5000. Discord scanner still runs.")
        try:
            asyncio.run(start_smm_offline())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
