"""
Alpha_X_Calls — Premium VIP payment flow (multi-chain).

Flow:
  /start                   → product page + 3 plan tiers
  Pick plan                → cart confirmation
  Continue to payment      → pick chain  (SOL / ETH / BNB)
  Pick chain               → store address + checkout total
  Paste sender wallet      → confirmation + ask for tx hash
  Paste tx hash            → on-chain verify  →  VIP group link
"""

import logging
import os
import time
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from blockchain_verify import (
    verify_transaction,
    SOL_ADDRESS, ETH_ADDRESS, BNB_HEX_ADDRESS,
)

log = logging.getLogger(__name__)

GROUP_LINK     = os.getenv("VIP_GROUP_LINK",  "https://t.me/+b7UesS3ulxxlZDdk")
SUPPORT_USER   = os.getenv("SUPPORT_USERNAME", "@Dave_211")
if not SUPPORT_USER.startswith("@"):
    SUPPORT_USER = "@" + SUPPORT_USER
# Markdown-safe variant for inline display (escape underscores)
SUPPORT_USER_MD = SUPPORT_USER.replace("_", r"\_")
CHANNEL_NAME    = os.getenv("CHANNEL_NAME",     "Alpha_X_Calls")
CHANNEL_NAME_MD = CHANNEL_NAME.replace("_", r"\_")

PLANS = {
    "monthly":   {"label": "$44 / month",     "usd": 44,  "short": "Monthly"},
    "quarterly": {"label": "$69 / 3 months",  "usd": 69,  "short": "3 Months"},
    "lifetime":  {"label": "$99 / lifetime",  "usd": 99,  "short": "Lifetime"},
}

# ── Desks ─────────────────────────────────────────────────────────────────────
# Each /start <key>  →  its own intro page + its own pricing tiers.
# All desks unlock the SAME VIP group, just framed for that user's interest.

