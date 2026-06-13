"""
Real Organic Lead Engine — finds REAL HUMANS discussing your keywords on Reddit (comments + posts).
Reddit comment authors are real people, not bots. Each lead is linked back to their real profile.
Nitter/Twitter is used only as a fallback and with heavy bot filtering.
Auto-assigns the best matching persona based on niche keywords.
"""
import logging
import asyncio
import aiohttp
import time
import re
import random
from typing import List, Dict, Any, Optional

import marketing_db

logger = logging.getLogger(__name__)

# Niche keyword fingerprints for auto-persona matching
NICHE_KEYWORDS = {
    "crypto": [
        "solana", "bitcoin", "ethereum", "memecoin", "crypto", "defi", "nft",
        "pump", "dex", "token", "altcoin", "sol", "btc", "eth", "web3",
        "airdrop", "presale", "moonshot", "100x", "gem", "chart", "wallet",
        "trading", "hodl", "bull", "bear", "ape", "yield"
    ],
    "celeb": [
        "model", "onlyfans", "creator", "influencer", "fans", "exclusive",
        "vip", "beauty", "fashion", "lifestyle", "content", "photo", "video",
        "subscribe", "follow", "celebrity", "actress", "singer", "stream",
        "twitch", "youtube", "tiktok creator", "instagram model"
    ],
    "casual": [
        "travel", "food", "fitness", "health", "friends", "family", "motivation",
        "daily", "vlog", "music", "art", "gaming", "sports", "entrepeneur",
        "startup", "advice", "rant", "dating", "relationship", "career"
    ]
}

# Per-niche subreddits targeting REAL HUMANS (not crypto bots)
NICHE_SUBREDDITS = {
    "crypto": [
        "CryptoCurrency", "solana", "Bitcoin", "ethfinance",
        "CryptoMoonShots", "SatoshiStreetBets", "defi"
    ],
    "celeb": [
        "Onlyfans101", "CreatorEconomy", "InstagramMarketing",
        "BeautyGuruChatter", "popculturechat", "Twitch", "NewTubers"
    ],
    "lifestyle": [
        "Entrepreneur", "personalfinance", "selfimprovement",
        "DecidingToBeBetter", "AskWomen", "AskMen", "dating_advice"
    ],
    "casual": [
        "CasualConversation", "AskReddit", "offmychest",
        "relationship_advice", "AITA", "TrueOffMyChest"
    ],
    "viral": [
        "nextfuckinglevel", "mildlyinteresting", "interestingasfuck",
        "entertainment", "Music", "movies"
    ],
    "solana": ["solana", "SolanaNFT", "solanamemes"],
    "ethereum": ["ethfinance", "ethereum", "0xPolygon"],
    "memecoins": ["CryptoMoonShots", "memecoins", "SatoshiStreetBets"],
}

# Obvious bot name patterns to filter out
BOT_PATTERNS = [
    r"^[A-Z][a-z]+[A-Z][0-9]+$",           # CamelCase + numbers like BuidlersC2
    r"^[A-Za-z]+[0-9]{3,}$",               # letters + 3+ digits
    r"(bot|Bot|BOT)$",
    r"^0x[0-9a-fA-F]+",                     # 0x hex addresses
    r"^[A-Z][a-z]+[A-Z][a-z]+[A-Z0-9]",    # MultiCapsCamelCase like PikaGambles
]

def looks_like_bot(handle: str) -> bool:
    """Returns True if the handle looks like an automated bot account."""
    clean = handle.lstrip("@").lstrip("u/")
    for pat in BOT_PATTERNS:
        if re.search(pat, clean):
            return True
    # No vowels = likely a bot/generated name
    letters = re.sub(r"[^a-zA-Z]", "", clean)
    if len(letters) >= 4:
        vowels = sum(1 for c in letters.lower() if c in "aeiou")
        if vowels == 0:
            return True
    # All uppercase with numbers = bot
    if re.match(r"^[A-Z0-9_]+$", clean) and len(clean) > 5:
        return True
    return False


def build_profile_url(handle: str, platform: str) -> str:
    """Build a direct link to the person's profile on their platform."""
    clean = handle.lstrip("@").lstrip("u/")
    if platform == "reddit":
        return f"https://www.reddit.com/user/{clean}"
    elif platform in ("twitter", "x"):
        return f"https://twitter.com/{clean}"
    elif platform == "instagram":
        return f"https://www.instagram.com/{clean}"
    elif platform == "tiktok":
        return f"https://www.tiktok.com/@{clean}"
    elif platform == "facebook":
        return f"https://www.facebook.com/{clean}"
    elif platform == "telegram":
        return f"https://t.me/{clean}"
    return ""


