"""
Outreach Agent — full auto-pilot for connected accounts.

As soon as you add an account with "Enable outreach posts" checked, this agent:
  1. Posts niche content every 30 min → people see it → they DM you
  2. Searches for people talking about your niche → comments on their posts → they DM you
  3. Proactively DMs targeted users in your niche → they reply → inbox fills up
  4. Runs immediately on first start and every 30 min after

Platforms supported for full auto-pilot:
  - Twitter / X   → posts, searches, comments, proactive DMs (auth_token + ct0)
  - Instagram     → posts notes, searches hashtags/users, comments (sessionid)
  - TikTok        → searches trending posts, comments (sessionid + ttwid)
  - Facebook      → searches posts, comments (c_user + xs)

Niches: crypto, solana, ethereum, memecoins, celeb, lifestyle, viral
"""
import asyncio
import aiohttp
import logging
import time
import json
import random
import re

import marketing_db
import comment_filter

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

# ─── TIKTOK SEARCH QUERIES BY NICHE ──────────────────────────────────────────

TIKTOK_SEARCH_QUERIES = {
    "crypto":    ["crypto gem", "100x altcoin", "crypto alpha", "crypto calls", "memecoin pump"],
    "solana":    ["solana memecoin", "solana gem", "solana 100x", "$sol crypto"],
    "ethereum":  ["ethereum gem", "eth crypto", "base chain"],
    "memecoins": ["memecoin 100x", "memecoin gem", "degen memecoin", "meme coin pump"],
    "celeb":     ["exclusive content", "vip fans", "private chat", "close friends"],
    "lifestyle": ["passive income", "travel lifestyle", "make money online", "digital nomad"],
    "viral":     ["viral trend", "trending now", "going viral"],
}

# ─── INSTAGRAM SEARCH QUERIES BY NICHE ───────────────────────────────────────

INSTAGRAM_SEARCH_QUERIES = {
    "crypto":    ["crypto", "altcoin", "memecoin", "defi", "web3"],
    "solana":    ["solana", "solmemecoin", "solanacrypto"],
    "ethereum":  ["ethereum", "ethcrypto", "basechain"],
    "memecoins": ["memecoin", "degen", "memecrypto"],
    "celeb":     ["influencer", "creator", "exclusive", "vipcontent"],
    "lifestyle": ["lifestyle", "travelgram", "digitalnomad", "passiveincome"],
    "viral":     ["viral", "trending", "explorepage"],
}

# ─── FACEBOOK SEARCH QUERIES BY NICHE ────────────────────────────────────────

FACEBOOK_SEARCH_QUERIES = {
    "crypto":    ["crypto trading", "altcoin gem", "memecoin", "crypto calls"],
    "solana":    ["solana crypto", "solana memecoin", "sol trading"],
    "ethereum":  ["ethereum trading", "eth gem", "base chain"],
    "memecoins": ["memecoin", "meme coin gem", "degen crypto"],
    "celeb":     ["exclusive content", "vip fans", "creator"],
    "lifestyle": ["passive income", "remote work", "travel lifestyle"],
    "viral":     ["viral content", "trending topic"],
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


# ─── INSTAGRAM: SEARCH POSTS BY HASHTAG/QUERY ────────────────────────────────

async def _search_instagram(acc: dict, query: str, http: aiohttp.ClientSession) -> list:
    """
    Searches Instagram for posts matching a query using the internal web API.
    Returns list of {media_id, username, text, shortcode}.
    Requires: sessionid cookie.
    """
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return []
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
        "x-requested-with": "XMLHttpRequest",
    }
    import urllib.parse
    q = urllib.parse.quote(query)
    results = []

    # Strategy 1: Search hashtags (finds posts)
    try:
        url = f"https://www.instagram.com/web/search/topsearch/?query={q}&context=hashtag"
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                hashtags = data.get("hashtags", [])
                # Get posts from top hashtag result
                if hashtags:
                    tag_name = hashtags[0].get("hashtag", {}).get("name", query)
                    tag_results = await _get_instagram_hashtag_posts(acc, tag_name, http)
                    results.extend(tag_results)
    except Exception as e:
        logger.debug(f"[Outreach:Instagram:{acc['username']}] Search error: {e}")

    # Strategy 2: Search users → get their recent posts
    try:
        url = f"https://www.instagram.com/web/search/topsearch/?query={q}&context=user"
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                users = data.get("users", [])[:3]
                for user_data in users:
                    user = user_data.get("user", {})
                    username = user.get("username", "")
                    if not username or comment_filter.is_bot_username(username):
                        continue
                    user_posts = await _get_instagram_user_posts(acc, username, http)
                    results.extend(user_posts)
    except Exception as e:
        logger.debug(f"[Outreach:Instagram:{acc['username']}] User search error: {e}")

    return results[:8]


