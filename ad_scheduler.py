"""
Automated Ad Scheduler — Handles scheduling promotional ads and marketing content
across Telegram and other connected social media platforms at customized intervals.
"""
import logging
import asyncio
import time
from typing import Optional

import marketing_db
import config

logger = logging.getLogger(__name__)


async def post_ad_to_telegram(bot_instance, content: str, image_url: Optional[str] = None) -> bool:
    """Sends a promotional ad to the configured Telegram chat."""
    if not bot_instance or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot or Chat ID not configured. Cannot post ad.")
        return False
        
    try:
        if image_url:
            # Send photo with caption
            await bot_instance.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=image_url,
                caption=content,
                parse_mode="HTML"
            )
        else:
            # Send plain text
            await bot_instance.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=content,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        return True
    except Exception as e:
        logger.error(f"Error posting ad to Telegram: {e}")
        return False


async def post_ad_to_socials(ad: dict) -> bool:
    """Simulates/Executes posting advertisements to other connected social platforms."""
    platform = ad["platform"]
    logger.info(f"📣 [AUTO-AD] Publishing Scheduled Promotion to connected {platform.title()} accounts!")
    # Staggered posting simulation
    await asyncio.sleep(1)
    return True


async def check_and_run_scheduler(bot_instance=None):
    """Checks all active ads and posts them if their schedule interval is met."""
    db = marketing_db.load_db()
    ads = db["ads"]
    settings = db["settings"]
    
    if not settings.get("auto_post_enabled", True):
        return
        
    now = time.time()
    
    for ad in ads:
        if not ad.get("active", True):
            continue
            
        interval_sec = ad.get("interval_min", 30) * 60
        last_posted = ad.get("last_posted", 0)
        
        if now - last_posted >= interval_sec:
            logger.info(f"⏳ Running scheduled ad: {ad['id']}...")
            
            success_tg = True
            success_social = True
            
            # Post to Telegram if matching target
            if ad["platform"] in ["telegram", "all"]:
                success_tg = await post_ad_to_telegram(bot_instance, ad["content"], ad.get("image_url"))
                
            # Post to connected social channels (Twitter, FB, TikTok, IG) if matching target
            if ad["platform"] != "telegram":
                success_social = await post_ad_to_socials(ad)
                
            if success_tg or success_social:
                ad["last_posted"] = now
                marketing_db.save_db()
                logger.info(f"✅ Ad {ad['id']} posted successfully.")


async def start_ad_scheduler_loop(bot_instance=None, check_interval=60):
    """Ad scheduler background loop."""
    logger.info("Ad Scheduler background task started.")
    while True:
        try:
            await check_and_run_scheduler(bot_instance)
        except Exception as e:
            logger.error(f"Error in ad scheduler loop: {e}")
        await asyncio.sleep(check_interval)
