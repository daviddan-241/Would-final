import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from blockchain_verify import (
    verify_transaction,
    SOL_ADDRESS, ETH_ADDRESS, BNB_HEX_ADDRESS
)

log = logging.getLogger(__name__)

GROUP_LINK = "https://t.me/+b7UesS3ulxxlZDdk"

BNB_ADDRESS = "bnb189gjjucwltdpnlemrveakf0q6xg0smfqdh6869"

CHOOSE_CHAIN, ENTER_WALLET, ENTER_TXHASH = range(3)

PAYMENT_MSG = (
    "🔥 *Alpha Circle — VIP Intel Group Access*\n\n"
    "Our private group gets early calls *before* the public channel.\n"
    "The results speak for themselves — 48X, 67X, 196X, 111X.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "💳 *Send payment to one of these addresses:*\n\n"
    f"◎ *Solana (SOL)*\n`{SOL_ADDRESS}`\n\n"
    f"⟠ *Ethereum (ETH)*\n`{ETH_ADDRESS}`\n\n"
    f"🟡 *BNB Chain*\n`{BNB_ADDRESS}`\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "After sending, select which chain you paid on 👇"
)


def payment_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◎ Solana", callback_data="chain_sol"),
            InlineKeyboardButton("⟠ Ethereum", callback_data="chain_eth"),
            InlineKeyboardButton("🟡 BNB", callback_data="chain_bnb"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="pay_cancel")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if args and args[0].lower() in ("vip", "join", "pay", "alpha"):
        return await _start_payment(update, context)
    await update.message.reply_text(
        "👋 *Alpha Circle Bot*\n\n"
        "I scan DEX Screener and post early Solana gem calls.\n\n"
        "🔥 Want early access? Join the private intel group:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Join Alpha VIP", callback_data="pay_start")
        ]])
    )
    return ConversationHandler.END


async def pay_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        PAYMENT_MSG, parse_mode="Markdown", reply_markup=payment_keyboard()
    )
    return CHOOSE_CHAIN


async def _start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        PAYMENT_MSG, parse_mode="Markdown", reply_markup=payment_keyboard()
    )
    return CHOOSE_CHAIN


async def choose_chain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "pay_cancel":
        await query.message.reply_text("❌ Cancelled. Come back when you're ready!")
        return ConversationHandler.END

    chain_map = {"chain_sol": "sol", "chain_eth": "eth", "chain_bnb": "bnb"}
    chain = chain_map.get(data)
    if not chain:
        return ConversationHandler.END

    context.user_data["chain"] = chain

    chain_labels = {"sol": "Solana (SOL)", "eth": "Ethereum (ETH)", "bnb": "BNB Chain"}
    await query.message.reply_text(
        f"✅ Chain selected: *{chain_labels[chain]}*\n\n"
        f"Now send me the *wallet address* you paid *from*:",
        parse_mode="Markdown"
    )
    return ENTER_WALLET


async def enter_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text.strip()
    if len(wallet) < 20:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid wallet address. Please try again:"
        )
        return ENTER_WALLET

    context.user_data["wallet"] = wallet
    chain = context.user_data.get("chain", "sol")
    chain_labels = {"sol": "Solana (SOL)", "eth": "Ethereum (ETH)", "bnb": "BNB Chain"}

    await update.message.reply_text(
        f"📋 Wallet recorded.\n\n"
        f"Now paste your *transaction hash* (tx ID) for the {chain_labels[chain]} payment:",
        parse_mode="Markdown"
    )
    return ENTER_TXHASH


async def enter_txhash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_hash = update.message.text.strip()
    if len(tx_hash) < 30:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid transaction hash. Please try again:"
        )
        return ENTER_TXHASH

    chain = context.user_data.get("chain", "sol")
    wallet = context.user_data.get("wallet", "")

    await update.message.reply_text("🔍 Verifying your transaction on-chain... please wait.")

    success, msg = verify_transaction(chain, tx_hash, wallet)

    if success:
        await update.message.reply_text(
            "✅ *Payment verified!*\n\n"
            "Welcome to the Alpha Circle intel group. "
            "You're now getting calls before the public channel. "
            "Don't share the link — it's member-only 🤫\n\n"
            f"👇 *Your exclusive access link:*\n{GROUP_LINK}",
            parse_mode="Markdown"
        )
        log.info(f"✅ Payment verified — user {update.effective_user.id} | chain={chain} | tx={tx_hash}")
    else:
        await update.message.reply_text(
            f"❌ *Verification failed*\n\n{msg}\n\n"
            "Double-check the details and try again with /pay",
            parse_mode="Markdown"
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def build_payment_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("pay", _start_payment),
            CommandHandler("join", _start_payment),
            CallbackQueryHandler(pay_start_callback, pattern="^pay_start$"),
        ],
        states={
            CHOOSE_CHAIN: [
                CallbackQueryHandler(choose_chain, pattern="^(chain_sol|chain_eth|chain_bnb|pay_cancel)$")
            ],
            ENTER_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_wallet)
            ],
            ENTER_TXHASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_txhash)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
