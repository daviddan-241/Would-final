"""
SMM Lead and Message Humanizer - Strip robotic structures, introduce natural delays,
and bypass AI-detection algorithms completely to look like a real mobile typist.
"""
import random
import re

SLANG_REPLACEMENTS = {
    r"\bwant to\b": "wanna",
    r"\bgoing to\b": "gonna",
    r"\byou are\b": "ur",
    r"\bfor real\b": "fr",
    r"\bof course\b": "ofc",
    r"\bby the way\b": "btw",
    r"\boh my god\b": "omg",
    r"\bto be honest\b": "tbh",
    r"\bright now\b": "rn",
    r"\bpeople\b": "ppl",
    r"\bare you\b": "ru"
}


def humanize_text(text: str) -> str:
    """
    Transforms clean, robotic AI text into 100% human-looking casual mobile typing.
    Subverts AI-detection algorithms (GPTZero, CopyLeaks, etc.) and looks authentic.
    """
    if not text:
        return text

    # 1. Lowercase everything except proper nouns (or leave casual lowercases)
    # 30% chance to lowercase the entire sentence to look like quick mobile typing
    if random.random() < 0.4:
        text = text.lower()
    else:
        # Lowercase the very first letter of the message (extremely common in mobile chats)
        text = text[0].lower() + text[1:] if text else text

    # 2. Swap formal words for casual keyboard contractions
    for pattern, replacement in SLANG_REPLACEMENTS.items():
        if random.random() < 0.8:  # 80% chance to apply casual contractions
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 3. Strip trailing punctuation
    # Real people rarely end single-sentence DMs with a formal period.
    if text.endswith(".") and not text.endswith("..") and random.random() < 0.9:
        text = text[:-1]

    # 4. Introduce minor natural touch-keyboard imperfections (caps lock omission or simple spelling vibes)
    # E.g., replace some exclamation marks with simple letters or casual emojis
    if "!" in text and random.random() < 0.5:
        text = text.replace("!", "")

    return text.strip()


def calculate_typing_delay(text: str) -> float:
    """
    Calculates a highly realistic, human-paced typing delay based on message length.
    Ensures replies do not send immediately, simulating a real person's keyboard pacing.
    """
    word_count = len(text.split())
    # Average human typing speed on mobile: ~35 words per minute (1.7 seconds per word)
    typing_speed_factor = random.uniform(1.2, 1.8)
    
    # Delay in seconds
    delay = word_count * typing_speed_factor
    
    # Cap delay between 6.0 and 25.0 seconds so it remains snappy but realistic
    return min(max(delay, 6.0), 25.0)
