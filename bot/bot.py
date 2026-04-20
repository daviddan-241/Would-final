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
    CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

from dex_fetcher import (
    fetch_trending_tokens, fetch_new_coins, fetch_ohlcv_data, format_mc
)
from chart_generator import generate_chart_image
from image_generator import generate_kol_card, generate_initial_call_image
from payment_handler import build_payment_conversation, start

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
CHAT_ID           = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is not set. Please add it as a secret.")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID environment variable is not set. Please add it as a secret.")

MIN_MC            = float(os.getenv("MIN_MC",            10_000))
MAX_MC            = float(os.getenv("MAX_MC",           800_000))
SCAN_INTERVAL     = int(os.getenv("SCAN_INTERVAL",          180))
SEND_INTERVAL_MIN = int(os.getenv("SEND_INTERVAL_MIN",      120))
SEND_INTERVAL_MAX = int(os.getenv("SEND_INTERVAL_MAX",      180))
PORT              = int(os.getenv("PORT",                   8080))

BOT_USERNAME      = os.getenv("BOT_USERNAME", "")

tracked_coins: dict = {}
sent_updates:  dict = {}
last_sent_time: float = 0.0

# ─── KOL-style caption templates ──────────────────────────────────────────────

INITIAL_TEMPLATES = [
    "EARLY CA PLAY IS HERE!!\n\nINSANE TEAM IMO SENDS HARD FR\n\n*{name}* — CA 👇 tap to copy\n\n`{ca}`\n\nAPE IN NOW AND HOLD!\nwe are so early! Im adding A LOT here\nAnything under {mc} here is very good",
    "bro this one is different fr\n\n*${symbol}* just hit my radar and I fw it heavy\n\nMC only {mc} rn. liq solid at {liq}\nteam hasn't posted in main channel yet\n\nCA 👇\n`{ca}`\n\n{dex_url}",
    "Notis ON for this one 🔔\n\n*{name}* — very early, low cap, strong activity onchain\n\nMC: {mc}  |  Liq: {liq}\nVol: {vol}\n\nThis is the type of entry we dream about. CA below 👇\n\n`{ca}`",
    "Team is starting the push in next 5-10 minutes\n\nVery good entry here rn\n\n*${symbol}*\nMC: {mc} — anything under this is a steal imo\nLiq: {liq}  |  Vol: {vol}\n\n`{ca}`\n{dex_url}",
    "🔥 *{name}* — fresh find, not posted anywhere yet\n\nOnly {mc} MC. This is EARLY.\nLiquidity: {liq} | Volume: {vol}\n\nDyor but this is sitting in my bag rn\n\nCA 👇\n`{ca}`\n{dex_url}",
    "Private server early call 👇\n\n*${symbol}* — {mc} MC\n\nClean chart, volume picking up, team active\nLiq is {liq} — manageable size\n\nMove fast on these low caps\n\n`{ca}`",
    "⚡ we don't miss in this circle\n\n*{name}* added to watchlist — {mc} MC entry\n\nLiq: {liq}  •  Vol: {vol}\n\nThis is how we catch them before CT even knows\n\nCA:\n`{ca}`\n{dex_url}",
    "ngl this one has that feeling\n\n*${symbol}* — super early play on Solana\n\n{mc} MC right now. chart looks clean.\nLiq holding at {liq}\n\nbag it and watch 👀\n\n`{ca}`",
    "🎯 if you've been around, you know we don't miss\n\n*{name}* — caught at {mc} MC\nLiq: {liq}  |  Vol: {vol}\n\nThis is the type of entry that changes wallets\n\nCA 👇\n`{ca}`",
    "ser we are SO early on this one\n\n*${symbol}* just launched — {mc} MC entry\nVolume already climbing: {vol}\n\nDon't sleep on this\n\n`{ca}`\n{dex_url}",
    "Intel just hit the private group and I'm sharing it now\n\n*{name}* — entry at {mc}\nLiq: {liq} — healthy for this stage\n\nCA 👇\n`{ca}`",
    "🌕 moonshot or not, this entry is too clean to pass\n\n*${symbol}*\nMC: {mc}  |  Liq: {liq}\n\nJumping in heavy here, come join me\n\n`{ca}`\n{dex_url}",
]

