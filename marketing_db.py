"""
Marketing database for storing profiles (personas), target accounts, ads, connected accounts, raids,
unified inbox conversations, messages, auto-responder rules, growth hacking campaigns, and settings.
Supports profile-specific Telegram bot tokens and chat IDs.
"""
import os
import json
import time
import logging


def add_push_subscription(endpoint: str, p256dh: str, auth: str) -> None:
    db = load_db()
    db['push_subscriptions'] = [s for s in db.get('push_subscriptions', []) if s.get('endpoint') != endpoint]
    db['push_subscriptions'].append({'endpoint': endpoint, 'p256dh': p256dh, 'auth': auth})
    save_db()


def get_push_subscriptions() -> list:
    return load_db().get('push_subscriptions', [])


def remove_push_subscription(endpoint: str) -> None:
    db = load_db()
    db['push_subscriptions'] = [s for s in db.get('push_subscriptions', []) if s.get('endpoint') != endpoint]
    save_db()

logger = logging.getLogger(__name__)

DB_FILE = os.getenv("MARKETING_DB_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketing_data.json"))

_data = {
    "profiles": [],          # SMM Personas: {id, name, niche, bio, cta_link, ai_tone, avatar, active, tg_bot_token, tg_chat_id}
    "targets": [],           # Influencer/Target accounts to mirror
    "ads": [],               # Scheduled promotional ads
    "accounts": [],          # Connected SMM Accounts fleet
    "raids": [],             # Created raids
    "conversations": [],     # Unified Inbox: {id, profile_id, platform, sender_handle, avatar, unread, last_message_time}
    "messages": {},          # Conversation messages: {conv_id: [messages]}
    "auto_replies": [],      # Chatbot rules: {id, profile_id, keyword, reply_text, active}
    "growth_campaigns": [],  # Viral traffic campaigns
    "discord_coins": [],       # Pump.fun coins with Discord links found
    "push_subscriptions": [],  # Web Push subscriber objects {endpoint, p256dh, auth}
    "analytics": {           # Real-time traffic funnel stats
        "impressions": 24500,
        "clicks": 1820,
        "leads": 412,
        "conversion_rate": 22.6
    },
    "settings": {
        "openai_key": "",
        "gemini_key": "",
        "global_cta_link": "", # Quick global redirect funnel override
        "auto_mirror_enabled": True,
        "auto_raid_enabled": True,
        "auto_post_enabled": True,
        "auto_dm_reply_enabled": True,
        "growth_hacks_enabled": True,
        "rewrite_style": "bullish_crypto_enthusiast",
        "proxy_list": []
    }
}
_loaded = False


def load_db():
    global _data, _loaded
    if _loaded:
        return _data
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                loaded_data = json.load(f)
            # Merge to ensure keys exist
            for key in _data:
                if key in loaded_data:
                    if isinstance(_data[key], dict) and isinstance(loaded_data[key], dict):
                        _data[key].update(loaded_data[key])
                    else:
                        _data[key] = loaded_data[key]
            logger.info("Marketing database loaded successfully.")
        else:
            save_db()
    except Exception as e:
        logger.error(f"Error loading marketing DB: {e}")
    _loaded = True
    return _data


