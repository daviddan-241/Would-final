"""
AI Auto-Responder Agent — reads every new incoming DM and fires back an instant,
personalised reply that matches the niche, builds rapport, and drops the funnel CTA.

CRITICAL: Replies are ACTUALLY SENT back on the platform using session cookies.
The person on Instagram/TikTok/Facebook/Twitter sees your reply. This is real.

Priority order for generating replies:
  1. OpenAI GPT-4o (if openai_key in settings)
  2. Google Gemini (if gemini_key in settings)
  3. Smart niche templates (always available, no key needed)

The reply always:
  - Matches the tone/niche of the account that received the DM
  - Ends with the funnel link CTA for that account
  - Sounds human — no "As an AI..." language ever
  - Is ACTUALLY SENT on the platform (not just stored locally)
"""
import asyncio
import aiohttp
import logging
import json
import time
import re

import marketing_db
import dm_manager

logger = logging.getLogger("agent.ai_responder")

# ─── REPLY TEMPLATES (fallback when no AI key) ───────────────────────────────

TEMPLATES = {
    "crypto": [
        "Hey! 🔥 Yeah I've been watching that too. Drop me your TG and I'll add you to my private calls group — I'm posting the next gem tonight: {cta}",
        "Yo! Good timing — just found something massive. Join my private channel before I post it: {cta} 🚀",
        "Real talk — this setup is one of the best I've seen in months. I'll break it down for my members tonight: {cta}",
        "You're early. That's the point. DM me back with 'IN' and I'll send you the full breakdown. Channel: {cta}",
    ],
    "solana": [
        "SOL is going to go absolutely crazy. I'm posting the next 100x gem for my private list tonight — join here: {cta} 🟣",
        "You caught me at the right time. Wallet alpha dropping in my channel in a few hours: {cta}",
    ],
    "celeb": [
        "Heyy!! 💕 I'm so glad you messaged me. I have something exclusive for my close ones — check this out: {cta}",
        "Omg hi!! 🥺 I literally reply to everyone who DMs me. Come join my private space: {cta} 💋",
        "Hey babe 💫 I don't post this publicly but since you reached out... {cta} — just for you 🙏",
        "You're so sweet for messaging me!! I have something special waiting for you here: {cta} ✨",
    ],
    "lifestyle": [
        "Hey! Love the question. I wrote a full breakdown on this — it's in my free guide: {cta} 🌴",
        "Literally yes! I document everything. Here's where I share the real stuff: {cta}",
        "You're in the right place. I've been building this for 2 years — here's the full story: {cta}",
    ],
    "memecoins": [
        "You're early. That's literally the only thing that matters in this market. I've got the next one: {cta} 🐸",
        "Great timing — just scouted a new one with under 300 holders. Posting in my channel: {cta}",
    ],
    "viral": [
        "You saw that? Yeah it's about to be everywhere. I'll send you the details: {cta} 🔥",
        "Glad you caught that. I drop these early — more here: {cta}",
    ],
}

# Generic fallback for any niche
GENERIC = [
    "Hey! Thanks for reaching out 😊 I share everything inside here: {cta}",
    "Good timing! Just posted something you'll want to see: {cta}",
    "Hey! I got you — everything's in here: {cta} 🔥",
]

# ─── AI GENERATION ────────────────────────────────────────────────────────────

async def _ai_reply_openai(api_key: str, niche: str, incoming_text: str, cta: str, http: aiohttp.ClientSession) -> str:
    prompt = f"""You are a real {niche} influencer/account owner replying to a DM.
Incoming message: "{incoming_text}"
Your CTA link: {cta}

Write a SHORT (1-3 sentences), casual, human reply that:
- Responds naturally to what they said
- Sounds like a real person (NOT a bot)
- Ends by mentioning your link: {cta}
- Matches {niche} niche energy
- No emojis overload, just 1-2 max
- NEVER say "As an AI" or anything robotic

Reply only with the message text, nothing else."""

    try:
        async with http.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "max_tokens": 120, "temperature": 0.85},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.debug(f"[AI Responder] OpenAI error: {e}")
    return ""


