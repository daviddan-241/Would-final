"""
Session-Cookie DM Agent — reads real DMs from real social accounts using browser session cookies.
No paid API needed. Works exactly like your browser does.

Supported platforms:
  - Twitter / X   → needs: auth_token + ct0 cookies
  - Instagram     → needs: sessionid cookie
  - TikTok        → needs: sessionid + ttwid cookies
  - Facebook      → needs: c_user + xs cookies

How to get session cookies (30 seconds):
  1. Open your browser, log into the account
  2. Press F12 → Application tab → Cookies → copy the values listed above
  3. Paste them into the Account Fleet in the dashboard
"""
import asyncio
import aiohttp
import logging
import time
import json

import marketing_db
import dm_manager

logger = logging.getLogger("agent.session_dm")

# Track last-seen DM IDs per account so we never double-import
_seen: dict[str, set] = {}

# ─── TWITTER / X ────────────────────────────────────────────────────────────

async def fetch_twitter_session_dms(acc: dict, session: aiohttp.ClientSession) -> list:
    """
    Uses Twitter's internal (browser) API with auth_token + ct0 cookies.
    This is exactly what your browser sends — totally free.
    """
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        return []

    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://twitter.com/messages",
    }
    url = "https://twitter.com/i/api/1.1/dm/inbox_timeline/trusted.json?filter_low_quality=true&include_quality=all&ext=mediaStats"
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (401, 403):
                logger.warning(f"[Twitter:{acc['username']}] Session expired — re-paste cookies in Account Fleet.")
                _mark_account_expired(acc["id"])
                return []
            if resp.status != 200:
                logger.debug(f"[Twitter:{acc['username']}] Inbox returned {resp.status}")
                return []
            raw = await resp.json()
            entries = []
            inbox = raw.get("inbox_timeline", {}).get("entries", {})
            for entry_id, entry in inbox.items():
                msg = entry.get("message", {})
                msg_data = msg.get("message_data", {})
                sender_id = str(msg_data.get("sender_id", ""))
                text = msg_data.get("text", "")
                dm_id = msg.get("id", entry_id)
                if not text or not sender_id:
                    continue
                # Resolve username from user_events
                user_events = raw.get("inbox_timeline", {}).get("user_events", {})
                user_data = user_events.get(sender_id, {})
                user_info = user_data.get("user", {}).get("legacy", {})
                username = user_info.get("screen_name", sender_id)
                entries.append({
                    "dm_id": dm_id,
                    "platform": "twitter",
                    "handle": f"@{username}",
                    "text": text,
                    "profile_url": f"https://twitter.com/{username}",
                })
            return entries
    except Exception as e:
        logger.debug(f"[Twitter:{acc['username']}] Error: {e}")
        return []


# ─── INSTAGRAM ───────────────────────────────────────────────────────────────

async def fetch_instagram_session_dms(acc: dict, session: aiohttp.ClientSession) -> list:
    """
    Uses Instagram's internal API with sessionid cookie.
    """
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return []

    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/direct/inbox/",
        "x-requested-with": "XMLHttpRequest",
    }
    url = "https://www.instagram.com/api/v1/direct_v2/inbox/?visual_message_return_type=unseen&persistentBadging=true&limit=20"
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (401, 403):
                logger.warning(f"[Instagram:{acc['username']}] Session expired — re-paste sessionid.")
                _mark_account_expired(acc["id"])
                return []
            if resp.status != 200:
                logger.debug(f"[Instagram:{acc['username']}] Inbox returned {resp.status}")
                return []
            raw = await resp.json()
            threads = raw.get("inbox", {}).get("threads", [])
            entries = []
            for thread in threads:
                items = thread.get("items", [])
                for item in items[:3]:
                    if item.get("item_type") != "text":
                        continue
                    text_content = item.get("text", "")
                    sender = item.get("user_id", "")
                    dm_id = item.get("item_id", "")
                    # Get sender username from thread users
                    users = thread.get("users", [])
                    username = ""
                    for u in users:
                        if str(u.get("pk", "")) == str(sender):
                            username = u.get("username", "")
                            break
                    if not username:
                        username = str(sender)
                    if not text_content:
                        continue
                    entries.append({
                        "dm_id": dm_id,
                        "platform": "instagram",
                        "handle": f"@{username}",
                        "text": text_content,
                        "profile_url": f"https://www.instagram.com/{username}",
                    })
            return entries
    except Exception as e:
        logger.debug(f"[Instagram:{acc['username']}] Error: {e}")
        return []


# ─── TIKTOK ──────────────────────────────────────────────────────────────────