UPDATE_TEMPLATES = [
    "We printed hard LFGGGG 💰🔥\n\n*{name}* called at {entry_mc} — it's a *{gain_str}* now 📈\n\nJust made too much money today, crazy play\n\nNotis ON, don't miss my next call, it's gonna be MASSIVE\n\n`{ca}`\n{dex_url}",
    "🚀 *${symbol}* is running exactly like I said\n\nCalled at {entry_mc} → now {current_mc}\nThat's *{gain_str}* in {time_str}\n\nThis is what happens when you move early with the right entries\nNo noise. Just calculated plays.\n\n`{ca}`",
    "Another solid win from the circle 📈\n\n*{name}* — *{gain_str}* from our entry\n\nEntry: {entry_mc}\nNow: {current_mc}  |  Liq: {liq}\n\nOne of the members just locked in serious profit on this call.\nThis is what happens when you move early with the right entries.\n\n`{ca}`\n{dex_url}",
    "👀 *${symbol}* doing exactly what we thought bro\n\nIn at {entry_mc}, sitting at {current_mc} now\n*{gain_str}* move — {time_str} since call\n\nwe don't miss in this circle fr\n\n`{ca}`",
    "*{gain_str}* on *{name}* 💰\n\nCalled it at {entry_mc}, now at {current_mc}\nLiquidity still healthy at {liq}\n\n{time_str} since the call. still watching, could push more\n\n`{ca}`\n{dex_url}",
    "locked in on *{name}* at {entry_mc}\nnow {current_mc} — that's *{gain_str}* 📊\n\n{time_str} since the call. this is what early entries look like\n\ndon't fade the circle\n\n`{ca}`",
    "🎯 *${symbol}* — *{gain_str}* return\n\nEntry MC: {entry_mc}\nCurrent MC: {current_mc}\nTime: {time_str}  |  Liq: {liq}\n\nwe move before the crowd. always.\n\n`{ca}`\n{dex_url}",
    "bro imagine not being in this circle rn 😭\n\n*{name}* just went *{gain_str}*\n\nCalled at {entry_mc} → {current_mc} now\n{time_str} hold. clean.\n\n`{ca}`",
    "called it at {entry_mc} and here we are 🔥\n\n*{name}* — *{gain_str}* from entry\nNow sitting at {current_mc}\n\nIntel group called this one early. the public saw it after.\n\n`{ca}`\n{dex_url}",
    "💎 this is why we don't sell early\n\n*${symbol}* — *{gain_str}*\n\nEntry {entry_mc} → Now {current_mc}\n{time_str} in\n\npatience + early entries = generational wealth\n\n`{ca}`",
    "the members who followed that call are very happy rn 😅\n\n*{name}* — *{gain_str}* from {entry_mc}\n\nwe don't miss bro\n\n`{ca}`\n{dex_url}",
    "🏆 scoreboard update\n\n*${symbol}* — *{gain_str}*\nIn: {entry_mc}  |  Now: {current_mc}\n\nThe intel group called this {time_str} ago. Public finding out now.\n\n`{ca}`",
]


def _fmt_time(s: float) -> str:
    if s < 60:   return f"{int(s)}s"
    if s < 3600: return f"{int(s//60)}m {int(s%60)}s"
    return f"{int(s//3600)}h {int((s%3600)//60)}m"


def _gain_str(pct: float) -> str:
    if pct >= 100: return f"{pct/100+1:.1f}X"
    return f"+{pct:.0f}%"


def _join_button(bot_username: str) -> InlineKeyboardMarkup | None:
    if not bot_username:
        return None
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🔥 Join Alpha VIP Group",
            url=f"https://t.me/{bot_username}?start=vip"
        )
    ]])


# ─── Health server ─────────────────────────────────────────────────────────────

class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b"OK - Alpha Circle Bot is alive")
    def log_message(self, *_):
        pass


def _start_health_server():
    for port in [PORT, 8080, 10000, 3000]:
        try:
            srv = HTTPServer(("0.0.0.0", port), _Health)
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            log.info(f"✅ Health server listening on port {port}")
            return
        except OSError:
            continue
    log.warning("Health server could not bind to any port")


def _self_ping_loop():
    import requests as _req
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        log.info("RENDER_EXTERNAL_URL not set — self-ping disabled")
        return
    ping_url = url + "/health"
    log.info(f"🏓 Self-ping enabled → {ping_url}")
    while True:
        time.sleep(13 * 60)
        try:
            r = _req.get(ping_url, timeout=15)
            log.info(f"🏓 Self-ping → {r.status_code}")
        except Exception as e:
            log.warning(f"🏓 Self-ping failed: {e}")


