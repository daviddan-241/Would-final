"""
Social Media Inbox & AI Chatbot Response Engine — Handles receiving and sending direct messages (DMs)
on X, Instagram, TikTok, and Facebook, with AI-driven natural conversational replies matching individual SMM Personas.
Delivers conversational text first, followed by a separate link after a natural keyboard delay.
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

# Simulated lists of leads based on niche targets with country details for sandbox representation
NICHE_LEADS = {
    "crypto": [
        {"username": "sol_whale_99", "country": "United States", "flag": "🇺🇸"},
        {"username": "crypto_kid_eth", "country": "United Kingdom", "flag": "🇬🇧"},
        {"username": "nft_collector_max", "country": "Germany", "flag": "🇩🇪"},
        {"username": "gem_hunter_v", "country": "Singapore", "flag": "🇸🇬"},
        {"username": "defi_explorer", "country": "Canada", "flag": "🇨🇦"}
    ],
    "celeb": [
        {"username": "fan_boy_lucas", "country": "Brazil", "flag": "🇧🇷"},
        {"username": "jack_love_reel", "country": "Australia", "flag": "🇦🇺"},
        {"username": "emma_star_x", "country": "France", "flag": "🇫🇷"},
        {"username": "official_tom", "country": "United States", "flag": "🇺🇸"},
        {"username": "kate_vlog_world", "country": "Japan", "flag": "🇯🇵"}
    ],
    "casual": [
        {"username": "lucas_crypto", "country": "Spain", "flag": "🇪🇸"},
        {"username": "hannah_brooks", "country": "Canada", "flag": "🇨🇦"},
        {"username": "sam_traveler", "country": "Australia", "flag": "🇦🇺"},
        {"username": "sophia_life", "country": "Italy", "flag": "🇮🇹"},
        {"username": "alex_adventures", "country": "United Kingdom", "flag": "🇬🇧"}
    ]
}

NICHE_MESSAGES = {
    "crypto": [
        "Hey! I saw your calls. Is the private channel free to join?",
        "Bro, do you have any new SOL gem suggestions? Missed the last pump.",
        "What exchange do you use for early token listing buying?",
        "Is your team launching a coin soon? Wanting to ape in."
    ],
    "celeb": [
        "Oh my god! Is this really you? I love your videos so much! 😍",
        "Hey Sophie, how do I join your private club? Want to see the exclusive content.",
        "Please reply to me! I've been a fan of yours for a year now.",
        "Collab on a video sometime? I'm also a content creator in Miami."
    ],
    "casual": [
        "Hey Sarah! Your profile look so cool, let's connect!",
        "Saw your post about Web3, are you attending any conferences soon?",
        "Where was that nice cafe photo taken? Looks beautiful.",
        "Just wanted to say hi! Have a great Sunday."
    ]
}


async def generate_ai_or_rule_reply(incoming_text: str, profile: Dict[str, Any]) -> tuple[str, str]:
    """
    Uses LLM API or custom keywords to generate replies matching SMM Personas.
    Returns a tuple: (conversational_body, link_or_cta_followup)
    This strictly separates the message body from the redirect link.
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


async def simulate_incoming_direct_message():
    """
    Simulates receiving messages from real external accounts on Twitter, Instagram, TikTok, etc.
    This creates an extremely active, alive unified inbox inside the control dashboard.
    """
    settings = marketing_db.get_settings()
    if not settings.get("auto_dm_reply_enabled", True):
        return

    profiles = marketing_db.get_profiles()
    active_profiles = [p for p in profiles if p.get("active", True)]
    if not active_profiles:
        return

    # 1. Randomly pick an active profile/persona
    profile = random.choice(active_profiles)
    niche = profile.get("niche", "casual")
    
    # 2. Randomly pick platform and targeted user based on niche
    platform = random.choice(["twitter", "instagram", "tiktok", "facebook"])
    
    leads_pool = NICHE_LEADS.get(niche, NICHE_LEADS["casual"])
    msgs_pool = NICHE_MESSAGES.get(niche, NICHE_MESSAGES["casual"])
    
    lead_info = random.choice(leads_pool)
    username = lead_info["username"]
    country_info = f"{lead_info['flag']} {lead_info['country']}"
    
    message_text = random.choice(msgs_pool)
    
    logger.info(f"📥 [DM-INCOMING] Received DM from @{username} ({country_info}) on {platform.title()} targeting Persona '{profile['name']}': '{message_text}'")
    
    # 3. Add message to database with country flag metadata embedded into the handle
    display_handle = f"@{username} ({country_info})"
    conv, new_msg = marketing_db.add_incoming_message(
        platform=platform,
        sender_handle=display_handle,
        text=message_text,
        profile_id=profile["id"]
    )
    
    # 4. Generate response content
    raw_body, raw_followup = await generate_ai_or_rule_reply(message_text, profile)
    
    # --- Humanize & Apply AI Bypass Filter ---
    human_body = humanizer.humanize_text(raw_body)
    human_followup = humanizer.humanize_text(raw_followup) if raw_followup else ""
    
    # --- Calculate Human typing delay for first message ---
    delay_body = humanizer.calculate_typing_delay(human_body)
    logger.info(f"⏳ [TYPING - MESSAGE] '{profile['name']}' is typing body reply to @{username}... Will take {delay_body:.1f}s.")
    await asyncio.sleep(delay_body)
    
    # Record conversational message body first
    marketing_db.add_outgoing_reply(conv["id"], human_body)
    logger.info(f"📤 [DM-AUTO-REPLY] Outbound body sent: '{human_body}'")
    
    # --- Wait another short delay before sending link ---
    if human_followup:
        delay_link = random.uniform(3.0, 6.0)
        logger.info(f"⏳ [TYPING - LINK] '{profile['name']}' is typing the follow-up CTA link... Will take {delay_link:.1f}s.")
        await asyncio.sleep(delay_link)
        
        # Record CTA Link message second
        marketing_db.add_outgoing_reply(conv["id"], human_followup)
        logger.info(f"📤 [DM-AUTO-REPLY] Outbound link follow-up sent: '{human_followup}'")


async def execute_send_custom_dm(conv_id: str, text_content: str) -> bool:
    """
    Simulates/Sends a custom DM to an external lead.
    In production, this hooks into social account automation libraries.
    """
    logger.info(f"📤 [DM-MANUAL-SEND] Sent outgoing DM to conversation {conv_id}: '{text_content}'")
    marketing_db.add_outgoing_reply(conv_id, text_content)
    return True


async def start_inbox_simulator_loop(check_interval=60):
    """Inbox simulation background task."""
    logger.info("Unified Inbox & Lead simulator background task started.")
    while True:
        try:
            # 25% chance to receive a fresh direct message every cycle check
            if random.random() < 0.25:
                await simulate_incoming_direct_message()
        except Exception as e:
            logger.error(f"Error in Inbox Simulator Loop: {e}")
        await asyncio.sleep(check_interval)
