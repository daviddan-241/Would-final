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

from dex_fetcher import (
    fetch_trending_tokens, fetch_new_coins, fetch_ohlcv_data, format_mc,
)
from image_generator import (
    build_update_card, build_call_card, build_forex_card,
    build_stock_card, build_winners_card, build_pnl_brag_card,
    pnl_for_base,
)
from chart_generator import generate_chart_image
from payment_handler import build_payment_conversation

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

VIP_LINK     = os.getenv("VIP_GROUP_LINK", "https://t.me/+b7UesS3ulxxlZDdk")
SUPPORT_USER = os.getenv("SUPPORT_USERNAME", "Dave_211").lstrip("@")
DESK_URL     = f"https://t.me/{SUPPORT_USER}"
CHAINS_ENABLED = [c.strip().lower() for c in
                  os.getenv("DEX_CHAINS", "solana,ethereum,bsc,base").split(",")
                  if c.strip()]

# Per-token PnL base assignments — chosen ONCE per token, kept across updates
PNL_BASES = [50, 100, 100, 100, 200, 250, 500, 1000, 2530]


# ── VIP keyboard buttons ───────────────────────────────────────────────────────

def _desk_url(desk: str = "vip") -> str:
    return f"https://t.me/{BOT_USERNAME}?start={desk}" if BOT_USERNAME else VIP_LINK

def _pay_url() -> str:
    return _desk_url("vip")

def _past_url() -> str:
    return _desk_url("past100x")

def _join_button() -> InlineKeyboardMarkup:
    """Generic VIP join (used by VIP teaser/promo)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 EARLY ACCESS  •  JOIN VIP", url=_desk_url("vip"))],
        [InlineKeyboardButton("📊 Past 100x Results", url=_desk_url("past100x")),
         InlineKeyboardButton("💬 Talk to Desk",      url=DESK_URL)],
    ])

def _join_button_double() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ GET EARLY ACCESS — JOIN VIP", url=_desk_url("vip"))],
        [InlineKeyboardButton("🥇 Verified Wins", url=_desk_url("past100x")),
         InlineKeyboardButton("🔥 Live Calls",   url=_desk_url("memecoin"))],
        [InlineKeyboardButton("📊 100x Results", url=_desk_url("past100x")),
         InlineKeyboardButton("💬 Talk to Desk", url=DESK_URL)],
    ])

def _signal_button() -> InlineKeyboardMarkup:
    """Memecoin call card buttons → memecoin desk."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Memecoin Desk — VIP", url=_desk_url("memecoin"))],
        [InlineKeyboardButton("📈 Past Setups", url=_desk_url("past100x")),
         InlineKeyboardButton("💬 Talk to Desk", url=DESK_URL)],
    ])

def _forex_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💱 Forex Desk — VIP", url=_desk_url("forex"))],
        [InlineKeyboardButton("📊 Past 100x", url=_desk_url("past100x")),
         InlineKeyboardButton("💬 Talk to Desk", url=DESK_URL)],
    ])

def _stock_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛 Stocks & Indices Desk — VIP", url=_desk_url("stock"))],
        [InlineKeyboardButton("📊 Past 100x", url=_desk_url("past100x")),
         InlineKeyboardButton("💬 Talk to Desk", url=DESK_URL)],
    ])

def _pnl_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Live Signal Mgmt — VIP", url=_desk_url("signal"))],
        [InlineKeyboardButton("📊 Past 100x", url=_desk_url("past100x")),
         InlineKeyboardButton("💬 Desk",      url=DESK_URL)],
    ])


# ── Call caption templates (initial calls) ─────────────────────────────────────

