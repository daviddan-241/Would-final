"""
Payment flow for Alpha_Calls VIP.
User clicks "Join VIP" in channel → opens bot DM → sees product + pricing.
Selects plan → sees SOL address + exact amount to send.
Pastes tx hash → verified → receives group link.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from blockchain_verify import verify_transaction, SOL_ADDRESS, ETH_ADDRESS

log = logging.getLogger(__name__)

GROUP_LINK  = "https://t.me/+b7UesS3ulxxlZDdk"
BNB_ADDRESS = "bnb189gjjucwltdpnlemrveakf0q6xg0smfqdh6869"

# Plans — update SOL amounts when price moves significantly
PLANS = {
    "monthly":  {"label": "$49 / month",    "usd": 49,  "sol": 0.42},
    "lifetime": {"label": "$75 / lifetime", "usd": 75,  "sol": 0.64},
}

SELECT_PLAN, ENTER_WALLET, ENTER_TXHASH = range(3)

# ── Product description (matches reference screenshots) ────────────────────────
PRODUCT_MSG = (
    "🚀 *Alpha_Calls VIP*\n\n"
    "💰 Very High ROI!\n\n"
    "For you exclusively on VIP Channel:\n\n"
    "✅ All the Calls our AI identifies, filtered and selected by our algorithm.\n"
    "✅ No delay in publication. Early entry, high winrate, high ROI.\n"
    "✅ Risks Classification.\n"
    "✅ Copy CA with tap.\n"
    "✅ No Spam.\n"
    "✅ \"Print Money\" Strategy\n"
    "🔥 Several 50-100x!\n\n"
    "——————-\n\n"
    "☝️ Don't pay with Cex.\n\n"
    "🆘 Support @alpha\\_circle1\n\n"
    "🔒 *Telegram access*\nAlpha_Calls VIP Channel 💰\n\n"
    "*Select your plan:*"
)

def _plan_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("$49 / month",    callback_data="plan_monthly"),
        InlineKeyboardButton("$75 / lifetime", callback_data="plan_lifetime"),
    ]])


# ── /start handler ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if args and args[0].lower() in ("vip", "join", "pay", "alpha", "get"):
        return await _show_product(update.message, context)

    # Generic /start — short welcome + button
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔐 Join VIP", callback_data="pay_start")
    ]])
    await update.message.reply_text(
        "👋 *Alpha_Calls Bot*\n\n"
        "We post early calls before CT finds them.\n"
        "VIP group gets them first — full details below 👇",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    return ConversationHandler.END


async def pay_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _show_product(update.callback_query.message, context)


async def _show_product(msg, context):
    await msg.reply_text(
        PRODUCT_MSG,
        parse_mode="Markdown",
        reply_markup=_plan_keyboard(),
    )
    return SELECT_PLAN


# ── Plan selected → show address + amount immediately ─────────────────────────
async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.replace("plan_", "")
    if plan_key not in PLANS:
        return SELECT_PLAN

    plan = PLANS[plan_key]
    sol  = plan["sol"]
    context.user_data["plan"] = plan_key

    await query.message.reply_text(
        f"✅ *{plan['label']}* selected\n\n"
        f"——————-\n\n"
        f"⏳ *Watching your wallet*\n"
        f"Send payment from your wallet ➜ to store address\n\n"
        f"🍎 *Store address* 📋\n"
        f"↓ Send SOL to:\n"
        f"`{SOL_ADDRESS}`\n\n"
        f"*Cart*\n"
        f"{plan['label']} 🟡 Alpha_Calls VIP\n"
        f"——————-\n"
        f"`{sol:.5f} SOL` ← checkout total\n\n"
        f"Once sent, paste the *wallet address you paid FROM* so we can verify 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩ Change plan", callback_data="pay_start")
        ]]),
    )
    return ENTER_WALLET


# ── User pastes sending wallet ─────────────────────────────────────────────────
async def enter_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text.strip()
    if len(wallet) < 20:
        await update.message.reply_text(
            "⚠️ That doesn't look right. Please paste your SOL wallet address (the one you sent FROM):"
        )
        return ENTER_WALLET

    context.user_data["wallet"] = wallet
    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    sol      = plan["sol"]
    short    = wallet[:6] + ".." + wallet[-4:]

    await update.message.reply_text(
        f"⏳ *Watching wallet* `{short}`\n\n"
        f"Amount to send: `{sol:.5f} SOL`\n"
        f"To: `{SOL_ADDRESS}`\n\n"
        f"After sending, paste your *transaction hash* (tx ID) here 👇\n"
        f"_Find it on Solscan or your wallet history_",
        parse_mode="Markdown",
    )
    return ENTER_TXHASH


# ── User pastes tx hash → verify → deliver group link ─────────────────────────
async def enter_txhash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_hash = update.message.text.strip()
    if len(tx_hash) < 30:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid tx hash. Paste the full transaction ID:"
        )
        return ENTER_TXHASH

    await update.message.reply_text("🔍 Verifying on-chain... one moment.")

    wallet  = context.user_data.get("wallet", "")
    success, msg = verify_transaction("sol", tx_hash, wallet)

    if success:
        plan_key = context.user_data.get("plan", "monthly")
        plan     = PLANS[plan_key]
        await update.message.reply_text(
            f"✅ *Payment confirmed!*\n\n"
            f"Plan: *{plan['label']}*\n\n"
            f"Welcome to Alpha_Calls VIP 🏆\n"
            f"You're now ahead of the public channel.\n"
            f"Don't share — member-only link 🤫\n\n"
            f"👇 *Your access link:*\n{GROUP_LINK}",
            parse_mode="Markdown",
        )
        log.info(f"✅ Payment OK — user={update.effective_user.id} "
                 f"plan={plan_key} tx={tx_hash}")
    else:
        await update.message.reply_text(
            f"❌ *Could not verify*\n\n{msg}\n\n"
            "Check your tx hash and try again with /pay\n"
            "_Make sure you sent from the wallet you registered above_",
            parse_mode="Markdown",
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Start again anytime with /pay")
    return ConversationHandler.END


# ── Build conversation handler ─────────────────────────────────────────────────
def build_payment_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("pay",  _show_product_cmd),
            CommandHandler("join", _show_product_cmd),
            CallbackQueryHandler(pay_start_cb, pattern="^pay_start$"),
        ],
        states={
            SELECT_PLAN: [
                CallbackQueryHandler(select_plan, pattern="^plan_(monthly|lifetime)$"),
                CallbackQueryHandler(pay_start_cb, pattern="^pay_start$"),
            ],
            ENTER_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_wallet),
                CallbackQueryHandler(pay_start_cb, pattern="^pay_start$"),
            ],
            ENTER_TXHASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_txhash),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
        per_message=False,
        allow_reentry=True,
    )


async def _show_product_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _show_product(update.message, context)
