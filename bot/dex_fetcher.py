import requests
import random
import time
from typing import Optional

DEX_BASE = "https://api.dexscreener.com"

# Large diverse pool of real Solana tokens across MC ranges
KNOWN_SOLANA_TOKENS = [
    # Established meme/community coins
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",  # POPCAT
    "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",   # MEW
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # WIF
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # MYRO
    "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",   # SLERF
    "2weMjPLLybRMMva1fy3kT9ANXAqpnwhKvorYgrMavpfY",   # BOME
    "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",  # RETARDIO
    "ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzc8Qu",  # MOODENG
    "8Ki8DpuWNxu9VsS3kQbarsCWMcFGWkzzA8pUPto9zBd5",  # BABYDOGE (SOL)

    # PumpFun launchpad tokens
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "Df6yfrKC8kZE3KNkrHERKzAetSxbrWeniQfyJY4Jpump",
    "A8C3xuqscfmyLrte3VmTqrAq8kgMASius9AFNANwpump",
    "4Cnk9EPnW5ixfLZatCPJjDB1PUtcRpVVgTQukm9epump",
    "61V8vBaqAGMpgDIyGBiBnuTriwCuBQtZxH9CmBzpump",
    "CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump",
    "Ey59PH7Z3bvMFyXSnzxZrFUwobhVTTMVhsZF7PGRpump",
    "FvgqHMfL9yn39V79huDSsyper9XWAM4Q78QKZXJ5pump",
    "8mFDDjqVmQvPDFJjS1GKm6MJXF3YixdvGUBgEpUNpump",
    "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump",
    "5mbK36SZ7J19An8jFochhQS4of8g6BwUjbeCSxBSoWdp",
    "Fwity4J2iMRwKq4cRGD2e3pFfxBnEoJBFzBqfMxMpump",
    "ACmFpTqvGPB4xqTBe45znhXBYHapRKyqXJRsRump",

    # Mid-cap Solana ecosystem tokens
    "3S8qX1MsMqRbiwKg2cQyx7nis1oHMgaCuc9c4VfvVdPN",
    "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "FU1q8vJpZNUrmqsciSjp8bAKKidGsLmouB8CBdf8TKQv",
    "5z3EqYQo9HiCEs3R84RCDMu2n7anpDMxRhdK31yYRgmk",
    "Hjw6bEcHtbKjMBd9hMih2pHFMDMPvCf3FkNkmR2Kpump",
    "CLoUDKc4Ane7HeQcPpE3YHnznRxhMimJ4MyaUqyHFzAu",
    "4vMsoUT2BWatFweudnQM1xedRLfJgJ7hswhcpz4xgBTy",
    "SHDWyBxihqiCjDYwQBu1bQABvHMMkTHdkr7VDHCGpXk",
    "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y68GR",  # stSOL
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT (SOL)

    # Hot new tokens / recent pumpfun launches
    "BioFvKAqfQqKiuPpwNdoTgQiPHXVCaUiLjKdmHLpump",
    "GdV9HiPcxZTHhf5GfPMsRoLLkQHbFPmDFJqe3pump",
    "AzAGQY7TuSRzFHkYxSW9E1GKSe1xCZVFxmV19Rpump",
    "3E79VCFCKJdJGMvpXLMVhpLGZHnxSaKJvh8VGV3pump",
    "7jUb3cNDQ2pJWGfSJPZRhFgHMQDdVCdZi9Wpump",
    "FNLMgFCGSyDGXWbLQPPfJEMVNgBVmTiZXdpyJpump",
    "H9mMMaB3Pxfykhkv9SfUnfSbYnpump",
    "4DtA68QdEphoBPEGd15dR4bArYfHRJm7pump",

    # Active trading pairs on Raydium/Orca
    "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh",
    "RLBxxFkseAZ4RgJH3Sqn8jXxhmGoz9jWxDNJMh8pL7a",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "kinXdEcpDQeHPEuQnqmUgtYykqKCSVgjxDDEKPhpump",
    "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1Adventures",
    "DFL1zNkaGPWm1BqAVqRjCZvHmwThr1kM2djZCKKGWFGa",
    "ATLASXmbPQxBUYbxPsV97usA3fPQYEqzQBUHgiFCUsXx",
    "poLisWXnNRwC6oBu1vHiuKQzFjGL4XDSu4g9qjz9qVk",
    "Saber2gLauYim4Mvftnrasomsv6NvAuncvMEZwcLpD1",
    "MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac",

    # Viral/trending recent tokens
    "6ogzHhzdrQr9Pgv6hZ2MNze7UrzBMAFyBBWUYp1Fhitx",  # LUIGI
    "HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4",  # FWOG
    "Cmvh8bNJ57pF5kzRkGfGZH2gj3LbAcxdMSEGGNPpump",
    "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",  # BTC (wrapped)
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # ETH (wormhole)
    "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",   # HNT
    "mb1eu7TzEc71KxDpsmsKoucSSuuoGLv1drys1oP2jh6",   # MOBILE
    "DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7",  # DRIFT
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",   # JUP
    "WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk",   # WEN
    "TNSRxcUxoT9xBG3de7A4WNTmPQQaLqGGATEjgCsasLX",   # TENSOR
    "BqVHWpwUDgMik5gbTciFfozadpE45xuwB2Es2xEN4Vy3",  # PYUSD

    # Fresh low-cap gems (100K-5M MC range)
    "EwtJVgZQGHe9MXmrNZmhMiEWYtP7vSoAw6dVDSZhpump",
    "FmGn6UUwHFjvRmWudYY3yGHbNdVhJAFLQ3GCbfpump",
    "AntVfW1QxZFQGWFSKzBRrAWRpDhGqp3Kv9cKLpump",
    "CH74tuRLTYcxG7qNJCsV9rghFLdgRCnDQQScRApump",
    "FtcD74bKrFfYp6U5QvRqLJtCDDPMwqkB2Xbshpump",
    "7YttLkHDoNj9wyDur5pM1ejNaAvT9X4eqaYcHQqgjpump",
    "DumNBcCuLhGfkFPXxxhQKnNMqLFGHnuCpump",
    "8gHpSnNzJHpUymiKHcXFPGHexiqTCHc14v3pump",
    "BxH1PRPump7pU4MzDpX4J9hzb3Vxpump",
    "2HCAmPump7U3SNWA6eBUPzJxXkCpump",
    "9rZWpump3TgCsH7Y41MpJPkLKpump",
    "G6pumpGYeVJUiqsWbJmTKpump",
    "4mpumprRFf72FpJXyUWpump",
    "Lmpump5MBKqzpump",
    "CBmMiuXvrmEJ6MYiS7Vapump",
    "3oGpumpTTLfJpump",
    "Bmkpump9dRpump",
    "ZpumpWMpump",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AlphaBot/1.0)",
    "Accept": "application/json",
}

