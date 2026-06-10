"""
Message formatter — clean caption + inline keyboard buttons (TG + Discord).
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from scanners.base import TokenInfo


def format_caption(token: TokenInfo) -> str:
    """Clean caption for photo/text message."""
    has_discord = bool(token.discord_link)
    has_tg = bool(token.telegram_link)

    socials_line = ""
    if has_tg and has_discord:
        socials_line = "\n💬 TG + <b>Discord</b> found"
    elif has_discord and not has_tg:
        socials_line = "\n💬 <b>Discord</b> community found"

    return (
        f"<b>{_esc(token.name)}</b> (${_esc(token.symbol)})\n"
        f"🔗 {token.chain}{socials_line}\n"
        f"<code>{token.contract_address}</code>"
    )


def build_keyboard(token: TokenInfo) -> InlineKeyboardMarkup:
    """Inline buttons — social links + chart."""
    rows = []

    # Row 1: Telegram + Discord side by side (if both), or whichever exists alone
    row1 = []
    if token.telegram_link:
        row1.append(InlineKeyboardButton("💬 Telegram", url=token.telegram_link))
    if token.discord_link:
        row1.append(InlineKeyboardButton("🎮 Discord", url=token.discord_link))
    if row1:
        rows.append(row1)

    # Row 2: Website + Twitter
    row2 = []
    if token.website:
        row2.append(InlineKeyboardButton("🌐 Website", url=token.website))
    if token.twitter:
        row2.append(InlineKeyboardButton("𝕏 Twitter", url=token.twitter))
    if row2:
        rows.append(row2)

    # Row 3: Chart + DexScreener
    row3 = []
    if token.pair_url:
        row3.append(InlineKeyboardButton("📊 Chart", url=token.pair_url))
    dex_url = f"https://dexscreener.com/solana/{token.contract_address}" if token.chain == "Solana" else token.pair_url
    if dex_url and dex_url != token.pair_url:
        row3.append(InlineKeyboardButton("🔍 DexScreener", url=dex_url))
    if row3:
        rows.append(row3)

    return InlineKeyboardMarkup(rows)


def _esc(text: str) -> str:
    """Escape HTML special chars."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