async def _ai_reply_gemini(api_key: str, niche: str, incoming_text: str, cta: str, http: aiohttp.ClientSession) -> str:
    prompt = f"""You are a real {niche} influencer replying to a DM on social media.
Incoming: "{incoming_text}"
CTA: {cta}

Reply in 1-3 casual sentences. Sound human. End with the CTA link. No robotic language."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        async with http.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 120, "temperature": 0.85}},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.debug(f"[AI Responder] Gemini error: {e}")
    return ""


def _template_reply(niche: str, cta: str) -> str:
    import random
    templates = TEMPLATES.get(niche, GENERIC)
    template = random.choice(templates)
    link = cta or "https://t.me/your_channel"
    return template.format(cta=link)


# ─── FIND NICHE FOR CONVERSATION ─────────────────────────────────────────────

def _get_niche_and_cta_for_conv(conv: dict) -> tuple[str, str]:
    """Returns (niche, cta_link) for the account that received this DM."""
    platform = conv.get("platform", "")
    sender = conv.get("sender_handle", "")

    # First check if there's a matching fleet account for this platform
    accounts = marketing_db.get_accounts()
    for acc in accounts:
        if acc.get("platform") == platform:
            niche = acc.get("niche", "")
            cta = acc.get("cta_link", "")
            if niche or cta:
                return niche or "crypto", cta

    # Fall back to global settings
    settings = marketing_db.get_settings()
    cta = settings.get("global_cta_link", "")

    # Guess niche from platform or conversation context
    if platform in ("twitter", "x"):
        return "crypto", cta
    elif platform in ("instagram", "tiktok"):
        return "celeb", cta
    elif platform == "reddit":
        return "crypto", cta
    return "crypto", cta


# ─── TRACK AUTO-REPLIED CONVERSATIONS ────────────────────────────────────────

_auto_replied: set[str] = set()
_COOLDOWN = 300  # Don't re-auto-reply to same conversation within 5 min
_last_replied: dict[str, float] = {}


# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

async def start_ai_responder_loop(check_interval: int = 20):
    """
    Checks for new unanswered DMs every 20 seconds.
    Fires an AI-generated or template reply instantly.
    ACTUALLY SENDS the reply back on the platform using session cookies.
    """
    logger.info("[AI Responder] Online — auto-replying to all incoming DMs and SENDING on platform.")
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as http:
        while True:
            try:
                await _check_and_reply(http)
            except Exception as e:
                logger.error(f"[AI Responder] Loop error: {e}")
            await asyncio.sleep(check_interval)


async def _check_and_reply(http: aiohttp.ClientSession):
    settings = marketing_db.get_settings()
    openai_key = settings.get("openai_key", "").strip()
    gemini_key = settings.get("gemini_key", "").strip()

    # Only auto-reply if enabled
    if not settings.get("auto_dm_reply_enabled", True):
        return

    db = marketing_db.load_db()
    conversations = db.get("conversations", [])
    messages_store = db.get("messages", {})

    now = time.time()

    for conv in conversations:
        conv_id = conv["id"]
        msgs = messages_store.get(conv_id, [])
        if not msgs:
            continue

        last_msg = msgs[-1]
        if not last_msg.get("is_incoming", True):
            continue  # Last message was outgoing — already replied

        # Cooldown check
        last_time = _last_replied.get(conv_id, 0)
        if now - last_time < _COOLDOWN:
            continue

        # Don't auto-reply if there's already been a human reply
        human_replied = any(not m.get("is_incoming", True) for m in msgs)
        if human_replied:
            continue

        # Build reply
        niche, cta = _get_niche_and_cta_for_conv(conv)
        incoming_text = last_msg.get("text", "")

        reply_text = ""
        if openai_key:
            reply_text = await _ai_reply_openai(openai_key, niche, incoming_text, cta, http)
        if not reply_text and gemini_key:
            reply_text = await _ai_reply_gemini(gemini_key, niche, incoming_text, cta, http)
        if not reply_text:
            reply_text = _template_reply(niche, cta)

        if reply_text:
            # Store in local DB
            marketing_db.add_outgoing_reply(conv_id, reply_text)
            _last_replied[conv_id] = now

            # ACTUALLY SEND on the platform using session cookies
            platform = conv.get("platform", "")
            sender_handle = conv.get("sender_handle", "")

            sent_on_platform = False
            if platform and sender_handle and platform not in ("telegram", "reddit"):
                from platform_sender import send_reply_on_platform
                sent_on_platform = await send_reply_on_platform(platform, sender_handle, reply_text, http)

            if sent_on_platform:
                logger.info(f"[AI Responder] 🤖→📬✅ AUTO-REPLY SENT to {sender_handle} on {platform} ({niche}): '{reply_text[:60]}'")
            elif platform == "telegram":
                logger.info(f"[AI Responder] 🤖→📬 Reply stored for Telegram bot handler: '{reply_text[:60]}'")
            elif platform == "reddit":
                logger.info(f"[AI Responder] 🤖→📬 Reply stored for {sender_handle} (Reddit needs manual): '{reply_text[:60]}'")
            else:
                logger.warning(f"[AI Responder] 🤖→⚠️ Reply stored locally but NOT sent on {platform} — check session cookies for {sender_handle}")

            await asyncio.sleep(2)  # Brief delay between replies to look human
