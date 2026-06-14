"""
Raid Coordination and Automated Raiding Engine — Creates high-converting raid alerts
and executes REAL automated interactions (likes, comments) across Twitter and Instagram
using connected account session cookies. No API keys needed — works like your browser.
"""
import logging
import asyncio
import aiohttp
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import marketing_db

logger = logging.getLogger(__name__)

AUTOMATED_COMMENTS = [
    "This is absolutely bullish! Let's go! 🚀🚀",
    "Secured my bag. Ready for the moon! 💎🙌",
    "Best community in Web3, hands down. Ticker is solid! 🔥",
    "Apeing in. The chart looks too good! 📈🦁",
    "Don't miss this opportunity. Next 100x gem! 🌟💎",
    "Parabolic expansion is imminent. Send it! ✈️📈",
    "Clean dev team, strong liquidity, massive hype. Bullish!",
    "Been waiting for this one. Full send! 🔥💎",
    "Chart looks incredible. Holding strong! 💪🚀",
    "LFG! This is the one everyone's been sleeping on 👀",
]

TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
TWITTER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
IG_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _extract_tweet_id(url: str) -> str:
    if "/status/" in url:
        return url.split("/status/")[-1].split("?")[0].split("/")[0]
    return ""


def _extract_instagram_shortcode(url: str) -> str:
    parts = url.rstrip("/").split("/")
    try:
        idx = parts.index("p")
        return parts[idx + 1]
    except (ValueError, IndexError):
        return ""


