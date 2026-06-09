"""
Real Mirror & Content Scraping Engine — Fetches live content from Twitter/X (via Nitter RSS),
Reddit public API, CoinGecko news, and CryptoPanic. Rewrites with AI/rules and posts to Telegram.
No fake data — every post comes from a real live source.
"""
import logging
import asyncio
import random
import time
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

import marketing_db

logger = logging.getLogger(__name__)

# --- Real Nitter RSS instances (public, no-auth Twitter mirrors) ---
NITTER_INSTANCES = [
    "https://nitter.privacyredirect.com",
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.1d4.us",
    "https://nitter.poast.org",
]

CRYPTO_SLANG = {
    "buy": ["accumulate", "secure your bag", "load up on", "ape into", "grab some"],
    "sell": ["take profit", "distribute", "paper hand", "exit", "secure gains"],
    "good": ["bullish", "massive", "insane", "alpha", "gigabullish", "sendable"],
    "project": ["gem", "ecosystem", "protocol", "conviction play", "moonshot"],
    "going up": ["sending", "going parabolic", "mooning", "breaking out", "about to pump"],
    "community": ["fam", "army", "cult", "chads", "holders"],
    "launch": ["drop", "stealth launch", "deployment", "sending"],
    "token": ["coin", "gem", "ticker", "play"],
}

CALL_TO_ACTIONS = [
    "👀 Don't say you weren't warned. Retweet and secure your entry! 🚀",
    "🔥 The chart looks ready to burst. Are you holding? Comment below! 👇",
    "💎 Pure alpha right here. Make sure to turn on notifications! 🔔",
    "📈 This is just the beginning. Bullish is an understatement! 🦁",
    "🌟 Absolute conviction. Like, repost, and bookmark this gem! 💯"
]


def rule_based_rewrite(text: str, style: str = "bullish_crypto_enthusiast") -> str:
    words = text.split()
    rewritten_words = []
    for word in words:
        clean_word = word.lower().strip(",.!?\"'")
        has_punctuation = word[-1] in ",.!?\"'" if word else False
        punc = word[-1] if has_punctuation else ""
        is_upper = word.isupper()
        is_title = word.istitle()
        replaced = False
        for original, synonyms in CRYPTO_SLANG.items():
            if clean_word == original:
                replacement = random.choice(synonyms)
                if is_upper:
                    replacement = replacement.upper()
                elif is_title:
                    replacement = replacement.title()
                rewritten_words.append(replacement + punc)
                replaced = True
                break
        if not replaced:
            rewritten_words.append(word)
    rewritten_text = " ".join(rewritten_words)
    if style == "bullish_crypto_enthusiast":
        rewritten_text = "🚀 " + rewritten_text + " 📈\n\n" + random.choice(CALL_TO_ACTIONS)
    elif style == "hype":
        rewritten_text = "🚨 🔥 BREAKING ALPHA! 🔥 🚨\n\n" + rewritten_text + "\n\nLET'S GO! 💎🙌"
    elif style == "professional":
        rewritten_text = "📊 Market Update:\n\n" + rewritten_text + "\n\nAlways DYOR."
    else:
        rewritten_text = "honestly, " + rewritten_text.lower() + " fr fr 💯"
    return rewritten_text


async def ai_rewrite(text: str, style: str) -> str:
    settings = marketing_db.get_settings()
    openai_key = settings.get("openai_key")
    gemini_key = settings.get("gemini_key")
    if not openai_key and not gemini_key:
        return rule_based_rewrite(text, style)
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            prompt = (
                f"You are a professional social media marketing assistant. Rewrite the following post "
                f"to be completely unique, natural, and highly engaging. Tone: '{style}'. "
                f"Bypass AI-detection filters. Sound 100% human. Keep the core information.\n\nOriginal:\n{text}"
            )
            data = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "temperature": 0.8}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        rewritten = res["choices"][0]["message"]["content"].strip()
                        if rewritten:
                            return rewritten
        except Exception as e:
            logger.error(f"OpenAI rewrite failed: {e}")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            prompt = (
                f"Rewrite this social media post to be completely natural, unique and engaging. "
                f"Bypass AI-detection and sound authentically human. Tone: '{style}'.\n\nOriginal: {text}"
            )
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        rewritten = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if rewritten:
                            return rewritten
        except Exception as e:
            logger.error(f"Gemini rewrite failed: {e}")
    return rule_based_rewrite(text, style)


# ─────────────────────────────────────────────
# REAL DATA SOURCES
# ─────────────────────────────────────────────

