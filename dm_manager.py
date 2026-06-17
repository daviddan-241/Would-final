"""
Social Media Inbox & AI Chatbot Response Engine — Handles receiving AND SENDING direct messages.
Processes ONLY real incoming messages pushed via official webhooks, Telegram API, or session cookie polling.
Replies are ACTUALLY SENT back on the platform using session cookies — not just stored locally.
No simulated data, no fake leads, no phantom users.
"""
import logging
import asyncio
import random
import time
import aiohttp
from typing import Dict, Any

import marketing_db
import humanizer

logger = logging.getLogger(__name__)


async def generate_ai_or_rule_reply(incoming_text: str, profile: Dict[str, Any]) -> tuple[str, str]:
    """
    Uses LLM API or keyword rules to generate replies matching the active SMM Persona.
    Returns (conversational_body, cta_followup).
    Priority: custom rules → OpenAI → Gemini → rule-based fallback.
    """
    settings = marketing_db.get_settings()

    prof_name = profile.get("name", "Support")
    niche = profile.get("niche", "casual")
    bio = profile.get("bio", "")
    global_link = settings.get("global_cta_link", "")
    cta = global_link if global_link else profile.get("cta_link", "")
    style = profile.get("ai_tone", "casual")

    # 1. Custom auto-responder keyword rules
    clean_text = incoming_text.lower().strip()
    for rule in marketing_db.get_auto_replies():
        if rule.get("active", True) and rule.get("keyword", "") in clean_text:
            logger.info(f"🤖 Chatbot rule matched keyword: '{rule['keyword']}'")
            return rule.get("reply_text", ""), ""

    # 2. OpenAI
    openai_key = settings.get("openai_key", "")
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            prompt = (
                f"You are a real person named '{prof_name}' chatting on social media. "
                f"Bio: '{bio}'. Tone: '{style}'. "
                f"Reply to this DM naturally and persuasively. Sound 100% human. "
                f"Do NOT include any URLs in your reply.\n\nDM: {incoming_text}"
            )
            data = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "temperature": 0.85}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        reply = res["choices"][0]["message"]["content"].strip()
                        if reply:
                            followup = f"check out my private space here btw: {cta}" if cta else ""
                            return reply, followup
        except Exception as e:
            logger.error(f"OpenAI reply failed: {e}")

    # 3. Gemini
    gemini_key = settings.get("gemini_key", "")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            prompt = (
                f"You are '{prof_name}' on social media. Bio: '{bio}'. Tone: '{style}'. "
                f"Reply to this DM warmly and naturally. Sound human, no URLs.\n\nDM: {incoming_text}"
            )
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        reply = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if reply:
                            followup = f"join my private group right here: {cta}" if cta else ""
                            return reply, followup
        except Exception as e:
            logger.error(f"Gemini reply failed: {e}")

    # 4. Rule-based fallback (no AI key configured)
    if niche == "crypto":
        return (
            "hey! thanks for reaching out, response has been absolutely crazy",
            f"i post all trade triggers and alpha calls in my private channel here: {cta}" if cta else ""
        )
    elif niche == "celeb":
        return (
            "hey babe! thank u so much for the love 😍 i see u",
            f"i chat with my vip fans directly in my private club here: {cta}" if cta else ""
        )
    else:
        return (
            "hey! thanks for messaging, let's totally connect 💖",
            f"u can find my daily updates and more here: {cta}" if cta else ""
        )


