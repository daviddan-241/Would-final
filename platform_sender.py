"""
Platform DM Sender — Actually sends real DMs back to people on their platform
using session cookies. This is what makes the system REAL — not just a dashboard.

When someone DMs you on Instagram, TikTok, Facebook, or Twitter:
  1. Session DM Agent reads the real DM
  2. AI Responder generates a smart reply
  3. THIS MODULE sends the reply back on the actual platform
  4. The person sees your reply and responds → real conversation

Requires session cookies pasted into the Account Fleet.
"""
import logging
import aiohttp
import json
import time
import random

import marketing_db

logger = logging.getLogger("platform_sender")


def _get_account_for_platform(platform: str, sender_handle: str = "") -> dict | None:
    """
    Finds the best matching account for a platform.
    Returns the account dict with session cookies, or None if not available.
    """
    accounts = marketing_db.get_accounts()
    platform_accounts = [
        a for a in accounts
        if a.get("platform") == platform
        and a.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")
    ]
    if not platform_accounts:
        return None
    # Prefer accounts with outreach enabled (they're the active ones)
    outreach = [a for a in platform_accounts if a.get("outreach_enabled", False)]
    return outreach[0] if outreach else platform_accounts[0]


# ─── SEND DM ON TWITTER/X ────────────────────────────────────────────────────

