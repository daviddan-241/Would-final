"""
Outreach Agent — full auto-pilot for connected accounts.

As soon as you add an account with "Enable outreach posts" checked, this agent:
  1. Posts niche content every 30 min → people see it → they DM you
  2. Searches for people talking about your niche → comments on their posts → they DM you
  3. Proactively DMs targeted users in your niche → they reply → inbox fills up
  4. Runs immediately on first start and every 30 min after

Niches: crypto, solana, ethereum, memecoins, celeb, lifestyle, viral
"""
import asyncio
import aiohttp
import logging
import time
import json
import random

import marketing_db

logger = logging.getLogger("agent.outreach")

# ─── NICHE CONTENT: POSTS ─────────────────────────────────────────────────────

NICHE_POSTS = {
    "crypto": [
        "🚨 Three wallets just loaded up on something quietly. Under 1M mcap. DM me 'GEM' and I'll send you the contract before I post it publicly.",
        "I've been in crypto 4 years. The next 30 days are going to make a lot of people rich. DM me if you're serious.",
        "🔥 Just exited a 40x in 6 hours. My next call goes to my private list tonight. DM me 'ALPHA' to get on it.",
        "Why is nobody talking about this? Insider buying detected on-chain. DM me for the ticker — posting publicly would move it.",
        "Not posting this CA publicly. Too early. DM me 'EARLY' if you want it.",
    ],
    "solana": [
        "🟣 SOL ecosystem is cooking. My whale wallet tracker just flagged something big — DM me 'PUMP' for the details.",
        "Just found a Solana memecoin with less than 500 holders. These are the ones that 100x. DM me for the CA.",
        "My private group caught 3 memecoins this month that all did 50x+. DM me 'SOL' to get tonight's call.",
    ],
    "ethereum": [
        "💎 ETH Base chain gem — 200 holders, solid dev, audited. Not posting publicly. DM me 'BASE' to get in early.",
        "Three ETH plays that could 10x this week. DM me if you want the breakdown.",
    ],
    "memecoins": [
        "🐸 Memecoin season is HERE. I just called 4 10x's in a row. DM me 'MOON' to get my next call first.",
        "Everyone's buying the wrong memecoins. DM me 'GEM' and I'll show you what the smart money is loading right now.",
    ],
    "celeb": [
        "Hey 💕 I just posted something exclusive for my close ones. DM me if you want the link — only sharing with real ones.",
        "Starting a private chat with my real fans tonight. DM me 'VIP' if you want in 🌙",
        "I don't post this publicly but DM me and I'll send you something special 💋",
        "Missing my close friends rn 🥺 DM me — I respond to everyone tonight.",
    ],
    "lifestyle": [
        "Just landed in Bali 🌴 If you want my full travel guide DM me 'BALI'",
        "Built a $10k/month income stream from my phone while traveling. DM me if you want to know how.",
        "Dropped everything and moved abroad 6 months ago. DM me if you want the honest breakdown.",
    ],
    "viral": [
        "Something big is happening in the next 48 hours. Can't say it publicly. DM me if you want to know.",
        "I have 10 spots left for something I'm running tonight. DM me fast — first come first served.",
    ],
}

# ─── NICHE COMMENTS: posted on other people's tweets ────────────────────────

NICHE_COMMENTS = {
    "crypto": [
        "This is the move 🔥 DM me — I've got something even bigger dropping tonight",
        "Been watching this wallet for weeks. DM me if you want early calls",
        "Agree. The smart money is already in. DM me for the next gem 🚨",
        "Exactly this. DM me 'ALPHA' — I've got the contract ready to drop",
    ],
    "solana": [
        "SOL memes are going crazy rn. DM me — I track wallet movements all day 🟣",
        "This. DM me for the next 100x Solana gem before I post it",
    ],
    "celeb": [
        "Omg 💕 DM me I want to talk more!!",
        "This is everything 🔥 DM me!!",
        "Love this!! DM me 💋",
    ],
    "lifestyle": [
        "This is the life 🌴 DM me — I'm building the same thing",
        "Love this! DM me for my full guide on how I did it",
    ],
    "memecoins": [
        "This is the play 🐸 DM me for the next gem",
        "Real. DM me — I've got something bigger dropping tonight",
    ],
}

# ─── TWITTER SEARCH QUERIES BY NICHE ─────────────────────────────────────────

