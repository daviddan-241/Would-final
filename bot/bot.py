import asyncio
import logging
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter
from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, ContextTypes,
)

from dex_fetcher import fetch_trending_tokens, fetch_new_coins, format_mc
from image_generator import build_update_card, build_call_card, build_forex_card
from payment_handler import build_payment_conversation, start

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is not set.")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID environment variable is not set.")

MIN_MC            = float(os.getenv("MIN_MC",         10_000))
MAX_MC            = float(os.getenv("MAX_MC",        800_000))
SCAN_INTERVAL     = int(os.getenv("SCAN_INTERVAL",       180))
SEND_INTERVAL_MIN = int(os.getenv("SEND_INTERVAL_MIN",   120))
SEND_INTERVAL_MAX = int(os.getenv("SEND_INTERVAL_MAX",   180))
PORT              = int(os.getenv("PORT",              10000))
BOT_USERNAME      = os.getenv("BOT_USERNAME", "")

tracked_coins: dict = {}
sent_updates:  dict = {}
last_sent_time: float = 0.0

VIP_LINK = "https://t.me/+b7UesS3ulxxlZDdk"

# ─── Keyboard buttons ──────────────────────────────────────────────────────────

def _pay_url() -> str:
    return f"https://t.me/{BOT_USERNAME}?start=vip" if BOT_USERNAME else VIP_LINK

def _join_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔐 Get VIP Access — $49/mo or $75 lifetime", url=_pay_url())
    ]])

def _join_button_double() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 GET VIP ACCESS", url=_pay_url())],
        [InlineKeyboardButton("$49 / month  |  $75 / lifetime", url=_pay_url())],
    ])


# ─── Caption templates — whale/professional tone ───────────────────────────────

CALL_TEMPLATES = [
    "🟢 *${symbol}*\n\nMC: `{mc}` — caught before CT woke up\nLiq `{liq}` confirmed. Vol moving: `{vol}`\n\nCA 👇\n`{ca}`\n{dex_url}",

    "just added *${symbol}* to the bag\n\n`{mc}` MC right now. liq is clean at `{liq}`\nvolume already ticking: `{vol}`\n\nthis is exactly how the good ones start\n\n`{ca}`",

    "🎯 *{name}*\n\nentry at `{mc}` MC — pre-narrative\nLiq `{liq}` | Vol `{vol}`\n\nCA:\n`{ca}`\n{dex_url}",

    "new call dropping 🔔\n\n*${symbol}* — `{mc}` MC\n\nteam moving quietly. liq `{liq}`, vol starting to pick up: `{vol}`\n\nwe are early. very.\n\n`{ca}`",

    "🟢 caught *{name}* at `{mc}` MC\n\nLiq `{liq}` | Vol 1H `{vol}`\n\nthis is the type of entry that changes wallets. you know what to do.\n\n`{ca}`\n{dex_url}",

    "alpha leak 🔑\n\n*${symbol}* on my radar — `{mc}` MC\n\nliq holding strong at `{liq}`, vol building\n\nCA:\n`{ca}`",

    "📡 scanner flagged *${symbol}*\n\n`{mc}` MC. clean structure. liq `{liq}`\n\nnot posted anywhere else yet. move fast.\n\n`{ca}`\n{dex_url}",

    "i only share the ones i'm actually in\n\n*{name}* — `{mc}` MC entry\nLiq `{liq}` | Vol `{vol}`\n\nCA below:\n`{ca}`",

    "🐋 wallet activity flagged *${symbol}*\n\nentry `{mc}` — before any push\nliq confirmed: `{liq}`\n\n`{ca}`\n{dex_url}",

    "this one hasn't been posted anywhere 👀\n\n*${symbol}* — `{mc}` MC\nLiq `{liq}` / Vol `{vol}`\n\n`{ca}`",
]

