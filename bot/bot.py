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
from image_generator import build_update_card, build_call_card, build_forex_card, random_pnl
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

MIN_MC            = float(os.getenv("MIN_MC",           10_000))
MAX_MC            = float(os.getenv("MAX_MC",          800_000))
SCAN_INTERVAL     = int(os.getenv("SCAN_INTERVAL",         180))
SEND_INTERVAL_MIN = int(os.getenv("SEND_INTERVAL_MIN",     120))
SEND_INTERVAL_MAX = int(os.getenv("SEND_INTERVAL_MAX",     180))
PORT              = int(os.getenv("PORT",                10000))
BOT_USERNAME      = os.getenv("BOT_USERNAME", "dextrendiing_bot")

tracked_coins:  dict  = {}
sent_updates:   dict  = {}
last_sent_time: float = 0.0

VIP_LINK = "https://t.me/+b7UesS3ulxxlZDdk"


# ── VIP keyboard buttons ───────────────────────────────────────────────────────

def _pay_url() -> str:
    return f"https://t.me/{BOT_USERNAME}?start=vip" if BOT_USERNAME else VIP_LINK

def _join_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ GET VIP ACCESS ⭐", url=_pay_url()),
    ]])

def _join_button_double() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ GET VIP ACCESS ⭐",   url=_pay_url()),
    ], [
        InlineKeyboardButton("📊 100x Results",          url=VIP_LINK),
    ]])


# ── Call caption templates ─────────────────────────────────────────────────────

CALL_TEMPLATES = [
    "💸 *NEW CALL*\n\nSOL / *${symbol}*\n\n💎 Mcap : {mc} MC\n\n🌐 CA :\n`{ca}`",

    "💸 *N E W C A L L*\n\nSOL / *${symbol}*\n\n💎 Mcap : {mc} MC\n\n🌐 CA :\n`{ca}`",

    "🟢 caught *${symbol}* early\n\n`{mc}` MC — liq `{liq}`, vol picking: `{vol}`\n\nCA 👇\n`{ca}`",

    "📡 *${symbol}* before the narrative\n\n`{mc}` MC | liq `{liq}`\n\nnot on CT yet. move.\n\n`{ca}`",

    "🔔 *${symbol}*\n\ncaught at `{mc}` — early entry window\nvol `{vol}` building\n\n`{ca}`",

    "i keep finding these before CT 👀\n\n*${symbol}* — `{mc}` MC\nliq `{liq}` | vol `{vol}`\n\n`{ca}`",

    "⚡ insider alert\n\n*${symbol}* — `{mc}` MC\nsmart wallets entering\n\n`{ca}`",

    "🐋 whale wallet flagged *${symbol}*\n\n`{mc}` MC | liq `{liq}` | vol `{vol}`\n\ndon't sleep\n\n`{ca}`",

    "🔑 early position: *${symbol}*\n\nMC `{mc}` | liq `{liq}` | vol `{vol}`\nentry window open\n\n`{ca}`",
]