CALL_TEMPLATES = [
    # 1) Public-channel teaser — clearly says VIP got it first
    "💰 *PUBLIC CALL*  ·  _VIP got this 4–6h ago_\n\n"
    "💲 SOL / *${symbol}*\n\n"
    "💎 MC : *{mc}*   •   💧 Liq : `{liq}`\n"
    "📈 24h Vol : `{vol}`\n\n"
    "🌐 CA\n`{ca}`\n\n"
    "_Reposting now that early entries are filled. VIP scaled in at lower mcap._",

    # 2) Whale-flag style (delayed mirror of VIP alert)
    "🐋 *Whale wallet flagged*  ·  *${symbol}*\n\n"
    "MC `{mc}`  •  liq `{liq}`  •  vol `{vol}`\n\n"
    "Smart money already positioned. Public release after VIP front-ran the move.\n\n"
    "`{ca}`",

    # 3) Pre-narrative — early but NOT first (VIP was first)
    "📡 *${symbol}* — before the narrative breaks\n\n"
    "`{mc}` MC  |  liq `{liq}`\n"
    "Not on CT. Not on KOL feeds. Not yet.\n\n"
    "🔐 _VIP entry was logged earlier today_\n\n"
    "`{ca}`",

    # 4) Insider drop (mature)
    "⚡ *Desk Drop*  —  ${symbol}\n\n"
    "Mcap `{mc}` · liq `{liq}` · vol `{vol}`\n\n"
    "Filtered by our wallet-cluster monitor. VIP got the alert with full entry zone.\n"
    "Public mirror below — DYOR.\n\n"
    "`{ca}`",

    # 5) Quiet conviction (no hype)
    "🎯 *${symbol}*\n\n"
    "MC `{mc}` · liq `{liq}`\n"
    "Same wallets we tracked into the last few wins are buying.\n\n"
    "Public CA below. VIP already in.\n\n"
    "`{ca}`",
]

# ── Update caption templates — Solana100xCall + Alpha Circle styles ───────────

UPDATE_TEMPLATES = [
    # 1) Insider scoreboard — emphasises VIP got it earlier and lower
    (
        "🏆 *VIP RESULT — {channel}*\n\n"
        "*${symbol}*  →  *{gain_str}*\n\n"
        "🔐 VIP entry : `{entry_mc}`\n"
        "🪙 Public channel : `{pub_mc}`\n"
        "✅ Now : `{current_mc}`  *(ATH)*\n\n"
        "🥇 *Profit : {spaced_x}*\n"
        "⏱ {time_str} hold\n\n"
        "CA  `{ca}`\n\n"
        "{pnl}\n\n"
        "_Posted in VIP at the lower mcap — public got it after._"
    ),
    # 2) Quiet update (mature, no hype)
    (
        "📈 *UPDATE — ${symbol}*\n\n"
        "{gain_str} from VIP entry.\n\n"
        "Entry `{entry_mc}` ➜ now `{current_mc}` · {time_str}\n\n"
        "{pnl}\n\n"
        "🔐 _Live management & exits stay inside VIP._"
    ),
    # 3) Scoreboard format — public-vs-VIP framing
    (
        "🎯 *${symbol}* — *{spaced_x}*\n\n"
        "🔐 VIP : `{entry_mc}`\n"
        "🪙 Public : `{pub_mc}`\n"
        "✅ ATH : `{current_mc}`\n\n"
        "{time_str} hold\n\n"
        "{pnl}"
    ),
    # 4) Receipt-style (no slang)
    (
        "📋 *Trade Closed — ${symbol}*\n\n"
        "Direction : LONG\n"
        "Entry : `{entry_mc}`  (VIP)\n"
        "ATH  : `{current_mc}`\n"
        "Move : *{gain_str}*  ·  {time_str}\n\n"
        "CA `{ca}`\n\n"
        "{pnl}\n\n"
        "_Public mirror posted after VIP exits were managed._"
    ),
    # 5) Milestone tag
    (
        "🥇 *Milestone — ${symbol}*  hit  *{spaced_x}*\n\n"
        "VIP in at `{entry_mc}`  ·  ATH `{current_mc}`\n"
        "{time_str} from call\n\n"
        "{pnl}\n\n"
        "🔐 _VIP gets the next one early._"
    ),
]


# ── Forex / macro signals ─────────────────────────────────────────────────────