async def _twitter_like_tweet(acc: dict, tweet_id: str, http: aiohttp.ClientSession) -> bool:
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        return False
    headers = {
        "authorization": f"Bearer {TWITTER_BEARER}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": TWITTER_UA,
    }
    try:
        async with http.post(
            "https://twitter.com/i/api/1.1/favorites/create.json",
            data={"id": tweet_id},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status in (200, 403):  # 403 = already liked
                return True
            logger.debug(f"[Raid:Like] @{acc.get('username')} → {resp.status}")
            return False
    except Exception as e:
        logger.debug(f"[Raid:Like] @{acc.get('username')} error: {e}")
        return False


async def _twitter_comment_tweet(acc: dict, tweet_id: str, comment: str, http: aiohttp.ClientSession) -> bool:
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        return False
    headers = {
        "authorization": f"Bearer {TWITTER_BEARER}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "Content-Type": "application/json",
        "User-Agent": TWITTER_UA,
    }
    payload = {
        "variables": {
            "tweet_text": comment,
            "reply": {"in_reply_to_tweet_id": tweet_id, "exclude_reply_user_ids": []},
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
        },
        "features": {
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "freedom_of_speech_not_reach_tweet_label_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_feature_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "interactive_text_enabled": True,
            "responsive_web_text_conversations_enabled": False,
            "vibe_api_enabled": True,
        },
    }
    try:
        async with http.post(
            "https://twitter.com/i/api/graphql/a1p9RWpkYKBjWv_I3WzS-A/CreateTweet",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            ok = resp.status == 200
            if not ok:
                logger.debug(f"[Raid:Comment] @{acc.get('username')} → {resp.status}")
            return ok
    except Exception as e:
        logger.debug(f"[Raid:Comment] @{acc.get('username')} error: {e}")
        return False


async def _instagram_get_media_id(shortcode: str, sessionid: str, http: aiohttp.ClientSession) -> str:
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": IG_UA,
    }
    try:
        url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=1"
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("graphql", {}).get("shortcode_media", {}).get("id", "")
    except Exception:
        pass
    return ""


async def _instagram_like_post(acc: dict, shortcode: str, http: aiohttp.ClientSession) -> bool:
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return False
    media_id = await _instagram_get_media_id(shortcode, sessionid, http)
    if not media_id:
        logger.debug(f"[Raid:IG:Like] @{acc.get('username')} — could not resolve media_id for {shortcode}")
        return False
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": IG_UA,
    }
    try:
        async with http.post(
            f"https://www.instagram.com/api/v1/media/{media_id}/like/",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            ok = resp.status == 200
            if not ok:
                logger.debug(f"[Raid:IG:Like] @{acc.get('username')} → {resp.status}")
            return ok
    except Exception as e:
        logger.debug(f"[Raid:IG:Like] @{acc.get('username')} error: {e}")
        return False


async def _instagram_comment_post(acc: dict, shortcode: str, comment: str, http: aiohttp.ClientSession) -> bool:
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return False
    media_id = await _instagram_get_media_id(shortcode, sessionid, http)
    if not media_id:
        return False
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": IG_UA,
    }
    try:
        async with http.post(
            f"https://www.instagram.com/api/v1/media/{media_id}/comment/",
            data={"comment_text": comment},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            return resp.status == 200
    except Exception as e:
        logger.debug(f"[Raid:IG:Comment] @{acc.get('username')} error: {e}")
        return False


def generate_raid_keyboard(platform: str, post_url: str) -> InlineKeyboardMarkup:
    rows = []
    platform_name = platform.title() if platform else "Social Media"
    rows.append([InlineKeyboardButton(f"🔗 Go to {platform_name} Post", url=post_url)])

    actions_row = []
    if "twitter.com" in post_url or "x.com" in post_url:
        tweet_id = post_url.split("/status/")[-1].split("?")[0] if "/status/" in post_url else ""
        if tweet_id:
            actions_row.append(InlineKeyboardButton("❤️ Like", url=f"https://twitter.com/intent/like?tweet_id={tweet_id}"))
            actions_row.append(InlineKeyboardButton("🔁 Repost", url=f"https://twitter.com/intent/retweet?tweet_id={tweet_id}"))
            actions_row.append(InlineKeyboardButton("💬 Comment", url=f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}"))
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
    rows.append([InlineKeyboardButton("✅ I RAIDED! (Verify)", callback_data=f"verify_raid_{int(time.time())}")])
    return InlineKeyboardMarkup(rows)


def build_raid_message(platform: str, post_url: str, caption: str = "") -> str:
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


async def execute_automated_raid(raid_id: str):
    """
    Executes REAL automated interactions (likes + comments) on the target post
    using connected account session cookies — no API keys needed.
    Twitter: auth_token + ct0 | Instagram: sessionid
    """
    db = marketing_db.load_db()
    raids = db["raids"]
    accounts = db["accounts"]
    settings = db["settings"]

    if not settings.get("auto_raid_enabled", True):
        logger.info("Auto-Raid disabled in settings. Skipping.")
        return

    target_raid = next((r for r in raids if r["id"] == raid_id), None)
    if not target_raid:
        return

    platform = target_raid["platform"]
    post_url = target_raid["url"]
    logger.info(f"⚡ Starting real automated raid on {post_url} ...")

    platform_accounts = [
        acc for acc in accounts
        if acc.get("platform") == platform
        and acc.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")
    ]
    if not platform_accounts:
        logger.warning(f"⚠️ No connected {platform} accounts. Add them in Tools → SMM Fleet.")
        marketing_db.update_raid_stats(raid_id=raid_id, current_likes=0, current_comments=0, status="Completed")
        return

    likes_added = 0
    comments_added = 0

    tweet_id = _extract_tweet_id(post_url) if platform in ("twitter", "x") else ""
    ig_shortcode = _extract_instagram_shortcode(post_url) if platform == "instagram" else ""

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as http:
        for acc in platform_accounts:
            username = acc.get("username", "unknown")
            proxy_label = random.choice(settings["proxy_list"]) if settings.get("proxy_list") else "direct"

            if platform in ("twitter", "x") and tweet_id:
                liked = await _twitter_like_tweet(acc, tweet_id, http)
                if liked:
                    likes_added += 1
                    logger.info(f"   ❤️  @{username} liked tweet {tweet_id} [{proxy_label}]")
                else:
                    logger.debug(f"   ⚠️  @{username} like failed — cookies may be expired")

                if random.random() < 0.6:
                    comment = random.choice(AUTOMATED_COMMENTS)
                    commented = await _twitter_comment_tweet(acc, tweet_id, comment, http)
                    if commented:
                        comments_added += 1
                        logger.info(f"   💬 @{username} commented: '{comment[:50]}'")
                    await asyncio.sleep(random.uniform(3, 8))

            elif platform == "instagram" and ig_shortcode:
                liked = await _instagram_like_post(acc, ig_shortcode, http)
                if liked:
                    likes_added += 1
                    logger.info(f"   ❤️  @{username} liked Instagram /{ig_shortcode}/")

                if random.random() < 0.6:
                    comment = random.choice(AUTOMATED_COMMENTS)
                    commented = await _instagram_comment_post(acc, ig_shortcode, comment, http)
                    if commented:
                        comments_added += 1
                        logger.info(f"   💬 @{username} commented on Instagram: '{comment[:50]}'")
                    await asyncio.sleep(random.uniform(3, 8))

            else:
                logger.info(
                    f"   ℹ️  @{username} ({platform}): automated likes/comments for this platform "
                    f"require account session cookies — link is live: {post_url}"
                )

            marketing_db.update_raid_stats(
                raid_id=raid_id,
                current_likes=target_raid["current_likes"] + likes_added,
                current_comments=target_raid["current_comments"] + comments_added
            )
            await asyncio.sleep(random.uniform(2.0, 5.0))

    marketing_db.update_raid_stats(
        raid_id=raid_id,
        current_likes=target_raid["current_likes"] + likes_added,
        current_comments=target_raid["current_comments"] + comments_added,
        status="Completed"
    )
    logger.info(f"✅ Raid {raid_id} complete — {likes_added} real likes, {comments_added} real comments.")