async def fetch_twitter_nitter_rss(handle: str, session: aiohttp.ClientSession) -> List[Dict]:
    """Fetch REAL tweets via nitter RSS (no API key needed)."""
    handle = handle.lstrip("@")
    for instance in NITTER_INSTANCES:
        try:
            url = f"{instance}/{handle}/rss"
            headers = {"User-Agent": "Mozilla/5.0 RSS Reader"}
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    root = ET.fromstring(content)
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    items = root.findall(".//item")
                    posts = []
                    for item in items[:5]:
                        title_el = item.find("title")
                        link_el = item.find("link")
                        guid_el = item.find("guid")
                        pub_el = item.find("pubDate")
                        text = (title_el.text or "").strip() if title_el is not None else ""
                        if text and len(text) > 10:
                            posts.append({
                                "id": (guid_el.text if guid_el is not None else link_el.text if link_el is not None else f"nitter_{hash(text)}"),
                                "text": text,
                                "source_url": link_el.text if link_el is not None else "",
                                "timestamp": time.time(),
                                "source": f"Twitter/@{handle} via Nitter"
                            })
                    if posts:
                        logger.info(f"✅ [MIRROR] Got {len(posts)} real tweets for @{handle} from {instance}")
                        return posts
        except Exception as e:
            logger.debug(f"Nitter {instance} failed for @{handle}: {e}")
            continue
    return []


