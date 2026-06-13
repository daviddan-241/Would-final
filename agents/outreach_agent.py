"""
Outreach Agent — posts real content FROM your connected accounts to attract real DMs.

How the full pipeline works:
  1. You connect a real account (Twitter, Instagram, TikTok) with session cookies
  2. This agent posts niche content FROM that account (crypto alpha, celeb promo, lifestyle)
  3. Real people see the post → some DM you asking about it
  4. Those DMs land in your inbox in real time via the Session DM Agent
  5. You reply → they follow your funnel link

No bots. Real followers, real DMs, real conversions.

Niches supported: crypto, celeb, lifestyle, viral, memecoins, solana, ethereum
"""
import asyncio
import aiohttp
import logging
import time
import json
import urllib.parse

import marketing_db

logger = logging.getLogger("agent.outreach")

# ─── NICHE CONTENT TEMPLATES ─────────────────────────────────────────────────

NICHE_POSTS = {
    "crypto": [
        "🚨 $SOL just broke resistance. This is the move everyone's been waiting for. DM me 'ALPHA' for my private calls before they're gone.",
        "Three wallets just loaded up on this gem quietly. Under 1M mcap. DM me for the ticker — posting publicly would send it 10x immediately.",
        "I've been in crypto 4 years. The next 30 days are going to make a lot of people rich. DM me if you're serious about it.",
        "Why is nobody talking about this? Insider buying detected on-chain. DM me 'GEM' and I'll send you the contract.",
        "🔥 Just exited a 40x in 6 hours. My next call goes out to my private list tonight. DM me to get on it.",
    ],
    "solana": [
        "Solana is moving. My private group caught 3 100x memecoins this month. DM me 'SOL' to join before tonight's call.",
        "Just found a new Solana memecoin with less than 500 holders. These are the ones that 100x. DM me for the CA.",
        "🟣 SOL ecosystem is absolutely cooking. My whale wallet tracker just flagged something big. DM me 'PUMP' to get the details.",
    ],
    "ethereum": [
        "ETH Base chain is the new playground. Found a gem with 200 holders and a solid dev team. DM me for the contract.",
        "💎 Three ETH plays that could 10x this week. Not posting publicly — DM me 'BASE' if you want in.",
    ],
    "memecoins": [
        "🐸 Memecoin season is HERE. I just called 4 10x's in a row. DM me 'MOON' to get my next call first.",
        "Found a memecoin with a viral TikTok trend behind it and only 1M mcap. This is going to explode. DM me.",
        "Everyone's looking at the wrong memecoins. DM me 'GEM' and I'll show you what the smart money is loading.",
    ],
    "celeb": [
        "Hey 💕 I just posted something exclusive on my private page. DM me if you want the link — I only share with real ones.",
        "Surprise for everyone who DMs me tonight 🔥 limited time. You know who you are.",
        "I don't post this publicly but DM me and I'll send you something special 💋",
        "Missing my close friends rn 🥺 DM me and let's actually talk — I respond to everyone tonight.",
        "Starting a private chat with my real fans tonight. DM me 'VIP' if you want in 🌙",
    ],
    "lifestyle": [
        "Just landed in Bali 🌴 If you want my full travel guide (flights, hotels, hidden spots) DM me 'BALI'",
        "Built a $10k/month income stream from my phone while traveling. DM me if you want to know how — I'll explain everything.",
        "My morning routine completely changed my life. DM me 'ROUTINE' and I'll send you my full guide for free.",
        "Dropped everything and moved abroad 6 months ago. Zero regrets. DM me if you want the honest breakdown of how I did it.",
    ],
    "viral": [
        "This clip is about to go viral and I'm posting it 24 hours early to my DMs. Message me 'FIRST' right now.",
        "Something big is happening in the next 48 hours. I can't say it publicly. DM me if you want to know.",
        "I have 10 spots left for something I'm running tonight. DM me fast — first come first served.",
    ],
}

# ─── TWITTER POSTING ─────────────────────────────────────────────────────────