DESKS = {
    "vip": {
        "title": "Apex Desk  ·  Full VIP Access",
        "intro": (
            "*Apex Desk — Full VIP Access*\n\n"
            "Every desk under one roof: memecoin alpha, forex, equities, "
            "on-chain whale alerts, live entry/scale-in/exit calls, VIP chatroom.\n\n"
            "🥷 Sniper · ⚡ Alpha · 💎 Apex\n"
            "🏆 VIP Milestone Tracker · 💬 Direct line to the desk\n\n"
            "📊 30+ quality signals / day  ·  300+ active members"
        ),
        "plans": {
            "monthly":   {"label": "$44 / month",     "usd": 44},
            "quarterly": {"label": "$69 / 3 months",  "usd": 69},
            "lifetime":  {"label": "$99 / lifetime",  "usd": 99},
        },
    },

    "memecoin": {
        "title": "Memecoin Sniper Desk",
        "intro": (
            "🚀 *Memecoin Sniper Desk*\n\n"
            "Multi-chain memecoin alpha — Solana · Ethereum · BNB · Base.\n"
            "Calls go out *4–6h before* the public mirror, with entry zone, "
            "scale-in plan and live exits.\n\n"
            "▸ Wallet-cluster monitor (smart money tracking)\n"
            "▸ DEX scanner across 4 chains\n"
            "▸ Sniper-only channel inside VIP\n"
            "▸ Live exits & take-profit ladders\n\n"
            "_Past hits: PEPE · WIF · BOME · MOODENG · BONK · MEW · CHSN +196x_"
        ),
        "plans": {
            "monthly":   {"label": "$35 / month",     "usd": 35},
            "quarterly": {"label": "$59 / 3 months",  "usd": 59},
            "lifetime":  {"label": "$89 / lifetime",  "usd": 89},
        },
    },

    "forex": {
        "title": "Forex & Macro Desk",
        "intro": (
            "💱 *Forex & Macro Desk*\n\n"
            "Live FX setups managed by the desk — entry, TP1/TP2/TP3, SL, "
            "and trail rules. Majors + crosses + gold.\n\n"
            "▸ EUR/USD · GBP/USD · USD/JPY · GBP/JPY · XAU/USD\n"
            "▸ London + New York session signals\n"
            "▸ Risk-managed — fixed % per trade\n"
            "▸ Macro briefings before NFP / CPI / FOMC\n\n"
            "_Average 6–10 setups per week. Win rate tracked live._"
        ),
        "plans": {
            "monthly":   {"label": "$39 / month",     "usd": 39},
            "quarterly": {"label": "$65 / 3 months",  "usd": 65},
            "lifetime":  {"label": "$95 / lifetime",  "usd": 95},
        },
    },

    "stock": {
        "title": "Stocks & Indices Desk",
        "intro": (
            "🏛 *Stocks & Indices Desk*\n\n"
            "Equity & index trade ideas with full risk frame.\n\n"
            "▸ NVDA · TSLA · META · AMD · COIN · AAPL · SPY · QQQ\n"
            "▸ Pre-market gameplan + intraday alerts\n"
            "▸ Earnings playbook (calls / puts / spreads)\n"
            "▸ Macro calendar overlay\n\n"
            "_Built for swing traders + active intraday._"
        ),
        "plans": {
            "monthly":   {"label": "$39 / month",     "usd": 39},
            "quarterly": {"label": "$65 / 3 months",  "usd": 65},
            "lifetime":  {"label": "$95 / lifetime",  "usd": 95},
        },
    },

    "signal": {
        "title": "Live Signal Management",
        "intro": (
            "📡 *Live Signal Management*\n\n"
            "Stop guessing entries and exits. The desk runs every position "
            "live: entry zone → scale-in → take-profit ladder → trail rule → exit.\n\n"
            "▸ Real-time entry / scale / exit pings\n"
            "▸ Direct line to desk in chatroom\n"
            "▸ Same plan structure as Apex VIP\n"
            "▸ Multi-asset (crypto + FX + equities)\n\n"
            "_The trade isn't the signal. The management is the signal._"
        ),
        "plans": {
            "monthly":   {"label": "$44 / month",     "usd": 44},
            "quarterly": {"label": "$69 / 3 months",  "usd": 69},
            "lifetime":  {"label": "$99 / lifetime",  "usd": 99},
        },
    },

    "past100x": {
        "title": "Past 100x Archive",
        "intro": (
            "🏆 *Past 100x — VIP Archive*\n\n"
            "The 100x receipts (PEPE, WIF, BOME, MOODENG, BONK, MEW, "
            "$CHSN +196x and the rest) live inside the VIP archive.\n\n"
            "Public channel only shows the *late-stage mirror*. "
            "VIP archive shows the *original entries* — call mcap, exit mcap, "
            "timestamp, screenshots, on-chain tx.\n\n"
            "It's the receipts. Not marketing.\n\n"
            "👇 Pick a plan to unlock the archive."
        ),
        "plans": {
            "monthly":   {"label": "$29 / month  (archive + live)",  "usd": 29},
            "quarterly": {"label": "$59 / 3 months  (archive + live)","usd": 59},
            "lifetime":  {"label": "$89 / lifetime  (archive + live)","usd": 89},
        },
    },
}


def _desk(desk_key: str) -> dict:
    return DESKS.get(desk_key, DESKS["vip"])


def _resolve_plan(desk_key: str, plan_key: str) -> dict:
    """Get the price record for (desk, plan)."""
    desk = _desk(desk_key)
    return desk["plans"].get(plan_key, desk["plans"]["monthly"])

CHAINS = {
    "sol": {"label": "Solana (SOL)",   "symbol": "SOL",  "address": SOL_ADDRESS,
            "explorer": "https://solscan.io/tx/",
            "coingecko": "solana", "decimals": 5},
    "eth": {"label": "Ethereum (ETH)", "symbol": "ETH",  "address": ETH_ADDRESS,
            "explorer": "https://etherscan.io/tx/",
            "coingecko": "ethereum", "decimals": 6},
    "bnb": {"label": "BNB Chain (BNB)","symbol": "BNB",  "address": BNB_HEX_ADDRESS,
            "explorer": "https://bscscan.com/tx/",
            "coingecko": "binancecoin", "decimals": 5},
}

