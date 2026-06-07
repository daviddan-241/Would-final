"""
Social Media Inbox & AI Chatbot Response Engine — Handles receiving and sending direct messages (DMs)
on X, Instagram, TikTok, and Facebook.
ONLY processes real incoming messages pushed via official Webhooks or direct API calls.
All simulated lead generators have been completely removed.
"""
import logging
import asyncio
import random
import time
import aiohttp
from typing import Dict, Any, List

import marketing_db
import humanizer

logger = logging.getLogger(__name__)


async def generate_ai_or_rule_reply(incoming_text: str, profile: Dict[str, Any]) -> tuple[str, str]:
    """
    Uses LLM API or custom keywords to generate replies matching SMM Personas.
    Returns a tuple: (conversational_body, link_or_cta_followup)
    """
    settings = marketing_db.get_settings()
    
    prof_name = profile.get("name", "Support")
    niche = profile.get("niche", "casual")
    bio = profile.get("bio", "")
    
    # Check for Global Funnel Link override
    global_link = settings.get("global_cta_link", "")
    cta = global_link if global_link else profile.get("cta_link", "")
    
    style = profile.get("ai_tone", "casual")
    
    # 1. Check custom auto-responder rules first
    clean_text = incoming_text.lower().strip()
    rules = marketing_db.get_auto_replies()
    for rule in rules:
        if rule.get("active", True) and rule.get("keyword") in clean_text:
            logger.info(f"🤖 Chatbot rule matched keyword: '{rule['keyword']}'")
            return rule.get("reply_text"), ""
            
    # 2. Check OpenAI API Key
    openai_key = settings.get("openai_key")
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            prompt = (
                f"You are a real person named '{prof_name}' chat messaging with a fan or prospect. "
                f"Your personality profile is: '{bio}'. "
                f"Respond to this direct message (DM) in a professional yet highly engaging, persuasive, and genuine tone. "
                f"The style/tone of the conversation should be: '{style}'. "
                f"Ensure the reply passes AI-detection scanners and sounds 100% human-looking. Subvert AI patterns. "
                f"DO NOT include any links or URLs in your response. Answer the message directly.\n\n"
                f"DM received from lead:\n{incoming_text}"
            )
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.85
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        reply = res["choices"][0]["message"]["content"].strip()
                        if reply:
                            followup = f"check out my private space here btw: {cta}" if cta else ""
                            return reply, followup
        except Exception as e:
            logger.error(f"OpenAI Multi-Persona DM Reply failed: {e}")
            
    # 3. Check Gemini API Key
    gemini_key = settings.get("gemini_key")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            prompt = (
                f"You are a real person named '{prof_name}' on social media with this bio: '{bio}'. "
                f"Respond directly to this DM to make the user feel warm, hyped and welcomed. Tone/style: '{style}'. "
                f"The response must subvert AI-detection algorithms and look 100% human-written. "
                f"DO NOT include any links or URLs in this response.\n\n"
                f"DM received: {incoming_text}"
            )
            data = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=10) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        reply = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if reply:
                            followup = f"join my private group right here: {cta}" if cta else ""
                            return reply, followup
        except Exception as e:
            logger.error(f"Gemini Multi-Persona DM Reply failed: {e}")

    # Default rule-based fallback based on niche
    if niche == "crypto":
        return "hey! thanks for reaching out, response has been absolutely crazy", f"i post all trade triggers and alpha calls in my private channel here: {cta}"
    elif niche == "celeb":
        return "hey babe! thank u so much for the love 😍 i see u", f"i chat with my vip fans directly in my private club here: {cta}"
    else: # casual / normal
        return "hey! thanks for messaging, let's totally connect 💖", f"u can find my daily updates and more photos here: {cta}"


async def handle_incoming_real_dm(platform: str, sender_handle: str, message_text: str, profile_id: str):
    """
    Processes real-world direct messages pushed via Webhooks or active API sessions.
    Runs conversational humanization, typing delays, and sends responses back.
    """
    profiles = marketing_db.get_profiles()
    profile = next((p for p in profiles if p["id"] == profile_id), None)
    if not profile:
        return

    # Add real message to database
    conv, new_msg = marketing_db.add_incoming_message(
        platform=platform,
        sender_handle=sender_handle,
        text=message_text,
        profile_id=profile_id
    )

    # Generate response content
    raw_body, raw_followup = await generate_ai_or_rule_reply(message_text, profile)
    
    # Humanize & Apply AI Bypass Filter
    human_body = humanizer.humanize_text(raw_body)
    human_followup = humanizer.humanize_text(raw_followup) if raw_followup else ""
    
    # Calculate Human typing delay for first message
    delay_body = humanizer.calculate_typing_delay(human_body)
    logger.info(f"⏳ [TYPING] Real Persona '{profile['name']}' is typing body reply... Will take {delay_body:.1f}s.")
    await asyncio.sleep(delay_body)
    
    # Record conversational message body first
    marketing_db.add_outgoing_reply(conv["id"], human_body)
    logger.info(f"📤 [DM-REPLY] Outbound body sent: '{human_body}'")
    
    # Wait another short delay before sending link
    if human_followup:
        delay_link = random.uniform(3.0, 6.0)
        logger.info(f"⏳ [TYPING] Real Persona '{profile['name']}' is typing the follow-up CTA link... Will take {delay_link:.1f}s.")
        await asyncio.sleep(delay_link)
        
        # Record CTA Link message second
        marketing_db.add_outgoing_reply(conv["id"], human_followup)
        logger.info(f"📤 [DM-REPLY] Outbound link follow-up sent: '{human_followup}'")


async def start_inbox_simulator_loop(check_interval=60):
    """
    Keeps background tasks safe. 
    Organic simulated leads have been removed completely to guarantee only real chats.
    """
    logger.info("SMM Lead Direct Message Receiver Service online.")
    while True:
        await asyncio.sleep(check_interval)
