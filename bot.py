"""
SMM Raid Engine & SMM Marketing Bot (Verizon Suite)
Multi-Platform Auto-Post, Mirroring, Ad Scheduling & Auto-Raid Engine.
"""
import logging
import asyncio
import aiohttp
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import config
from server import start_health_server

logger = logging.getLogger(__name__)


# --- SMM Telegram Handlers ---

async def private_dm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives real private Telegram DMs, routes them through the active AI persona,
    and sends the reply back to the sender automatically.
    """
    if not update.message or not update.message.text:
        return
    if update.effective_chat.type != "private":
        return

    sender = update.effective_user
    sender_handle = sender.username or f"tg_{sender.id}"
    message_text = update.message.text
    chat_id = update.effective_chat.id

    import marketing_db as mdb
    profiles = mdb.get_profiles()
    active_profiles = [p for p in profiles if p.get("active", True)]
    if not active_profiles:
        return

    target_profile = active_profiles[0]

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Store incoming DM
    conv, _ = mdb.add_incoming_message(
        platform="telegram",
        sender_handle=sender_handle,
        text=message_text,
        profile_id=target_profile["id"]
    )

    from dm_manager import generate_ai_or_rule_reply
    import humanizer as hum

    raw_body, raw_followup = await generate_ai_or_rule_reply(message_text, target_profile)
    human_body = hum.humanize_text(raw_body)
    human_followup = hum.humanize_text(raw_followup) if raw_followup else ""

    # Realistic typing delay (capped at 8s for Telegram responsiveness)
    delay = min(hum.calculate_typing_delay(human_body), 8.0)
    await asyncio.sleep(delay)

    try:
        await update.message.reply_text(human_body)
        mdb.add_outgoing_reply(conv["id"], human_body)

        if human_followup:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(2.5)
            await update.message.reply_text(human_followup)
            mdb.add_outgoing_reply(conv["id"], human_followup)
    except Exception as e:
        logger.error(f"Failed to reply to @{sender_handle}: {e}")

    logger.info(f"📬 Telegram DM handled: @{sender_handle} → persona '{target_profile['name']}'")


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


# --- Core Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 <b>SMM Master Bot (Verizon Suite)</b>\n\n"
        f"Group/Chat ID: <code>{cid}</code>\n\n"
        "🟢 <b>Core Commands:</b>\n"
        "/status — View system health\n\n"
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
        f"🎯 <b>SMM Marketing Engine:</b>\n"
        f"• Clone targets: <b>{targets_count}</b>\n"
        f"• Connected automated accounts: <b>{accounts_count}</b>\n"
        f"• Active ad rotations: <b>{ads_count}</b>\n"
        f"• Automated raids executed: <b>{completed_raids}</b>",
        parse_mode=ParseMode.HTML
    )


async def post_init(app: Application):
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
    print("🚀 Starting SMM-Upgraded Bot...")

    # Start Telegram bot polling ONLY if tokens are provided
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        print("🤖 Initializing Telegram SMM Bot...")
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Core commands
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("status", status_command))
        
        # SMM commands
        app.add_handler(CommandHandler("mirror", mirror_command))
        app.add_handler(CommandHandler("raid", raid_command))
        app.add_handler(CommandHandler("schedule_ad", schedule_ad_command))
        app.add_handler(CommandHandler("accounts", accounts_command))

        # Real private DM handler — AI persona auto-responds to anyone who messages the bot
        app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, private_dm_handler))
        
        app.post_init = post_init
        app.run_polling(drop_pending_updates=True)
    else:
        print("⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing!")
        print("💡 The Telegram SMM Bot will remain inactive, but the SMM Marketing Engines, DMs Inbox, and Web Dashboard are fully operational on port 5000.")
        
        # Start background SMM services directly in a clean active asyncio loop
        try:
            asyncio.run(start_smm_offline())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