async def fetch_tiktok_session_dms(acc: dict, session: aiohttp.ClientSession) -> list:
    """
    Uses TikTok's internal messaging API with sessionid + ttwid cookies.
    """
    sessionid = acc.get("sessionid", "")
    ttwid = acc.get("ttwid", "")
    if not sessionid:
        return []

    cookie_str = f"sessionid={sessionid}"
    if ttwid:
        cookie_str += f"; ttwid={ttwid}"

    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/messages",
        "x-secsdk-csrf-version": "1.2.8",
    }
    url = "https://www.tiktok.com/api/im/query_conversation_list/?count=20&cursor=0"
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (401, 403):
                logger.warning(f"[TikTok:{acc['username']}] Session expired — re-paste cookies.")
                _mark_account_expired(acc["id"])
                return []
            if resp.status != 200:
                logger.debug(f"[TikTok:{acc['username']}] Inbox returned {resp.status}")
                return []
            raw = await resp.json()
            convs = raw.get("data", {}).get("conversationList", [])
            entries = []
            for conv in convs:
                last_msg = conv.get("lastMessage", {})
                text = last_msg.get("content", "")
                try:
                    msg_body = json.loads(text)
                    text = msg_body.get("text", text)
                except Exception:
                    pass
                dm_id = last_msg.get("msgId", "")
                user_info = conv.get("conversationWith", {})
                username = user_info.get("uniqueId", user_info.get("uid", "unknown"))
                if not text or not username:
                    continue
                entries.append({
                    "dm_id": dm_id,
                    "platform": "tiktok",
                    "handle": f"@{username}",
                    "text": text,
                    "profile_url": f"https://www.tiktok.com/@{username}",
                })
            return entries
    except Exception as e:
        logger.debug(f"[TikTok:{acc['username']}] Error: {e}")
        return []


# ─── FACEBOOK ────────────────────────────────────────────────────────────────

async def fetch_facebook_session_dms(acc: dict, session: aiohttp.ClientSession) -> list:
    """
    Uses Facebook's internal Messenger API with c_user + xs cookies.
    """
    c_user = acc.get("c_user", "")
    xs = acc.get("xs", "")
    if not c_user or not xs:
        return []

    headers = {
        "Cookie": f"c_user={c_user}; xs={xs}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.facebook.com/messages/",
        "x-fb-friendly-name": "MercuryThreadlistQuery",
    }
    url = "https://www.facebook.com/api/graphql/"
    payload = {
        "doc_id": "6451810948172600",
        "variables": json.dumps({"count": 10, "includeDeliveryReceipts": True}),
    }
    try:
        async with session.post(url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (401, 403):
                logger.warning(f"[Facebook:{acc['username']}] Session expired.")
                _mark_account_expired(acc["id"])
                return []
            if resp.status != 200:
                return []
            raw = await resp.json()
            threads = (raw.get("data", {}).get("viewer", {}).get("message_threads", {}).get("nodes", []))
            entries = []
            for thread in threads:
                last_msg = (thread.get("last_message") or {})
                text = (last_msg.get("snippet") or "")
                dm_id = last_msg.get("message_id", "")
                participants = thread.get("all_participants", {}).get("nodes", [])
                sender_name = ""
                for p in participants:
                    actor = p.get("messaging_actor", {})
                    uid = str(actor.get("id", ""))
                    if uid and uid != str(c_user):
                        sender_name = actor.get("name", uid)
                        break
                if not text or not sender_name:
                    continue
                entries.append({
                    "dm_id": dm_id,
                    "platform": "facebook",
                    "handle": sender_name,
                    "text": text,
                    "profile_url": f"https://www.facebook.com/profile.php?id={c_user}",
                })
            return entries
    except Exception as e:
        logger.debug(f"[Facebook:{acc['username']}] Error: {e}")
        return []


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _mark_account_expired(acc_id: str):
    db = marketing_db.load_db()
    for acc in db.get("accounts", []):
        if acc["id"] == acc_id:
            acc["status"] = "Expired — re-paste cookies"
            break
    marketing_db.save_db()


async def _process_account(acc: dict, http: aiohttp.ClientSession):
    platform = acc.get("platform", "")
    acc_id = acc["id"]
    if acc_id not in _seen:
        _seen[acc_id] = set()

    if platform == "twitter":
        dms = await fetch_twitter_session_dms(acc, http)
    elif platform == "instagram":
        dms = await fetch_instagram_session_dms(acc, http)
    elif platform == "tiktok":
        dms = await fetch_tiktok_session_dms(acc, http)
    elif platform == "facebook":
        dms = await fetch_facebook_session_dms(acc, http)
    else:
        return

    new_count = 0
    for dm in dms:
        dm_id = dm.get("dm_id", "")
        key = dm_id or f"{dm['handle']}:{dm['text'][:40]}"
        if key in _seen[acc_id]:
            continue
        _seen[acc_id].add(key)
        logger.info(f"📬 [{platform.upper()}:{acc['username']}] Real DM from {dm['handle']}: '{dm['text'][:60]}'")
        await dm_manager.handle_incoming_real_dm(
            platform=platform,
            sender_handle=dm["handle"],
            message_text=dm["text"],
            profile_url=dm.get("profile_url", ""),
            source_url=dm.get("profile_url", ""),
        )
        new_count += 1
        await asyncio.sleep(0.5)

    if new_count:
        logger.info(f"[Session DM] {new_count} new real DMs from {platform}:{acc['username']}")


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

async def start_session_dm_loop(check_interval: int = 60):
    """
    Main polling loop. Runs every `check_interval` seconds.
    Loops through every account in the fleet and pulls real DMs.
    """
    logger.info("[Session DM Agent] Online — polling real DMs from all connected accounts every 60s.")
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as http:
        while True:
            try:
                accounts = marketing_db.get_accounts()
                active = [a for a in accounts if a.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")]
                if active:
                    tasks = [_process_account(acc, http) for acc in active]
                    await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"[Session DM] Loop error: {e}")
            await asyncio.sleep(check_interval)
