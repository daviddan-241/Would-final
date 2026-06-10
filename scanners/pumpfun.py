"""
Pump.fun Scanner (V3 API) - Fresh coins ONLY.
Posts coins created within the last MAX_AGE_MIN minutes.
Captures both Telegram AND Discord links.
"""
import logging
import time
import aiohttp
from typing import List
from .base import TokenInfo, extract_telegram_links, extract_discord_links

logger = logging.getLogger(__name__)

BASE = "https://frontend-api-v3.pump.fun"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

MAX_AGE_MIN = 60

SPAM_TG = {"masslauncherbot", "masslaunchbot", "masslauncher"}


async def scan_pumpfun(session: aiohttp.ClientSession) -> List[TokenInfo]:
    """Scan Pump.fun V3 for BRAND NEW coins with TG or Discord links."""
    tokens = []
    seen = set()
    now_ms = time.time() * 1000

    for offset in range(0, 1000, 50):
        url = f"{BASE}/coins?limit=50&offset={offset}&sort=created_timestamp&order=DESC&includeNsfw=false"
        too_old = False
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    coins = await resp.json()
                    if not isinstance(coins, list) or not coins:
                        break
                    for coin in coins:
                        created = coin.get("created_timestamp", 0)
                        if created < 1e12:
                            created = created * 1000
                        age_min = (now_ms - created) / 60000 if created else 99999

                        if age_min > MAX_AGE_MIN:
                            too_old = True
                            break

                        t = _parse(coin, age_min)
                        if t and t.contract_address.lower() not in seen:
                            seen.add(t.contract_address.lower())
                            tokens.append(t)
                else:
                    break
        except Exception as e:
            logger.debug(f"Pump.fun page {offset} error: {e}")
            break

        if too_old:
            break

    tg_count = sum(1 for t in tokens if t.telegram_link)
    dc_count = sum(1 for t in tokens if t.discord_link)
    logger.info(f"Pump.fun: {len(tokens)} fresh tokens — TG:{tg_count} Discord:{dc_count} (under {MAX_AGE_MIN}min)")
    return tokens


def _parse(coin: dict, age_min: float) -> TokenInfo | None:
    """Parse a pump.fun coin - capture TG and Discord links."""
    try:
        name = (coin.get("name", "") or "").strip()
        symbol = (coin.get("symbol", "") or "").strip()
        mint = coin.get("mint", "")
        tg_raw = (coin.get("telegram", "") or "").strip()
        discord_raw = (coin.get("discord", "") or "").strip()
        website = (coin.get("website", "") or "").strip()
        twitter = (coin.get("twitter", "") or "").strip()
        image = (coin.get("image_uri", "") or "").strip()
        description = (coin.get("description", "") or "").strip()

        if not mint or not name:
            return None

        # --- TG validation ---
        tg_link = _validate_tg(tg_raw)

        if not tg_link and description:
            found = extract_telegram_links(description)
            if found:
                tg_link = found[0]

        # Filter spam TG handles
        if tg_link:
            tg_handle = tg_link.split("t.me/")[-1].lower().strip("/") if "t.me/" in tg_link else ""
            if tg_handle in SPAM_TG:
                tg_link = ""

        # --- Discord extraction ---
        discord_link = _extract_discord(discord_raw)
        if not discord_link and description:
            found = extract_discord_links(description)
            if found:
                discord_link = found[0]
        if not discord_link and website and "discord" in website.lower():
            found = extract_discord_links(website)
            if found:
                discord_link = found[0]
        if not discord_link and twitter and "discord" in twitter.lower():
            found = extract_discord_links(twitter)
            if found:
                discord_link = found[0]

        # Must have at least one social link (TG or Discord)
        if not tg_link and not discord_link:
            return None

        # Clean website - skip if it's just a social link
        if website:
            if any(x in website for x in ["t.me/", "x.com/", "twitter.com/", "discord.gg/", "discord.com/invite"]):
                website = ""

        if twitter and "t.me/" in twitter:
            twitter = ""

        return TokenInfo(
            name=name,
            symbol=symbol,
            contract_address=mint,
            chain="Solana",
            telegram_link=tg_link or "",
            source="Pump.fun",
            website=website or None,
            twitter=twitter or None,
            image_url=image or None,
            pair_url=f"https://pump.fun/{mint}",
            discord_link=discord_link or None,
        )
    except Exception as e:
        logger.debug(f"Pump.fun parse error: {e}")
        return None


def _extract_discord(raw: str) -> str | None:
    """Extract and validate a Discord invite link."""
    if not raw:
        return None
    raw = raw.strip()
    found = extract_discord_links(raw)
    if found:
        return found[0]
    # Handle bare invite codes like "AbCdEf"
    if raw and "/" not in raw and len(raw) >= 4 and len(raw) <= 20:
        return f"https://discord.gg/{raw}"
    return None


def _validate_tg(raw: str) -> str | None:
    """Strictly validate that the TG field is a REAL t.me/ link."""
    if not raw:
        return None

    raw = raw.strip()

    if "x.com" in raw or "twitter.com" in raw or "discord" in raw:
        return None

    if raw.startswith("https://t.me/") or raw.startswith("http://t.me/"):
        handle = raw.split("t.me/")[1].strip("/")
        if handle and len(handle) >= 2:
            return raw
        return None

    if raw.startswith("t.me/"):
        handle = raw[5:].strip("/")
        if handle and len(handle) >= 2:
            return f"https://{raw}"
        return None

    if raw.startswith("@") and len(raw) > 2 and "." not in raw:
        return f"https://t.me/{raw[1:]}"

    if raw and "/" not in raw and " " not in raw and len(raw) >= 3:
        if "." in raw:
            return None
        return f"https://t.me/{raw}"

    found = extract_telegram_links(raw)
    return found[0] if found else None