UPDATE_TEMPLATES = [
    "🟢 *${symbol}* — *{gain_str}*\n\ncalled at `{entry_mc}` → now `{current_mc}`\n{time_str} in the trade\n\nthis is why we move early\n\n`{ca}`",

    "we printed 💰\n\n*{name}* — *{gain_str}* from entry\n\nin at `{entry_mc}`, sitting at `{current_mc}` now\n{time_str} hold. clean.\n\n`{ca}`\n{dex_url}",

    "scoreboard update 📋\n\n*${symbol}* — *{gain_str}*\nentry `{entry_mc}` → `{current_mc}`\ntime: {time_str}\n\n`{ca}`",

    "🏆 *{name}* doing what we thought\n\n*{gain_str}* since our call\ncalled at `{entry_mc}` | now `{current_mc}`\n\n`{ca}`\n{dex_url}",

    "the members who followed this call are very happy rn\n\n*${symbol}* — *{gain_str}*\ncalled at `{entry_mc}` → `{current_mc}` now\n{time_str}\n\n`{ca}`",

    "💎 *${symbol}* — *{gain_str}*\n\nentry `{entry_mc}` → `{current_mc}`\ntime in: {time_str} | liq: `{liq}`\n\npatience + early entry. always.\n\n`{ca}`\n{dex_url}",

    "another W for the circle 🎯\n\n*{name}* — *{gain_str}*\nfrom `{entry_mc}` to `{current_mc}`\n{time_str}\n\n`{ca}`",

    "called it at `{entry_mc}` and here we are 🔥\n\n*${symbol}* — *{gain_str}*\nnow at `{current_mc}`\n\nVIP group was in before CT even heard the name\n\n`{ca}`\n{dex_url}",

    "imagine not being in this circle rn 😭\n\n*{name}* — *{gain_str}*\ncalled at `{entry_mc}` → `{current_mc}` now\n{time_str} hold\n\n`{ca}`",

    "🐋 *${symbol}* running exactly like we said\n\n*{gain_str}* | in at `{entry_mc}` → `{current_mc}`\nliq still holding: `{liq}`\n\n`{ca}`\n{dex_url}",
]

# ─── Forex / macro signal data ─────────────────────────────────────────────────