# ── States ────────────────────────────────────────────────────────────────────
SELECT_PLAN, CONFIRM_CART, SELECT_CHAIN, ENTER_WALLET, ENTER_TXHASH = range(5)


# ── Live coin price (cached 5 min per asset) ─────────────────────────────────
_price_cache: dict = {}

def _price(coingecko_id: str, fallback: float) -> float:
    rec = _price_cache.get(coingecko_id)
    if rec and time.time() - rec["ts"] < 300:
        return rec["price"]
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coingecko_id, "vs_currencies": "usd"},
            timeout=8,
        )
        p = float(r.json()[coingecko_id]["usd"])
        if p > 0:
            _price_cache[coingecko_id] = {"price": p, "ts": time.time()}
            return p
    except Exception as e:
        log.warning(f"{coingecko_id} price fetch failed: {e}")
    return fallback


def _usd_to_native(usd: float, chain: str) -> float:
    cfg = CHAINS[chain]
    fallback = {"sol": 145.0, "eth": 3300.0, "bnb": 600.0}.get(chain, 1.0)
    p = _price(cfg["coingecko"], fallback)
    return round(usd / p, cfg["decimals"])


# ══════════════════════════════════════════════════════════════════════════════
#  /start  →  product page
# ══════════════════════════════════════════════════════════════════════════════

DESK_ALIASES = {
    "results":  "past100x",
    "100x":     "past100x",
    "memes":    "memecoin",
    "meme":     "memecoin",
    "fx":       "forex",
    "stocks":   "stock",
    "equities": "stock",
    "signals":  "signal",
    "":         "vip",
}


def _normalise_desk(arg: str) -> str:
    arg = (arg or "").lower().strip()
    arg = DESK_ALIASES.get(arg, arg)
    return arg if arg in DESKS else "vip"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """`/start [desk]` — each desk has its own page + own pricing."""
    args = context.args or []
    desk_key = _normalise_desk(args[0] if args else "")
    return await _show_desk(update.message, context, desk_key)


def _plan_keyboard(desk_key: str):
    desk = _desk(desk_key)
    rows = []
    for tier_key, p in desk["plans"].items():
        rows.append([InlineKeyboardButton(
            p["label"], callback_data=f"plan_{desk_key}_{tier_key}"
        )])
    if desk_key != "vip":
        rows.append([InlineKeyboardButton(
            "🔓 See full Apex VIP",
            callback_data="pay_start_vip",
        )])
    rows.append([InlineKeyboardButton(
        "💬 Talk to the desk",
        url=f"https://t.me/{SUPPORT_USER.lstrip('@')}",
    )])
    return InlineKeyboardMarkup(rows)


def _desk_page_text(desk_key: str) -> str:
    desk = _desk(desk_key)
    return (
        f"*{CHANNEL_NAME_MD}  ·  {desk['title']}*\n\n"
        f"{desk['intro']}\n\n"
        f"💳 *Payment — 3 chains accepted*  ·  Solana · Ethereum · BNB Chain.\n"
        f"⚠️ *Never pay from a CEX* (Binance / Coinbase / OKX). Tx will not match.\n"
        f"✅ Instant access after on-chain confirmation.\n\n"
        f"❓ Support: {SUPPORT_USER_MD}  _(payment or access issues only)_\n\n"
        f"*Pricing*"
    )


async def _show_desk(msg, context, desk_key: str):
    desk_key = _normalise_desk(desk_key)
    context.user_data["desk"] = desk_key
    await msg.reply_text(
        _desk_page_text(desk_key),
        parse_mode="Markdown",
        reply_markup=_plan_keyboard(desk_key),
    )
    return SELECT_PLAN