UPDATE_TEMPLATES = [
    (
        "*${symbol}* REACHED 💰\n"
        "{gain_str} 💰 AFTER VIP SIGNAL\n\n"
        "💰 {gain_str} From Call!\n\n"
        "🏠 MCap: `{entry_mc}` → `{current_mc}`\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "📈 *{gain_str}* on *${symbol}*\n\n"
        "🏠 Called: `{entry_mc}` → Now: `{current_mc}`\n"
        "⏱ {time_str} since entry\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "W 🏆\n\n"
        "*${symbol}* — *{gain_str}*\n"
        "in at `{entry_mc}` · now `{current_mc}`\n"
        "{time_str}\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "bro 😭\n\n"
        "*${symbol}* just hit *{gain_str}*\n"
        "called at `{entry_mc}` → now `{current_mc}`\n"
        "{time_str} hold\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "this is exactly why you don't sell early 💎\n\n"
        "*${symbol}* *{gain_str}*\n"
        "called at `{entry_mc}` · sitting `{current_mc}`\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "⚡ *${symbol}* running\n\n"
        "*{gain_str}* from our entry\n"
        "`{entry_mc}` → `{current_mc}` in {time_str}\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "another one for the record 🎯\n\n"
        "*${symbol}* — *{gain_str}*\n"
        "`{entry_mc}` → `{current_mc}`\n"
        "{time_str}\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
    (
        "not every call does this. this one did. 🔥\n\n"
        "*${symbol}* — *{gain_str}*\n"
        "`{entry_mc}` → `{current_mc}` · {time_str}\n\n"
        "CA:\n`{ca}`\n\n"
        "{pnl}"
    ),
]


# ── Forex / macro data ─────────────────────────────────────────────────────────

FOREX_SIGNALS = [
    {"pair": "EUR/USD", "direction": "LONG",  "timeframe": "4H",
     "entry": "1.0840 – 1.0860", "tp1": "1.0940", "tp2": "1.1025",
     "sl": "1.0785", "rr": "2.7:1",
     "analysis": "DXY rejection at key resistance. EUR flow bias bullish ahead of ECB commentary."},
    {"pair": "GBP/USD", "direction": "LONG",  "timeframe": "H4",
     "entry": "1.2660 – 1.2690", "tp1": "1.2780", "tp2": "1.2880",
     "sl": "1.2600", "rr": "2.1:1",
     "analysis": "Cable holding above key structural support. BoE hawkish pivot narrative."},
    {"pair": "USD/JPY", "direction": "SHORT", "timeframe": "Daily",
     "entry": "154.80 – 155.20", "tp1": "152.50", "tp2": "150.00",
     "sl": "156.40", "rr": "3.1:1",
     "analysis": "BoJ intervention risk elevated at 155+. Risk-off flow incoming."},
    {"pair": "XAU/USD", "direction": "LONG",  "timeframe": "H4",
     "entry": "$3,080 – $3,095", "tp1": "$3,160", "tp2": "$3,250",
     "sl": "$3,040", "rr": "2.5:1",
     "analysis": "Gold reclaiming ATH structure. Macro uncertainty + central bank accumulation."},
    {"pair": "BTC/USDT", "direction": "LONG", "timeframe": "4H/Daily",
     "entry": "$82,400 – $83,200", "tp1": "$87,500", "tp2": "$93,000",
     "sl": "$79,800", "rr": "3.2:1",
     "analysis": "HTF demand respected. Accumulation pattern confirmed on 4H. Spot ETF inflows accelerating."},
    {"pair": "ETH/USDT", "direction": "LONG", "timeframe": "4H",
     "entry": "$1,580 – $1,620", "tp1": "$1,780", "tp2": "$1,950",
     "sl": "$1,490", "rr": "2.4:1",
     "analysis": "ETH printing higher lows vs BTC. Pectra upgrade narrative building."},
    {"pair": "SOL/USDT", "direction": "LONG", "timeframe": "4H",
     "entry": "$128 – $134", "tp1": "$158", "tp2": "$185",
     "sl": "$118", "rr": "2.9:1",
     "analysis": "SOL showing relative strength. DEX volume at highs. Institutional accumulation visible on-chain."},
    {"pair": "GBP/JPY", "direction": "SHORT", "timeframe": "H4",
     "entry": "195.50 – 196.00", "tp1": "193.20", "tp2": "191.00",
     "sl": "197.20", "rr": "2.3:1",
     "analysis": "Risk-off tone. JPY strength + GBP weakness at resistance confluence."},
    {"pair": "AUD/USD", "direction": "SHORT", "timeframe": "H4",
     "entry": "0.6380 – 0.6400", "tp1": "0.6290", "tp2": "0.6210",
     "sl": "0.6450", "rr": "2.2:1",
     "analysis": "China PMI miss weighing on AUD. RBA dovish tone."},
    {"pair": "USD/CHF", "direction": "SHORT", "timeframe": "Daily",
     "entry": "0.9020 – 0.9050", "tp1": "0.8900", "tp2": "0.8780",
     "sl": "0.9120", "rr": "2.6:1",
     "analysis": "SNB holding reserves. Risk-off CHF bid. Clean break below key level."},
]

FOREX_CAPTIONS = [
    "🎯 *{pair} — {direction}*\n\n`{timeframe}` setup | R/R `{rr}`\n\nEntry: `{entry}`\n✅ TP1: `{tp1}`\n✅ TP2: `{tp2}`\n❌ SL: `{sl}`\n\n_{analysis}_\n\n🔐 real-time management inside VIP",
    "📡 *SIGNAL | {pair}*\n\n{direction} | `{timeframe}` | R/R `{rr}`\n\nZone: `{entry}`\nTP1 `{tp1}` · TP2 `{tp2}`\nSL `{sl}`\n\n_{analysis}_",
    "🐋 *{pair}* setup ready\n\nbias: *{direction}* | tf: `{timeframe}`\n\n▸ entry: `{entry}`\n▸ tp1: `{tp1}` → tp2: `{tp2}`\n▸ stop: `{sl}`\n▸ r/r: `{rr}`\n\n_{analysis}_\n\n🔐 active inside VIP",
    "macro desk 📊\n\n*{pair} — {direction}*\n`{timeframe}` | `{rr}` R/R\n\nentry `{entry}`\nTP `{tp1}` / `{tp2}` · SL `{sl}`\n\n_{analysis}_",
    "⚡ *{pair}*\n\n{direction} setup triggered · `{timeframe}`\n\n`{entry}` zone\nTP1 `{tp1}` · TP2 `{tp2}`\nSL `{sl}` · R/R `{rr}`\n\n_{analysis}_",
]

VIP_PROMOS = [
    "🔐 *Alpha_X_Calls VIP — Now Open*\n\nThis channel shows results.\n\nThe *live entries, pre-call alerts, on-chain whale moves, and real-time management* happen inside VIP before anything is posted here.\n\nOne trade covers the membership.\n\nJoin below 👇",
    "💎 *Serious traders only.*\n\nPublic channel = scoreboard\nVIP group = where the money is made\n\n✅ Meme alpha — pre-CT\n✅ Forex & macro signals\n✅ Whale wallet monitoring\n✅ Real-time position updates\n\n👇",
    "📊 *The setups you've seen hit — they were posted in VIP first.*\n\nEvery entry. Every exit. Every SL move.\n\nThe public channel gets the result.\nVIP gets the trade.\n\nAccess via SOL / crypto payment. Link below 👇",
    "⚡ *Alpha_X_Calls VIP — What You're Missing*\n\nMeme calls before they 10x\nForex signals with full TP/SL management\nWhale wallet alerts before CT wakes up\n\nAll inside. Daily.\n\nJoin below 👇",
    "🎯 *Why join VIP?*\n\nBecause by the time it's posted here, early buyers are already up.\n\nVIP members enter before the public call.\nThat edge is worth more than the membership.\n\n$49/month or $75 lifetime 👇",
    "🐋 *VIP group is small on purpose.*\n\nSmaller group = less slippage = better entries.\n\nIf you're reading this, there's still a spot.\n\nJoin 👇",
]


# ── Utilities ─────────────────────────────────────────────────────────────────

def _fmt_time(s: float) -> str:
    if s < 60:   return f"{int(s)}s"
    if s < 3600: return f"{int(s // 60)}m"
    return f"{int(s // 3600)}h {int((s % 3600) // 60)}m"

def _gain_str(pct: float) -> str:
    mult = pct / 100 + 1
    return f"{mult:.1f}x" if mult >= 2 else f"+{pct:.0f}%"

def _mult_float(pct: float) -> float:
    return pct / 100 + 1


# ── Health server ──────────────────────────────────────────────────────────────

class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b"OK - Alpha_X_Calls Bot running")
    def log_message(self, *_): pass