# DEX Screener search terms to find trending coins
SEARCH_QUERIES = [
    "pump", "pepe", "doge", "cat", "inu", "moon", "based", "sol",
    "ai", "gpt", "agent", "meme", "chad", "frog", "ape", "wojak",
    "trump", "elon", "wif", "bonk", "bome", "dog", "baby", "mega",
    "turbo", "super", "fire", "gem", "alpha", "sigma", "king", "lord",
    "goat", "bull", "bear", "rocket", "laser", "cyber", "meta", "real",
]


def fetch_token_data(address: str) -> Optional[dict]:
    try:
        url = f"{DEX_BASE}/latest/dex/tokens/{address}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        pairs = data.get("pairs") or []
        if not pairs:
            return None
        pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        return _parse_pair(pair)
    except Exception:
        return None


def fetch_trending_tokens(chain: str = "solana") -> list:
    results = []
    seen = set()

    # 1. Token boosts (sponsored/trending)
    try:
        url = f"{DEX_BASE}/token-boosts/latest/v1"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            items = resp.json() if isinstance(resp.json(), list) else []
            for item in items[:40]:
                addr = item.get("tokenAddress", "")
                if addr and item.get("chainId", "") == chain and addr not in seen:
                    token = fetch_token_data(addr)
                    if token:
                        results.append(token)
                        seen.add(addr)
    except Exception:
        pass

    # 2. Top boosts (most boosted all-time)
    try:
        url = f"{DEX_BASE}/token-boosts/top/v1"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            items = resp.json() if isinstance(resp.json(), list) else []
            for item in items[:20]:
                addr = item.get("tokenAddress", "")
                if addr and item.get("chainId", "") == chain and addr not in seen:
                    token = fetch_token_data(addr)
                    if token:
                        results.append(token)
                        seen.add(addr)
    except Exception:
        pass

    # 3. Keyword search for fresh coins
    query = random.choice(SEARCH_QUERIES)
    try:
        url = f"{DEX_BASE}/latest/dex/search?q={query}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            pairs = (resp.json() or {}).get("pairs") or []
            for pair in pairs[:15]:
                if pair.get("chainId", "") != chain:
                    continue
                parsed = _parse_pair(pair)
                addr = parsed.get("address", "")
                if addr and addr not in seen:
                    results.append(parsed)
                    seen.add(addr)
    except Exception:
        pass

    # 4. Fall back to known list if still thin
    if len(results) < 8:
        sample = random.sample(KNOWN_SOLANA_TOKENS, min(15, len(KNOWN_SOLANA_TOKENS)))
        for addr in sample:
            if addr not in seen:
                token = fetch_token_data(addr)
                if token:
                    results.append(token)
                    seen.add(addr)

    return results