async def post_tweet(acc: dict, text: str, session: aiohttp.ClientSession) -> bool:
    """Posts a tweet from a connected Twitter account using session cookies."""
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
    # Twitter v2 create tweet
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
            "responsive_web_twitter_article_tweet_consumption_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "rweb_video_timestamps_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "freedom_of_speech_not_reach_tweet_label_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_feature_enabled": True,
            "interactive_text_enabled": True,
            "responsive_web_text_conversations_enabled": False,
            "vibe_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        },
    }
    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Twitter:{acc['username']}] ✅ Posted tweet successfully.")
                return True
            else:
                body = await resp.text()
                logger.debug(f"[Outreach:Twitter:{acc['username']}] Post failed {resp.status}: {body[:200]}")
                return False
    except Exception as e:
        logger.debug(f"[Outreach:Twitter:{acc['username']}] Error posting: {e}")
        return False


# ─── INSTAGRAM DM OUTREACH ────────────────────────────────────────────────────

async def send_instagram_dm(acc: dict, target_user_id: str, text: str, session: aiohttp.ClientSession) -> bool:
    """Sends a DM from connected Instagram account to a target user."""
    sessionid = acc.get("sessionid", "")
    if not sessionid:
        return False

    headers = {
        "Cookie": f"sessionid={sessionid}",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
        "x-requested-with": "XMLHttpRequest",
    }
    url = f"https://www.instagram.com/api/v1/direct_v2/threads/broadcast/text/"
    data = {
        "text": text,
        "recipient_users": f"[[{target_user_id}]]",
        "thread_ids": "[]",
    }
    try:
        async with session.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                logger.info(f"[Outreach:Instagram:{acc['username']}] ✅ DM sent to {target_user_id}.")
                return True
            return False
    except Exception as e:
        logger.debug(f"[Outreach:Instagram:{acc['username']}] DM error: {e}")
        return False


# ─── MAIN OUTREACH CYCLE ─────────────────────────────────────────────────────

def _pick_post_text(acc: dict) -> str:
    """Picks the best content template based on the account's niche tag."""
    niche = acc.get("niche", "").lower()
    if not niche:
        # Try to guess from username
        uname = acc.get("username", "").lower()
        if any(w in uname for w in ["sol", "eth", "crypto", "coin", "gem", "moon"]):
            niche = "crypto"
        elif any(w in uname for w in ["celeb", "vip", "fan", "love", "official"]):
            niche = "celeb"
        else:
            niche = "crypto"

    templates = NICHE_POSTS.get(niche) or NICHE_POSTS.get("crypto")
    # Rotate through templates using current hour so it cycles automatically
    idx = int(time.time() / 3600) % len(templates)
    cta = acc.get("cta_link", "")
    text = templates[idx]
    # Append funnel link if set
    if cta and len(text) + len(cta) + 2 < 280:
        text = f"{text}\n{cta}"
    return text


async def _run_outreach_for_account(acc: dict, http: aiohttp.ClientSession):
    platform = acc.get("platform", "")
    # Only post if outreach is enabled on the account
    if not acc.get("outreach_enabled", False):
        return

    text = _pick_post_text(acc)

    if platform == "twitter":
        await post_tweet(acc, text, http)
    # Instagram story/post outreach can be added here in future


async def start_outreach_loop(check_interval: int = 3600):
    """
    Runs once per hour per connected account.
    Posts niche content to attract real DMs from real people.
    """
    logger.info("[Outreach Agent] Online — posting niche content from connected accounts every hour.")
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as http:
        while True:
            try:
                accounts = marketing_db.get_accounts()
                active = [
                    a for a in accounts
                    if a.get("outreach_enabled", False)
                    and a.get("status", "Active") not in ("Expired — re-paste cookies", "Disabled")
                ]
                if active:
                    tasks = [_run_outreach_for_account(acc, http) for acc in active]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    if active:
                        logger.info(f"[Outreach] Ran outreach cycle for {len(active)} accounts.")
            except Exception as e:
                logger.error(f"[Outreach] Loop error: {e}")
            await asyncio.sleep(check_interval)