def save_db():
    try:
        with open(DB_FILE, "w") as f:
            json.dump(_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving marketing DB: {e}")


# --- Multi-Profile (Persona) CRUD ---

def get_profiles():
    db = load_db()
    # No auto-seeding default profiles anymore to prevent them from showing up when you want a clean slate
    if "profiles" not in db:
        db["profiles"] = []
        save_db()
    return db["profiles"]


def add_profile(name, niche, bio, cta_link, ai_tone, avatar="", tg_bot_token="", tg_chat_id=""):
    db = load_db()
    if "profiles" not in db:
        db["profiles"] = []
    
    prof_id = f"prof_{int(time.time() * 1000)}"
    new_prof = {
        "id": prof_id,
        "name": name,
        "niche": niche,         # crypto, celeb, casual
        "bio": bio,
        "cta_link": cta_link,   # private account or target url
        "ai_tone": ai_tone,     # bullish_crypto_enthusiast, hype, professional, casual
        "avatar": avatar or f"https://api.dicebear.com/7.x/pixel-art/svg?seed={name}",
        "active": True,
        "tg_bot_token": tg_bot_token.strip(),
        "tg_chat_id": tg_chat_id.strip()
    }
    db["profiles"].append(new_prof)
    save_db()
    return new_prof


def delete_profile(prof_id):
    db = load_db()
    if "profiles" in db:
        db["profiles"] = [p for p in db["profiles"] if p["id"] != prof_id]
        save_db()


def toggle_profile(prof_id):
    db = load_db()
    for p in db.get("profiles", []):
        if p["id"] == prof_id:
            p["active"] = not p["active"]
            break
    save_db()


# Targets CRUD
def get_targets():
    db = load_db()
    return db["targets"]


def add_target(platform, handle, destination, active=True):
    db = load_db()
    target_id = f"target_{int(time.time() * 1000)}"
    new_target = {
        "id": target_id,
        "platform": platform,
        "handle": handle,
        "destination": destination,
        "active": active,
        "last_post_id": "",
        "last_checked": 0,
        "created_at": time.time()
    }
    db["targets"].append(new_target)
    save_db()
    return new_target


def delete_target(target_id):
    db = load_db()
    db["targets"] = [t for t in db["targets"] if t["id"] != target_id]
    save_db()


def toggle_target(target_id):
    db = load_db()
    for t in db["targets"]:
        if t["id"] == target_id:
            t["active"] = not t["active"]
            break
    save_db()


# Ads CRUD
def get_ads():
    db = load_db()
    return db["ads"]


def add_ad(platform, content, interval_min, image_url="", active=True):
    db = load_db()
    ad_id = f"ad_id_{int(time.time() * 1000)}"
    new_ad = {
        "id": ad_id,
        "platform": platform,
        "content": content,
        "interval_min": int(interval_min),
        "image_url": image_url,
        "active": active,
        "last_posted": 0,
        "created_at": time.time()
    }
    db["ads"].append(new_ad)
    save_db()
    return new_ad


def delete_ad(ad_id):
    db = load_db()
    db["ads"] = [a for a in db["ads"] if a["id"] != ad_id]
    save_db()


def toggle_ad(ad_id):
    db = load_db()
    for a in db["ads"]:
        if a["id"] == ad_id:
            a["active"] = not a["active"]
            break
    save_db()


# Connected Accounts CRUD
def get_accounts():
    db = load_db()
    if "accounts" not in db:
        db["accounts"] = []
    return db["accounts"]


def add_account(platform, username, password="", token_session="", status="Active"):
    db = load_db()
    if "accounts" not in db:
        db["accounts"] = []
    
    acc_id = f"acc_{int(time.time() * 1000)}"
    new_acc = {
        "id": acc_id,
        "platform": platform,
        "username": username,
        "password": password,
        "token_session": token_session,
        "status": status,
        "created_at": time.time()
    }
    db["accounts"].append(new_acc)
    save_db()
    return new_acc


def delete_account(acc_id):
    db = load_db()
    if "accounts" in db:
        db["accounts"] = [a for a in db["accounts"] if a["id"] != acc_id]
        save_db()


# Raids CRUD
def get_raids():
    db = load_db()
    return db["raids"]


def add_raid(platform, url, caption=""):
    db = load_db()
    raid_id = f"raid_{int(time.time() * 1000)}"
    new_raid = {
        "id": raid_id,
        "platform": platform,
        "url": url,
        "caption": caption,
        "target_likes": 100,
        "current_likes": 0,
        "target_comments": 20,
        "current_comments": 0,
        "status": "Active",
        "created_at": time.time()
    }
    db["raids"].append(new_raid)
    save_db()
    return new_raid


def update_raid_stats(raid_id, current_likes, current_comments, status=None):
    db = load_db()
    for r in db["raids"]:
        if r["id"] == raid_id:
            r["current_likes"] = current_likes
            r["current_comments"] = current_comments
            if status:
                r["status"] = status
            break
    save_db()


def delete_raid(raid_id):
    db = load_db()
    db["raids"] = [r for r in db["raids"] if r["id"] != raid_id]
    save_db()


# Unified DM Inbox
def get_conversations():
    db = load_db()
    if "conversations" not in db:
        db["conversations"] = []
    return db["conversations"]


def get_conversation_messages(conv_id):
    db = load_db()
    if "messages" not in db:
        db["messages"] = {}
    return db["messages"].get(conv_id, [])


def add_incoming_message(platform, sender_handle, text, avatar="", profile_id=None):
    db = load_db()
    if "conversations" not in db:
        db["conversations"] = []
    if "messages" not in db:
        db["messages"] = {}

    # Default to first profile if not specified
    if not profile_id:
        profiles = get_profiles()
        profile_id = profiles[0]["id"] if profiles else "prof_default_crypto"

    conv = None
    for c in db["conversations"]:
        if c["platform"] == platform and c["sender_handle"].lower() == sender_handle.lower() and c.get("profile_id") == profile_id:
            conv = c
            break

    now = time.time()
    if not conv:
        conv_id = f"conv_{int(now * 1000)}"
        conv = {
            "id": conv_id,
            "profile_id": profile_id,
            "platform": platform,
            "sender_handle": sender_handle,
            "avatar": avatar or f"https://api.dicebear.com/7.x/bottts/svg?seed={sender_handle}",
            "unread": 0,
            "last_message_time": now,
            "last_message_text": text
        }
        db["conversations"].insert(0, conv)
    else:
        conv["last_message_time"] = now
        conv["last_message_text"] = text
        db["conversations"].remove(conv)
        db["conversations"].insert(0, conv)

    conv_id = conv["id"]
    conv["unread"] += 1

    if conv_id not in db["messages"]:
        db["messages"][conv_id] = []

    new_msg = {
        "sender": sender_handle,
        "text": text,
        "timestamp": now,
        "is_incoming": True
    }
    db["messages"][conv_id].append(new_msg)
    save_db()
    return conv, new_msg


def add_outgoing_reply(conv_id, text):
    db = load_db()
    if "conversations" not in db:
        return None
    if "messages" not in db:
        return None

    conv = None
    for c in db["conversations"]:
        if c["id"] == conv_id:
            conv = c
            break

    if not conv:
        return None

    now = time.time()
    conv["last_message_time"] = now
    conv["last_message_text"] = text
    conv["unread"] = 0

    if conv_id not in db["messages"]:
        db["messages"][conv_id] = []

    new_msg = {
        "sender": "Admin",
        "text": text,
        "timestamp": now,
        "is_incoming": False
    }
    db["messages"][conv_id].append(new_msg)
    save_db()
    return new_msg


def mark_conversation_read(conv_id):
    db = load_db()
    if "conversations" not in db:
        return
    for c in db["conversations"]:
        if c["id"] == conv_id:
            c["unread"] = 0
            break
    save_db()


# Auto Replies
def get_auto_replies():
    db = load_db()
    if "auto_replies" not in db:
        db["auto_replies"] = []
    return db["auto_replies"]


def add_auto_reply(keyword, reply_text):
    db = load_db()
    if "auto_replies" not in db:
        db["auto_replies"] = []
    rule_id = f"rule_{int(time.time() * 1000)}"
    new_rule = {
        "id": rule_id,
        "keyword": keyword.lower().strip(),
        "reply_text": reply_text,
        "active": True,
        "created_at": time.time()
    }
    db["auto_replies"].append(new_rule)
    save_db()
    return new_rule


def delete_auto_reply(rule_id):
    db = load_db()
    db["auto_replies"] = [r for r in db["auto_replies"] if r["id"] != rule_id]
    save_db()


def toggle_auto_reply(rule_id):
    db = load_db()
    for r in db["auto_replies"]:
        if r["id"] == rule_id:
            r["active"] = not r["active"]
            break
    save_db()


# Growth campaigns
def get_growth_campaigns():
    db = load_db()
    if "growth_campaigns" not in db:
        db["growth_campaigns"] = []
    return db["growth_campaigns"]


def add_growth_campaign(niche, keywords, cta_link, platform):
    db = load_db()
    if "growth_campaigns" not in db:
        db["growth_campaigns"] = []
    
    camp_id = f"camp_{int(time.time() * 1000)}"
    new_camp = {
        "id": camp_id,
        "niche": niche,
        "keywords": [k.strip().lower() for k in keywords.split(",") if k.strip()],
        "cta_link": cta_link,
        "platform": platform,
        "status": "Active",
        "impressions_generated": 0,
        "clicks_generated": 0,
        "leads_captured": 0,
        "created_at": time.time()
    }
    db["growth_campaigns"].append(new_camp)
    save_db()
    return new_camp


def delete_growth_campaign(camp_id):
    db = load_db()
    if "growth_campaigns" in db:
        db["growth_campaigns"] = [c for c in db["growth_campaigns"] if c["id"] != camp_id]
        save_db()


def get_analytics():
    db = load_db()
    if "analytics" not in db:
        db["analytics"] = {"impressions": 24500, "clicks": 1820, "leads": 412, "conversion_rate": 22.6}
    return db["analytics"]


def increment_analytics(impressions=0, clicks=0, leads=0):
    db = load_db()
    if "analytics" not in db:
        db["analytics"] = {"impressions": 24500, "clicks": 1820, "leads": 412, "conversion_rate": 22.6}
        
    db["analytics"]["impressions"] += impressions
    db["analytics"]["clicks"] += clicks
    db["analytics"]["leads"] += leads
    
    c = db["analytics"]["clicks"]
    l = db["analytics"]["leads"]
    db["analytics"]["conversion_rate"] = round((l / c) * 100, 1) if c > 0 else 0.0
    save_db()
    return db["analytics"]


# Settings Management
def get_settings():
    db = load_db()
    return db["settings"]


def update_settings(new_settings):
    db = load_db()
    db["settings"].update(new_settings)
    save_db()
    return db["settings"]


# --- Discord Coins (pump.fun coins with Discord links) ---

def add_discord_coin(name: str, symbol: str, mint: str, chain: str, discord_link: str,
                     telegram_link: str = "", twitter: str = "", website: str = "",
                     image_url: str = "", pair_url: str = "", source: str = "") -> dict:
    """Store a coin with a Discord link found by the scanner."""
    db = load_db()
    if "discord_coins" not in db:
        db["discord_coins"] = []

    # Avoid duplicates by mint address
    existing_mints = {c.get("mint", "") for c in db["discord_coins"]}
    if mint in existing_mints:
        return {}

    import time as _t
    entry = {
        "name": name,
        "symbol": symbol,
        "mint": mint,
        "chain": chain,
        "discord_link": discord_link,
        "telegram_link": telegram_link,
        "twitter": twitter,
        "website": website,
        "image_url": image_url,
        "pair_url": pair_url,
        "source": source,
        "found_at": _t.time(),
    }
    db["discord_coins"].append(entry)
    # Keep last 500
    if len(db["discord_coins"]) > 500:
        db["discord_coins"] = db["discord_coins"][-500:]
    save_db()
    return entry


def get_discord_coins(limit: int = 100) -> list:
    """Return the most recent Discord coins."""
    db = load_db()
    coins = db.get("discord_coins", [])
    return list(reversed(coins[-limit:]))