FOREX_SIGNALS = [
    {"pair": "EUR/USD", "direction": "LONG",  "timeframe": "4H",
     "entry": "1.0840 – 1.0860", "tp1": "1.0940", "tp2": "1.1025", "sl": "1.0785", "rr": "2.7:1",
     "analysis": "DXY rejection at key resistance. EUR flow bias bullish ahead of ECB commentary."},
    {"pair": "GBP/USD", "direction": "LONG",  "timeframe": "H4",
     "entry": "1.2660 – 1.2690", "tp1": "1.2780", "tp2": "1.2880", "sl": "1.2600", "rr": "2.1:1",
     "analysis": "Cable holding above key structural support. BoE hawkish pivot narrative."},
    {"pair": "USD/JPY", "direction": "SHORT", "timeframe": "Daily",
     "entry": "154.80 – 155.20", "tp1": "152.50", "tp2": "150.00", "sl": "156.40", "rr": "3.1:1",
     "analysis": "BoJ intervention risk elevated at 155+. Risk-off flow incoming."},
    {"pair": "XAU/USD", "direction": "LONG",  "timeframe": "H4",
     "entry": "$3,080 – $3,095", "tp1": "$3,160", "tp2": "$3,250", "sl": "$3,040", "rr": "2.5:1",
     "analysis": "Gold reclaiming ATH structure. Macro uncertainty + central bank accumulation."},
    {"pair": "BTC/USDT", "direction": "LONG", "timeframe": "4H/Daily",
     "entry": "$82,400 – $83,200", "tp1": "$87,500", "tp2": "$93,000", "sl": "$79,800", "rr": "3.2:1",
     "analysis": "HTF demand respected. Accumulation pattern confirmed on 4H. Spot ETF inflows accelerating."},
    {"pair": "ETH/USDT", "direction": "LONG", "timeframe": "4H",
     "entry": "$1,580 – $1,620", "tp1": "$1,780", "tp2": "$1,950", "sl": "$1,490", "rr": "2.4:1",
     "analysis": "ETH printing higher lows vs BTC. Pectra upgrade narrative building."},
    {"pair": "SOL/USDT", "direction": "LONG", "timeframe": "4H",
     "entry": "$128 – $134", "tp1": "$158", "tp2": "$185", "sl": "$118", "rr": "2.9:1",
     "analysis": "SOL showing relative strength. DEX volume at highs. Institutional accumulation visible on-chain."},
    {"pair": "GBP/JPY", "direction": "SHORT", "timeframe": "H4",
     "entry": "195.50 – 196.00", "tp1": "193.20", "tp2": "191.00", "sl": "197.20", "rr": "2.3:1",
     "analysis": "Risk-off tone. JPY strength + GBP weakness at resistance confluence."},
    {"pair": "AUD/USD", "direction": "SHORT", "timeframe": "H4",
     "entry": "0.6380 – 0.6400", "tp1": "0.6290", "tp2": "0.6210", "sl": "0.6450", "rr": "2.2:1",
     "analysis": "China PMI miss weighing on AUD. RBA dovish tone."},
    {"pair": "USD/CHF", "direction": "SHORT", "timeframe": "Daily",
     "entry": "0.9020 – 0.9050", "tp1": "0.8900", "tp2": "0.8780", "sl": "0.9120", "rr": "2.6:1",
     "analysis": "SNB holding reserves. Risk-off CHF bid. Clean break below key level."},
]

# ── Stock & index signals (NASDAQ, NYSE) ──────────────────────────────────────

