"""
Social Media Inbox & AI Chatbot Response Engine — Handles receiving and sending direct messages (DMs)
on X, Instagram, TikTok, and Facebook, with AI-driven natural conversational replies matching individual SMM Personas.
"""
import logging
import asyncio
import random
import time
import aiohttp
from typing import Dict, Any, List

import marketing_db

logger = logging.getLogger(__name__)

# Simulated lists of leads based on niche targets
NICHE_LEADS = {
    "crypto": ["sol_whale_99", "crypto_kid_eth", "nft_collector_max", "gem_hunter_v", "defi_explorer"],
    "celeb": ["fan_boy_lucas", "jack_love_reel", "emma_star_x", "official_tom", "kate_vlog_world"],
    "casual": ["lucas_crypto", "hannah_brooks", "sam_traveler", "sophia_life", "alex_adventures"]
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


async def generate_ai_or_rule_reply(incoming_text: str, profile: Dict[str, Any]) -> str:
    """Uses LLM API or custom keywords to generate human-like direct message replies matching SMM Personas."""
    settings = marketing_db.get_settings()
    
    prof_name = profile.get("name", "Support")
    niche = profile.get("niche", "casual")
    bio = profile.get("bio", "")
    cta = profile.get("cta_link", "")
    style = profile.get("ai_tone", "casual")
    
    # 1. Check custom auto-responder rules first
    clean_text = incoming_text.lower().strip()
    rules = marketing_db.get_auto_replies()
    for rule in rules:
        if rule.get("active", True) and rule.get("keyword") in clean_text:
            logger.info(f"🤖 Chatbot rule matched keyword: '{rule['keyword']}'")
            return rule.get("reply_text")
            
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
                f"If the lead is asking to buy, join, see content, or get details, guide them gently to your call-to-action link: {cta}. "
                f"Do not sound like a bot. Keep your answer short (1-3 sentences) to look like real mobile texting.\n\n"
                f"DM received from lead:\n{incoming_text}"
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
                        reply = res["choices"][0]["message"]["content"].strip()
                        if reply:
                            return reply
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
                f"Guide them to your CTA link: '{cta}' if appropriate. Keep it short (2 sentences max) to look like an authentic DM.\n\n"
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
                            return reply
        except Exception as e:
            logger.error(f"Gemini Multi-Persona DM Reply failed: {e}")

    # Default rule-based fallback based on niche
    if niche == "crypto":
        return f"Hey there! Thanks for reaching out! 🚀 The response has been absolutely insane. I post all my trade triggers and alpha calls directly in our private channel here: {cta}. Join up so you don't miss the next move!"
    elif niche == "celeb":
        return f"Hey babe! Aw, thank you so much for the love! 😍 I chat with all my vip fans directly in my private club here: {cta}. Go join and message me there, I'll send you a special voice note!"
    else: # casual / normal
        return f"Hey! Thanks for messaging, let's totally connect! 💖 You can find more of my daily thoughts and photos over at my main page: {cta} - send me a request!"


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
    
    username = random.choice(leads_pool)
    message_text = random.choice(msgs_pool)
    
    logger.info(f"📥 [DM-INCOMING] Received DM from @{username} on {platform.title()} targeting Persona '{profile['name']}': '{message_text}'")
    
    # 3. Add message to persistent database bound to specific profile
    conv, new_msg = marketing_db.add_incoming_message(
        platform=platform,
        sender_handle=f"@{username}",
        text=message_text,
        profile_id=profile["id"]
    )
    
    # 4. Handle Auto-Responder replying automatically after 1-3 seconds
    await asyncio.sleep(random.uniform(1.0, 3.0))
    
    reply_text = await generate_ai_or_rule_reply(message_text, profile)
    marketing_db.add_outgoing_reply(conv["id"], reply_text)
    
    logger.info(f"📤 [DM-AUTO-REPLY] Auto-replied under Persona '{profile['name']}' to @{username}: '{reply_text}'")


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