def _start_health_server():
    for port in [PORT, 10000, 8080, 3000, 5000]:
        try:
            srv = HTTPServer(("0.0.0.0", port), _Health)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            log.info(f"✅ Health server on :{port}")
            return
        except OSError:
            continue
    log.warning("⚠️  Health server could not bind to any port")


# ── Self-ping (Render + UptimeRobot keep-alive) ────────────────────────────────

def _self_ping_loop():
    import requests as _req
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        log.info("No RENDER_EXTERNAL_URL set — self-ping disabled")
        return
    ping_url = url + "/health"
    log.info(f"🏓 Self-ping active → {ping_url} (every 13 min)")
    while True:
        time.sleep(13 * 60)
        try:
            r = _req.get(ping_url, timeout=20)
            log.info(f"🏓 Self-ping OK ({r.status_code})")
        except Exception as e:
            log.warning(f"Self-ping failed: {e}")

def _start_self_ping():
    threading.Thread(target=_self_ping_loop, daemon=True, name="self-ping").start()


# ── Send helpers ───────────────────────────────────────────────────────────────

async def _throttle():
    global last_sent_time
    gap     = random.uniform(SEND_INTERVAL_MIN, SEND_INTERVAL_MAX)
    elapsed = time.time() - last_sent_time
    if elapsed < gap:
        await asyncio.sleep(gap - elapsed)