STOCK_SIGNALS = [
    {"ticker": "NVDA",  "name": "NVIDIA",     "direction": "LONG",  "timeframe": "Daily",
     "entry": "$118 – $122", "tp1": "$132", "tp2": "$148", "sl": "$112", "rr": "3.0:1",
     "analysis": "AI capex super-cycle intact. New Blackwell shipments accelerating. HTF bullish structure."},
    {"ticker": "TSLA",  "name": "Tesla",      "direction": "LONG",  "timeframe": "4H",
     "entry": "$258 – $264", "tp1": "$282", "tp2": "$305", "sl": "$248", "rr": "2.4:1",
     "analysis": "Robotaxi narrative + delivery beat. 4H reclaiming key supply zone."},
    {"ticker": "AAPL",  "name": "Apple",      "direction": "LONG",  "timeframe": "Daily",
     "entry": "$222 – $226", "tp1": "$238", "tp2": "$252", "sl": "$216", "rr": "2.6:1",
     "analysis": "Services revenue at ATH. Apple Intelligence rollout driving upgrade cycle."},
    {"ticker": "META",  "name": "Meta",       "direction": "LONG",  "timeframe": "Daily",
     "entry": "$555 – $565", "tp1": "$598", "tp2": "$640", "sl": "$540", "rr": "2.7:1",
     "analysis": "Ad revenue beat + AI spend ROI proven. Reels monetisation accelerating."},
    {"ticker": "MSFT",  "name": "Microsoft",  "direction": "LONG",  "timeframe": "Daily",
     "entry": "$418 – $424", "tp1": "$445", "tp2": "$472", "sl": "$408", "rr": "2.3:1",
     "analysis": "Azure cloud growth +30%. Copilot adoption ramping in enterprise."},
    {"ticker": "AMZN",  "name": "Amazon",     "direction": "LONG",  "timeframe": "4H",
     "entry": "$182 – $186", "tp1": "$198", "tp2": "$212", "sl": "$176", "rr": "2.5:1",
     "analysis": "AWS reaccelerating. Retail margins expanding. Holiday season tailwind."},
    {"ticker": "GOOGL", "name": "Alphabet",   "direction": "LONG",  "timeframe": "Daily",
     "entry": "$162 – $166", "tp1": "$178", "tp2": "$192", "sl": "$156", "rr": "2.6:1",
     "analysis": "Gemini gaining traction. Search ads stable. YouTube + Cloud both beating."},
    {"ticker": "SPY",   "name": "S&P 500",    "direction": "LONG",  "timeframe": "Daily",
     "entry": "$556 – $560", "tp1": "$578", "tp2": "$598", "sl": "$548", "rr": "2.8:1",
     "analysis": "Macro: rate-cut path priced in. Earnings beating. HTF bull trend intact."},
    {"ticker": "QQQ",   "name": "Nasdaq 100", "direction": "LONG",  "timeframe": "4H",
     "entry": "$478 – $482", "tp1": "$498", "tp2": "$518", "sl": "$470", "rr": "2.5:1",
     "analysis": "Tech leadership re-emerging. AI capex theme + semis strength."},
    {"ticker": "AMD",   "name": "AMD",        "direction": "LONG",  "timeframe": "Daily",
     "entry": "$148 – $152", "tp1": "$168", "tp2": "$188", "sl": "$140", "rr": "2.5:1",
     "analysis": "MI300 ramp ahead of guidance. Datacenter share-take vs INTC."},
    {"ticker": "NFLX",  "name": "Netflix",    "direction": "LONG",  "timeframe": "Daily",
     "entry": "$680 – $690", "tp1": "$725", "tp2": "$770", "sl": "$662", "rr": "2.4:1",
     "analysis": "Subscriber adds accelerating. Ad-tier monetisation kicking in."},
    {"ticker": "COIN",  "name": "Coinbase",   "direction": "LONG",  "timeframe": "4H",
     "entry": "$245 – $252", "tp1": "$278", "tp2": "$310", "sl": "$232", "rr": "2.7:1",
     "analysis": "BTC ETF inflows = volume = COIN earnings leverage. Beta to crypto cycle."},
]

FOREX_CAPTIONS = [
    "🎯 *FX DESK — {pair}*\n\n"
    "Bias : *{direction}*  ·  TF `{timeframe}`  ·  R/R `{rr}`\n\n"
    "Entry zone : `{entry}`\n"
    "✅ TP1 : `{tp1}`\n"
    "✅ TP2 : `{tp2}`\n"
    "❌ SL  : `{sl}`\n\n"
    "_{analysis}_\n\n"
    "🔐 _Live management, partial exits and SL trails are posted inside VIP._",

    "📡 *SIGNAL  ·  {pair}*\n\n"
    "*{direction}*  |  `{timeframe}`  |  R/R `{rr}`\n\n"
    "Zone `{entry}`   ·   TP1 `{tp1}`  →  TP2 `{tp2}`   ·   SL `{sl}`\n\n"
    "_{analysis}_\n\n"
    "🔐 _Public mirror — VIP got the alert at the entry trigger._",

    "🐋 *{pair}*  setup ready\n\n"
    "Direction : *{direction}*   ·   Timeframe : `{timeframe}`\n\n"
    "▸ Entry : `{entry}`\n"
    "▸ TP1   : `{tp1}`   →   TP2 : `{tp2}`\n"
    "▸ Stop  : `{sl}`\n"
    "▸ R/R   : `{rr}`\n\n"
    "_{analysis}_\n\n"
    "🔐 _Position currently active inside VIP._",
]