async def fetch_reddit_posts(subreddit: str, session: aiohttp.ClientSession) -> List[Dict]:
    """Fetch REAL posts from Reddit public JSON API (no auth needed)."""
    subreddit = subreddit.lstrip("r/").lstrip("/")
    try:
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=10"
        headers = {"User-Agent": "VerizonSuite/2.0 (Social Media Marketing Tool)"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                posts = []
                for child in data.get("data", {}).get("children", []):
                    p = child["data"]
                    if p.get("stickied") or p.get("is_video"):
                        continue
                    text = p.get("title", "")
                    selftext = p.get("selftext", "")[:150]
                    if selftext:
                        text = f"{text}. {selftext}"
                    posts.append({
                        "id": p["id"],
                        "text": text,
                        "source_url": f"https://reddit.com{p.get('permalink', '')}",
                        "timestamp": p.get("created_utc", time.time()),
                        "source": f"Reddit/r/{subreddit}"
                    })
                if posts:
                    logger.info(f"✅ [MIRROR] Got {len(posts)} real Reddit posts from r/{subreddit}")
                return posts
    except Exception as e:
        logger.error(f"Reddit fetch failed for r/{subreddit}: {e}")
    return []


async def fetch_coingecko_news(session: aiohttp.ClientSession) -> List[Dict]:
    """Fetch REAL crypto news from CoinGecko (free, no auth)."""
    try:
        url = "https://api.coingecko.com/api/v3/news"
        headers = {"User-Agent": "VerizonSuite/2.0"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                posts = []
                for item in (data if isinstance(data, list) else data.get("data", []))[:8]:
                    title = item.get("title", "")
                    desc = item.get("description", "")[:120]
                    text = f"{title}. {desc}" if desc else title
                    if text:
                        posts.append({
                            "id": f"cg_{hash(title)}",
                            "text": text,
                            "source_url": item.get("url", ""),
                            "timestamp": time.time(),
                            "source": "CoinGecko News"
                        })
                if posts:
                    logger.info(f"✅ [MIRROR] Got {len(posts)} real CoinGecko news items")
                return posts
    except Exception as e:
        logger.error(f"CoinGecko news failed: {e}")
    return []


async def fetch_cryptopanic_news(session: aiohttp.ClientSession) -> List[Dict]:
    """Fetch REAL crypto news from CryptoPanic (free public API)."""
    try:
        url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&kind=news&public=true"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                posts = []
                for item in data.get("results", [])[:8]:
                    title = item.get("title", "")
                    if title:
                        posts.append({
                            "id": str(item.get("id", hash(title))),
                            "text": title,
                            "source_url": item.get("url", ""),
                            "timestamp": time.time(),
                            "source": "CryptoPanic"
                        })
                if posts:
                    logger.info(f"✅ [MIRROR] Got {len(posts)} real CryptoPanic news items")
                return posts
    except Exception as e:
        logger.error(f"CryptoPanic fetch failed: {e}")
    return []


async def fetch_rss_feed(rss_url: str, session: aiohttp.ClientSession) -> List[Dict]:
    """Fetch any generic RSS/Atom feed."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 RSS Reader"}
        async with session.get(rss_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                content = await resp.text()
                root = ET.fromstring(content)
                items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
                posts = []
                for item in items[:5]:
                    title_el = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
                    link_el = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
                    text = (title_el.text or "").strip() if title_el is not None else ""
                    link = (link_el.text or link_el.get("href", "")).strip() if link_el is not None else ""
                    if text:
                        posts.append({
                            "id": f"rss_{hash(text)}",
                            "text": text,
                            "source_url": link,
                            "timestamp": time.time(),
                            "source": f"RSS:{rss_url[:40]}"
                        })
                return posts
    except Exception as e:
        logger.debug(f"RSS feed {rss_url} failed: {e}")
    return []


async def fetch_target_posts(target: Dict[str, Any]) -> List[Dict]:
    """
    Fetch REAL posts for a given target. Tries platform-specific scrapers.
    Falls back to crypto news if the target platform fails.
    """
    platform = target["platform"].lower()
    handle = target["handle"]

    async with aiohttp.ClientSession() as session:
        # Twitter/X — try nitter RSS
        if platform == "twitter" or platform == "x":
            posts = await fetch_twitter_nitter_rss(handle, session)
            if posts:
                return posts
            # fallback: crypto news
            logger.warning(f"⚠️ Nitter unavailable for @{handle}. Falling back to CryptoPanic.")
            return await fetch_cryptopanic_news(session)

        # Reddit
        elif platform == "reddit":
            subreddit = handle.lstrip("r/")
            return await fetch_reddit_posts(subreddit, session)

        # Instagram / TikTok / Facebook — check if it's an RSS URL
        elif handle.startswith("http") and ("rss" in handle or ".xml" in handle):
            return await fetch_rss_feed(handle, session)

        # Crypto platforms → use CoinGecko + CryptoPanic mix
        else:
            news = await fetch_coingecko_news(session)
            panic = await fetch_cryptopanic_news(session)
            combined = news + panic
            random.shuffle(combined)
            return combined[:5]


async def execute_mirror_cycle(bot_instance=None):
    """
    Fetches REAL content from all registered targets, rewrites with AI/rules,
    and posts to the configured Telegram destination.
    """
    targets = marketing_db.get_targets()
    settings = marketing_db.get_settings()
    profiles = marketing_db.get_profiles()

    if not settings.get("auto_mirror_enabled", True):
        return

    mirrored_count = 0
    for target in targets:
        if not target.get("active", True):
            continue
        try:
            posts = await fetch_target_posts(target)
            if not posts:
                logger.warning(f"No posts fetched for {target['handle']}")
                continue

            latest_post = posts[0]
            if str(latest_post["id"]) == str(target.get("last_post_id", "")):
                continue  # No new content

            original_text = latest_post["text"]
            style = settings.get("rewrite_style", "bullish_crypto_enthusiast")
            source = latest_post.get("source", target["platform"])

            logger.info(f"🔄 [REAL-MIRROR] New content from {source}: {original_text[:60]}...")
            rewritten_text = await ai_rewrite(original_text, style)

            destination = target.get("destination", "TG_GROUP")
            success = False

            if destination == "TG_GROUP":
                active_profile = next((p for p in profiles if p.get("active", True)), None)
                import config
                bot_token = config.TELEGRAM_BOT_TOKEN
                chat_id = config.TELEGRAM_CHAT_ID
                active_bot = bot_instance

                if active_profile and active_profile.get("tg_bot_token") and active_profile.get("tg_chat_id"):
                    bot_token = active_profile["tg_bot_token"]
                    chat_id = active_profile["tg_chat_id"]
                    from telegram import Bot
                    active_bot = Bot(token=bot_token)

                if active_bot and chat_id:
                    source_line = f"📡 <b>Source:</b> <i>{source}</i>\n\n"
                    msg = f"📢 <b>Mirrored Content</b>\n{source_line}{rewritten_text}"
                    if latest_post.get("source_url"):
                        msg += f"\n\n🔗 <a href='{latest_post['source_url']}'>Original</a>"
                    await active_bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML",
                                                   disable_web_page_preview=True)
                    success = True
                    logger.info(f"✅ [MIRROR-POST] Posted real mirrored content to Telegram group")
            else:
                logger.info(f"📤 [MIRROR] Content ready for {target['platform']} — add API credentials to enable posting")
                success = True

            if success:
                target["last_post_id"] = str(latest_post["id"])
                target["last_checked"] = time.time()
                target["posts_mirrored"] = target.get("posts_mirrored", 0) + 1
                marketing_db.save_db()
                marketing_db.increment_analytics(impressions=1)
                mirrored_count += 1

        except Exception as e:
            logger.error(f"Mirror error for {target['handle']}: {e}")
        await asyncio.sleep(2)

    return mirrored_count


async def start_mirror_loop(bot_instance=None, interval=300):
    logger.info("Mirroring Engine background task started.")
    while True:
        try:
            count = await execute_mirror_cycle(bot_instance)
            if count:
                logger.info(f"🔄 Mirror cycle complete: {count} real posts mirrored.")
        except Exception as e:
            logger.error(f"Mirror loop error: {e}")
        await asyncio.sleep(interval)