FOREX_SIGNALS = [
    {
        "pair": "EUR/USD", "direction": "LONG", "timeframe": "4H",
        "entry": "1.0840 – 1.0860", "tp1": "1.0940", "tp2": "1.1025",
        "sl": "1.0785", "rr": "2.7:1",
        "analysis": "DXY rejection at key resistance. EUR flow bias bullish ahead of ECB commentary. Strong demand zone at entry.",
    },
    {
        "pair": "GBP/USD", "direction": "LONG", "timeframe": "H4",
        "entry": "1.2660 – 1.2690", "tp1": "1.2780", "tp2": "1.2880",
        "sl": "1.2600", "rr": "2.1:1",
        "analysis": "Cable holding above key structural support. BoE hawkish pivot narrative supporting GBP bids.",
    },
    {
        "pair": "USD/JPY", "direction": "SHORT", "timeframe": "Daily",
        "entry": "154.80 – 155.20", "tp1": "152.50", "tp2": "150.00",
        "sl": "156.40", "rr": "3.1:1",
        "analysis": "BoJ intervention risk elevated at 155+. Risk-off flow incoming. Clean short from upper range.",
    },
    {
        "pair": "XAU/USD", "direction": "LONG", "timeframe": "H4",
        "entry": "$3,080 – $3,095", "tp1": "$3,160", "tp2": "$3,250",
        "sl": "$3,040", "rr": "2.5:1",
        "analysis": "Gold reclaiming ATH structure. Macro uncertainty + central bank accumulation = sustained bid.",
    },
    {
        "pair": "BTC/USDT", "direction": "LONG", "timeframe": "4H/Daily",
        "entry": "$82,400 – $83,200", "tp1": "$87,500", "tp2": "$93,000",
        "sl": "$79,800", "rr": "3.2:1",
        "analysis": "HTF demand respected. Accumulation pattern confirmed on 4H. Spot ETF inflows accelerating.",
    },
    {
        "pair": "ETH/USDT", "direction": "LONG", "timeframe": "4H",
        "entry": "$1,580 – $1,620", "tp1": "$1,780", "tp2": "$1,950",
        "sl": "$1,490", "rr": "2.4:1",
        "analysis": "ETH printing higher lows vs BTC. Pectra upgrade narrative building. Risk/reward favours longs here.",
    },
    {
        "pair": "SOL/USDT", "direction": "LONG", "timeframe": "4H",
        "entry": "$128 – $134", "tp1": "$158", "tp2": "$185",
        "sl": "$118", "rr": "2.9:1",
        "analysis": "SOL showing relative strength. DEX volume at highs. Institutional accumulation visible on-chain.",
    },
    {
        "pair": "GBP/JPY", "direction": "SHORT", "timeframe": "H4",
        "entry": "195.50 – 196.00", "tp1": "193.20", "tp2": "191.00",
        "sl": "197.20", "rr": "2.3:1",
        "analysis": "Risk-off tone. JPY strength + GBP weakness at resistance confluence. Clean R:R.",
    },
    {
        "pair": "AUD/USD", "direction": "SHORT", "timeframe": "H4",
        "entry": "0.6380 – 0.6400", "tp1": "0.6290", "tp2": "0.6210",
        "sl": "0.6450", "rr": "2.2:1",
        "analysis": "China PMI miss weighing on AUD. RBA dovish tone. Break of demand signals continuation lower.",
    },
    {
        "pair": "USD/CHF", "direction": "SHORT", "timeframe": "Daily",
        "entry": "0.9020 – 0.9050", "tp1": "0.8900", "tp2": "0.8780",
        "sl": "0.9120", "rr": "2.6:1",
        "analysis": "SNB holding reserves. Risk-off CHF bid. Clean break below key level = trend continuation.",
    },
]

FOREX_CAPTION_TEMPLATES = [
    "🎯 *SIGNAL | {pair}*\n\n📊 Bias: *{direction}*\n⏱ Timeframe: `{timeframe}`\n\n🎯 Entry Zone: `{entry}`\n✅ TP1: `{tp1}`\n✅ TP2: `{tp2}`\n❌ SL: `{sl}`\n📐 R/R: `{rr}`\n\n💡 _{analysis}_\n\n🔐 Live position updates in VIP group",

    "📡 *ALPHA SIGNAL — {pair}*\n\n*{direction}* | `{timeframe}`\n\nEntry: `{entry}`\nTP1: `{tp1}` | TP2: `{tp2}`\nSL: `{sl}`\nRisk/Reward: `{rr}`\n\n_{analysis}_\n\n🔐 Full trade management inside VIP",

    "🐋 *WHALE DESK | {pair}*\n\n{direction} SETUP | `{timeframe}`\n\n▶ Entry: `{entry}`\n▶ Target 1: `{tp1}`\n▶ Target 2: `{tp2}`\n▶ Stop: `{sl}`\n▶ R/R: `{rr}`\n\n_{analysis}_",

    "📊 *TRADE IDEA — {pair}*\n\nDirection: *{direction}*\nTF: `{timeframe}` | R/R: `{rr}`\n\nEntry: `{entry}`\nTP1: `{tp1}` → TP2: `{tp2}`\nStop: `{sl}`\n\n💡 _{analysis}_\n\n🔐 Managed in real-time inside VIP",
]

# ─── VIP promo (standalone channel post) ──────────────────────────────────────

