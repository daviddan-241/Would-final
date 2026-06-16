"""
Comment & DM Spam Filter — Detects and blocks bot accounts, spam phrases,
and low-quality targets before posting comments or processing DMs.
All rules are deterministic — no fake scoring.
"""
import re
import logging

logger = logging.getLogger("spam_filter")

# ─── SPAM PHRASES IN INCOMING DMs ─────────────────────────────────────────────

SPAM_DM_PHRASES = [
    "click here to verify",
    "your account has been suspended",
    "congratulations you won",
    "claim your prize",
    "send crypto to",
    "invest now and earn",
    "guaranteed profit",
    "100% daily returns",
    "join my pump group free",
    "airdrop claim",
    "free nft giveaway",
    "dm me for free",
    "check my bio link",
    "earn money fast",
    "whatsapp +",
    "telegram @",
    "signal group",
    "copy trade guaranteed",
    "send me your wallet",
    "seed phrase",
    "private key",
    "recovery phrase",
    "i'm a professional trader",
    "invest $100 get $1000",
    "limited time offer act now",
    "crypto recovery",
    "lost funds recovery",
    "binary options",
    "forex signal",
]

# ─── BOT-LIKE USERNAME PATTERNS ────────────────────────────────────────────────

BOT_USERNAME_PATTERNS = [
    r"^[a-z]+_[a-z]+_\d{3,}$",          # word_word_123
    r"^[a-z]{2,}\d{5,}$",               # word12345 (5+ digits)
    r"^(buy|sell|cheap|best)_",          # buy_cheap_...
    r"_?(bot|spam|promo|official)\d*$",  # ends with bot/spam
    r"^(follow|like|sub)_",             # follow_me_...
    r"^ig_\w+",                         # ig_ prefixed
    r"^the_real_",                       # the_real_...
    r"^\w+_f4f",                        # word_f4f
    r"^\w+_l4l",                        # word_l4l
    r"dm_for_\w+",                      # dm_for_promo
    r"^free_\w+_\d+",                   # free_followers_2024
]

# ─── NICHE-SPECIFIC COMMENT TEMPLATES PER PLATFORM ────────────────────────────

TIKTOK_COMMENTS = {
    "crypto": [
        "yo this is actually fire 🔥 been looking into this space heavy",
        "the way you broke this down is crazy, need more of this content",
        "this is what I've been saying!! finally someone gets it",
        "real ones know 💎 been stacking since day one",
        "literally just got into this last week, timing is everything",
    ],
    "solana": [
        "sol fam we up 🟣 this is the way",
        "been tracking the sol ecosystem all month, this is huge",
        "solana builders are different breed fr",
    ],
    "memecoins": [
        "memecoin szn is actually unreal rn 🐸",
        "the degen plays this month have been insane",
        "this is the alpha everyone needed to see",
    ],
    "celeb": [
        "you're literally my favorite creator rn 💕",
        "this is everything!! your content always hits different",
        "obsessed with this!! 😍 need pt 2 asap",
        "no bc this is actually so good 🔥",
    ],
    "lifestyle": [
        "this is the motivation I needed today 🙌",
        "literally my dream lifestyle, you're living it",
        "this hits different when you're actually grinding",
        "goals!! 🌴 need to make this happen",
    ],
    "viral": [
        "how does this not have more views??",
        "this is about to blow up fr",
        "came from the fyp and I'm not disappointed",
    ],
}

INSTAGRAM_COMMENTS = {
    "crypto": [
        "this is the alpha we need 📈 great analysis",
        "been watching this space closely, solid take",
        "real talk, more people need to see this 🔥",
        "the fundamentals here are actually insane",
    ],
    "solana": [
        "SOL ecosystem is unmatched right now 🟣",
        "this is exactly what I've been tracking",
        "solana community is built different 💜",
    ],
    "memecoins": [
        "memecoin season just getting started 🐸🚀",
        "the charts don't lie, this is real",
        "degen season is upon us 🔥",
    ],
    "celeb": [
        "absolutely stunning as always 💕",
        "this feed is literally perfect ✨",
        "you never miss!! every post is a vibe",
        "this content is next level 🔥",
    ],
    "lifestyle": [
        "this is what living looks like 🌟",
        "adding this to my vision board fr",
        "the aesthetic here is unmatched ✨",
    ],
    "viral": [
        "this deserves so much more attention 🔥",
        "came here from explore and wow",
        "this is the content I'm here for",
    ],
}