async def pay_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-open the product page. Pattern: `pay_start` or `pay_start_<desk>`."""
    q = update.callback_query
    await q.answer()
    data = q.data or "pay_start"
    desk_key = data[len("pay_start_"):] if data.startswith("pay_start_") else \
               context.user_data.get("desk", "vip")
    return await _show_desk(q.message, context, desk_key)


# ══════════════════════════════════════════════════════════════════════════════
#  Plan selected → cart confirmation
# ══════════════════════════════════════════════════════════════════════════════

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # plan_<desk>_<tier>  OR legacy plan_<tier>

    parts = data.split("_", 2)
    if len(parts) == 3:
        _, desk_key, tier_key = parts
    else:
        desk_key = context.user_data.get("desk", "vip")
        tier_key = parts[1] if len(parts) > 1 else "monthly"

    desk_key = _normalise_desk(desk_key)
    desk = _desk(desk_key)
    if tier_key not in desk["plans"]:
        tier_key = "monthly"
    plan = desk["plans"][tier_key]

    context.user_data["desk"] = desk_key
    context.user_data["plan"] = tier_key

    other_rows = []
    for k, v in desk["plans"].items():
        if k == tier_key:
            continue
        other_rows.append([InlineKeyboardButton(
            v["label"], callback_data=f"plan_{desk_key}_{k}"
        )])

    cart_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ {plan['label']}",
                              callback_data=f"plan_{desk_key}_{tier_key}")],
        *other_rows,
        [InlineKeyboardButton("💳 Continue to payment", callback_data="cart_pay")],
        [InlineKeyboardButton("↩ Change desk",          callback_data="pay_start_vip")],
    ])

    await query.message.reply_text(
        f"🟡 *In cart*\n\n"
        f"——————\n\n"
        f"*{CHANNEL_NAME_MD}  ·  {desk['title']}*\n\n"
        f"🟡 {plan['label']}\n\n"
        f"——————\n\n"
        f"Same VIP group, framed for {desk['title']}.\n"
        f"Next step: pick the chain you want to pay from (SOL · ETH · BNB).",
        parse_mode="Markdown",
        reply_markup=cart_kb,
    )
    return CONFIRM_CART


# ══════════════════════════════════════════════════════════════════════════════
#  Continue to payment → ask for chain
# ══════════════════════════════════════════════════════════════════════════════

async def cart_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    desk_key = context.user_data.get("desk", "vip")
    plan_key = context.user_data.get("plan", "monthly")
    plan     = _resolve_plan(desk_key, plan_key)

    chain_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Solana (SOL)",   callback_data="chain_sol")],
        [InlineKeyboardButton("🟣 Ethereum (ETH)", callback_data="chain_eth")],
        [InlineKeyboardButton("🟡 BNB Chain (BNB)",callback_data="chain_bnb")],
        [InlineKeyboardButton("↩ Change plan",     callback_data=f"pay_start_{desk_key}")],
    ])

    await query.message.reply_text(
        f"💳 *Pick your payment chain*\n\n"
        f"Plan : *{plan['label']}*\n\n"
        f"Pick the chain you'll send the payment from. "
        f"You'll get the deposit address and the live checkout total in the next step.\n\n"
        f"⚠️ Only pay from a *self-custody wallet* "
        f"(Phantom · MetaMask · Trust · Backpack · Solflare · Trojan · Bloom).\n"
        f"⚠️ *Never pay from a CEX* — the tx won't match and access won't unlock.",
        parse_mode="Markdown",
        reply_markup=chain_kb,
    )
    return SELECT_CHAIN


# ══════════════════════════════════════════════════════════════════════════════
#  Chain picked → show deposit address + checkout total
# ══════════════════════════════════════════════════════════════════════════════

async def select_chain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chain_key = query.data.replace("chain_", "")
    if chain_key not in CHAINS:
        return SELECT_CHAIN

    context.user_data["chain"] = chain_key
    chain = CHAINS[chain_key]
    desk_key = context.user_data.get("desk", "vip")
    desk     = _desk(desk_key)
    plan_key = context.user_data.get("plan", "monthly")
    plan     = _resolve_plan(desk_key, plan_key)
    native   = _usd_to_native(plan["usd"], chain_key)

    await query.message.reply_text(
        f"⏳ *Watching the {chain['symbol']} address*\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send `{chain['symbol']}` to:\n"
        f"`{chain['address']}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']}  🟡  {CHANNEL_NAME_MD} · {desk['title']}\n"
        f"——————\n"
        f"`{native} {chain['symbol']}` ← checkout total\n"
        f"_(based on live {chain['symbol']}/USD)_\n\n"
        f"——————\n\n"
        f"👇 Paste the wallet address you're *sending FROM*\n"
        f"_(So we can match your payment on-chain)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Change chain", callback_data="cart_pay")],
            [InlineKeyboardButton("↩ Change plan",  callback_data=f"pay_start_{desk_key}")],
        ]),
    )
    return ENTER_WALLET


# ══════════════════════════════════════════════════════════════════════════════
#  User pastes sending wallet
# ══════════════════════════════════════════════════════════════════════════════

async def enter_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet    = update.message.text.strip()
    chain_key = context.user_data.get("chain", "sol")
    chain     = CHAINS[chain_key]

    valid = True
    if chain_key == "sol":
        if len(wallet) < 32 or len(wallet) > 44 or " " in wallet:
            valid = False
    else:  # eth / bnb
        if not (wallet.startswith("0x") and len(wallet) == 42):
            valid = False

    if not valid:
        sample = ("32–44 chars, no spaces"
                  if chain_key == "sol"
                  else "0x… 42 chars")
        await update.message.reply_text(
            f"⚠️ That doesn't look like a valid {chain['symbol']} address.\n"
            f"Paste the {chain['symbol']} address you're *sending from* ({sample}):",
            parse_mode="Markdown",
        )
        return ENTER_WALLET

    context.user_data["wallet"] = wallet
    desk_key = context.user_data.get("desk", "vip")
    plan_key = context.user_data.get("plan", "monthly")
    plan     = _resolve_plan(desk_key, plan_key)
    native   = _usd_to_native(plan["usd"], chain_key)
    short    = wallet[:6] + ".." + wallet[-4:]

    await update.message.reply_text(
        f"⏳ *Watching wallet* `{short}`  ▸  Pay from here\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send `{chain['symbol']}` from `{short}` to:\n"
        f"`{chain['address']}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']}  🟡  {CHANNEL_NAME_MD} VIP {chain['symbol']}\n"
        f"——————\n"
        f"`{native} {chain['symbol']}` ← checkout total\n\n"
        f"——————\n\n"
        f"👇 After sending, paste your *transaction signature* (tx ID)\n"
        f"_Find it in your wallet history or on the explorer_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ {plan['label']}",
                                 callback_data=f"plan_{desk_key}_{plan_key}"),
            InlineKeyboardButton("↩ Change wallet",
                                 callback_data="cart_pay"),
        ]]),
    )
    return ENTER_TXHASH


# ══════════════════════════════════════════════════════════════════════════════
#  User pastes tx hash → verify → deliver group link
# ══════════════════════════════════════════════════════════════════════════════

async def enter_txhash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_hash   = update.message.text.strip()
    chain_key = context.user_data.get("chain", "sol")
    chain     = CHAINS[chain_key]

    if len(tx_hash) < 30 or " " in tx_hash:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid transaction signature.\n"
            "Paste the full tx ID (no spaces):",
            parse_mode="Markdown",
        )
        return ENTER_TXHASH

    await update.message.reply_text(
        f"🔍 *Verifying on-chain on {chain['label']}...*\n"
        f"This usually takes a few seconds.",
        parse_mode="Markdown",
    )

    wallet   = context.user_data.get("wallet", "")
    success, msg_text = verify_transaction(chain_key, tx_hash, wallet)

    if success:
        desk_key = context.user_data.get("desk", "vip")
        desk     = _desk(desk_key)
        plan_key = context.user_data.get("plan", "monthly")
        plan     = _resolve_plan(desk_key, plan_key)
        await update.message.reply_text(
            f"✅ *Payment confirmed on-chain!*\n\n"
            f"Desk  : *{desk['title']}*\n"
            f"Chain : *{chain['label']}*\n"
            f"Plan  : *{plan['label']}*\n"
            f"Tx    : [{tx_hash[:18]}…]({chain['explorer']}{tx_hash})\n\n"
            f"Welcome to *{CHANNEL_NAME_MD} VIP* 🏆\n\n"
            f"You now have access to:\n"
            f"🥷 Sniper  •  ⚡ Alpha  •  💎 Apex\n"
            f"🏆 VIP Milestone Tracker  •  💬 VIP Chatroom\n\n"
            f"Don't share this link — members only 🤫\n\n"
            f"👇 *Your private access link:*\n{GROUP_LINK}",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        log.info(f"✅ VIP payment confirmed — uid={update.effective_user.id} "
                 f"plan={plan_key} chain={chain_key} tx={tx_hash}")
    else:
        await update.message.reply_text(
            f"❌ *Could not verify payment*\n\n"
            f"{msg_text}\n\n"
            f"Double-check your tx and try again. Make sure you sent from "
            f"the wallet you registered above to the {chain['symbol']} store address shown.\n\n"
            f"Need help? Contact {SUPPORT_USER_MD}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔁 Try again",   callback_data="cart_pay"),
                InlineKeyboardButton("❓ Get support", url=f"https://t.me/{SUPPORT_USER.lstrip('@')}"),
            ]]),
        )

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  /pay and /cancel
# ══════════════════════════════════════════════════════════════════════════════

async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desk_key = context.user_data.get("desk", "vip")
    return await _show_desk(update.message, context, desk_key)


async def desk_cmd_factory(desk_key: str):
    async def _h(update, context):
        return await _show_desk(update.message, context, desk_key)
    return _h


async def memecoin_cmd(update, context):
    return await _show_desk(update.message, context, "memecoin")

async def forex_cmd(update, context):
    return await _show_desk(update.message, context, "forex")

async def stock_cmd(update, context):
    return await _show_desk(update.message, context, "stock")

async def signal_cmd(update, context):
    return await _show_desk(update.message, context, "signal")

async def past100x_cmd(update, context):
    return await _show_desk(update.message, context, "past100x")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cancelled. Start again any time with /pay 👋",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 Join VIP", callback_data="pay_start_vip"),
        ]]),
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
def build_payment_conversation() -> ConversationHandler:
    PLAN_PAT  = r"^plan_[a-z0-9]+_(monthly|quarterly|lifetime)$|^plan_(monthly|quarterly|lifetime)$"
    START_PAT = r"^pay_start(_[a-z0-9]+)?$"
    CHAIN_PAT = r"^chain_(sol|eth|bnb)$"
    return ConversationHandler(
        entry_points=[
            CommandHandler("start",    start),
            CommandHandler("pay",      pay_cmd),
            CommandHandler("join",     pay_cmd),
            CommandHandler("vip",      pay_cmd),
            CommandHandler("memecoin", memecoin_cmd),
            CommandHandler("forex",    forex_cmd),
            CommandHandler("stock",    stock_cmd),
            CommandHandler("signal",   signal_cmd),
            CommandHandler("past100x", past100x_cmd),
            CallbackQueryHandler(pay_start_cb, pattern=START_PAT),
            CallbackQueryHandler(select_plan,  pattern=PLAN_PAT),
            CallbackQueryHandler(cart_pay,     pattern=r"^cart_pay$"),
            CallbackQueryHandler(select_chain, pattern=CHAIN_PAT),
        ],
        states={
            SELECT_PLAN: [
                CallbackQueryHandler(select_plan,   pattern=PLAN_PAT),
                CallbackQueryHandler(pay_start_cb,  pattern=START_PAT),
            ],
            CONFIRM_CART: [
                CallbackQueryHandler(cart_pay,      pattern=r"^cart_pay$"),
                CallbackQueryHandler(select_plan,   pattern=PLAN_PAT),
                CallbackQueryHandler(pay_start_cb,  pattern=START_PAT),
            ],
            SELECT_CHAIN: [
                CallbackQueryHandler(select_chain,  pattern=CHAIN_PAT),
                CallbackQueryHandler(cart_pay,      pattern=r"^cart_pay$"),
                CallbackQueryHandler(pay_start_cb,  pattern=START_PAT),
            ],
            ENTER_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_wallet),
                CallbackQueryHandler(cart_pay,      pattern=r"^cart_pay$"),
                CallbackQueryHandler(pay_start_cb,  pattern=START_PAT),
            ],
            ENTER_TXHASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_txhash),
                CallbackQueryHandler(cart_pay,      pattern=r"^cart_pay$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
        per_message=False,
        allow_reentry=True,
    )
