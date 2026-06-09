"""
Ad Scheduler — Posts real scheduled promotional ads to Telegram and connected social accounts.
For Telegram: sends real messages via the configured bot.
For Twitter accounts with bearer tokens: posts real tweets via Twitter API v2.
For other platforms without API tokens: logs what's needed — never fakes a successful post.
"""
import logging
import asyncio
import aiohttp
import time
from typing import Optional

import marketing_db
import config

logger = logging.getLogger(__name__)


async def post_ad_to_telegram(bot_instance, content: str, image_url: Optional[str] = None) -> bool:
    """Sends a real promotional ad to the configured Telegram chat."""
    profiles = marketing_db.get_profiles()
    active_profile = next((p for p in profiles if p.get("active", True)), None)

    bot_token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    active_bot = bot_instance

    if active_profile and active_profile.get("tg_bot_token") and active_profile.get("tg_chat_id"):
        bot_token = active_profile["tg_bot_token"]
        chat_id = active_profile["tg_chat_id"]
        from telegram import Bot
        active_bot = Bot(token=bot_token)
        logger.info(f"🤖 Posting ad using credentials for persona '{active_profile['name']}' to chat {chat_id}.")

    if not active_bot or not chat_id:
        logger.warning("Telegram bot or chat ID not configured. Add TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to enable.")
        return False

    try:
        if image_url:
            await active_bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=content,
                parse_mode="HTML"
            )
        else:
            await active_bot.send_message(
                chat_id=chat_id,
                text=content,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        logger.info(f"✅ Ad posted to Telegram.")
        return True
    except Exception as e:
        logger.error(f"Telegram ad post failed: {e}")
        return False


async def _post_tweet(content: str, bearer_token: str, username: str) -> bool:
    """Post a real tweet via Twitter API v2."""
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    text = content[:280]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"text": text}, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    tweet_id = data.get("data", {}).get("id", "unknown")
                    logger.info(f"✅ Tweet posted by @{username}: id={tweet_id}")
                    return True
                body = await resp.text()
                logger.warning(f"Twitter post failed for @{username} ({resp.status}): {body[:200]}")
    except Exception as e:
        logger.warning(f"Twitter post error for @{username}: {e}")
    return False


async def post_ad_to_socials(ad: dict) -> bool:
    """
    Posts a real ad to connected social platform accounts that have API tokens.
    Twitter/X: posts a real tweet via API v2 if a bearer token is stored.
    Other platforms: logs that OAuth credentials are needed — never fakes success.
    Returns True if at least one real post succeeded.
    """
    platform = ad.get("platform", "")
    content = ad.get("content", "")

    accounts = marketing_db.get_accounts()
    platform_accounts = [
        a for a in accounts
        if a.get("platform") == platform and a.get("token_session", "").strip()
    ]

    if not platform_accounts:
        logger.info(
            f"📢 No {platform} accounts with API tokens configured. "
            f"Add {platform} accounts and their API tokens in Fleet Accounts to enable real posting."
        )
        return False

    succeeded = False

    if platform in ("twitter", "x"):
        for acc in platform_accounts:
            token = acc["token_session"].strip()
            username = acc.get("username", "unknown")
            ok = await _post_tweet(content, token, username)
            if ok:
                succeeded = True
    else:
        logger.info(
            f"ℹ️ Automated posting for {platform} requires platform-specific OAuth integration. "
            f"Currently supported: Telegram (via bot token), Twitter/X (via bearer token). "
            f"Add {platform} OAuth support or use Telegram as the delivery channel."
        )

    return succeeded


async def check_and_run_scheduler(bot_instance=None):
    """Checks all active ads and posts them if their schedule interval is met."""
    db = marketing_db.load_db()
    ads = db.get("ads", [])
    settings = db.get("settings", {})

    if not settings.get("auto_post_enabled", True):
        return

    now = time.time()

    for ad in ads:
        if not ad.get("active", True):
            continue

        interval_sec = ad.get("interval_min", 30) * 60
        last_posted = ad.get("last_posted", 0)

        if now - last_posted < interval_sec:
            continue

        logger.info(f"⏳ Scheduled ad {ad['id']} is due — posting now...")

        success_tg = False
        success_social = False

        if ad["platform"] in ("telegram", "all"):
            success_tg = await post_ad_to_telegram(bot_instance, ad["content"], ad.get("image_url"))

        if ad["platform"] not in ("telegram",):
            success_social = await post_ad_to_socials(ad)

        if success_tg or success_social:
            ad["last_posted"] = now
            ad["total_sends"] = ad.get("total_sends", 0) + 1
            marketing_db.save_db()
            marketing_db.increment_analytics(impressions=1)
            logger.info(f"✅ Ad {ad['id']} posted (tg={success_tg}, social={success_social}).")


async def start_ad_scheduler_loop(bot_instance=None, check_interval=60):
    """Ad scheduler background loop."""
    logger.info("Ad Scheduler background task started.")
    while True:
        try:
            await check_and_run_scheduler(bot_instance)
        except Exception as e:
            logger.error(f"Error in ad scheduler loop: {e}")
        await asyncio.sleep(check_interval)
