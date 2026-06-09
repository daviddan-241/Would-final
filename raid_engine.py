"""
Raid Coordination Engine — Posts real Telegram raid alerts with deep-link action buttons.
For connected accounts with real API tokens (Twitter/X): executes real likes/retweets via Twitter API v2.
For platforms without tokens: sends the Telegram community alert (the real action) and tracks
community participation via the callback verification button.
No fake accounts. No simulated interactions.
"""
import logging
import asyncio
import aiohttp
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import marketing_db

logger = logging.getLogger(__name__)


def generate_raid_keyboard(platform: str, post_url: str) -> InlineKeyboardMarkup:
    """Generates direct quick-action deep links for community raiders."""
    rows = []

    rows.append([InlineKeyboardButton(f"🔗 Go to {platform.title()} Post", url=post_url)])

    actions_row = []
    if "twitter.com" in post_url or "x.com" in post_url:
        tweet_id = post_url.split("/status/")[-1].split("?")[0] if "/status/" in post_url else ""
        if tweet_id:
            actions_row.append(InlineKeyboardButton("❤️ Like", url=f"https://twitter.com/intent/like?tweet_id={tweet_id}"))
            actions_row.append(InlineKeyboardButton("🔁 Repost", url=f"https://twitter.com/intent/retweet?tweet_id={tweet_id}"))
            actions_row.append(InlineKeyboardButton("💬 Reply", url=f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}"))
    elif "tiktok.com" in post_url:
        actions_row.append(InlineKeyboardButton("❤️ Like & Share", url=post_url))
        actions_row.append(InlineKeyboardButton("💬 Comment", url=post_url))
    elif "instagram.com" in post_url:
        actions_row.append(InlineKeyboardButton("❤️ Like & Save", url=post_url))
        actions_row.append(InlineKeyboardButton("💬 Comment", url=post_url))
    else:
        actions_row.append(InlineKeyboardButton("👍 Like", url=post_url))
        actions_row.append(InlineKeyboardButton("💬 Comment", url=post_url))
        actions_row.append(InlineKeyboardButton("🔁 Share", url=post_url))

    if actions_row:
        rows.append(actions_row)

    rows.append([
        InlineKeyboardButton("✅ I RAIDED! (Verify)", callback_data=f"verify_raid_{int(time.time())}")
    ])

    return InlineKeyboardMarkup(rows)


def build_raid_message(platform: str, post_url: str, caption: str = "") -> str:
    """Formats the raid alert message."""
    icon = "𝕏"
    if "tiktok" in platform:
        icon = "🎵"
    elif "instagram" in platform:
        icon = "📸"
    elif "facebook" in platform:
        icon = "👤"

    custom_caption = f"\n📝 <b>Message:</b> {caption}\n" if caption else ""

    return (
        f"🚨 <b>COMMUNITY RAID INCOMING! DETONATE IT!</b> 🚨\n\n"
        f"{icon} <b>Platform:</b> {platform.upper()}\n"
        f"🎯 <b>Objective:</b> Like, Repost, Comment & Bookmark!\n"
        f"{custom_caption}\n"
        f"⚔️ <i>Unleash the army. Click the action buttons below to raid instantly!</i>"
    )


async def _twitter_like(tweet_id: str, user_id: str, bearer_token: str) -> bool:
    """Attempt a real Twitter API v2 like."""
    url = f"https://api.twitter.com/2/users/{user_id}/likes"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"tweet_id": tweet_id}, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    return data.get("data", {}).get("liked", False)
                body = await resp.text()
                logger.warning(f"Twitter like failed ({resp.status}): {body[:200]}")
    except Exception as e:
        logger.warning(f"Twitter like error: {e}")
    return False


async def _twitter_retweet(tweet_id: str, user_id: str, bearer_token: str) -> bool:
    """Attempt a real Twitter API v2 retweet."""
    url = f"https://api.twitter.com/2/users/{user_id}/retweets"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"tweet_id": tweet_id}, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    return data.get("data", {}).get("retweeted", False)
                body = await resp.text()
                logger.warning(f"Twitter retweet failed ({resp.status}): {body[:200]}")
    except Exception as e:
        logger.warning(f"Twitter retweet error: {e}")
    return False


async def _get_twitter_user_id(bearer_token: str, username: str) -> str | None:
    """Look up Twitter user ID from username using API v2."""
    username = username.lstrip("@")
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {}).get("id")
    except Exception as e:
        logger.warning(f"Twitter user ID lookup failed: {e}")
    return None


async def execute_automated_raid(raid_id: str):
    """
    Executes real raid actions for connected accounts that have API tokens.
    For Twitter/X accounts with bearer tokens: real likes and retweets via API v2.
    For other platforms or accounts without tokens: logs clearly that credentials are needed.
    The Telegram raid alert (sent separately on raid creation) IS the real community action.
    """
    db = marketing_db.load_db()
    settings = db.get("settings", {})

    if not settings.get("auto_raid_enabled", True):
        logger.info("Auto-raid disabled in settings.")
        return

    target_raid = next((r for r in db.get("raids", []) if r["id"] == raid_id), None)
    if not target_raid:
        return

    platform = target_raid["platform"]
    url = target_raid["url"]

    logger.info(f"⚡ Raid executor started for {platform}: {url[:60]}")

    accounts = marketing_db.get_accounts()
    platform_accounts = [a for a in accounts if a.get("platform") == platform and a.get("token_session")]

    if not platform_accounts:
        logger.info(
            f"📢 No {platform} accounts with API tokens found. "
            f"The Telegram community raid alert was the real action. "
            f"Add {platform} accounts with API tokens in Fleet Accounts to enable automated interactions."
        )
        marketing_db.update_raid_stats(raid_id, 0, 0, status="Alert Sent — Awaiting Community")
        return

    likes_done = 0
    retweets_done = 0

    if platform == "twitter" or platform == "x":
        tweet_id = url.split("/status/")[-1].split("?")[0] if "/status/" in url else ""
        if not tweet_id:
            logger.warning(f"Could not extract tweet ID from URL: {url}")
            marketing_db.update_raid_stats(raid_id, 0, 0, status="Error — Invalid Tweet URL")
            return

        for acc in platform_accounts:
            token = acc.get("token_session", "").strip()
            username = acc.get("username", "")
            if not token:
                continue

            user_id = await _get_twitter_user_id(token, username)
            if not user_id:
                logger.warning(f"Could not resolve Twitter user ID for @{username} — token may be invalid or expired.")
                continue

            liked = await _twitter_like(tweet_id, user_id, token)
            if liked:
                likes_done += 1
                logger.info(f"✅ @{username} liked tweet {tweet_id}")
            else:
                logger.warning(f"⚠️ @{username} like failed — check token permissions (needs tweet.like.write scope).")

            retweeted = await _twitter_retweet(tweet_id, user_id, token)
            if retweeted:
                retweets_done += 1
                logger.info(f"✅ @{username} retweeted tweet {tweet_id}")

            await asyncio.sleep(2.0)

    else:
        logger.info(
            f"ℹ️ Automated interactions for {platform} require platform-specific OAuth integration. "
            f"Connect real {platform} accounts and their session tokens in Fleet Accounts."
        )

    final_status = "Completed" if (likes_done + retweets_done) > 0 else "Alert Sent — Awaiting Community"
    marketing_db.update_raid_stats(raid_id, likes_done, retweets_done, status=final_status)
    marketing_db.increment_analytics(clicks=likes_done + retweets_done)
    logger.info(
        f"✅ Raid {raid_id} done: {likes_done} real likes + {retweets_done} real retweets. Status: {final_status}"
    )