def _start_self_ping():
    t = threading.Thread(target=_self_ping_loop, daemon=True, name="self-ping")
    t.start()


# ─── Telegram helpers ─────────────────────────────────────────────────────────

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
                log.error("❌ Bot not in group — add the bot to the channel")
                return False
            log.warning(f"Telegram error ({attempt+1}): {e}")
            await asyncio.sleep(6 * (attempt + 1))
        except Exception as e:
            log.warning(f"Send error ({attempt+1}): {e}")
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
                log.error("❌ Bot not in group")
                return False
            log.warning(f"Telegram error ({attempt+1}): {e}")
            await asyncio.sleep(6 * (attempt + 1))
        except Exception as e:
            log.warning(f"Send error ({attempt+1}): {e}")
            await asyncio.sleep(5)
    return False


# ─── Send functions ───────────────────────────────────────────────────────────

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

    text = random.choice(INITIAL_TEMPLATES).format(
        name=name, symbol=symbol,
        mc=format_mc(mc), liq=format_mc(liq), vol=format_mc(vol),
        ca=ca, dex_url=dex_url
    )

    # 25% of initial calls include the VIP join button
    markup = _join_button(bot_username) if random.random() < 0.25 else None

    call_card = chart_img = None
    try:
        call_card = generate_initial_call_image(token)
    except Exception as e:
        log.warning(f"Call card error: {e}")
    try:
        bars = fetch_ohlcv_data(token.get("pair_address", ""))
        chart_img = generate_chart_image(token, bars)
    except Exception as e:
        log.warning(f"Chart error: {e}")

    sent = False
    if call_card:
        sent = await _send_photo(bot, call_card, text, reply_markup=markup)
    elif chart_img:
        sent = await _send_photo(bot, chart_img, text, reply_markup=markup)
    else:
        sent = await _send_text(bot, text, reply_markup=markup)

    if sent and call_card and chart_img:
        await asyncio.sleep(random.uniform(3, 7))
        await _send_photo(bot, chart_img, f"📊 *{symbol}* chart — dexscreener")

    if sent:
        last_sent_time = time.time()
        log.info(f"✅ Call sent: {symbol}  MC={format_mc(mc)}")


async def send_gain_update(bot: Bot, token: dict,
                           entry_mc: float, gain_pct: float,
                           called_at: str, bot_username: str = ""):
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

    text = random.choice(UPDATE_TEMPLATES).format(
        name=name, symbol=symbol,
        entry_mc=called_at, current_mc=format_mc(mc),
        gain_str=gain_s, liq=format_mc(liq),
        ca=ca, dex_url=dex_url, time_str=_fmt_time(elapsed)
    )

    # 55% of update posts include the VIP join button
    markup = _join_button(bot_username) if random.random() < 0.55 else None

    kol_card = chart_img = None
    try:
        kol_card = generate_kol_card(token, gain_pct, entry_mc, called_at,
                                     elapsed_str=_fmt_time(elapsed))
    except Exception as e:
        log.warning(f"KOL card error: {e}")
    try:
        bars = fetch_ohlcv_data(token.get("pair_address", ""))
        chart_img = generate_chart_image(token, bars)
    except Exception as e:
        log.warning(f"Chart error: {e}")

    sent = False
    if kol_card:
        sent = await _send_photo(bot, kol_card, text, reply_markup=markup)
    else:
        sent = await _send_text(bot, text, reply_markup=markup)

    if sent and chart_img:
        await asyncio.sleep(random.uniform(2, 5))
        await _send_photo(bot, chart_img, f"📊 *{symbol}* — {gain_s} from entry")

    if sent:
        last_sent_time = time.time()
        log.info(f"✅ Update sent: {symbol}  {gain_s}")


# ─── Scan loop (runs as a job) ────────────────────────────────────────────────

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


# ─── Bot startup ──────────────────────────────────────────────────────────────

async def post_init(application: Application):
    me = await application.bot.get_me()
    username = me.username or ""
    log.info(f"✅ Connected as @{username}")

    global BOT_USERNAME
    BOT_USERNAME = username

    application.job_queue.run_repeating(
        scan_and_send,
        interval=SCAN_INTERVAL,
        first=10,
        data={"bot_username": username},
        name="scanner",
    )


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

    log.info("📡 Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
