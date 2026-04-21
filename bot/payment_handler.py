"""
Alpha_X_Calls — Premium VIP payment flow.

Flow:
  /start  →  welcome
  /start?vip  →  product page (full feature list)
  Select plan  →  cart confirmation
  Continue to payment  →  wallet address + checkout total
  User pastes FROM-wallet  →  watching wallet message
  User pastes TX hash  →  on-chain verify  →  group link
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from blockchain_verify import verify_transaction, SOL_ADDRESS, ETH_ADDRESS

log = logging.getLogger(__name__)

GROUP_LINK     = "https://t.me/+b7UesS3ulxxlZDdk"
SUPPORT_USER   = "@dextrendiing_bot"
BNB_ADDRESS    = "bnb189gjjucwltdpnlemrveakf0q6xg0smfqdh6869"
CHANNEL_NAME   = "Alpha_X_Calls"

PLANS = {
    "monthly":  {"label": "$49 / month",    "usd": 49,  "sol": 0.42, "short": "Monthly"},
    "lifetime": {"label": "$75 / lifetime", "usd": 75,  "sol": 0.64, "short": "Lifetime"},
}

# ── States ────────────────────────────────────────────────────────────────────
SELECT_PLAN, CONFIRM_CART, ENTER_WALLET, ENTER_TXHASH = range(4)


# ══════════════════════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if args and args[0].lower() in ("vip", "join", "pay", "alpha", "get", "premium"):
        return await _show_product(update.message, context)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔐 Get VIP Access", callback_data="pay_start"),
    ], [
        InlineKeyboardButton("📊 What's inside?",  callback_data="pay_start"),
    ]])
    await update.message.reply_text(
        f"👋 *Welcome to {CHANNEL_NAME} Bot*\n\n"
        "We catch gems on Solana before CT wakes up.\n\n"
        "📡 Public channel: free calls & updates\n"
        "🔐 VIP group: *live entries before the post*\n\n"
        "Every call you've seen hit — VIP members got in first.\n\n"
        "Tap below to see what's inside 👇",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  Product page
# ══════════════════════════════════════════════════════════════════════════════

PRODUCT_TEXT = (
    f"*Alpha Premium Access*\n\n"
    f"🚀 *{CHANNEL_NAME} | Premium Signals*\n\n"
    "Real alpha. No fluff.\n\n"
    "💎 *Your VIP Access:*\n\n"
    "📊 30+ quality signals daily\n"
    "👥 300+ active traders\n\n"
    "✅ All calls our AI identifies — filtered & selected by our algorithm.\n"
    "✅ No delay in publication. Early entry, high winrate, high ROI.\n"
    "✅ Risks Classification.\n"
    "✅ Copy CA with tap.\n"
    "✅ No Spam.\n"
    "✅ \"Print Money\" Strategy\n"
    "🔥 Several 50–100x!\n\n"
    "——————\n\n"
    "💳 *Payment & Access*\n\n"
    "Pay with your Solana wallet:\n"
    "Phantom • Backpack • Solflare • Trojan • Bloom\n\n"
    "⚠️ Do NOT pay from Cex (Binance, Coinbase, etc.)\n\n"
    "✅ Instant access after payment\n"
    "No waiting, no manual approval\n\n"
    f"❓ Support: {SUPPORT_USER}\n"
    "_(Payment or access issues only)_\n\n"
    "🔒 *Telegram access*\n"
    f"{CHANNEL_NAME} 💰 VIP Channel\n\n"
    "*Pricing:*"
)


def _plan_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("$49 / month",    callback_data="plan_monthly"),
        InlineKeyboardButton("$75 / lifetime", callback_data="plan_lifetime"),
    ], [
        InlineKeyboardButton("🛒 Back to cart", callback_data="pay_start"),
    ]])


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

    cart_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ {plan['label']}",    callback_data=f"plan_{plan_key}"),
        InlineKeyboardButton("$75 / lifetime" if plan_key == "monthly" else "$49 / month",
                             callback_data="plan_lifetime" if plan_key == "monthly" else "plan_monthly"),
    ], [
        InlineKeyboardButton("💳 Continue to payment", callback_data="cart_pay"),
    ], [
        InlineKeyboardButton("✕ Remove from cart",    callback_data="pay_start"),
    ]])

    await query.message.reply_text(
        f"🟡 *in cart*\nproceed to payment\n\n"
        f"——————\n\n"
        f"*{CHANNEL_NAME}*\n\n"
        f"🟡 {plan['label']} {CHANNEL_NAME} VIP\n\n"
        f"——————\n\n"
        f"*All plans = Same VIP access.*\n"
        f"Only difference: How long you stay.",
        parse_mode="Markdown",
        reply_markup=cart_kb,
    )
    return CONFIRM_CART


# ══════════════════════════════════════════════════════════════════════════════
#  Continue to payment → show wallet address & checkout total
# ══════════════════════════════════════════════════════════════════════════════

async def cart_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    sol      = plan["sol"]

    await query.message.reply_text(
        f"⏳ *Watching your wallet*\n"
        f"Pay from here → store address\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send SOL to:\n"
        f"`{SOL_ADDRESS}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']} 🟡 {CHANNEL_NAME} VIP\n"
        f"——————\n"
        f"`{sol:.5f} SOL` ← checkout total\n\n"
        f"——————\n\n"
        f"Paste the wallet address you're *sending FROM* 👇\n"
        f"_(So we can match your payment on-chain)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩ Change plan", callback_data="pay_start"),
        ]]),
    )
    return ENTER_WALLET


# ══════════════════════════════════════════════════════════════════════════════
#  User pastes sending wallet address
# ══════════════════════════════════════════════════════════════════════════════

async def enter_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text.strip()

    if len(wallet) < 20 or " " in wallet:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid wallet address.\n"
            "Paste the SOL address you're *sending from* (no spaces):",
            parse_mode="Markdown",
        )
        return ENTER_WALLET

    context.user_data["wallet"] = wallet
    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    sol      = plan["sol"]
    short    = wallet[:6] + ".." + wallet[-4:]

    await update.message.reply_text(
        f"⏳ *Watching wallet* `{short}`  ›  Pay from here\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send SOL from `{short}` to:\n"
        f"`{SOL_ADDRESS}`\n\n"
        f"*Cart*\n"
        f"  {plan['label']} 🟡 {CHANNEL_NAME} Solana\n"
        f"——————\n"
        f"`{sol:.5f} SOL` ← checkout total\n\n"
        f"——————\n\n"
        f"After sending, paste your *transaction hash* (tx ID) here 👇\n"
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
            "⚠️ That doesn't look like a valid transaction hash.\n"
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
            f"✅ *Payment confirmed!*\n\n"
            f"Plan: *{plan['label']}*\n\n"
            f"Welcome to *{CHANNEL_NAME} VIP* 🏆\n\n"
            f"You're now ahead of 99% of the market.\n"
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
            f"Double-check your tx hash and try again with /pay\n\n"
            f"Make sure you sent from the wallet you registered above.\n"
            f"Need help? Contact {SUPPORT_USER}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔁 Try again",   callback_data="cart_pay"),
                InlineKeyboardButton("❓ Get support", url=f"https://t.me/{SUPPORT_USER.lstrip('@')}"),
            ]]),
        )

    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
#  /pay and /cancel direct commands
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
#  Build ConversationHandler
# ══════════════════════════════════════════════════════════════════════════════

def build_payment_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("pay",    pay_cmd),
            CommandHandler("join",   pay_cmd),
            CommandHandler("vip",    pay_cmd),
            CallbackQueryHandler(pay_start_cb, pattern="^pay_start$"),
        ],
        states={
            SELECT_PLAN: [
                CallbackQueryHandler(select_plan,   pattern="^plan_(monthly|lifetime)$"),
                CallbackQueryHandler(pay_start_cb,  pattern="^pay_start$"),
            ],
            CONFIRM_CART: [
                CallbackQueryHandler(cart_pay,      pattern="^cart_pay$"),
                CallbackQueryHandler(select_plan,   pattern="^plan_(monthly|lifetime)$"),
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