SEARCH_QUERIES = {
    "crypto":    ["crypto gem 2024", "100x altcoin", "buy crypto now", "next 100x coin", "crypto calls"],
    "solana":    ["solana gem", "sol memecoin", "solana 100x", "new solana coin", "$sol pump"],
    "ethereum":  ["eth gem", "base chain gem", "ethereum 100x", "new eth token"],
    "memecoins": ["new memecoin", "memecoin gem", "memecoin 100x", "degen play", "meme coin launch"],
    "celeb":     ["dm me", "vip fans", "exclusive content", "private account", "fan chat"],
    "lifestyle": ["passive income", "travel life", "remote work", "freedom lifestyle", "digital nomad"],
    "viral":     ["viral trend", "trending now", "going viral", "watch this"],
}

# ─── TWITTER: POST TWEET ──────────────────────────────────────────────────────

async def _post_tweet(acc: dict, text: str, http: aiohttp.ClientSession) -> bool:
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
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
    url = "https://twitter.com/i/api/graphql/a1p9RWpkYKBjWv_I3WzS-A/CreateTweet"
    payload = {
        "variables": {
            "tweet_text": text,
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
        async with http.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Twitter:{acc['username']}] ✅ Posted tweet")
                return True
            logger.debug(f"[Outreach:Twitter:{acc['username']}] Post failed {resp.status}")
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Twitter:{acc['username']}] Error: {e}")
        return False


# ─── TWITTER: SEARCH POSTS IN NICHE ──────────────────────────────────────────

async def _search_twitter(acc: dict, query: str, http: aiohttp.ClientSession) -> list:
    """Returns list of tweet IDs from the search results for a given query."""
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        return []
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    import urllib.parse
    q = urllib.parse.quote(query)
    url = f"https://twitter.com/i/api/2/search/adaptive.json?q={q}&count=10&tweet_mode=extended&result_type=recent"
    try:
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            raw = await resp.json()
            tweets = raw.get("globalObjects", {}).get("tweets", {})
            result = []
            for tid, t in tweets.items():
                author_id = t.get("user_id_str", "")
                result.append({"id": tid, "author_id": author_id, "text": t.get("full_text", "")[:100]})
            return result[:5]
    except Exception as e:
        logger.debug(f"[Outreach:Twitter:{acc['username']}] Search error: {e}")
        return []


# ─── TWITTER: COMMENT ON A TWEET ─────────────────────────────────────────────

async def _comment_tweet(acc: dict, tweet_id: str, comment: str, http: aiohttp.ClientSession) -> bool:
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        return False
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    url = "https://twitter.com/i/api/graphql/a1p9RWpkYKBjWv_I3WzS-A/CreateTweet"
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
        async with http.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Twitter:{acc['username']}] 💬 Commented on tweet {tweet_id}")
                return True
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Twitter:{acc['username']}] Comment error: {e}")
        return False


# ─── TWITTER: PROACTIVE DM ────────────────────────────────────────────────────

async def _send_twitter_dm(acc: dict, target_user_id: str, text: str, http: aiohttp.ClientSession) -> bool:
    auth_token = acc.get("auth_token", "")
    ct0 = acc.get("ct0", "")
    if not auth_token or not ct0:
        return False
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    url = "https://twitter.com/i/api/1.1/direct_messages/new.json"
    data = {"text": text, "recipient_id": target_user_id}
    try:
        async with http.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Twitter:{acc['username']}] 📨 Proactive DM sent to {target_user_id}")
                return True
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Twitter:{acc['username']}] DM error: {e}")
        return False


# ─── INSTAGRAM: POST NOTE ────────────────────────────────────────────────────

async def _post_instagram(acc: dict, text: str, http: aiohttp.ClientSession) -> bool:
    """
    Posts an Instagram Note (shown in DM inbox, up to 60 chars) using sessionid cookie.
    For photo posts with an image_url, use ad_scheduler._post_instagram instead.
    """
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return False
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        async with http.post(
            "https://www.instagram.com/api/v1/notes/create_note/",
            data={"text": text[:60], "audience": "2"},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=12)
        ) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Instagram:{acc['username']}] ✅ Note posted")
                return True
            logger.debug(f"[Outreach:Instagram:{acc['username']}] Note failed {resp.status}")
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Instagram:{acc['username']}] Post error: {e}")
        return False


# ─── INSTAGRAM: COMMENT ──────────────────────────────────────────────────────