VIP_PROMOS = [
    "🔐 *Alpha VIP — Now Open*\n\nIf you're watching this channel, you're seeing the public results.\n\nThe *live setups, pre-call entries, on-chain alerts, and real-time position updates* are inside the VIP group.\n\nOne call covers the membership.\n\nAccess below 👇",
    "💎 *Premium Intelligence. Serious Traders Only.*\n\nThis channel posts results.\nThe VIP group posts the setups *before* the move.\n\n• Crypto alpha (pre-DEX)\n• Forex & macro signals\n• Whale wallet alerts\n• On-chain flow reads\n\nIf you're serious about edges — the group is below 👇",
    "🎯 *Everything you see here started inside the VIP group.*\n\nThe entries. The timing. The analysis.\n\nThe public channel is the scoreboard.\nThe group is where the game is played.\n\nAccess via crypto payment. Link below 👇",
    "📡 *Our signal record speaks for itself.*\n\nWe don't post losses here because we manage them live inside.\n\nVIP members get:\n✅ Real-time entry alerts\n✅ SL management\n✅ Forex + crypto daily setups\n✅ On-chain whale flow\n\nJoin below 👇",
]


# ─── Utility ───────────────────────────────────────────────────────────────────

def _fmt_time(s: float) -> str:
    if s < 60:   return f"{int(s)}s"
    if s < 3600: return f"{int(s//60)}m"
    return f"{int(s//3600)}h {int((s%3600)//60)}m"


def _gain_str(pct: float) -> str:
    mult = pct / 100 + 1
    if mult >= 2:
        return f"{mult:.1f}x"
    return f"+{pct:.0f}%"


def _mult_float(pct: float) -> float:
    return pct / 100 + 1


# ─── Health server (Render keep-alive) ────────────────────────────────────────

class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b"OK - Alpha Circle Bot running")
    def log_message(self, *_): pass


def _start_health_server():
    for port in [PORT, 10000, 8080, 3000]:
        try:
            srv = HTTPServer(("0.0.0.0", port), _Health)
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            log.info(f"✅ Health server on :{port}")
            return
        except OSError:
            continue
    log.warning("⚠️  Health server could not bind to any port")


def _self_ping_loop():
    import requests as _req
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        return
    ping_url = url + "/health"
    log.info(f"🏓 Self-ping → {ping_url}")
    while True:
        time.sleep(13 * 60)
        try:
            _req.get(ping_url, timeout=15)
        except Exception as e:
            log.warning(f"Self-ping failed: {e}")


def _start_self_ping():
    threading.Thread(target=_self_ping_loop, daemon=True, name="self-ping").start()


# ─── Telegram send helpers ─────────────────────────────────────────────────────

last_sent_time: float = 0.0


async def _throttle():
    global last_sent_time
    gap     = random.uniform(SEND_INTERVAL_MIN, SEND_INTERVAL_MAX)
    elapsed = time.time() - last_sent_time
    if elapsed < gap:
        await asyncio.sleep(gap - elapsed)