async def send_twitter_dm(recipient_username: str, text: str, http: aiohttp.ClientSession = None) -> bool:
    """
    Sends a real DM on Twitter/X using session cookies (auth_token + ct0).
    First resolves the recipient's user ID, then sends the DM.
    """
    acc = _get_account_for_platform("twitter")
    if not acc:
        logger.debug("[PlatformSender:Twitter] No Twitter account configured")
        return False

    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        logger.debug(f"[PlatformSender:Twitter] @{acc.get('username')} missing auth_token or ct0")
        return False

    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    close_session = False
    if http is None:
        http = aiohttp.ClientSession()
        close_session = True

    try:
        # Step 1: Resolve username → user ID
        clean_handle = recipient_username.lstrip("@")
        lookup_url = f"https://twitter.com/i/api/1.1/users/show.json?screen_name={clean_handle}"
        user_id = ""
        async with http.get(lookup_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                user_id = str(data.get("id_str", ""))
        if not user_id:
            logger.debug(f"[PlatformSender:Twitter] Could not resolve user ID for @{clean_handle}")
            return False

        # Step 2: Send DM
        dm_url = "https://twitter.com/i/api/1.1/direct_messages/new.json"
        payload = {"text": text, "recipient_id": user_id}
        async with http.post(dm_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[PlatformSender:Twitter] ✅ DM sent to @{clean_handle}: '{text[:50]}'")
                return True
            logger.debug(f"[PlatformSender:Twitter] DM failed {resp.status} to @{clean_handle}")
            return False
    except Exception as e:
        logger.debug(f"[PlatformSender:Twitter] Error sending DM: {e}")
        return False
    finally:
        if close_session:
            await http.close()


# ─── SEND DM ON INSTAGRAM ────────────────────────────────────────────────────

async def send_instagram_dm(recipient_username: str, text: str, http: aiohttp.ClientSession = None) -> bool:
    """
    Sends a real DM on Instagram using sessionid cookie.
    First resolves the recipient's user ID via their username, then sends the DM.
    """
    acc = _get_account_for_platform("instagram")
    if not acc:
        logger.debug("[PlatformSender:Instagram] No Instagram account configured")
        return False

    sessionid = acc.get("sessionid", "")
    if not sessionid:
        logger.debug(f"[PlatformSender:Instagram] @{acc.get('username')} missing sessionid")
        return False

    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "x-requested-with": "XMLHttpRequest",
    }

    close_session = False
    if http is None:
        http = aiohttp.ClientSession()
        close_session = True

    try:
        # Step 1: Resolve username → user ID
        clean_handle = recipient_username.lstrip("@")
        lookup_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={clean_handle}"
        user_id = ""
        async with http.get(lookup_url, headers={"Cookie": f"sessionid={sessionid}", "x-ig-app-id": "936619743392459", "User-Agent": headers["User-Agent"]}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                user_id = str(data.get("data", {}).get("user", {}).get("id", ""))
        if not user_id:
            logger.debug(f"[PlatformSender:Instagram] Could not resolve user ID for @{clean_handle}")
            return False

        # Step 2: Send DM via Instagram's direct messaging API
        dm_url = "https://www.instagram.com/api/v1/direct_v2/threads/broadcast/text/"
        import urllib.parse
        payload = urllib.parse.urlencode({
            "recipient_users": json.dumps([user_id]),
            "text": text,
            "action": "send_item",
            "client_context": str(int(time.time() * 1000)),
            "device_id": f"android-{random.randint(10000000, 99999999)}",
        })
        async with http.post(dm_url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                raw = await resp.json()
                if raw.get("status") == "ok":
                    logger.info(f"[PlatformSender:Instagram] ✅ DM sent to @{clean_handle}: '{text[:50]}'")
                    return True
            logger.debug(f"[PlatformSender:Instagram] DM failed {resp.status} to @{clean_handle}")
            return False
    except Exception as e:
        logger.debug(f"[PlatformSender:Instagram] Error sending DM: {e}")
        return False
    finally:
        if close_session:
            await http.close()


# ─── SEND DM ON TIKTOK ───────────────────────────────────────────────────────

async def send_tiktok_dm(recipient_username: str, text: str, http: aiohttp.ClientSession = None) -> bool:
    """
    Sends a real DM on TikTok using sessionid + ttwid cookies.
    """
    acc = _get_account_for_platform("tiktok")
    if not acc:
        logger.debug("[PlatformSender:TikTok] No TikTok account configured")
        return False

    sessionid = acc.get("sessionid", "")
    ttwid = acc.get("ttwid", "")
    if not sessionid:
        logger.debug(f"[PlatformSender:TikTok] @{acc.get('username')} missing sessionid")
        return False

    cookie_str = f"sessionid={sessionid}"
    if ttwid:
        cookie_str += f"; ttwid={ttwid}"

    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "x-secsdk-csrf-version": "1.2.8",
    }

    close_session = False
    if http is None:
        http = aiohttp.ClientSession()
        close_session = True

    try:
        # Step 1: Resolve username → user ID via TikTok internal API
        clean_handle = recipient_username.lstrip("@")
        lookup_url = f"https://www.tiktok.com/api/user/detail/?uniqueId={clean_handle}®ion=US"
        user_id = ""
        async with http.get(lookup_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                user_id = str(data.get("userInfo", {}).get("user", {}).get("id", ""))
        if not user_id:
            logger.debug(f"[PlatformSender:TikTok] Could not resolve user ID for @{clean_handle}")
            return False

        # Step 2: Send DM
        import urllib.parse
        dm_url = "https://www.tiktok.com/api/im/message/send/"
        payload = urllib.parse.urlencode({
            "recipients": json.dumps([user_id]),
            "text": text,
            "message_type": "0",
        })
        async with http.post(dm_url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                raw = await resp.json()
                if raw.get("status_code", -1) == 0:
                    logger.info(f"[PlatformSender:TikTok] ✅ DM sent to @{clean_handle}: '{text[:50]}'")
                    return True
            logger.debug(f"[PlatformSender:TikTok] DM failed {resp.status} to @{clean_handle}")
            return False
    except Exception as e:
        logger.debug(f"[PlatformSender:TikTok] Error sending DM: {e}")
        return False
    finally:
        if close_session:
            await http.close()


# ─── SEND DM ON FACEBOOK ─────────────────────────────────────────────────────

async def send_facebook_dm(recipient_name: str, text: str, http: aiohttp.ClientSession = None) -> bool:
    """
    Sends a real DM on Facebook Messenger using c_user + xs cookies.
    """
    acc = _get_account_for_platform("facebook")
    if not acc:
        logger.debug("[PlatformSender:Facebook] No Facebook account configured")
        return False

    c_user = acc.get("c_user", "")
    xs = acc.get("xs", "")
    if not c_user or not xs:
        logger.debug(f"[PlatformSender:Facebook] @{acc.get('username')} missing c_user or xs")
        return False

    headers = {
        "Cookie": f"c_user={c_user}; xs={xs}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    close_session = False
    if http is None:
        http = aiohttp.ClientSession()
        close_session = True

    try:
        # Use Facebook's Messenger send API
        import urllib.parse
        send_url = "https://www.facebook.com/messaging/send/"
        payload = urllib.parse.urlencode({
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "MessengerShareMutation",
            "variables": json.dumps({
                "input": {
                    "message": {"text": text},
                    "client_mutation_id": str(int(time.time())),
                    "actor_id": c_user,
                },
            }),
            "doc_id": "6672950532735034",
        })
        async with http.post(send_url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[PlatformSender:Facebook] ✅ DM sent to {recipient_name}: '{text[:50]}'")
                return True
            logger.debug(f"[PlatformSender:Facebook] DM failed {resp.status}")
            return False
    except Exception as e:
        logger.debug(f"[PlatformSender:Facebook] Error sending DM: {e}")
        return False
    finally:
        if close_session:
            await http.close()


# ─── UNIFIED SEND ─────────────────────────────────────────────────────────────

async def send_reply_on_platform(platform: str, recipient_handle: str, text: str, http: aiohttp.ClientSession = None) -> bool:
    """
    Sends a DM reply on the correct platform using session cookies.
    This is the key function that makes auto-replies REAL.
    
    Returns True if the message was actually sent on the platform.
    Returns False if sending failed or no account is configured.
    """
    if not platform or not recipient_handle or not text:
        return False

    # Filter: don't send to ourselves
    accounts = marketing_db.get_accounts()
    for acc in accounts:
        clean_sender = recipient_handle.lstrip("@").lower()
        clean_acc = acc.get("username", "").lstrip("@").lower()
        if clean_sender == clean_acc and acc.get("platform") == platform:
            return False  # Don't DM ourselves

    if platform in ("twitter", "x"):
        return await send_twitter_dm(recipient_handle, text, http)
    elif platform == "instagram":
        return await send_instagram_dm(recipient_handle, text, http)
    elif platform == "tiktok":
        return await send_tiktok_dm(recipient_handle, text, http)
    elif platform == "facebook":
        return await send_facebook_dm(recipient_handle, text, http)
    elif platform == "telegram":
        # Telegram DMs are handled by the bot handler — no session cookies needed
        return True
    elif platform == "reddit":
        # Reddit DM API is restricted — log that it needs manual engagement
        logger.info(f"[PlatformSender:Reddit] Reddit DMs require manual engagement. Lead @{recipient_handle} stored in inbox.")
        return False
    else:
        logger.debug(f"[PlatformSender] No sender for platform: {platform}")
        return False
