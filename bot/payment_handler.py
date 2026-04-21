"""
Alpha_X_Calls — Premium VIP payment flow.

Matches the real "Bullish Calls / Solana100xCall" Telegram payment-bot UX:
  /start                       → numbered steps + watching wallet + store address
  Choose plan                  → in-cart confirmation
  Continue to payment          → wallet to send FROM
  Paste sender wallet          → store address + checkout total in SOL
  Paste tx hash                → on-chain verify  →  VIP group link
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
from blockchain_verify import verify_transaction, SOL_ADDRESS

log = logging.getLogger(__name__)

GROUP_LINK     = os.getenv("VIP_GROUP_LINK",  "https://t.me/+b7UesS3ulxxlZDdk")
SUPPORT_USER   = os.getenv("SUPPORT_USERNAME", "@JordanDev1979")
if not SUPPORT_USER.startswith("@"):
    SUPPORT_USER = "@" + SUPPORT_USER
CHANNEL_NAME   = os.getenv("CHANNEL_NAME",     "Alpha_X_Calls")

PLANS = {
    "monthly":   {"label": "$44 / month",     "usd": 44,  "short": "Monthly"},
    "quarterly": {"label": "$69 / 3 months",  "usd": 69,  "short": "3 Months"},
    "lifetime":  {"label": "$99 / lifetime",  "usd": 99,  "short": "Lifetime"},
}

# ── States ────────────────────────────────────────────────────────────────────
SELECT_PLAN, CONFIRM_CART, ENTER_WALLET, ENTER_TXHASH = range(4)


# ── Live SOL price (cached 5 min) ────────────────────────────────────────────
_sol_price_cache = {"price": 145.0, "ts": 0.0}

def _sol_price() -> float:
    if time.time() - _sol_price_cache["ts"] < 300:
        return _sol_price_cache["price"]
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "solana", "vs_currencies": "usd"},
            timeout=8,
        )
        p = float(r.json()["solana"]["usd"])
        if p > 0:
            _sol_price_cache.update({"price": p, "ts": time.time()})
    except Exception as e:
        log.warning(f"SOL price fetch failed: {e}")
    return _sol_price_cache["price"]


def _usd_to_sol(usd: float) -> float:
    return round(usd / _sol_price(), 5)


# ══════════════════════════════════════════════════════════════════════════════
#  /start  →  Bullish-Calls-style numbered steps + cart
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Plain /start in DM → straight to the product page (cleaner UX)."""
    return await _show_product(update.message, context)


# ══════════════════════════════════════════════════════════════════════════════
#  Product page — matches Solana100xCall "Alpha Premium Access"
# ══════════════════════════════════════════════════════════════════════════════

PRODUCT_TEXT = (
    f"*{CHANNEL_NAME}  ·  Premium Access*\n\n"
    "Real alpha. No fluff. No hype posts.\n\n"
    "🔐 *What you actually get*\n"
    "▸ *Memecoin alpha 4–6h before* the public mirror\n"
    "▸ Forex / macro setups with live TP & SL management\n"
    "▸ Index & equities desk (NVDA, TSLA, META, AMD, COIN…)\n"
    "▸ On-chain whale & insider wallet alerts\n"
    "▸ Real-time entry / scale-in / exit calls\n"
    "▸ VIP chatroom — direct access to the desk\n\n"
    "💎 *Inside the group*\n"
    "🥷 Sniper  ·  ⚡ Alpha  ·  💎 Apex\n"
    "🏆 VIP Milestone Tracker  ·  💬 Chatroom\n\n"
    "📊 30+ quality signals / day  ·  300+ active traders\n\n"
    "💳 *Payment*\n"
    "Pay with your Solana wallet — Phantom · Backpack · Solflare · Trojan · Bloom.\n"
    "⚠️ *Never pay from a CEX* (Binance, Coinbase, OKX). Tx will not match.\n\n"
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
        [InlineKeyboardButton("🛒 Back to cart",  callback_data="pay_start")],
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
        f"🟡 *in cart*\nproceed to payment\n\n"
        f"——————\n\n"
        f"*{CHANNEL_NAME}*\n\n"
        f"🟡 {plan['label']}  •  {CHANNEL_NAME} VIP Solana\n\n"
        f"——————\n\n"
        f"*All plans = Same VIP access.*\n"
        f"Only difference: How long you stay.",
        parse_mode="Markdown",
        reply_markup=cart_kb,
    )
    return CONFIRM_CART


