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
CHANNEL_NAME   = os.getenv("CHANNEL_NAME",     "Alpha_X_Calls")

PLANS = {
    "monthly":   {"label": "$44 / month",     "usd": 44,  "short": "Monthly"},
    "quarterly": {"label": "$69 / 3 months",  "usd": 69,  "short": "3 Months"},
    "lifetime":  {"label": "$99 / lifetime",  "usd": 99,  "short": "Lifetime"},
}

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Plain /start in DM → straight to the product page."""
    args = context.args or []
    arg = args[0].lower() if args else ""
    if arg == "past100x":
        return await _past_100x_intro(update.message, context)
    if arg == "results":
        return await _past_100x_intro(update.message, context)
    return await _show_product(update.message, context)


async def _past_100x_intro(msg, context):
    text = (
        f"🏆 *Past 100x — VIP Archive*\n\n"
        f"The 100x receipts (PEPE, WIF, BOME, MOODENG, BONK, MEW, "
        f"$CHSN +196x and the rest) live inside the VIP archive.\n\n"
        f"Public channel only shows the *late-stage mirror*. "
        f"VIP archive shows the *original entries* — call mcap, exit mcap, "
        f"timestamp, screenshots, on-chain tx.\n\n"
        f"It's the receipts. Not marketing.\n\n"
        f"👇 Pick a plan to unlock the archive."
    )
    await msg.reply_text(text, parse_mode="Markdown",
                         reply_markup=_plan_keyboard())
    return SELECT_PLAN


# ══════════════════════════════════════════════════════════════════════════════
#  Product page
# ══════════════════════════════════════════════════════════════════════════════

PRODUCT_TEXT = (
    f"*{CHANNEL_NAME}  ·  Premium Access*\n\n"
    "Real alpha. No hype. No fluff.\n\n"
    "🔐 *What you actually get*\n"
    "▸ *Memecoin alpha 4–6h before* the public mirror\n"
    "▸ Multi-chain coverage  ·  Solana · Ethereum · BNB Chain · Base\n"
    "▸ Forex / macro setups with live TP & SL management\n"
    "▸ Index & equities desk (NVDA, TSLA, META, AMD, COIN…)\n"
    "▸ On-chain whale & insider wallet alerts\n"
    "▸ Real-time entry / scale-in / exit calls\n"
    "▸ VIP chatroom — direct line to the desk\n\n"
    "💎 *Inside the group*\n"
    "🥷 Sniper  ·  ⚡ Alpha  ·  💎 Apex\n"
    "🏆 VIP Milestone Tracker  ·  💬 Chatroom\n\n"
    "📊 30+ quality signals / day  ·  300+ active members\n\n"
    "💳 *Payment — 3 chains accepted*\n"
    "Solana · Ethereum · BNB Chain.\n"
    "⚠️ *Never pay from a CEX* (Binance / Coinbase / OKX). Tx will not match.\n\n"
    "✅ *Instant access* after on-chain confirmation. No manual approval.\n\n"
    "👇 *All plans = same VIP access.*  Only difference: how long you stay inside.\n\n"
    f"❓ Support: {SUPPORT_USER}  _(payment or access issues only)_\n\n"
    "*Pricing*"
)


def _plan_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("$44 / month",      callback_data="plan_monthly")],
        [InlineKeyboardButton("$69 / 3 months",   callback_data="plan_quarterly")],
        [InlineKeyboardButton("$99 / lifetime",   callback_data="plan_lifetime")],
        [InlineKeyboardButton("💬 Talk to the desk",
                              url=f"https://t.me/{SUPPORT_USER.lstrip('@')}")],
    ])


async def pay_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _show_product(update.callback_query.message, context)


async def _show_product(msg, context):
    await msg.reply_text(
        PRODUCT_TEXT,
        parse_mode="Markdown",
        reply_markup=_plan_keyboard(),
    )
    return SELECT_PLAN


# ══════════════════════════════════════════════════════════════════════════════
#  Plan selected → cart confirmation
# ══════════════════════════════════════════════════════════════════════════════

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.replace("plan_", "")
    if plan_key not in PLANS:
        return SELECT_PLAN

    plan = PLANS[plan_key]
    context.user_data["plan"] = plan_key

    other_rows = []
    for k, v in PLANS.items():
        if k == plan_key:
            continue
        other_rows.append([InlineKeyboardButton(v["label"], callback_data=f"plan_{k}")])

    cart_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ {plan['label']}",      callback_data=f"plan_{plan_key}")],
        *other_rows,
        [InlineKeyboardButton("💳 Continue to payment",   callback_data="cart_pay")],
        [InlineKeyboardButton("✕ Remove from cart",      callback_data="pay_start")],
    ])

    await query.message.reply_text(
        f"🟡 *In cart*\n\n"
        f"——————\n\n"
        f"*{CHANNEL_NAME}*\n\n"
        f"🟡 {plan['label']}  •  VIP Access (multi-chain)\n\n"
        f"——————\n\n"
        f"*All plans = same VIP access.*\n"
        f"Only difference: how long you stay.\n\n"
        f"Next step: pick the chain you want to pay from "
        f"(SOL · ETH · BNB).",
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

    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]

    chain_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Solana (SOL)",   callback_data="chain_sol")],
        [InlineKeyboardButton("🟣 Ethereum (ETH)", callback_data="chain_eth")],
        [InlineKeyboardButton("🟡 BNB Chain (BNB)",callback_data="chain_bnb")],
        [InlineKeyboardButton("↩ Change plan",     callback_data="pay_start")],
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
    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    native   = _usd_to_native(plan["usd"], chain_key)

    await query.message.reply_text(
        f"⏳ *Watching the {chain['symbol']} address*\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send `{chain['symbol']}` to:\n"
        f"`{chain['address']}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']}  🟡  {CHANNEL_NAME} VIP\n"
        f"——————\n"
        f"`{native} {chain['symbol']}` ← checkout total\n"
        f"_(based on live {chain['symbol']}/USD)_\n\n"
        f"——————\n\n"
        f"👇 Paste the wallet address you're *sending FROM*\n"
        f"_(So we can match your payment on-chain)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Change chain", callback_data="cart_pay")],
            [InlineKeyboardButton("↩ Change plan",  callback_data="pay_start")],
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
    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    native   = _usd_to_native(plan["usd"], chain_key)
    short    = wallet[:6] + ".." + wallet[-4:]

    await update.message.reply_text(
        f"⏳ *Watching wallet* `{short}`  ▸  Pay from here\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send `{chain['symbol']}` from `{short}` to:\n"
        f"`{chain['address']}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']}  🟡  {CHANNEL_NAME} VIP {chain['symbol']}\n"
        f"——————\n"
        f"`{native} {chain['symbol']}` ← checkout total\n\n"
        f"——————\n\n"
        f"👇 After sending, paste your *transaction signature* (tx ID)\n"
        f"_Find it in your wallet history or on the explorer_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ {plan['label']}", callback_data=f"plan_{plan_key}"),
            InlineKeyboardButton("↩ Change wallet",    callback_data="cart_pay"),
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
        plan_key = context.user_data.get("plan", "monthly")
        plan     = PLANS[plan_key]
        await update.message.reply_text(
            f"✅ *Payment confirmed on-chain!*\n\n"
            f"Chain : *{chain['label']}*\n"
            f"Plan  : *{plan['label']}*\n"
            f"Tx    : [{tx_hash[:18]}…]({chain['explorer']}{tx_hash})\n\n"
            f"Welcome to *{CHANNEL_NAME} VIP* 🏆\n\n"
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
            f"Need help? Contact {SUPPORT_USER}",
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
    return await _show_product(update.message, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cancelled. Start again any time with /pay 👋",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 Join VIP", callback_data="pay_start"),
        ]]),
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
def build_payment_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start",  start),
            CommandHandler("pay",    pay_cmd),
            CommandHandler("join",   pay_cmd),
            CommandHandler("vip",    pay_cmd),
            CallbackQueryHandler(pay_start_cb, pattern="^pay_start$"),
            CallbackQueryHandler(select_plan,  pattern="^plan_(monthly|quarterly|lifetime)$"),
            CallbackQueryHandler(cart_pay,     pattern="^cart_pay$"),
            CallbackQueryHandler(select_chain, pattern="^chain_(sol|eth|bnb)$"),
        ],
        states={
            SELECT_PLAN: [
                CallbackQueryHandler(select_plan,   pattern="^plan_(monthly|quarterly|lifetime)$"),
                CallbackQueryHandler(pay_start_cb,  pattern="^pay_start$"),
            ],
            CONFIRM_CART: [
                CallbackQueryHandler(cart_pay,      pattern="^cart_pay$"),
                CallbackQueryHandler(select_plan,   pattern="^plan_(monthly|quarterly|lifetime)$"),
                CallbackQueryHandler(pay_start_cb,  pattern="^pay_start$"),
            ],
            SELECT_CHAIN: [
                CallbackQueryHandler(select_chain,  pattern="^chain_(sol|eth|bnb)$"),
                CallbackQueryHandler(cart_pay,      pattern="^cart_pay$"),
                CallbackQueryHandler(pay_start_cb,  pattern="^pay_start$"),
            ],
            ENTER_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_wallet),
                CallbackQueryHandler(cart_pay,      pattern="^cart_pay$"),
                CallbackQueryHandler(pay_start_cb,  pattern="^pay_start$"),
            ],
            ENTER_TXHASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_txhash),
                CallbackQueryHandler(cart_pay,      pattern="^cart_pay$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
        per_message=False,
        allow_reentry=True,
    )