async def _get_instagram_hashtag_posts(acc: dict, tag: str, http: aiohttp.ClientSession) -> list:
    """Get recent posts from an Instagram hashtag."""
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return []
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        url = f"https://www.instagram.com/explore/tags/{tag}/?__a=1&__d=1"
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                # Fallback: try the web API
                url2 = f"https://www.instagram.com/api/v1/tags/{tag}/info/"
                async with http.get(url2, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                    if resp2.status != 200:
                        return []
                    data2 = await resp2.json()
                    return []
            data = await resp.json()
            sections = data.get("graphql", {}).get("hashtag", {}).get("edge_hashtag_to_media", {}).get("edges", [])
            results = []
            for edge in sections[:4]:
                node = edge.get("node", {})
                media_id = node.get("id", "")
                shortcode = node.get("shortcode", "")
                caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                caption = caption_edges[0]["node"]["text"][:80] if caption_edges else ""
                owner = node.get("owner", {}).get("username", "unknown")
                if media_id:
                    results.append({
                        "media_id": media_id,
                        "shortcode": shortcode,
                        "username": owner,
                        "text": caption,
                    })
            return results
    except Exception as e:
        logger.debug(f"[IG hashtag posts] Error: {e}")
        return []


async def _get_instagram_user_posts(acc: dict, username: str, http: aiohttp.ClientSession) -> list:
    """Get recent posts from an Instagram user profile."""
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return []
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            media = data.get("data", {}).get("user", {}).get("edge_owner_to_timeline_media", {}).get("edges", [])
            results = []
            for edge in media[:3]:
                node = edge.get("node", {})
                media_id = node.get("id", "")
                shortcode = node.get("shortcode", "")
                caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                caption = caption_edges[0]["node"]["text"][:80] if caption_edges else ""
                if media_id:
                    results.append({
                        "media_id": media_id,
                        "shortcode": shortcode,
                        "username": username,
                        "text": caption,
                    })
            return results
    except Exception as e:
        logger.debug(f"[IG user posts] Error for @{username}: {e}")
        return []


# ─── INSTAGRAM: COMMENT ON A POST ────────────────────────────────────────────

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
            if resp.status == 200:
                logger.info(f"[Outreach:Instagram:{acc['username']}] 💬 Commented on media {media_id}")
                return True
            logger.debug(f"[Outreach:Instagram:{acc['username']}] Comment failed {resp.status}")
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Instagram:{acc['username']}] Comment error: {e}")
        return False


# ─── TIKTOK: SEARCH POSTS ────────────────────────────────────────────────────