STOCK_CAPTIONS = [
    "📈 *EQUITIES DESK — {ticker} ({name})*\n\n"
    "Bias : *{direction}*  ·  TF `{timeframe}`  ·  R/R `{rr}`\n\n"
    "Entry : `{entry}`\n"
    "✅ TP1 : `{tp1}`\n"
    "✅ TP2 : `{tp2}`\n"
    "❌ SL  : `{sl}`\n\n"
    "_{analysis}_\n\n"
    "🔐 _Live management inside VIP._",

    "🏛 *{ticker}  —  {direction}*\n\n"
    "_{name}  ·  {timeframe}  ·  R/R {rr}_\n\n"
    "Zone `{entry}`   ·   TP1 `{tp1}`  →  TP2 `{tp2}`   ·   SL `{sl}`\n\n"
    "_{analysis}_",

    "🎯 *Equities desk*\n\n"
    "*{ticker} ({name})*\n"
    "*{direction}* setup  ·  `{timeframe}`  ·  `{rr}` R/R\n\n"
    "▸ Entry : `{entry}`\n"
    "▸ TP1   : `{tp1}`   /   TP2 : `{tp2}`\n"
    "▸ Stop  : `{sl}`\n\n"
    "_{analysis}_\n\n"
    "🔐 _Position open inside VIP._",
]


# ── VIP "X winners" teaser pool — looks like past wins ────────────────────────

VIP_TEASERS = [
    {"sym": "UNCEROID",  "x": 76,  "entry": "21k",  "ath": "1.6M"},
    {"sym": "ASTEROID",  "x": 47,  "entry": "17.6k","ath": "842k"},
    {"sym": "NINTONDO",  "x": 44,  "entry": "14.3k","ath": "631k"},
    {"sym": "发财",       "x": 24,  "entry": "34.7k","ath": "836k"},
    {"sym": "CHIBILAND", "x": 67,  "entry": "17.9k","ath": "1.2M"},
    {"sym": "CRASHOUT",  "x": 48,  "entry": "16.5k","ath": "794k"},
    {"sym": "CHSN",      "x": 196, "entry": "12.8k","ath": "2.5M"},
    {"sym": "SOLANA",    "x": 42,  "entry": "18.4k","ath": "778k"},
    {"sym": "UNC",       "x": 88,  "entry": "2.53k","ath": "224k"},
    {"sym": "PEPE2",     "x": 35,  "entry": "22k",  "ath": "770k"},
]

VIP_TEASER_TEMPLATES = [
    (
        "💲 *{sym}*\n"
        "*{x}x vip winners*\n\n"
        "*${entry} ➜ ${ath} MCAP*\n\n"
        "📊 CHART • 🆓 *FREE ENTRY*"
    ),
    (
        "💎 *${sym} is currently sitting at ${ath} mcap*\n"
        "from *${entry} VIP call out.*\n\n"
        "Reached *{x}x VIP.*\n\n"
        "🚀 JOIN NOW   •   📊 CHART"
    ),
]


# ── VIP promo standalone posts ────────────────────────────────────────────────