def detect_niche_from_text(text: str) -> str:
    """Auto-detect the best niche for a given text based on keyword matching."""
    text_lower = text.lower()
    scores = {niche: 0 for niche in NICHE_KEYWORDS}
    for niche, keywords in NICHE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[niche] += 1
    best = max(scores, key=lambda n: scores[n])
    return best if scores[best] > 0 else "casual"


def select_best_persona(message_text: str, platform: str = "unknown") -> Optional[Dict]:
    """
    Auto-selects the best matching active persona for an incoming message.
    Priority: keyword niche match > platform-specific persona > first active persona.
    """
    profiles = marketing_db.get_profiles()
    active_profiles = [p for p in profiles if p.get("active", True)]
    if not active_profiles:
        return None

    detected_niche = detect_niche_from_text(message_text)

    for profile in active_profiles:
        if profile.get("niche", "casual").lower() == detected_niche:
            return profile

    if platform == "telegram":
        for profile in active_profiles:
            if profile.get("tg_bot_token"):
                return profile

    return active_profiles[0]


async def fetch_reddit_comment_authors(subreddit: str, keywords: List[str], session: aiohttp.ClientSession) -> List[Dict]:
    """
    Finds REAL humans by searching for Reddit posts/comments matching keywords.
    Reddit users are overwhelmingly real people — not bots.
    Returns lead dicts with platform, handle, text, source_url, and profile_url.
    """
    leads = []
    keyword = keywords[0] if keywords else subreddit

    # Use Reddit search to find real people posting about the keyword
    try:
        url = f"https://www.reddit.com/r/{subreddit}/search.json?q={keyword}&sort=new&limit=20&restrict_sr=1"
        headers = {"User-Agent": "VerizonSuite/2.0 (lead discovery)"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            posts = data.get("data", {}).get("children", [])
            for child in posts:
                p = child.get("data", {})
                author = p.get("author", "")
                title = p.get("title", "")
                selftext = p.get("selftext", "")
                permalink = p.get("permalink", "")

                if not author or author in ("[deleted]", "AutoModerator", ""):
                    continue
                if looks_like_bot(author):
                    continue
                # Skip posts with too few upvotes (likely low engagement / bots)
                if p.get("score", 0) < 2:
                    continue

                text = title
                if selftext and len(selftext) > 20:
                    text = f"{title}. {selftext[:150]}"

                profile_url = build_profile_url(f"u/{author}", "reddit")
                source_url = f"https://reddit.com{permalink}"

                leads.append({
                    "platform": "reddit",
                    "handle": f"u/{author}",
                    "text": text[:200],
                    "source_url": source_url,
                    "profile_url": profile_url,
                    "score": p.get("score", 1)
                })
    except Exception as e:
        logger.debug(f"Reddit search r/{subreddit} '{keyword}': {e}")

    return leads


async def fetch_reddit_hot_commenters(subreddit: str, session: aiohttp.ClientSession) -> List[Dict]:
    """
    Gets the authors of hot/new posts from a subreddit — real active users.
    """
    leads = []
    try:
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=15"
        headers = {"User-Agent": "VerizonSuite/2.0"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            posts = data.get("data", {}).get("children", [])
            for child in posts:
                p = child.get("data", {})
                author = p.get("author", "")
                if not author or author in ("[deleted]", "AutoModerator", ""):
                    continue
                if looks_like_bot(author):
                    continue
                if p.get("score", 0) < 1:
                    continue

                title = p.get("title", "")
                permalink = p.get("permalink", "")
                profile_url = build_profile_url(f"u/{author}", "reddit")
                source_url = f"https://reddit.com{permalink}"

                leads.append({
                    "platform": "reddit",
                    "handle": f"u/{author}",
                    "text": title[:200],
                    "source_url": source_url,
                    "profile_url": profile_url,
                    "score": p.get("score", 1)
                })
    except Exception as e:
        logger.debug(f"Reddit hot r/{subreddit}: {e}")
    return leads


async def run_organic_growth_cycle():
    """
    Executes REAL organic lead discovery:
    1. Reads all active growth campaigns with their keywords/niche
    2. Finds REAL HUMANS on Reddit who are posting/commenting about those keywords
    3. Filters out bots using pattern detection
    4. Injects found users as real DM leads into the inbox with the right persona auto-selected
    5. Stores profile_url so you can click through to their real profile
    """
    settings = marketing_db.get_settings()
    if not settings.get("growth_hacks_enabled", True):
        return

    campaigns = marketing_db.get_growth_campaigns()

    # Also run a default cycle even without explicit campaigns, using persona niches
    profiles = marketing_db.get_profiles()
    active_profiles = [p for p in profiles if p.get("active", True)]

    # Build a synthetic campaign from each active persona if no campaigns
    if not campaigns and active_profiles:
        campaigns = []
        for prof in active_profiles:
            niche = prof.get("niche", "casual")
            kw_map = {
                "crypto": ["solana", "memecoin", "crypto trading"],
                "celeb": ["onlyfans creator", "content creator", "influencer"],
                "casual": ["lifestyle", "entrepreneur", "self improvement"],
            }
            campaigns.append({
                "id": f"auto_{prof['id']}",
                "niche": niche,
                "keywords": kw_map.get(niche, ["general"]),
                "cta_link": prof.get("cta_link", ""),
                "platform": "all",
                "status": "Active",
                "leads_captured": 0
            })

    if not campaigns:
        return

    async with aiohttp.ClientSession() as session:
        for camp in campaigns:
            if camp.get("status") != "Active":
                continue

            niche = camp.get("niche", "casual").lower()
            keywords = camp.get("keywords", [])
            if not keywords:
                continue

            # Map niche → subreddits with real humans
            sub_key = niche if niche in NICHE_SUBREDDITS else "casual"
            subreddits = NICHE_SUBREDDITS.get(sub_key, ["CasualConversation"])

            all_leads: List[Dict] = []

            # Primary: search for people discussing our keywords
            for subreddit in subreddits[:2]:
                reddit_leads = await fetch_reddit_comment_authors(subreddit, keywords, session)
                all_leads.extend(reddit_leads)
                await asyncio.sleep(0.8)

            # Secondary: hot post authors (recent active users)
            for subreddit in subreddits[2:3]:
                hot_leads = await fetch_reddit_hot_commenters(subreddit, session)
                all_leads.extend(hot_leads)
                await asyncio.sleep(0.5)

            if not all_leads:
                logger.debug(f"[GROWTH] No leads found for '{niche}' this cycle")
                continue

            # Sort by real engagement score, take top 3
            all_leads.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_leads = all_leads[:3]

            injected = 0
            existing_convs = marketing_db.get_conversations()

            for lead in top_leads:
                platform = lead["platform"]
                handle = lead["handle"]
                text = lead["text"]
                profile_url = lead.get("profile_url", "")
                source_url = lead.get("source_url", "")

                # Dedup — skip if this person is already in inbox
                already_exists = any(
                    c["platform"] == platform and c["sender_handle"].lower() == handle.lower()
                    for c in existing_convs
                )
                if already_exists:
                    continue

                # Auto-select best matching persona
                combined_text = f"{text} {niche} {' '.join(keywords)}"
                best_profile = select_best_persona(combined_text, platform)
                if not best_profile:
                    continue

                profile_id = best_profile["id"]

                # Inject as real incoming lead DM
                import dm_manager
                await dm_manager.handle_incoming_real_dm(
                    platform=platform,
                    sender_handle=handle,
                    message_text=text,
                    profile_id=profile_id,
                    profile_url=profile_url,
                    source_url=source_url
                )

                camp["leads_captured"] = camp.get("leads_captured", 0) + 1
                marketing_db.increment_analytics(impressions=1, leads=1)
                injected += 1
                logger.info(
                    f"🎯 [REAL LEAD] {handle} on {platform} → persona '{best_profile['name']}' "
                    f"| Score:{lead.get('score',0)} | '{text[:50]}...'"
                )
                await asyncio.sleep(random.uniform(1.5, 3.0))

            if injected > 0:
                marketing_db.save_db()
                logger.info(f"✅ [GROWTH] {injected} real humans injected from '{niche}' campaign")


async def start_organic_growth_loop(check_interval=120):
    """Periodically runs real organic lead discovery and injects real humans into inbox."""
    logger.info("Real Organic Lead Engine started — finding real people on Reddit for your campaigns.")
    while True:
        try:
            await run_organic_growth_cycle()
        except Exception as e:
            logger.error(f"Error in organic growth loop: {e}")
        await asyncio.sleep(check_interval)