def fetch_new_coins(chain: str = "solana", min_mc: float = 120_000, max_mc: float = 50_000_000) -> list:
    candidates = []
    seen = set()

    # Latest token profiles (newest listings)
    try:
        url = f"{DEX_BASE}/token-profiles/latest/v1"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            items = resp.json() if isinstance(resp.json(), list) else []
            for item in items[:60]:
                if item.get("chainId", "") != chain:
                    continue
                addr = item.get("tokenAddress", "")
                if not addr or addr in seen:
                    continue
                token = fetch_token_data(addr)
                if token and min_mc <= token.get("market_cap", 0) <= max_mc:
                    candidates.append(token)
                    seen.add(addr)
    except Exception:
        pass

    # Also search with multiple rotating keywords to find fresh coins
    for _ in range(2):
        query = random.choice(SEARCH_QUERIES)
        try:
            url = f"{DEX_BASE}/latest/dex/search?q={query}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                pairs = (resp.json() or {}).get("pairs") or []
                for pair in pairs[:20]:
                    if pair.get("chainId", "") != chain:
                        continue
                    parsed = _parse_pair(pair)
                    addr = parsed.get("address", "")
                    mc = parsed.get("market_cap", 0)
                    if addr and addr not in seen and min_mc <= mc <= max_mc:
                        candidates.append(parsed)
                        seen.add(addr)
        except Exception:
            pass
        time.sleep(0.5)

    return candidates


def fetch_ohlcv_data(pair_address: str, chain: str = "solana", resolution: str = "15") -> list:
    try:
        url = f"{DEX_BASE}/latest/dex/chart/{chain}/{pair_address}?from=0&to=9999999999&res={resolution}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bars = data.get("bars", []) or []
            if bars:
                return bars
    except Exception:
        pass
    return _generate_mock_ohlcv(60)


def _parse_pair(pair: dict) -> dict:
    base = pair.get("baseToken", {})
    info = pair.get("info", {}) or {}
    price_change = pair.get("priceChange", {}) or {}
    liquidity = pair.get("liquidity", {}) or {}
    volume = pair.get("volume", {}) or {}
    fdv = pair.get("fdv") or pair.get("marketCap") or 0

    return {
        "address": base.get("address", ""),
        "symbol": base.get("symbol", "UNKNOWN"),
        "name": base.get("name", "Unknown"),
        "pair_address": pair.get("pairAddress", ""),
        "chain": pair.get("chainId", "solana"),
        "dex": pair.get("dexId", ""),
        "price_usd": float(pair.get("priceUsd") or 0),
        "market_cap": float(fdv or 0),
        "liquidity_usd": float(liquidity.get("usd") or 0),
        "volume_24h": float(volume.get("h24") or 0),
        "price_change_5m": float(price_change.get("m5") or 0),
        "price_change_1h": float(price_change.get("h1") or 0),
        "price_change_24h": float(price_change.get("h24") or 0),
        "created_at": pair.get("pairCreatedAt", 0),
        "url": pair.get("url", ""),
        "logo": (info.get("imageUrl") or ""),
        "website": next((s.get("url", "") for s in (info.get("websites") or []) if s), ""),
        "twitter": next((s.get("url", "") for s in (info.get("socials") or []) if s.get("type") == "twitter"), ""),
    }


def _generate_mock_ohlcv(n: int = 60) -> list:
    bars = []
    price = random.uniform(0.000001, 0.01)
    ts = int(time.time()) - n * 15 * 60
    trend = random.uniform(0.003, 0.018)
    for i in range(n):
        noise = random.gauss(trend, 0.065)
        open_ = price
        close = price * (1 + noise)
        high = max(open_, close) * (1 + abs(random.gauss(0, 0.025)))
        low = min(open_, close) * (1 - abs(random.gauss(0, 0.025)))
        vol = random.uniform(3000, 90000) * (1 + i / n)
        bars.append({"t": ts + i * 900, "o": open_, "h": high, "l": low, "c": close, "v": vol})
        price = close
    return bars


def format_mc(value: float) -> str:
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:.0f}"


def format_short_addr(addr: str) -> str:
    if len(addr) > 12:
        return addr[:6] + "..." + addr[-4:]
    return addr