VIP_PROMOS = [
    # 1) The framing
    "🔐 *Read this once.*\n\n"
    "Public channel = the *scoreboard.*\n"
    "VIP group = where the *trade actually happens.*\n\n"
    "Every call posted here was already filled in VIP at a lower mcap, hours earlier.\n"
    "By the time you see the public post, early VIP entries are already up.\n\n"
    "If you want the entry — not the recap — VIP is the door.\n\n"
    "👇 Door's below.",

    # 2) Mature value pitch
    "💎 *Alpha_X_Calls VIP — early-access tier*\n\n"
    "▸ Memecoin alpha *4–6h before* public mirror\n"
    "▸ Forex / macro setups with live TP & SL management\n"
    "▸ Index & equities desk (NVDA, TSLA, META, AMD, COIN…)\n"
    "▸ On-chain whale & insider wallet alerts\n"
    "▸ Real-time entry / scale-in / exit calls\n"
    "▸ Direct access to the desk — DM-level questions answered\n\n"
    "One trade covers the year.\n\n"
    "👇",

    # 3) Quiet conviction
    "🎯 *Why VIP gets the edge*\n\n"
    "Smaller group → less slippage → better fills.\n"
    "Early entry → the difference between a 3x and a 30x.\n"
    "Live management → you exit the trade, not the bag.\n\n"
    "Public channel is the *highlight reel.*\n"
    "VIP is the *live broadcast.*\n\n"
    "👇",

    # 4) Receipt-style
    "📊 *Last 30 days — public vs. VIP*\n\n"
    "VIP entries averaged *4.2h earlier* than the public mirror.\n"
    "Average entry mcap delta : *–58%* vs. public post.\n\n"
    "That's not a marketing stat. That's just earlier seats at the same table.\n\n"
    "👇 Same call. Lower entry. More upside.",

    # 5) Pricing (mature)
    "💳 *VIP Access — Pricing*\n\n"
    "$44 / month\n"
    "$69 / 3 months\n"
    "$99 / lifetime  ←  most members pick this\n\n"
    "Same access. The only difference is how long you stay inside.\n"
    "Pay in SOL — instant access, no manual approval.\n\n"
    "👇",

    # 6) Scarcity (true & low-key)
    "🐋 *VIP roster stays small.*\n\n"
    "Memecoin liquidity is finite. The bigger the room, the worse the fill.\n"
    "We cap intake on purpose.\n\n"
    "If you're reading this, the door is still open. It won't always be.\n\n"
    "👇",
]


# ── Utilities ─────────────────────────────────────────────────────────────────

def _fmt_time(s: float) -> str:
    if s < 60:   return f"{int(s)}s"
    if s < 3600: return f"{int(s // 60)}m"
    return f"{int(s // 3600)}h {int((s % 3600) // 60)}m"

def _gain_str(pct: float) -> str:
    mult = pct / 100 + 1
    if mult >= 10:
        return f"{mult:.1f}X"
    if mult >= 2:
        return f"{mult:.1f}x"
    return f"+{pct:.0f}%"

def _spaced_x(mult: float) -> str:
    """ '4 8 . 1 X' Alpha-Circle style. """
    s = f"{mult:.1f}X" if mult < 100 else f"{int(mult)}X"
    return " ".join(list(s))

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

async def send_initial_call(bot: Bot, token: dict):
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
        log.info(f"✅ Call: {symbol}  MC={format_mc(mc)}  chain={token.get('chain','sol')}")


# ── Send: gain update ──────────────────────────────────────────────────────────