async def _comment_instagram(acc: dict, media_id: str, comment: str, http: aiohttp.ClientSession) -> bool:
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return False
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    url = f"https://www.instagram.com/api/v1/media/{media_id}/comment/"
    try:
        async with http.post(url, data={"comment_text": comment}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            return resp.status == 200
    except Exception:
        return False


# ─── PER-ACCOUNT OUTREACH CYCLE ───────────────────────────────────────────────

# Track which tweet IDs we've already commented on
_commented: set = set()
# Track when each account last posted
_last_post: dict[str, float] = {}

async def _run_outreach_for_account(acc: dict, http: aiohttp.ClientSession, force: bool = False):
    platform = acc.get("platform", "")
    if not acc.get("outreach_enabled", False):
        return

    acc_id = acc["id"]
    niche = acc.get("niche", "crypto")
    cta = acc.get("cta_link", "")
    now = time.time()

    # Rate limit: post max once per 30 min per account
    since_last = now - _last_post.get(acc_id, 0)
    if not force and since_last < 1800:
        pass  # Skip posting but still do comments
    else:
        # 1. POST original content
        templates = NICHE_POSTS.get(niche, NICHE_POSTS["crypto"])
        idx = int(now / 1800) % len(templates)
        text = templates[idx]
        if cta and len(text) + len(cta) + 2 < 280:
            text = f"{text}\n{cta}"

        if platform == "twitter":
            ok = await _post_tweet(acc, text, http)
            if ok:
                _last_post[acc_id] = now

        elif platform == "instagram":
            ok = await _post_instagram(acc, text[:60], http)
            if ok:
                _last_post[acc_id] = now

    # 2. COMMENT on relevant posts to attract attention (do this every cycle)
    if platform == "twitter":
        queries = SEARCH_QUERIES.get(niche, SEARCH_QUERIES["crypto"])
        query = random.choice(queries)
        tweets = await _search_twitter(acc, query, http)
        comments = NICHE_COMMENTS.get(niche, NICHE_COMMENTS["crypto"])

        sent_comments = 0
        for tweet in tweets:
            tid = tweet["id"]
            if tid in _commented:
                continue
            if sent_comments >= 2:  # Max 2 comments per cycle
                break
            comment = random.choice(comments)
            ok = await _comment_tweet(acc, tid, comment, http)
            if ok:
                _commented.add(tid)
                sent_comments += 1
                await asyncio.sleep(random.uniform(8, 20))  # Human-like delay

        # 3. PROACTIVE DMs to search results authors (max 1 per cycle, new targets only)
        dm_template = f"Hey! Saw your post about {query}. I've been tracking this space — got something you'd want to see. Check this out: {cta or 'DM me back'}"
        for tweet in tweets[:2]:
            author_id = tweet.get("author_id", "")
            if not author_id:
                continue
            await _send_twitter_dm(acc, author_id, dm_template, http)
            await asyncio.sleep(random.uniform(5, 15))
            break  # 1 proactive DM per cycle max


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

async def run_outreach_once(force: bool = False):
    """Run one outreach cycle immediately — called when a new account is added."""
    async with aiohttp.ClientSession() as http:
        accounts = marketing_db.get_accounts()
        active = [a for a in accounts if a.get("outreach_enabled", False) and a.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")]
        if active:
            tasks = [_run_outreach_for_account(acc, http, force=force) for acc in active]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"[Outreach] Immediate cycle ran for {len(active)} accounts.")


async def start_outreach_loop(check_interval: int = 1800):
    """
    Full auto-pilot loop:
    - Posts niche content every 30 min
    - Comments on relevant posts every 30 min
    - Proactively DMs targeted users every 30 min
    """
    logger.info("[Outreach Agent] Online — full auto-pilot: posting, commenting, DMing every 30 min.")
    # Run immediately on start
    await run_outreach_once(force=True)
    async with aiohttp.ClientSession() as http:
        while True:
            await asyncio.sleep(check_interval)
            try:
                accounts = marketing_db.get_accounts()
                active = [a for a in accounts if a.get("outreach_enabled", False) and a.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")]
                if active:
                    tasks = [_run_outreach_for_account(acc, http) for acc in active]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info(f"[Outreach] Cycle complete for {len(active)} active accounts.")
            except Exception as e:
                logger.error(f"[Outreach] Loop error: {e}")
