"""
Twitter / X DM Polling Agent.
Polls Twitter API v2 for real Direct Messages sent to the authenticated account.
Requires a Twitter Bearer Token + User Access Token (OAuth 2.0 PKCE) stored in Settings.
Injects real DMs into the unified inbox with profile_url pointing to the sender's Twitter profile.
"""
import asyncio
import logging
import aiohttp

import marketing_db
import dm_manager
from growth_engine import build_profile_url

logger = logging.getLogger(__name__)


async def fetch_twitter_dms(bearer_token: str, access_token: str) -> list:
    """
    Fetches the most recent Twitter DM events for the authenticated user.
    Uses Twitter API v2 /2/dm_events endpoint.
    """
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    url = "https://api.twitter.com/2/dm_events?dm_event.fields=sender_id,text,created_at&expansions=sender_id&user.fields=username,name&max_results=10"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 401:
                    logger.warning("[Twitter] Invalid credentials — update Twitter API keys in Settings.")
                    return []
                if resp.status != 200:
                    logger.debug(f"[Twitter] DM API returned {resp.status}")
                    return []
                data = await resp.json()
                events = data.get("data", [])
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                results = []
                for event in events:
                    sender_id = event.get("sender_id", "")
                    text = event.get("text", "")
                    user = users.get(sender_id, {})
                    username = user.get("username", sender_id)
                    results.append({
                        "platform": "twitter",
                        "handle": f"@{username}",
                        "text": text,
                        "profile_url": build_profile_url(f"@{username}", "twitter"),
                        "sender_id": sender_id,
                        "event_id": event.get("id", "")
                    })
                return results
    except Exception as e:
        logger.debug(f"[Twitter] DM fetch error: {e}")
        return []


async def run_twitter_dm_poll():
    """
    Single poll cycle: check for new Twitter DMs and inject them into the inbox.
    """
    settings = marketing_db.get_settings()
    bearer_token = settings.get("twitter_bearer_token", "")
    access_token = settings.get("twitter_access_token", "")

    if not bearer_token and not access_token:
        return

    dms = await fetch_twitter_dms(bearer_token, access_token)
    if not dms:
        return

    existing = marketing_db.get_conversations()
    seen_ids = set(
        c.get("sender_id", c["sender_handle"])
        for c in existing if c["platform"] == "twitter"
    )

    for dm in dms:
        handle = dm["handle"]
        sid = dm.get("sender_id", handle)
        if sid in seen_ids:
            continue
        logger.info(f"📬 [Twitter] Real DM from {handle}: '{dm['text'][:60]}'")
        await dm_manager.handle_incoming_real_dm(
            platform="twitter",
            sender_handle=handle,
            message_text=dm["text"],
            profile_url=dm["profile_url"],
            source_url=dm["profile_url"]
        )
        seen_ids.add(sid)
        await asyncio.sleep(1.0)


async def start_twitter_dm_loop(check_interval: int = 60):
    """Periodically polls Twitter for new real DMs."""
    logger.info("[Twitter Agent] Twitter DM poller online. Checking every 60s.")
    while True:
        try:
            await run_twitter_dm_poll()
        except Exception as e:
            logger.error(f"[Twitter] Poll loop error: {e}")
        await asyncio.sleep(check_interval)