FACEBOOK_COMMENTS = {
    "crypto": [
        "Great post! Been following this space closely",
        "Solid analysis, more people need to see this",
        "This is exactly what I've been thinking too",
        "Really well said, the market is shifting fast",
    ],
    "solana": [
        "SOL ecosystem is really heating up",
        "Great take on the Solana landscape right now",
        "The Solana community keeps growing for a reason",
    ],
    "memecoins": [
        "Memecoin season is real, the numbers don't lie",
        "Some of these plays have been incredible lately",
        "The memecoin space is evolving fast",
    ],
    "celeb": [
        "Love this content! Always quality from you",
        "This is amazing, keep it up!",
        "Your page is consistently the best",
    ],
    "lifestyle": [
        "This is so inspiring, thanks for sharing",
        "Living the dream! Great post",
        "This is the kind of content I love seeing",
    ],
    "viral": [
        "This needs to go viral, sharing with everyone",
        "Why doesn't this have more engagement? So good!",
        "This is exactly what I needed to see today",
    ],
}

# ─── FILTER FUNCTIONS ─────────────────────────────────────────────────────────

def is_spam_dm(text: str) -> bool:
    """
    Returns True if an incoming DM looks like spam/scam.
    Checks against known spam phrases (case-insensitive).
    """
    if not text:
        return False
    clean = text.lower().strip()
    for phrase in SPAM_DM_PHRASES:
        if phrase in clean:
            logger.debug(f"[SpamFilter] DM matched spam phrase: '{phrase}'")
            return True
    # All caps + short = likely spam
    if text.isupper() and len(text) > 10 and len(text) < 60:
        return True
    # Excessive links (3+ URLs in a short message)
    url_count = len(re.findall(r'https?://\S+', text))
    if url_count >= 3:
        return True
    return False


def is_bot_username(handle: str) -> bool:
    """
    Returns True if the username matches common bot/spam patterns.
    """
    if not handle:
        return False
    clean = handle.lstrip("@").lstrip("u/").lower()
    for pat in BOT_USERNAME_PATTERNS:
        if re.search(pat, clean):
            return True
    # No vowels in a long username = likely generated
    letters = re.sub(r"[^a-zA-Z]", "", clean)
    if len(letters) >= 6:
        vowels = sum(1 for c in letters.lower() if c in "aeiou")
        if vowels == 0:
            return True
    return False


def is_quality_engagement_target(handle: str, bio_text: str = "", follower_count: int = 0) -> bool:
    """
    Returns True if this looks like a real person worth engaging with.
    Filters out bots, spam accounts, and empty profiles.
    """
    if is_bot_username(handle):
        return False
    if is_spam_dm(bio_text):
        return False
    # If we have follower data, filter very low follower accounts
    # (0-2 followers often = bot or inactive)
    if 0 < follower_count < 3:
        return False
    return True


def get_niche_comments(platform: str, niche: str) -> list:
    """
    Returns the comment templates for a given platform and niche.
    Falls back to crypto if niche not found.
    """
    if platform == "tiktok":
        return TIKTOK_COMMENTS.get(niche, TIKTOK_COMMENTS.get("crypto", []))
    elif platform == "instagram":
        return INSTAGRAM_COMMENTS.get(niche, INSTAGRAM_COMMENTS.get("crypto", []))
    elif platform == "facebook":
        return FACEBOOK_COMMENTS.get(niche, FACEBOOK_COMMENTS.get("crypto", []))
    return []
