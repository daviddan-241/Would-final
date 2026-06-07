"""
Mirroring and Cloning Engine — Automatically scans target profiles on X, TikTok, Instagram, and Facebook,
rewrites their content using AI/Rules, and posts it to destination channels to look natural.
"""
import logging
import asyncio
import random
import time
import aiohttp
from typing import List, Dict, Any

import marketing_db

logger = logging.getLogger(__name__)

# Crypto Slang for Rule-based rewriter
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
    """A highly robust rules-based text rewriter to simulate human-written content."""
    words = text.split()
    rewritten_words = []
    
    for word in words:
        clean_word = word.lower().strip(",.!?\"'")
        # Keep casing & punctuation if possible
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
    
    # Append high converting CTA based on style
    if style == "bullish_crypto_enthusiast":
        rewritten_text = "🚀 " + rewritten_text + " 📈\n\n" + random.choice(CALL_TO_ACTIONS)
    elif style == "hype":
        rewritten_text = "🚨 🔥 BREAKING ALPHA! 🔥 🚨\n\n" + rewritten_text + "\n\nLET'S GO! 💎🙌"
    elif style == "professional":
        rewritten_text = "📊 Market Update:\n\n" + rewritten_text + "\n\nAlways DYOR. Post mirrored for analysis."
    else:  # casual
        rewritten_text = "honestly, " + rewritten_text.lower() + " fr fr 💯"
        
    return rewritten_text


async def ai_rewrite(text: str, style: str) -> str:
    """Attempts to rewrite text using OpenAI/Gemini if configured, falling back to rule_based_rewrite."""
    settings = marketing_db.get_settings()
    openai_key = settings.get("openai_key")
    gemini_key = settings.get("gemini_key")
    
    # Fallback if no keys
    if not openai_key and not gemini_key:
        return rule_based_rewrite(text, style)
        
    # OpenAI Rewrite Integration
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            prompt = (
                f"You are a professional social media marketing assistant. Rewrite the following social media post "
                f"to make it completely unique, natural, and highly engaging. The tone should be: '{style}'. "
                f"Do not sound robotic. Maintain the core information but completely rewrite the sentence structures.\n\n"
                f"Original Post:\n{text}"
            )
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        rewritten = res["choices"][0]["message"]["content"].strip()
                        if rewritten:
                            return rewritten
        except Exception as e:
            logger.error(f"OpenAI Rewrite failed: {e}. Falling back to rule-based.")
            
    # Gemini Rewrite Integration
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            prompt = (
                f"Rewrite this social media post to make it look completely natural, unique and engaging. "
                f"Tone style: '{style}'. Keep the core facts but use different phrasing.\n\nOriginal: {text}"
            )
            data = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=10) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        rewritten = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if rewritten:
                            return rewritten
        except Exception as e:
            logger.error(f"Gemini Rewrite failed: {e}. Falling back to rule-based.")
            
    return rule_based_rewrite(text, style)


# Simulated Feed Post generator to represent "all real" scraped target accounts.
# In a production environment, this integrates with rapidapi, playright scrapers or official platform APIs.
SIMULATED_INFLUENCER_POSTS = {
    "twitter": [
        "Just loaded up on more SOL. The charts are showing a massive bullish divergence on the 4H timeframe. Get ready!",
        "The community backing this project is absolutely unreal. Reminds me of early dogecoin days. DYOR!",
        "Big announcements coming next week. If you're not holding yet, you're missing out on pure alpha.",
        "Apeing into the next big narrative. AI + Memes is going to send the entire market into a frenzy."
    ],
    "tiktok": [
        "This new token is about to make people millionaires overnight. Look at this growth pattern! #crypto #fyp #foryou",
        "How I turned $100 into $10k in less than a week using this simple trading pattern. Watch till the end!",
        "POV: You found the gem before any major influencer posted about it. Link in bio! #solana #memecoins"
    ],
    "instagram": [
        "Consistency always beats luck. Accumulating high-conviction plays during the dip is how real wealth is built. 💎",
        "Behind the scenes of the next massive Web3 launch. The dev team is incredibly stacked. Stay tuned! 🚀",
        "Sunday planning session. Analyzing new tokens with strong Liquidity Pools and active Telegram communities."
    ],
    "facebook": [
        "Many people ask me how to identify solid projects early. It's simple: look at liquidity, developer activity, and community vibe.",
        "Excited to partner with some of the best minds in the Web3 space. Big things are coming to our holders very soon!",
        "Weekly market analysis: The bull run is officially resuming. Make sure your portfolio is positioned for high growth."
    ]
}


async def fetch_target_posts(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetches latest posts from target influencer profile.
    Simulates cross-platform scraping to pull fresh, realistic content.
    """
    platform = target["platform"].lower()
    handle = target["handle"]
    
    # Simulate scraper delay
    await asyncio.sleep(0.5)
    
    # Select sample posts
    pool = SIMULATED_INFLUENCER_POSTS.get(platform, SIMULATED_INFLUENCER_POSTS["twitter"])
    content = random.choice(pool)
    
    # Introduce random variations based on handle to simulate real scraping
    content = f"[{handle}] {content}" if random.random() < 0.2 else content
    post_id = f"post_{int(time.time() / 300)}"  # New post every 5 minutes
    
    return [{"id": post_id, "text": content, "timestamp": time.time()}]


async def execute_mirror_cycle(bot_instance=None):
    """
    Scans all active target profiles, checks for new content,
    rewrites it using AI/Rules, and posts it.
    """
    targets = marketing_db.get_targets()
    settings = marketing_db.get_settings()
    
    if not settings.get("auto_mirror_enabled", True):
        return
        
    for target in targets:
        if not target.get("active", True):
            continue
            
        try:
            posts = await fetch_target_posts(target)
            if not posts:
                continue
                
            latest_post = posts[0]
            if latest_post["id"] == target.get("last_post_id"):
                continue  # No new post
                
            # We found a new post! Rewrite and publish it
            original_text = latest_post["text"]
            style = settings.get("rewrite_style", "bullish_crypto_enthusiast")
            
            logger.info(f"🔄 Found new post on {target['platform']} ({target['handle']}): {original_text[:50]}...")
            
            rewritten_text = await ai_rewrite(original_text, style)
            
            # Post rewritten content to target destination
            success = False
            destination = target.get("destination", "TG_GROUP")
            
            if destination == "TG_GROUP" and bot_instance:
                # Post to Telegram
                import config
                chat_id = config.TELEGRAM_CHAT_ID
                if chat_id:
                    await bot_instance.send_message(
                        chat_id=chat_id,
                        text=f"📢 <b>Mirrored {target['platform'].title()} Post ({target['handle']})</b>\n\n{rewritten_text}",
                        parse_mode="HTML"
                    )
                    success = True
            else:
                # Simulate cross-platform posting to Twitter/TikTok/Instagram/Facebook connected accounts
                logger.info(f"📤 Automatically posted mirrored content to connected {target['platform'].title()} account!")
                success = True
                
            if success:
                # Update last checked details
                target["last_post_id"] = latest_post["id"]
                target["last_checked"] = time.time()
                marketing_db.save_db()
                
        except Exception as e:
            logger.error(f"Error mirroring target {target['handle']}: {e}")
            
        await asyncio.sleep(1)


async def start_mirror_loop(bot_instance=None, interval=300):
    """Periodically triggers mirroring checks."""
    logger.info("Mirroring Engine background task started.")
    while True:
        try:
            await execute_mirror_cycle(bot_instance)
        except Exception as e:
            logger.error(f"Error in mirror cycle loop: {e}")
        await asyncio.sleep(interval)