# ══════════════════════════════════════════════════════════════════════════════
#  Continue to payment → ask for sender wallet
# ══════════════════════════════════════════════════════════════════════════════

async def cart_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    sol      = _usd_to_sol(plan["usd"])

    await query.message.reply_text(
        f"⏳ *Watching your wallet*\n"
        f"Pay from here ▸ store address\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send `SOL` to:\n"
        f"`{SOL_ADDRESS}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']}  🟡  {CHANNEL_NAME} VIP Solana\n"
        f"——————\n"
        f"`{sol:.5f} SOL` ← checkout total\n"
        f"_(based on live SOL/USD)_\n\n"
        f"——————\n\n"
        f"👇 Paste the wallet address you're *sending FROM*\n"
        f"_(So we can match your payment on-chain)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩ Change plan", callback_data="pay_start"),
        ]]),
    )
    return ENTER_WALLET


# ══════════════════════════════════════════════════════════════════════════════
#  User pastes sending wallet
# ══════════════════════════════════════════════════════════════════════════════

async def enter_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text.strip()

    if len(wallet) < 32 or " " in wallet:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid Solana address.\n"
            "Paste the SOL address you're *sending from* (32–44 chars, no spaces):",
            parse_mode="Markdown",
        )
        return ENTER_WALLET

    context.user_data["wallet"] = wallet
    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    sol      = _usd_to_sol(plan["usd"])
    short    = wallet[:6] + ".." + wallet[-4:]

    await update.message.reply_text(
        f"⏳ *Watching wallet* `{short}`  ▸  Pay from here\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send `SOL` from `{short}` to:\n"
        f"`{SOL_ADDRESS}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']}  🟡  {CHANNEL_NAME} VIP Solana\n"
        f"——————\n"
        f"`{sol:.5f} SOL` ← checkout total\n\n"
        f"——————\n\n"
        f"👇 After sending, paste your *transaction signature* (tx ID)\n"
        f"_Find it in your wallet history or on Solscan_",
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
    tx_hash = update.message.text.strip()

    if len(tx_hash) < 30 or " " in tx_hash:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid transaction signature.\n"
            "Paste the full tx ID (no spaces):",
            parse_mode="Markdown",
        )
        return ENTER_TXHASH

    await update.message.reply_text(
        "🔍 *Verifying on-chain...*\nThis takes a few seconds.",
        parse_mode="Markdown",
    )

    wallet   = context.user_data.get("wallet", "")
    success, msg_text = verify_transaction("sol", tx_hash, wallet)

    if success:
        plan_key = context.user_data.get("plan", "monthly")
        plan     = PLANS[plan_key]
        await update.message.reply_text(
            f"✅ *Payment confirmed on-chain!*\n\n"
            f"Plan: *{plan['label']}*\n"
            f"Tx: `{tx_hash[:24]}...`\n\n"
            f"Welcome to *{CHANNEL_NAME} VIP* 🏆\n\n"
            f"You now have access to:\n"
            f"🥷 Sniper  •  ⚡ Alpha  •  💎 Apex\n"
            f"🏆 VIP Milestone Tracker  •  💬 VIP Chatroom\n\n"
            f"Don't share this link — members only 🤫\n\n"
            f"👇 *Your private access link:*\n{GROUP_LINK}",
            parse_mode="Markdown",
        )
        log.info(f"✅ VIP payment confirmed — uid={update.effective_user.id} "
                 f"plan={plan_key} tx={tx_hash}")
    else:
        await update.message.reply_text(
            f"❌ *Could not verify payment*\n\n"
            f"{msg_text}\n\n"
            f"Double-check your tx and try again. Make sure you sent from "
            f"the wallet you registered above and to the store address shown.\n\n"
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
            ENTER_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_wallet),
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
