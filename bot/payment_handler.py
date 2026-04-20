"""
Payment flow modelled exactly on the Telegram-native payment bot UX shown in the reference screenshots.
Flow:
  1. /start vip  →  product description + pricing buttons
  2. User picks plan  →  "in cart" + Continue/Remove buttons
  3. Continue  →  wallet watch + SOL address + checkout total
  4. User pastes their sending wallet  →  bot watches / user submits tx hash
  5. Verified  →  group link delivered
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from blockchain_verify import verify_transaction, SOL_ADDRESS, ETH_ADDRESS

log = logging.getLogger(__name__)

GROUP_LINK   = "https://t.me/+b7UesS3ulxxlZDdk"
BNB_ADDRESS  = "bnb189gjjucwltdpnlemrveakf0q6xg0smfqdh6869"

# SOL price approximations — update when SOL moves significantly
PLANS = {
    "monthly":  {"label": "$49 / month",   "usd": 49,  "sol": 0.42},
    "lifetime": {"label": "$75 / lifetime", "usd": 75,  "sol": 0.64},
}

CHOOSE_PLAN, CONFIRM_PLAN, ENTER_WALLET, ENTER_TXHASH = range(4)

# ── Product description (matches screenshot exactly) ───────────────────────────
PRODUCT_HEADER = (
    "🚀 *Alpha Circle VIP Channel*\n\n"
    "💰 Very High ROI!\n\n"
    "For you exclusively on VIP Channel:\n\n"
    "✅ All the Calls our AI identifies, filtered and selected by our algorithm.\n"
    "✅ No delay in publication. Early entry, high winrate, high ROI.\n"
    "✅ Risks Classification.\n"
    "✅ Copy CA with tap.\n"
    "✅ No Spam.\n"
    "✅ \"Print Money\" Strategy\n"
    "🔥 Several 50\\-100x\\!\n\n"
    "——————\-\n\n"
    "☝️ Don't pay with Cex\\.\n\n"
    "🆘 Support @alpha\\_circle1\n\n"
    "🔒 *Telegram access*\n"
    "Alpha Circle VIP Channel 💰\n\n"
    "*Pricing:*"
)

PRODUCT_HEADER_MD = (
    "🚀 *Alpha Circle VIP Channel*\n\n"
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
    "🔒 *Telegram access*\n"
    "Alpha Circle VIP Channel 💰\n\n"
    "*Pricing:*"
)


def _plan_buttons():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("$49 / month",   callback_data="plan_monthly"),
        InlineKeyboardButton("$75 / lifetime", callback_data="plan_lifetime"),
    ]])


def _cart_buttons(plan_key: str):
    plan = PLANS[plan_key]
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ {plan['label']}", callback_data=f"plan_{plan_key}"),
            InlineKeyboardButton("$75 / lifetime" if plan_key == "monthly" else "$49 / month",
                                 callback_data="plan_lifetime" if plan_key == "monthly" else "plan_monthly"),
        ],
        [InlineKeyboardButton("🛒 Continue to payment", callback_data="cart_continue")],
        [InlineKeyboardButton("✕ Remove from cart",    callback_data="cart_remove")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if args and args[0].lower() in ("vip", "join", "pay", "alpha", "get"):
        return await _show_product(update, context)
    # Generic /start
    await update.message.reply_text(
        "👋 *Alpha Circle Bot*\n\n"
        "I track on-chain moves and post early gem calls before the crowd finds them.\n\n"
        "Want the full alpha? Hit below 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 Get VIP Access", callback_data="pay_start")
        ]])
    )
    return ConversationHandler.END


async def _show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return ConversationHandler.END
    await msg.reply_text(
        PRODUCT_HEADER_MD,
        parse_mode="Markdown",
        reply_markup=_plan_buttons(),
    )
    return CHOOSE_PLAN


async def pay_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _show_product(update, context)


async def choose_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.replace("plan_", "")
    if plan_key not in PLANS:
        return CHOOSE_PLAN

    plan = PLANS[plan_key]
    context.user_data["plan"] = plan_key

    await query.message.reply_text(
        f"🟡 *in cart*\nproceed to payment",
        parse_mode="Markdown",
        reply_markup=_cart_buttons(plan_key),
    )
    return CONFIRM_PLAN


async def cart_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("plan_"):
        # User changed plan
        plan_key = query.data.replace("plan_", "")
        if plan_key in PLANS:
            context.user_data["plan"] = plan_key
            plan = PLANS[plan_key]
            await query.message.reply_text(
                f"🟡 *in cart*\nproceed to payment",
                parse_mode="Markdown",
                reply_markup=_cart_buttons(plan_key),
            )
        return CONFIRM_PLAN

    if query.data == "cart_remove":
        await query.message.reply_text(
            "Removed from cart. Come back anytime — the group is open.",
        )
        return ConversationHandler.END

    if query.data == "cart_continue":
        plan_key = context.user_data.get("plan", "monthly")
        plan     = PLANS[plan_key]
        sol_amt  = plan["sol"]

        await query.message.reply_text(
            f"1\\. Register your sending wallet address\n"
            f"2\\. Manually send SOL to the store's address\n"
            f"3\\. Join the premium channel right away\n\n"
            f"⏳ *Watching your new wallet*\n"
            f"Send payment from your wallet \\> Pay from here\n\n"
            f"🍎 *store address* 📋\n"
            f"↓ Send SOL to:\n"
            f"`{SOL_ADDRESS}`\n\n"
            f"*Cart*\n"
            f"{plan['label']} 🟡 Alpha Circle VIP\n"
            f"——————————\n"
            f"`{sol_amt:.5f} SOL` ← checkout total\n\n"
            f"*Paste the wallet address you are paying FROM:*",
            parse_mode="MarkdownV2",
        )
        return ENTER_WALLET

    return CONFIRM_PLAN


async def enter_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text.strip()
    if len(wallet) < 20:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid wallet. Please paste your SOL wallet address:"
        )
        return ENTER_WALLET

    context.user_data["wallet"] = wallet
    plan_key = context.user_data.get("plan", "monthly")
    plan     = PLANS[plan_key]
    sol_amt  = plan["sol"]
    short    = wallet[:6] + ".." + wallet[-4:]

    await update.message.reply_text(
        f"⏳ *Watching your wallet* `{short}`\n\n"
        f"Send exactly `{sol_amt:.5f} SOL` to:\n"
        f"`{SOL_ADDRESS}`\n\n"
        f"Once sent, paste your *transaction hash* (tx ID) below so we can verify it:",
        parse_mode="Markdown",
    )
    return ENTER_TXHASH


async def enter_txhash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_hash = update.message.text.strip()
    if len(tx_hash) < 30:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid tx hash. Please paste the full transaction ID:"
        )
        return ENTER_TXHASH

    chain  = "sol"
    wallet = context.user_data.get("wallet", "")

    await update.message.reply_text("🔍 Verifying on-chain... hold tight.")
    success, msg = verify_transaction(chain, tx_hash, wallet)

    if success:
        plan_key = context.user_data.get("plan", "monthly")
        plan     = PLANS[plan_key]
        await update.message.reply_text(
            f"✅ *Payment confirmed!*\n\n"
            f"Plan: *{plan['label']}*\n\n"
            f"Welcome to Alpha Circle VIP. You're now ahead of the public channel. "
            f"Don't share this link — member-only access 🤫\n\n"
            f"👇 *Your access link:*\n{GROUP_LINK}",
            parse_mode="Markdown",
        )
        log.info(f"✅ Payment verified — user {update.effective_user.id} "
                 f"plan={plan_key} tx={tx_hash}")
    else:
        await update.message.reply_text(
            f"❌ *Could not verify the transaction*\n\n{msg}\n\n"
            "Please double-check the tx hash and wallet, then try again with /pay",
            parse_mode="Markdown",
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Use /pay to restart anytime.")
    return ConversationHandler.END


def build_payment_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("pay",  _show_product),
            CommandHandler("join", _show_product),
            CallbackQueryHandler(pay_start_callback, pattern="^pay_start$"),
        ],
        states={
            CHOOSE_PLAN: [
                CallbackQueryHandler(choose_plan, pattern="^plan_(monthly|lifetime)$"),
            ],
            CONFIRM_PLAN: [
                CallbackQueryHandler(cart_action,
                    pattern="^(plan_monthly|plan_lifetime|cart_continue|cart_remove)$"),
            ],
            ENTER_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_wallet),
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
