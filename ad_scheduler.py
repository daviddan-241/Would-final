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


async def _post_instagram(content: str, acc: dict, image_url: Optional[str] = None) -> bool:
    """
    Real Instagram posting via internal session API.
    If image_url is provided: uploads the photo and creates a grid post.
    If text-only: posts as an Instagram Note (up to 60 chars, shown in DM inbox).
    Requires: sessionid cookie pasted into the Account Fleet.
    """
    import json as _json
    import time as _time
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        logger.debug(f"[AdScheduler:Instagram] @{acc.get('username')} — no sessionid cookie. Paste it in Account Fleet.")
        return False

    base_headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    if image_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=15)) as img_resp:
                    if img_resp.status != 200:
                        logger.warning(f"[AdScheduler:Instagram] Could not download image {image_url}")
                        return False
                    image_bytes = await img_resp.read()

                upload_id = str(int(_time.time() * 1000))
                upload_headers = {
                    **base_headers,
                    "Content-Type": "image/jpeg",
                    "X-Instagram-Rupload-Params": _json.dumps({
                        "media_type": 1,
                        "upload_id": upload_id,
                        "upload_media_height": 1080,
                        "upload_media_width": 1080,
                    }),
                    "X-Entity-Length": str(len(image_bytes)),
                    "X-Entity-Name": f"fb_uploader_{upload_id}",
                    "Offset": "0",
                }
                async with session.post(
                    f"https://www.instagram.com/rupload_igphoto/fb_uploader_{upload_id}",
                    data=image_bytes, headers=upload_headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as up_resp:
                    if up_resp.status not in (200, 201):
                        logger.warning(f"[AdScheduler:Instagram] Photo upload failed {up_resp.status}")
                        return False

                async with session.post(
                    "https://www.instagram.com/api/v1/media/configure/",
                    data={"upload_id": upload_id, "caption": content[:2200]},
                    headers={**base_headers, "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as conf_resp:
                    if conf_resp.status == 200:
                        logger.info(f"✅ [AdScheduler:Instagram] Photo post by @{acc.get('username')}")
                        return True
                    logger.warning(f"[AdScheduler:Instagram] Configure failed {conf_resp.status}")
                    return False
        except Exception as e:
            logger.warning(f"[AdScheduler:Instagram] Photo post error: {e}")
            return False
    else:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://www.instagram.com/api/v1/notes/create_note/",
                    data={"text": content[:60], "audience": "2"},
                    headers={**base_headers, "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ [AdScheduler:Instagram] Note posted by @{acc.get('username')}")
                        return True
                    logger.debug(f"[AdScheduler:Instagram] Note failed {resp.status}")
                    return False
        except Exception as e:
            logger.debug(f"[AdScheduler:Instagram] Note error: {e}")
            return False


async def post_ad_to_socials(ad: dict) -> bool:
    """
    Posts a real ad to connected social platform accounts.
    Twitter/X: real tweet via API v2 bearer token.
    Instagram: real photo post (if image_url) or Note via sessionid cookie.
    Other platforms: clear log — no fake success.
    Returns True if at least one real post succeeded.
    """
    platform = ad.get("platform", "")
    content = ad.get("content", "")
    image_url = ad.get("image_url", "")

    accounts = marketing_db.get_accounts()
    platform_accounts = [
        a for a in accounts
        if a.get("platform") == platform
        and a.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")
    ]

    if not platform_accounts:
        logger.info(
            f"📢 No active {platform} accounts in fleet. "
            f"Add a {platform} account with session cookies in Tools → SMM Fleet."
        )
        return False

    succeeded = False

    if platform in ("twitter", "x"):
        for acc in platform_accounts:
            token = acc.get("token_session", "").strip()
            if not token:
                logger.debug(f"[AdScheduler] @{acc.get('username')} has no bearer token — skipping Twitter post.")
                continue
            ok = await _post_tweet(content, token, acc.get("username", "unknown"))
            if ok:
                succeeded = True

    elif platform == "instagram":
        for acc in platform_accounts:
            ok = await _post_instagram(content, acc, image_url or None)
            if ok:
                succeeded = True

    else:
        logger.info(
            f"ℹ️ Real posting for {platform} via session cookies is not yet implemented. "
            f"Supported: Telegram (bot token), Twitter/X (bearer token), Instagram (sessionid). "
            f"Use Telegram as the delivery channel or add {platform} support."
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