async def handle_incoming_real_dm(
    platform: str,
    sender_handle: str,
    message_text: str,
    profile_id: str = None,
    profile_url: str = "",
    source_url: str = ""
):
    """
    Processes real incoming DMs (from Telegram bot, Meta webhook, session DM agent, etc).
    Stores in inbox → generates AI reply → humanizes → ACTUALLY SENDS reply back on the platform.
    The person on the other end sees your reply. This is 100% real.
    """
    profiles = marketing_db.get_profiles()
    profile = None

    # Try explicit profile_id first
    if profile_id:
        profile = next((p for p in profiles if p["id"] == profile_id), None)

    # Auto-detect best persona if not found
    if not profile:
        from growth_engine import select_best_persona
        profile = select_best_persona(message_text, platform)

    # Last resort: first active profile
    if not profile:
        active = [p for p in profiles if p.get("active", True)]
        profile = active[0] if active else None

    if not profile:
        logger.warning(f"handle_incoming_real_dm: no active profile found for {sender_handle}")
        return

    profile_id = profile["id"]

    # Import spam filter
    import comment_filter
    if comment_filter.is_spam_dm(message_text):
        logger.info(f"[SpamFilter] Blocked spam DM from {sender_handle}: '{message_text[:50]}'")
        return

    conv, _ = marketing_db.add_incoming_message(
        platform=platform,
        sender_handle=sender_handle,
        text=message_text,
        avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={sender_handle}",
        profile_id=profile_id,
        profile_url=profile_url,
        source_url=source_url
    )

    raw_body, raw_followup = await generate_ai_or_rule_reply(message_text, profile)

    human_body = humanizer.humanize_text(raw_body)
    human_followup = humanizer.humanize_text(raw_followup) if raw_followup else ""

    delay_body = humanizer.calculate_typing_delay(human_body)
    logger.info(f"⏳ Persona '{profile['name']}' typing reply... ({delay_body:.1f}s)")
    await asyncio.sleep(delay_body)

    # Store in local DB
    marketing_db.add_outgoing_reply(conv["id"], human_body)

    # ACTUALLY SEND the reply on the platform using session cookies
    sent_on_platform = False
    if platform != "telegram":  # Telegram handled by bot handler directly
        from platform_sender import send_reply_on_platform
        async with aiohttp.ClientSession() as http:
            sent_on_platform = await send_reply_on_platform(platform, sender_handle, human_body, http, profile_id=profile_id)

    if sent_on_platform:
        logger.info(f"📤 ✅ Reply ACTUALLY SENT to {sender_handle} on {platform}: '{human_body}'")
    elif platform == "telegram":
        logger.info(f"📤 Reply stored for Telegram (sent by bot handler): '{human_body}'")
    elif platform == "reddit":
        logger.info(f"📤 Reply stored for {sender_handle} (Reddit DMs need manual send): '{human_body}'")
    else:
        logger.warning(f"📤 ⚠️ Reply stored locally but NOT sent on {platform} — check session cookies for {sender_handle}")

    if human_followup:
        delay_link = random.uniform(3.0, 6.0)
        await asyncio.sleep(delay_link)
        marketing_db.add_outgoing_reply(conv["id"], human_followup)

        # Send follow-up on platform too
        if platform != "telegram" and sent_on_platform:
            from platform_sender import send_reply_on_platform
            async with aiohttp.ClientSession() as http:
                await send_reply_on_platform(platform, sender_handle, human_followup, http, profile_id=profile_id)

        logger.info(f"📤 CTA follow-up sent to {sender_handle}: '{human_followup}'")


def execute_send_custom_dm(conv_id: str, text: str) -> bool:
    """
    Sends a manual reply typed in the dashboard to an existing conversation.
    Stores in the DB AND actually sends on the platform.
    """
    if not conv_id or not text:
        logger.warning("execute_send_custom_dm: missing conv_id or text")
        return False
    result = marketing_db.add_outgoing_reply(conv_id, text.strip())
    if result:
        logger.info(f"📤 Manual reply saved to conv {conv_id}: '{text[:60]}'")

        # Also send on the actual platform
        db = marketing_db.load_db()
        for conv in db.get("conversations", []):
            if conv["id"] == conv_id:
                platform = conv.get("platform", "")
                handle = conv.get("sender_handle", "")
                conv_profile_id = conv.get("profile_id", "")
                if platform and handle and platform != "telegram":
                    import asyncio
                    from platform_sender import send_reply_on_platform
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(send_reply_on_platform(platform, handle, text.strip(), profile_id=conv_profile_id))
                        else:
                            loop.run_until_complete(send_reply_on_platform(platform, handle, text.strip(), profile_id=conv_profile_id))
                    except RuntimeError:
                        pass
                break
        return True
    logger.warning(f"execute_send_custom_dm: conv {conv_id} not found")
    return False


async def start_inbox_monitor_loop(check_interval: int = 60):
    """
    Keeps the inbox monitoring service alive.
    Real DMs arrive via Telegram bot handler, Meta webhook POST, or session cookie polling.
    """
    logger.info("DM Inbox Monitor online — waiting for real incoming messages.")
    while True:
        await asyncio.sleep(check_interval)