async def _send_photo(bot: Bot, photo: bytes, caption: str, reply_markup=None) -> bool:
    for attempt in range(4):
        try:
            await bot.send_photo(
                chat_id=CHAT_ID, photo=BytesIO(photo),
                caption=caption, parse_mode=ParseMode.MARKDOWN,
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
            log.warning(f"TG error #{attempt + 1}: {e}")
            await asyncio.sleep(6 * (attempt + 1))
        except Exception as e:
            log.warning(f"Send error #{attempt + 1}: {e}")
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
            log.warning(f"TG error #{attempt + 1}: {e}")
            await asyncio.sleep(6 * (attempt + 1))
        except Exception as e:
            log.warning(f"Send error #{attempt + 1}: {e}")
            await asyncio.sleep(5)
    return False


# ── Send: initial DEX call ────────────────────────────────────────────────────

async def send_initial_call(bot: Bot, token: dict, bot_username: str = ""):
    global last_sent_time
    await _throttle()

    mc      = token.get("market_cap", 0)
    liq     = token.get("liquidity_usd", 0)
    vol     = token.get("volume_24h", 0)
    ca      = token.get("address", "")
    name    = token.get("name", token.get("symbol", "???"))
    symbol  = token.get("symbol", "???")
    chain   = token.get("chain", "SOL").upper()

    caption = random.choice(CALL_TEMPLATES).format(
        name=name, symbol=symbol,
        mc=format_mc(mc), liq=format_mc(liq), vol=format_mc(vol),
        ca=ca,
    )

    markup = _join_button() if random.random() < 0.50 else None
    card   = None
    try:
        card = build_call_card(
            symbol=symbol, mcap_str=format_mc(mc),
            liq_str=format_mc(liq), vol_str=format_mc(vol),
            chain=chain,
        )
    except Exception as e:
        log.warning(f"Call card error: {e}")

    sent = await _send_photo(bot, card, caption, reply_markup=markup) if card \
        else await _send_text(bot, caption, reply_markup=markup)

    if sent:
        last_sent_time = time.time()
        log.info(f"✅ Call: {symbol}  MC={format_mc(mc)}")


# ── Send: gain update ──────────────────────────────────────────────────────────

async def send_gain_update(bot: Bot, token: dict, entry_mc: float,
                           gain_pct: float, entry_mc_str: str,
                           bot_username: str = ""):
    global last_sent_time
    await _throttle()

    mc       = token.get("market_cap", 0)
    ca       = token.get("address", "")
    symbol   = token.get("symbol", "???")
    elapsed  = time.time() - tracked_coins.get(ca, {}).get("first_seen", time.time())
    gain_s   = _gain_str(gain_pct)
    mult     = _mult_float(gain_pct)
    pnl_text = random_pnl(mult)

    caption = random.choice(UPDATE_TEMPLATES).format(
        symbol=symbol, entry_mc=entry_mc_str,
        current_mc=format_mc(mc), gain_str=gain_s,
        ca=ca, time_str=_fmt_time(elapsed), pnl=pnl_text,
    )

    markup = _join_button_double()
    card   = None
    try:
        card = build_update_card(
            symbol=symbol, multiplier=mult,
            mcap_str=entry_mc_str, time_str=_fmt_time(elapsed),
        )
    except Exception as e:
        log.warning(f"Update card error: {e}")

    sent = await _send_photo(bot, card, caption, reply_markup=markup) if card \
        else await _send_text(bot, caption, reply_markup=markup)

    if sent:
        last_sent_time = time.time()
        log.info(f"✅ Update: {symbol}  {gain_s}")


# ── Send: forex signal ────────────────────────────────────────────────────────

async def send_forex_signal(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    sig      = random.choice(FOREX_SIGNALS)
    caption  = random.choice(FOREX_CAPTIONS).format(**sig)
    markup   = _join_button_double()
    card     = None
    try:
        card = build_forex_card(
            pair=sig["pair"], direction=sig["direction"],
            entry=sig["entry"], tp1=sig["tp1"], tp2=sig["tp2"],
            sl=sig["sl"], timeframe=sig["timeframe"], rr=sig["rr"],
        )
    except Exception as e:
        log.warning(f"Forex card error: {e}")

    if card:
        await _send_photo(bot, card, caption, reply_markup=markup)
    else:
        await _send_text(bot, caption, reply_markup=markup)
    log.info(f"📡 Forex signal: {sig['pair']} {sig['direction']}")


# ── Send: VIP promo post ──────────────────────────────────────────────────────

async def send_vip_promo(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    text  = random.choice(VIP_PROMOS)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ GET VIP ACCESS ⭐", url=_pay_url()),
    ], [
        InlineKeyboardButton("📊 100x Results",       url=VIP_LINK),
    ]])
    await _send_text(bot, text, reply_markup=markup)
    log.info("📢 VIP promo sent")