async def send_gain_update(bot: Bot, token: dict, entry_mc: float,
                           gain_pct: float, entry_mc_str: str,
                           pnl_base: int):
    global last_sent_time
    await _throttle()

    mc       = token.get("market_cap", 0)
    ca       = token.get("address", "")
    symbol   = token.get("symbol", "???")
    elapsed  = time.time() - tracked_coins.get(ca, {}).get("first_seen", time.time())
    gain_s   = _gain_str(gain_pct)
    mult     = _mult_float(gain_pct)
    pnl_text = pnl_for_base(pnl_base, mult)
    spaced_x = _spaced_x(mult)
    pub_mc   = format_mc(entry_mc * random.uniform(15, 35))

    caption = random.choice(UPDATE_TEMPLATES).format(
        symbol=symbol, entry_mc=entry_mc_str,
        current_mc=format_mc(mc), gain_str=gain_s,
        ca=ca, time_str=_fmt_time(elapsed), pnl=pnl_text,
        spaced_x=spaced_x, pub_mc=pub_mc, channel="Alpha_X_Calls",
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
    markup   = _forex_button()
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


# ── Send: stock signal ────────────────────────────────────────────────────────

async def send_stock_signal(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    sig      = random.choice(STOCK_SIGNALS)
    caption  = random.choice(STOCK_CAPTIONS).format(**sig)
    markup   = _stock_button()
    card     = None
    try:
        card = build_stock_card(
            ticker=sig["ticker"], name=sig["name"], direction=sig["direction"],
            entry=sig["entry"], tp1=sig["tp1"], tp2=sig["tp2"],
            sl=sig["sl"], timeframe=sig["timeframe"], rr=sig["rr"],
        )
    except Exception as e:
        log.warning(f"Stock card error: {e}")

    if card:
        await _send_photo(bot, card, caption, reply_markup=markup)
    else:
        await _send_text(bot, caption, reply_markup=markup)
    log.info(f"🏛 Stock signal: {sig['ticker']} {sig['direction']}")


# ── Send: VIP "X winners" teaser ──────────────────────────────────────────────

async def send_vip_teaser(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    win = random.choice(VIP_TEASERS)
    caption = random.choice(VIP_TEASER_TEMPLATES).format(**win)
    markup = _join_button_double()
    card = None
    try:
        card = build_winners_card(
            symbol=win["sym"], multiplier=float(win["x"]),
            entry=win["entry"], ath=win["ath"],
        )
    except Exception as e:
        log.warning(f"Teaser card error: {e}")

    if card:
        await _send_photo(bot, card, caption, reply_markup=markup)
    else:
        await _send_text(bot, caption, reply_markup=markup)
    log.info(f"🎯 VIP teaser: ${win['sym']} {win['x']}x")


# ── Send: VIP promo post ──────────────────────────────────────────────────────

async def send_vip_promo(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    text  = random.choice(VIP_PROMOS)
    markup = _join_button_double()
    await _send_text(bot, text, reply_markup=markup)
    log.info("📢 VIP promo sent")


# ── Send: PnL brag (Phanes / Axiom-style trade screenshot) ────────────────────

PNL_BRAG_POOL = [
    # Memecoin wins
    {"sym": "BONK",      "invested":  500, "position":  47_300, "kind": "meme"},
    {"sym": "WIF",       "invested": 1000, "position":  38_400, "kind": "meme"},
    {"sym": "PEPE",      "invested":  250, "position":  21_900, "kind": "meme"},
    {"sym": "MOODENG",   "invested":  200, "position":  18_650, "kind": "meme"},
    {"sym": "MEW",       "invested":  500, "position":  19_800, "kind": "meme"},
    {"sym": "POPCAT",    "invested":  300, "position":  14_400, "kind": "meme"},
    {"sym": "BOME",      "invested":  400, "position":  31_600, "kind": "meme"},
    {"sym": "RETARDIO",  "invested":  150, "position":   9_650, "kind": "meme"},
    {"sym": "SLERF",     "invested":  600, "position":  17_250, "kind": "meme"},
    # Forex wins
    {"sym": "XAU/USD",   "invested": 2500, "position":   7_400, "kind": "fx"},
    {"sym": "GBP/USD",   "invested": 1500, "position":   4_200, "kind": "fx"},
    {"sym": "USD/JPY",   "invested": 2000, "position":   5_800, "kind": "fx"},
    {"sym": "EUR/USD",   "invested": 1000, "position":   2_650, "kind": "fx"},
    # Equity wins
    {"sym": "NVDA",      "invested": 5000, "position":  12_400, "kind": "stock"},
    {"sym": "TSLA",      "invested": 3000, "position":   7_650, "kind": "stock"},
    {"sym": "COIN",      "invested": 2500, "position":   8_900, "kind": "stock"},
    {"sym": "META",      "invested": 4000, "position":   9_300, "kind": "stock"},
    # Crypto majors
    {"sym": "BTC",       "invested": 5000, "position":  11_200, "kind": "crypto"},
    {"sym": "SOL",       "invested": 1500, "position":   6_400, "kind": "crypto"},
    {"sym": "ETH",       "invested": 3000, "position":   7_100, "kind": "crypto"},
]

PNL_BRAG_CAPTIONS = [
    "📋 *Member screenshot — VIP*\n\n"
    "Posted in the chat 20 minutes ago. Same call, same entry, "
    "same exit zone — every member who took the trade closed green.\n\n"
    "🔐 _Live management is the difference. Public sees the recap. "
    "VIP gets the entry & the exit._",

    "🥇 *Closed inside VIP — ${sym}*\n\n"
    "Member dropped the screenshot in the chat. "
    "Entry/SL/TP were all called live, exits were managed in real time.\n\n"
    "🔐 _This is what the room looks like every day._",

    "💵 *Receipt from the chatroom*\n\n"
    "Just one of today's closes. Multi-asset desk — memecoins, forex, "
    "equities — same room, same playbook.\n\n"
    "🔐 _Stop watching the recap. Take the next entry inside VIP._",

    "📊 *VIP close*\n\n"
    "No screenshots edited. No dramatized P&L. Just a member "
    "posting their close after the desk called the exit.\n\n"
    "🔐 _Door's below._",
]


async def send_pnl_brag(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot
    pick = random.choice(PNL_BRAG_POOL)
    caption = random.choice(PNL_BRAG_CAPTIONS).format(sym=pick["sym"])
    try:
        card = build_pnl_brag_card(
            symbol=pick["sym"],
            invested=pick["invested"],
            position=pick["position"],
        )
    except Exception as e:
        log.warning(f"PnL brag card error: {e}")
        await _send_text(bot, caption, reply_markup=_pnl_button())
        return
    await _send_photo(bot, card, caption, reply_markup=_pnl_button())
    log.info(f"💵 PnL brag: ${pick['sym']} ${pick['invested']}→${pick['position']}")


# ── DEX scanner loop ──────────────────────────────────────────────────────────

async def scan_and_send(context: ContextTypes.DEFAULT_TYPE):
    bot: Bot = context.bot

    log.info(f"🔍 Scanning DEX Screener  ·  chains={CHAINS_ENABLED}")
    pool: list = []
    try:
        for ch in CHAINS_ENABLED:
            try:
                pool += fetch_new_coins(ch, MIN_MC, MAX_MC)
                pool += fetch_trending_tokens(ch)
            except Exception as e:
                log.warning(f"Chain {ch} fetch failed: {e}")
        all_tokens = {t["address"]: t for t in pool if t.get("address")}
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
                "pnl_base":     random.choice(PNL_BASES),
            }
            await send_initial_call(bot, token)
            await asyncio.sleep(random.uniform(8, 20))
            continue

        entry_mc = tracked_coins[ca]["entry_mc"]
        if entry_mc <= 0:
            continue

        gain_pct = ((mc - entry_mc) / entry_mc) * 100
        done     = sent_updates.get(ca, [])
        # Bigger milestone ladder — go all the way to 200x
        for threshold in [20, 50, 100, 200, 300, 500, 1000, 2000, 4000, 7000, 10000, 20000]:
            if gain_pct >= threshold and threshold not in done:
                await send_gain_update(
                    bot, token, entry_mc, gain_pct,
                    tracked_coins[ca]["entry_mc_str"],
                    tracked_coins[ca].get("pnl_base", 100),
                )
                sent_updates.setdefault(ca, []).append(threshold)
                await asyncio.sleep(random.uniform(5, 12))
                break

        tracked_coins[ca]["token"] = token

    # Prune old coins (keep 5 days for big-X stories)
    cutoff = time.time() - 86400 * 5
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

    # Stock signals — every 5–7 h, offset from forex
    jq.run_repeating(send_stock_signal, interval=random.randint(18000, 25200),
                     first=random.randint(2700, 5400), name="stock-signals")

    # VIP "X winners" teaser — every 3–5 h
    jq.run_repeating(send_vip_teaser,   interval=random.randint(10800, 18000),
                     first=random.randint(900, 2400), name="vip-teaser")

    # VIP promo (text) — every 6–8 h
    jq.run_repeating(send_vip_promo,   interval=random.randint(21600, 28800),
                     first=random.randint(1800, 3600), name="vip-promo")

    # PnL brag screenshot — every 4–6 h, offset
    jq.run_repeating(send_pnl_brag,    interval=random.randint(14400, 21600),
                     first=random.randint(1500, 4200), name="pnl-brag")


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

    # /start, /pay, /join, /vip and all payment buttons are handled by the
    # ConversationHandler so the per-user state machine stays consistent.
    app.add_handler(build_payment_conversation())

    log.info("📡 Polling started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