async def _send_photo(bot: Bot, photo: bytes, caption: str,
                      reply_markup=None) -> bool:
    for attempt in range(4):
        try:
            await bot.send_photo(
                chat_id=CHAT_ID,
                photo=BytesIO(photo),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramError as e:
            msg = str(e)
            if "Peer_id_invalid" in msg or "chat not found" in msg.lower():
                log.error("❌ Bot not in channel — add bot as admin")
                return False
            log.warning(f"TG error #{attempt+1}: {e}")
            await asyncio.sleep(6 * (attempt + 1))
        except Exception as e:
            log.warning(f"Send error #{attempt+1}: {e}")
            await asyncio.sleep(5)
    return False


async def _send_text(bot: Bot, text: str, reply_markup=None) -> bool:
    for attempt in range(4):
        try:
            await bot.send_message(
                chat_id=CHAT_ID, text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramError as e:
            msg = str(e)
            if "Peer_id_invalid" in msg or "chat not found" in msg.lower():
                log.error("❌ Bot not in channel")
                return False
            log.warning(f"TG error #{attempt+1}: {e}")
            await asyncio.sleep(6 * (attempt + 1))
        except Exception as e:
            log.warning(f"Send error #{attempt+1}: {e}")
            await asyncio.sleep(5)
    return False


# ─── Send: initial DEX call ───────────────────────────────────────────────────

async def send_initial_call(bot: Bot, token: dict, bot_username: str = ""):
    global last_sent_time
    await _throttle()

    mc      = token.get("market_cap", 0)
    liq     = token.get("liquidity_usd", 0)
    vol     = token.get("volume_24h", 0)
    ca      = token.get("address", "")
    name    = token.get("name", token.get("symbol", "???"))
    symbol  = token.get("symbol", "???")
    dex_url = token.get("url") or f"https://dexscreener.com/solana/{ca}"
    chain   = token.get("chain", "SOL").upper()

    caption = random.choice(CALL_TEMPLATES).format(
        name=name, symbol=symbol,
        mc=format_mc(mc), liq=format_mc(liq), vol=format_mc(vol),
        ca=ca, dex_url=dex_url
    )

    # 50% of calls show the VIP button
    markup = _join_button() if random.random() < 0.50 else None

    card = None
    try:
        card = build_call_card(
            symbol=symbol,
            mcap_str=format_mc(mc),
            liq_str=format_mc(liq),
            vol_str=format_mc(vol),
            chain=chain,
            username=bot_username or "alpha_circle1",
        )
    except Exception as e:
        log.warning(f"Call card error: {e}")

    sent = False
    if card:
        sent = await _send_photo(bot, card, caption, reply_markup=markup)
    else:
        sent = await _send_text(bot, caption, reply_markup=markup)

    if sent:
        last_sent_time = time.time()
        log.info(f"✅ Call: {symbol}  MC={format_mc(mc)}")


# ─── Send: gain update ────────────────────────────────────────────────────────

async def send_gain_update(bot: Bot, token: dict,
                           entry_mc: float, gain_pct: float,
                           entry_mc_str: str, bot_username: str = ""):
    global last_sent_time
    await _throttle()

    mc      = token.get("market_cap", 0)
    liq     = token.get("liquidity_usd", 0)
    ca      = token.get("address", "")
    name    = token.get("name", token.get("symbol", "???"))
    symbol  = token.get("symbol", "???")
    dex_url = token.get("url") or f"https://dexscreener.com/solana/{ca}"
    elapsed = time.time() - tracked_coins.get(ca, {}).get("first_seen", time.time())
    gain_s  = _gain_str(gain_pct)
    mult    = _mult_float(gain_pct)

    caption = random.choice(UPDATE_TEMPLATES).format(
        name=name, symbol=symbol,
        entry_mc=entry_mc_str, current_mc=format_mc(mc),
        gain_str=gain_s, liq=format_mc(liq),
        ca=ca, dex_url=dex_url, time_str=_fmt_time(elapsed)
    )

    # 100% of update posts get the double VIP button — this is how people join
    markup = _join_button_double()

    card = None
    try:
        card = build_update_card(
            symbol=symbol,
            multiplier=mult,
            mcap_str=entry_mc_str,
            time_str=_fmt_time(elapsed),
            username=bot_username or "alpha_circle1",
        )
    except Exception as e:
        log.warning(f"Update card error: {e}")

    sent = False
    if card:
        sent = await _send_photo(bot, card, caption, reply_markup=markup)
    else:
        sent = await _send_text(bot, caption, reply_markup=markup)

    if sent:
        last_sent_time = time.time()
        log.info(f"✅ Update: {symbol}  {gain_s}")


# ─── Send: forex / macro signal ───────────────────────────────────────────────

async def send_forex_signal(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    bot_username = context.job.data.get("bot_username", "alpha_circle1")

    sig = random.choice(FOREX_SIGNALS)
    caption = random.choice(FOREX_CAPTION_TEMPLATES).format(**sig)

    # Always show VIP button on forex signals
    markup = _join_button_double()

    card = None
    try:
        card = build_forex_card(
            pair=sig["pair"],
            direction=sig["direction"],
            entry=sig["entry"],
            tp1=sig["tp1"],
            tp2=sig["tp2"],
            sl=sig["sl"],
            timeframe=sig["timeframe"],
            rr=sig["rr"],
            username=bot_username,
        )
    except Exception as e:
        log.warning(f"Forex card error: {e}")

    if card:
        await _send_photo(bot, card, caption, reply_markup=markup)
    else:
        await _send_text(bot, caption, reply_markup=markup)

    log.info(f"📡 Forex signal sent: {sig['pair']} {sig['direction']}")


# ─── Send: VIP promo post ──────────────────────────────────────────────────────

async def send_vip_promo(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    text = random.choice(VIP_PROMOS)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔐 Get VIP Access — $49/mo", url=_pay_url())
    ], [
        InlineKeyboardButton("$75 lifetime access →", url=_pay_url())
    ]])
    await _send_text(bot, text, reply_markup=markup)
    log.info("📢 VIP promo post sent")


# ─── DEX scanner loop ─────────────────────────────────────────────────────────

async def scan_and_send(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    bot_username = context.job.data.get("bot_username", "")

    log.info("🔍 Scanning DEX Screener...")
    try:
        new_coins = fetch_new_coins("solana", MIN_MC, MAX_MC)
        trending  = fetch_trending_tokens("solana")
        all_tokens = {t["address"]: t for t in (new_coins + trending)
                      if t.get("address")}
    except Exception as e:
        log.error(f"Fetch error: {e}")
        return

    for ca, token in all_tokens.items():
        mc = token.get("market_cap", 0)
        if not ca or not (MIN_MC <= mc <= MAX_MC):
            continue

        if ca not in tracked_coins:
            tracked_coins[ca] = {
                "token":        token,
                "entry_mc":     mc,
                "entry_mc_str": format_mc(mc),
                "first_seen":   time.time(),
            }
            await send_initial_call(bot, token, bot_username)
            await asyncio.sleep(random.uniform(8, 20))
            continue

        entry_mc = tracked_coins[ca]["entry_mc"]
        if entry_mc <= 0:
            continue

        gain_pct = ((mc - entry_mc) / entry_mc) * 100
        done = sent_updates.get(ca, [])
        for threshold in [20, 50, 100, 200, 300, 500, 1000]:
            if gain_pct >= threshold and threshold not in done:
                await send_gain_update(
                    bot, token, entry_mc, gain_pct,
                    tracked_coins[ca]["entry_mc_str"],
                    bot_username=bot_username
                )
                sent_updates.setdefault(ca, []).append(threshold)
                await asyncio.sleep(random.uniform(5, 12))
                break

        tracked_coins[ca]["token"] = token

    cutoff = time.time() - 86400 * 3
    for ca in [k for k, v in tracked_coins.items()
               if v.get("first_seen", 0) < cutoff]:
        tracked_coins.pop(ca, None)
        sent_updates.pop(ca, None)


# ─── Post-init (register jobs) ────────────────────────────────────────────────

async def post_init(application: Application):
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username or ""
    log.info(f"✅ Connected as @{BOT_USERNAME}")

    jq = application.job_queue

    # DEX scanner — every 3 min
    jq.run_repeating(
        scan_and_send,
        interval=SCAN_INTERVAL,
        first=15,
        data={"bot_username": BOT_USERNAME},
        name="dex-scanner",
    )

    # Forex / macro signals — every ~4-5 hours with slight jitter
    jq.run_repeating(
        send_forex_signal,
        interval=random.randint(14400, 18000),   # 4–5 h
        first=random.randint(600, 1200),          # 10–20 min after start
        data={"bot_username": BOT_USERNAME},
        name="forex-signals",
    )

    # VIP promo post — every ~7 hours
    jq.run_repeating(
        send_vip_promo,
        interval=random.randint(21600, 28800),   # 6–8 h
        first=random.randint(1800, 3600),         # 30–60 min after start
        data={},
        name="vip-promo",
    )


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    log.info("🚀 Alpha Circle Bot starting...")
    _start_health_server()
    _start_self_ping()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(build_payment_conversation())

    log.info("📡 Polling started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