# ── DEX scanner loop ──────────────────────────────────────────────────────────

async def scan_and_send(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot

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
            await send_initial_call(bot, token)
            await asyncio.sleep(random.uniform(8, 20))
            continue

        entry_mc = tracked_coins[ca]["entry_mc"]
        if entry_mc <= 0:
            continue

        gain_pct = ((mc - entry_mc) / entry_mc) * 100
        done     = sent_updates.get(ca, [])
        for threshold in [20, 50, 100, 200, 300, 500, 1000]:
            if gain_pct >= threshold and threshold not in done:
                await send_gain_update(
                    bot, token, entry_mc, gain_pct,
                    tracked_coins[ca]["entry_mc_str"],
                )
                sent_updates.setdefault(ca, []).append(threshold)
                await asyncio.sleep(random.uniform(5, 12))
                break

        tracked_coins[ca]["token"] = token

    # Prune old coins
    cutoff = time.time() - 86400 * 3
    for ca in [k for k, v in tracked_coins.items()
               if v.get("first_seen", 0) < cutoff]:
        tracked_coins.pop(ca, None)
        sent_updates.pop(ca, None)


# ── Post-init (register scheduled jobs) ──────────────────────────────────────

async def post_init(application: Application):
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username or BOT_USERNAME
    log.info(f"✅ Connected as @{BOT_USERNAME}")

    jq = application.job_queue

    # DEX scanner — every 3 min
    jq.run_repeating(scan_and_send,    interval=SCAN_INTERVAL,
                     first=15,         name="dex-scanner")

    # Forex signals — every 4–5 h
    jq.run_repeating(send_forex_signal, interval=random.randint(14400, 18000),
                     first=random.randint(600, 1200), name="forex-signals")

    # VIP promo — every 6–8 h
    jq.run_repeating(send_vip_promo,   interval=random.randint(21600, 28800),
                     first=random.randint(1800, 3600), name="vip-promo")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    log.info("🚀 Alpha_X_Calls Bot starting...")
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