async def _search_tiktok(acc: dict, query: str, http: aiohttp.ClientSession) -> list:
    """
    Searches TikTok for videos matching a query using the internal web API.
    Returns list of {aweme_id, author, text, author_handle}.
    Requires: sessionid + ttwid cookies.
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
        "Referer": "https://www.tiktok.com/search",
        "x-secsdk-csrf-version": "1.2.8",
    }

    import urllib.parse
    q = urllib.parse.quote(query)

    # Strategy 1: Search general API
    results = []
    try:
        url = f"https://www.tiktok.com/api/search/general/full/?keyword={q}&count=10&cursor=0&search_id=&search_source=normal_search"
        async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                raw = await resp.json()
                items = raw.get("data", [])
                for item in items:
                    aweme = item.get("aweme_info", {})
                    if not aweme:
                        continue
                    aweme_id = aweme.get("aweme_id", "")
                    desc = aweme.get("desc", "")[:100]
                    author = aweme.get("author", {})
                    author_handle = author.get("unique_id", author.get("nickname", "unknown"))
                    author_uid = author.get("uid", "")

                    # Skip spam/bot accounts
                    if comment_filter.is_bot_username(author_handle):
                        continue

                    if aweme_id:
                        results.append({
                            "aweme_id": aweme_id,
                            "author_handle": f"@{author_handle}",
                            "author_uid": author_uid,
                            "text": desc,
                        })
            elif resp.status in (401, 403):
                logger.warning(f"[TikTok:{acc['username']}] Session expired during search")
                return []
            else:
                logger.debug(f"[TikTok:{acc['username']}] Search returned {resp.status}")
    except Exception as e:
        logger.debug(f"[TikTok:{acc['username']}] Search error: {e}")

    # Strategy 2: Search via hashtag if general search fails
    if not results:
        try:
            tag = query.replace(" ", "").lower()
            url = f"https://www.tiktok.com/api/challenge/item_list?challengeName={tag}&count=10&cursor=0"
            async with http.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    raw = await resp.json()
                    items = raw.get("item_list", [])
                    for item in items:
                        aweme_id = item.get("aweme_id", "")
                        desc = item.get("desc", "")[:100]
                        author = item.get("author", {})
                        author_handle = author.get("unique_id", "unknown")
                        if comment_filter.is_bot_username(author_handle):
                            continue
                        if aweme_id:
                            results.append({
                                "aweme_id": aweme_id,
                                "author_handle": f"@{author_handle}",
                                "author_uid": author.get("uid", ""),
                                "text": desc,
                            })
        except Exception as e:
            logger.debug(f"[TikTok:{acc['username']}] Hashtag search error: {e}")

    return results[:5]


# ─── TIKTOK: COMMENT ON A VIDEO ──────────────────────────────────────────────

async def _comment_tiktok(acc: dict, aweme_id: str, comment: str, http: aiohttp.ClientSession) -> bool:
    """
    Posts a comment on a TikTok video using session cookies.
    Requires: sessionid + ttwid cookies.
    """
    sessionid = acc.get("sessionid", "")
    ttwid = acc.get("ttwid", "")
    if not sessionid:
        return False

    cookie_str = f"sessionid={sessionid}"
    if ttwid:
        cookie_str += f"; ttwid={ttwid}"

    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://www.tiktok.com/@{acc.get('username', '')}/video/{aweme_id}",
        "Content-Type": "application/x-www-form-urlencoded",
        "x-secsdk-csrf-version": "1.2.8",
    }

    import urllib.parse
    data = {
        "aweme_id": aweme_id,
        "text": comment,
        "text_extra": "[]",
        "is_self": "0",
    }

    try:
        url = "https://www.tiktok.com/api/comment/post/"
        async with http.post(url, data=urllib.parse.urlencode(data), headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                raw = await resp.json()
                status_code = raw.get("status_code", -1)
                if status_code == 0:
                    logger.info(f"[Outreach:TikTok:{acc['username']}] 💬 Commented on video {aweme_id}")
                    return True
                logger.debug(f"[Outreach:TikTok:{acc['username']}] Comment status_code={status_code}")
                return False
            elif resp.status in (401, 403):
                logger.warning(f"[TikTok:{acc['username']}] Session expired during comment")
                return False
            else:
                logger.debug(f"[Outreach:TikTok:{acc['username']}] Comment failed {resp.status}")
                return False
    except Exception as e:
        logger.debug(f"[Outreach:TikTok:{acc['username']}] Comment error: {e}")
        return False


# ─── TIKTOK: PROACTIVE DM ────────────────────────────────────────────────────

async def _send_tiktok_dm(acc: dict, recipient_uid: str, text: str, http: aiohttp.ClientSession) -> bool:
    """
    Sends a proactive DM on TikTok using session cookies.
    """
    sessionid = acc.get("sessionid", "")
    ttwid = acc.get("ttwid", "")
    if not sessionid or not recipient_uid:
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

    import urllib.parse
    data = {
        "recipients": json.dumps([recipient_uid]),
        "text": text,
        "message_type": "0",
    }

    try:
        url = "https://www.tiktok.com/api/im/message/send/"
        async with http.post(url, data=urllib.parse.urlencode(data), headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                raw = await resp.json()
                if raw.get("status_code", -1) == 0:
                    logger.info(f"[Outreach:TikTok:{acc['username']}] 📨 DM sent to {recipient_uid}")
                    return True
            return False
    except Exception as e:
        logger.debug(f"[Outreach:TikTok:{acc['username']}] DM error: {e}")
        return False


# ─── FACEBOOK: SEARCH POSTS ──────────────────────────────────────────────────

async def _search_facebook(acc: dict, query: str, http: aiohttp.ClientSession) -> list:
    """
    Searches Facebook for public posts matching a query using the internal GraphQL API.
    Returns list of {post_id, username, text, profile_url}.
    Requires: c_user + xs cookies.
    """
    c_user = acc.get("c_user", "")
    xs = acc.get("xs", "")
    if not c_user or not xs:
        return []

    headers = {
        "Cookie": f"c_user={c_user}; xs={xs}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-fb-friendly-name": "SearchCometResultsPaginatedQuery",
    }

    import urllib.parse
    results = []

    # Use Facebook's internal search
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.facebook.com/api/graphql/"
        # Use the search results page scraping approach
        search_url = f"https://www.facebook.com/search/posts/?q={encoded_query}"
        async with http.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.debug(f"[Facebook:{acc['username']}] Search returned {resp.status}")
                return []
            html = await resp.text()
            # Extract post IDs and content from the HTML response
            # Facebook embeds data in JSON within script tags
            post_pattern = re.findall(r'"post_id":"(\d+)"', html)
            story_pattern = re.findall(r'"story_id":"(\d+_\d+)"', html)

            # Get unique post IDs
            seen_ids = set()
            for pid in post_pattern[:5]:
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append({
                        "post_id": pid,
                        "username": "facebook_user",
                        "text": query,
                    })
            for sid in story_pattern[:5]:
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    results.append({
                        "post_id": sid.split("_")[1] if "_" in sid else sid,
                        "username": "facebook_user",
                        "text": query,
                    })
    except Exception as e:
        logger.debug(f"[Facebook:{acc['username']}] Search error: {e}")

    return results[:5]


# ─── FACEBOOK: COMMENT ON A POST ─────────────────────────────────────────────

async def _comment_facebook(acc: dict, post_id: str, comment: str, http: aiohttp.ClientSession) -> bool:
    """
    Posts a comment on a Facebook post using session cookies.
    Uses Facebook's internal GraphQL mutation.
    """
    c_user = acc.get("c_user", "")
    xs = acc.get("xs", "")
    if not c_user or not xs:
        return False

    headers = {
        "Cookie": f"c_user={c_user}; xs={xs}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "x-fb-friendly-name": "CommentCreateMutation",
    }

    import urllib.parse
    data = {
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "CommentCreateMutation",
        "variables": json.dumps({
            "input": {
                "comment_level": 0,
                "feedback_ref": f"post:{post_id}",
                "message": {"text": comment},
                "actor_id": c_user,
                "client_mutation_id": str(int(time.time())),
            },
        }),
        "doc_id": "6672950532735034",
    }

    try:
        url = "https://www.facebook.com/api/graphql/"
        async with http.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Facebook:{acc['username']}] 💬 Commented on post {post_id}")
                return True
            logger.debug(f"[Outreach:Facebook:{acc['username']}] Comment failed {resp.status}")
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Facebook:{acc['username']}] Comment error: {e}")
        return False


# ─── PER-ACCOUNT OUTREACH CYCLE ───────────────────────────────────────────────

# Track which tweet IDs / media IDs we've already commented on
_commented: set = set()
# Track when each account last posted
_last_post: dict[str, float] = {}

# Spam filter: skip DM to these handles
_dm_blacklist: set = set()


async def _run_outreach_for_account(acc: dict, http: aiohttp.ClientSession, force: bool = False):
    """
    Full auto-pilot outreach for a single account.
    Platform-aware: handles Twitter, Instagram, TikTok, and Facebook.
    """
    platform = acc.get("platform", "")
    if not acc.get("outreach_enabled", False):
        return

    acc_id = acc["id"]
    niche = acc.get("niche", "crypto")
    cta = acc.get("cta_link", "")
    now = time.time()

    # Rate limit: post max once per 30 min per account
    since_last = now - _last_post.get(acc_id, 0)
    should_post = force or since_last >= 1800

    if should_post:
        # 1. POST original content (platform-specific)
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

        elif platform == "tiktok":
            # TikTok posting via session is very restricted — skip to avoid bans
            # Focus on comments which are the primary DM driver
            pass

        elif platform == "facebook":
            # Facebook posting via session — comment-driven outreach is primary
            pass

    # ─── 2. SEARCH + COMMENT (every cycle, all platforms) ────────────────────

    comment_count = 0
    max_comments_per_cycle = 2

    if platform == "twitter":
        queries = SEARCH_QUERIES.get(niche, SEARCH_QUERIES["crypto"])
        query = random.choice(queries)
        tweets = await _search_twitter(acc, query, http)

        for tweet in tweets:
            tid = tweet["id"]
            if tid in _commented:
                continue
            if comment_count >= max_comments_per_cycle:
                break
            # Filter: skip if author looks like a bot
            if comment_filter.is_bot_username(tweet.get("author_id", "")):
                continue
            comments = comment_filter.get_niche_comments("twitter", niche)
            if not comments:
                comments = _get_twitter_comments_fallback(niche)
            comment = random.choice(comments)
            ok = await _comment_tweet(acc, tid, comment, http)
            if ok:
                _commented.add(tid)
                comment_count += 1
                await asyncio.sleep(random.uniform(8, 20))  # Human-like delay

        # 3. PROACTIVE DMs (max 1 per cycle)
        dm_template = f"Hey! Saw your post about {query}. I've been tracking this space — got something you'd want to see. Check this out: {cta or 'DM me back'}"
        for tweet in tweets[:2]:
            author_id = tweet.get("author_id", "")
            if not author_id or author_id in _dm_blacklist:
                continue
            if comment_filter.is_bot_username(author_id):
                _dm_blacklist.add(author_id)
                continue
            await _send_twitter_dm(acc, author_id, dm_template, http)
            _dm_blacklist.add(author_id)
            await asyncio.sleep(random.uniform(5, 15))
            break  # 1 proactive DM per cycle max

    elif platform == "instagram":
        queries = INSTAGRAM_SEARCH_QUERIES.get(niche, INSTAGRAM_SEARCH_QUERIES["crypto"])
        query = random.choice(queries)
        posts = await _search_instagram(acc, query, http)

        for post in posts:
            media_id = post.get("media_id", "")
            if not media_id or media_id in _commented:
                continue
            if comment_count >= max_comments_per_cycle:
                break
            # Filter: skip bot usernames
            if comment_filter.is_bot_username(post.get("username", "")):
                continue
            comments = comment_filter.get_niche_comments("instagram", niche)
            if not comments:
                comments = _get_instagram_comments_fallback(niche)
            comment = random.choice(comments)
            ok = await _comment_instagram(acc, media_id, comment, http)
            if ok:
                _commented.add(media_id)
                comment_count += 1
                await asyncio.sleep(random.uniform(10, 25))  # IG is more aggressive with rate limits

    elif platform == "tiktok":
        queries = TIKTOK_SEARCH_QUERIES.get(niche, TIKTOK_SEARCH_QUERIES["crypto"])
        query = random.choice(queries)
        videos = await _search_tiktok(acc, query, http)

        for video in videos:
            aweme_id = video.get("aweme_id", "")
            if not aweme_id or aweme_id in _commented:
                continue
            if comment_count >= max_comments_per_cycle:
                break
            # Filter: skip bot usernames
            if comment_filter.is_bot_username(video.get("author_handle", "").lstrip("@")):
                continue
            comments = comment_filter.get_niche_comments("tiktok", niche)
            if not comments:
                comments = _get_tiktok_comments_fallback(niche)
            comment = random.choice(comments)
            ok = await _comment_tiktok(acc, aweme_id, comment, http)
            if ok:
                _commented.add(aweme_id)
                comment_count += 1
                await asyncio.sleep(random.uniform(10, 30))  # TikTok rate limits aggressively

            # Proactive DM to video author (max 1 per cycle)
            if comment_count == 1 and video.get("author_uid"):
                author_uid = video["author_uid"]
                if author_uid not in _dm_blacklist:
                    dm_text = f"hey! just saw your video about {query}, really good stuff. I've been building something in this space — check it out: {cta or 'dm me back'}"
                    await _send_tiktok_dm(acc, author_uid, dm_text, http)
                    _dm_blacklist.add(author_uid)
                    await asyncio.sleep(random.uniform(5, 15))

    elif platform == "facebook":
        queries = FACEBOOK_SEARCH_QUERIES.get(niche, FACEBOOK_SEARCH_QUERIES["crypto"])
        query = random.choice(queries)
        posts = await _search_facebook(acc, query, http)

        for post in posts:
            post_id = post.get("post_id", "")
            if not post_id or post_id in _commented:
                continue
            if comment_count >= max_comments_per_cycle:
                break
            comments = comment_filter.get_niche_comments("facebook", niche)
            if not comments:
                comments = _get_facebook_comments_fallback(niche)
            comment = random.choice(comments)
            ok = await _comment_facebook(acc, post_id, comment, http)
            if ok:
                _commented.add(post_id)
                comment_count += 1
                await asyncio.sleep(random.uniform(10, 25))

    if comment_count > 0:
        logger.info(f"[Outreach:{platform}:{acc['username']}] 🔥 {comment_count} comments posted this cycle")


# ─── FALLBACK COMMENT TEMPLATES ──────────────────────────────────────────────

def _get_twitter_comments_fallback(niche: str) -> list:
    templates = {
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
    return templates.get(niche, templates["crypto"])


def _get_instagram_comments_fallback(niche: str) -> list:
    return comment_filter.INSTAGRAM_COMMENTS.get(niche, comment_filter.INSTAGRAM_COMMENTS.get("crypto", ["Great post! 🔥"]))


def _get_tiktok_comments_fallback(niche: str) -> list:
    return comment_filter.TIKTOK_COMMENTS.get(niche, comment_filter.TIKTOK_COMMENTS.get("crypto", ["this is fire 🔥"]))


def _get_facebook_comments_fallback(niche: str) -> list:
    return comment_filter.FACEBOOK_COMMENTS.get(niche, comment_filter.FACEBOOK_COMMENTS.get("crypto", ["Great post!"]))


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
    - Searches & comments on relevant posts every 30 min (Twitter + IG + TikTok + FB)
    - Proactively DMs targeted users every 30 min
    - Filters spam/bots before engaging
    """
    logger.info("[Outreach Agent] Online — full auto-pilot: posting, searching, commenting, DMing across Twitter + Instagram + TikTok + Facebook.")
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
