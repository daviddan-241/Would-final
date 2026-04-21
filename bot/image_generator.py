"""
Alpha_X_Calls card generator — Solana100xCall-exact visual style.

Card types: build_call_card, build_update_card, build_forex_card
Each post gets a DIFFERENT style/character/theme so the feed never looks repetitive.
"""

import io
import math
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 640
ASSETS_DIR    = os.path.join(os.path.dirname(__file__), "assets")
TEMPLATES_DIR = os.path.join(ASSETS_DIR, "templates")
CHANNEL_TAG = "ALPHA_X_CALLS"
VIP_TAG     = "ALPHA_X_CALLS • JOIN VIP"

# ── PnL base investment amounts — randomised per post ─────────────────────────
PNL_BASES = [50, 100, 100, 100, 200, 250, 500, 1000]

def random_pnl(multiplier: float) -> str:
    base = random.choice(PNL_BASES)
    return pnl_for_base(base, multiplier)


def pnl_for_base(base: int, multiplier: float) -> str:
    """PnL block matching Solana100xCall caption style — fixed base per token."""
    result = round(base * multiplier)
    profit = result - base
    return (
        f"📋 *Position PnL*\n"
        f"💵 ${base:,} ➜ ${result:,} (PnL + ${profit:,})"
    )


# ── Character images ───────────────────────────────────────────────────────────
_CHAR_POOL = [
    "ts_angry.jpg", "ts_chef.jpg", "ts_furious.jpg",
    "ts_grey.jpg",  "ts_sunglasses.jpg", "ts_toilet.jpg",
    "ac_pepe_laser.jpg", "ac_pepe_money.jpg",
    "ac_pepe_suit.jpg",  "ac_pepe_suit2.jpg", "ac_pepe_sword.jpg",
]
_last_char: str = ""

def _pick_char() -> str:
    global _last_char
    pool = [c for c in _CHAR_POOL if c != _last_char]
    pick = random.choice(pool)
    _last_char = pick
    p1 = os.path.join(TEMPLATES_DIR, pick)
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(ASSETS_DIR, pick)
    if os.path.exists(p2):
        return p2
    # fall back to any png in assets/
    for f in os.listdir(ASSETS_DIR):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            return os.path.join(ASSETS_DIR, f)
    return p1


# ── Font helpers ───────────────────────────────────────────────────────────────
_FC: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _FC:
        return _FC[key]
    for p in ([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]):
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _FC[key] = f
                return f
            except Exception:
                pass
    f = ImageFont.load_default()
    _FC[key] = f
    return f

def _tw(draw: ImageDraw.Draw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))

def _fit(draw: ImageDraw.Draw, text: str, max_w: int,
         mx: int = 220, mn: int = 50) -> int:
    for sz in range(mx, mn - 1, -4):
        if _tw(draw, text, _font(sz, bold=True)) <= max_w:
            return sz
    return mn

def _save(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=95)
    buf.seek(0)
    return buf.read()


# ── Background themes ──────────────────────────────────────────────────────────
# Each has a gradient dark bg + optional radial glow colour

THEMES = [
    {"name": "green",    "glow": (0, 255, 80),   "accent": (0, 230, 100),  "ticker": (0, 255, 100)},
    {"name": "neon",     "glow": (0, 220, 255),  "accent": (0, 200, 255),  "ticker": (0, 255, 200)},
    {"name": "gold",     "glow": (255, 200, 0),  "accent": (255, 190, 0),  "ticker": (255, 220, 60)},
    {"name": "purple",   "glow": (160, 0, 255),  "accent": (180, 80, 255), "ticker": (200, 100, 255)},
    {"name": "fire",     "glow": (255, 80, 0),   "accent": (255, 120, 0),  "ticker": (255, 160, 0)},
    {"name": "cyan",     "glow": (0, 230, 230),  "accent": (0, 210, 210),  "ticker": (0, 255, 220)},
    {"name": "lime",     "glow": (120, 255, 0),  "accent": (140, 255, 0),  "ticker": (180, 255, 60)},
    {"name": "electric", "glow": (80, 160, 255), "accent": (100, 180, 255),"ticker": (140, 200, 255)},
]
_last_theme_name: str = ""

def _pick_theme() -> dict:
    global _last_theme_name
    pool = [t for t in THEMES if t["name"] != _last_theme_name]
    t = random.choice(pool)
    _last_theme_name = t["name"]
    return t


# ── Dark background with radial glow ──────────────────────────────────────────
def _make_bg(glow_rgb: tuple) -> Image.Image:
    bg = Image.new("RGBA", (W, H), (6, 8, 10, 255))
    draw = ImageDraw.Draw(bg)

    # Subtle radial glow centred at top-right
    cx, cy = int(W * 0.72), int(H * 0.35)
    for r in range(320, 0, -8):
        alpha = int(18 * (1 - r / 320) ** 1.6)
        if alpha < 1:
            continue
        col = glow_rgb + (alpha,)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)

    # Scanline texture
    for y in range(0, H, 5):
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, 22))

    # Subtle grid dots
    for gx in range(0, W, 60):
        for gy in range(0, H, 60):
            draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(255, 255, 255, 18))

    return bg


def _paste_char(canvas: Image.Image, char_path: str):
    """Paste character on right side with a left-edge fade."""
    if not os.path.exists(char_path):
        return
    try:
        char = Image.open(char_path).convert("RGBA")
        # Scale to fill right 50% of card height
        char_h = H
        char_w = int(char.width * (char_h / char.height))
        char = char.resize((char_w, char_h), Image.LANCZOS)

        # Position: right-aligned
        x_off = W - char_w
        if x_off < int(W * 0.42):
            x_off = int(W * 0.42)

        # Fade in from left edge of character
        fade_w = min(int(char_w * 0.45), 280)
        fade = Image.new("L", char.size, 255)
        fd = ImageDraw.Draw(fade)
        for px in range(fade_w):
            alpha = int(255 * (px / fade_w) ** 1.8)
            fd.line([(px, 0), (px, char_h)], fill=alpha)

        r, g, b, a = char.split()
        new_a = Image.composite(a, Image.new("L", a.size, 0), fade)
        char.putalpha(new_a)

        canvas.paste(char, (x_off, 0), char)
    except Exception:
        pass


def _dark_left_panel(canvas: Image.Image, width_frac: float = 0.50,
                     opacity: int = 245):
    """Solid dark overlay on left side, fading into transparent."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d  = ImageDraw.Draw(ov)
    solid_end = int(W * width_frac)
    fade_end  = int(W * (width_frac + 0.18))
    for px in range(W):
        if px <= solid_end:
            a = opacity
        elif px <= fade_end:
            t = (px - solid_end) / (fade_end - solid_end)
            a = int(opacity * (1 - t ** 0.5))
        else:
            a = 0
        d.line([(px, 0), (px, H)], fill=(4, 6, 10, a))
    return Image.alpha_composite(canvas, ov)


def _draw_channel_logo(draw: ImageDraw.Draw, x: int, y: int,
                       accent: tuple, name: str = CHANNEL_TAG):
    """Draw small bar-chart icon + channel name wordmark."""
    heights = [28, 18, 28, 20]
    bw, gap = 7, 3
    for i, bh in enumerate(heights):
        bx = x + i * (bw + gap)
        draw.rectangle([bx, y + (28 - bh), bx + bw, y + 28], fill=accent + (255,))
    draw.text(
        (x + 4 * (bw + gap) + 10, y),
        name, font=_font(26, bold=True), fill=(230, 230, 230, 255)
    )


def _draw_username_badge(draw: ImageDraw.Draw, x: int, y: int,
                         username: str, accent: tuple):
    """Green pill badge with avatar circle + @username."""
    f    = _font(26, bold=True)
    text = f"@{username.lstrip('@')}"
    tw   = _tw(draw, text, f)
    bw, bh = tw + 56, 44
    bg = accent + (255,)
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=22, fill=bg)
    draw.ellipse([x + 4, y + 4, x + 36, y + 36], fill=(255, 255, 255, 180))
    draw.text((x + 44, y + 9), text, font=f, fill=(255, 255, 255, 255))


def _draw_vip_bar(draw: ImageDraw.Draw, theme: dict):
    """Bottom bar: 'CHANNEL • JOIN VIP'"""
    bar_h = 42
    draw.rectangle([0, H - bar_h, W, H], fill=(0, 0, 0, 200))
    text = VIP_TAG
    f = _font(24, bold=True)
    tw = _tw(draw, text, f)
    draw.text(((W - tw) // 2, H - bar_h + 9), text, font=f,
              fill=theme["accent"] + (255,))


# ══════════════════════════════════════════════════════════════════════════════
#  CALL CARD STYLES (new gem entry)
# ══════════════════════════════════════════════════════════════════════════════

def _call_style_1(symbol: str, mc: str, liq: str, vol: str,
                  chain: str, theme: dict) -> Image.Image:
    """Style 1 — TokenScan classic: logo top-left, ticker, NEW CALL label."""
    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.50, 248)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 44, int(W * 0.48) - 44
    accent = theme["accent"] + (255,)
    ticker_col = theme["ticker"] + (255,)

    _draw_channel_logo(draw, tx, 32, theme["accent"])

    # Chain pill
    chain_col = {"SOL": (153, 69, 255), "ETH": (100, 149, 237),
                 "BNB": (243, 186, 47)}.get(chain.upper(), (100, 100, 180))
    draw.rounded_rectangle([tx, 76, tx + 88, 76 + 34], radius=9, fill=chain_col + (255,))
    draw.text((tx + 10, 81), chain.upper(), font=_font(22, bold=True),
              fill=(255, 255, 255, 255))

    # Ticker
    sym_sz = _fit(draw, f"${symbol.upper()}", lim, 80, 38)
    draw.text((tx, 124), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=ticker_col)

    # NEW CALL label
    draw.text((tx, 124 + sym_sz + 10), "✦  NEW CALL",
              font=_font(40, bold=True), fill=(255, 214, 0, 255))

    # Stats
    fn, fb = _font(28), _font(28, bold=True)
    dim, whi = (155, 155, 160, 220), (225, 225, 230, 255)
    y0 = 124 + sym_sz + 66
    for lbl, val in [("MC:   ", mc), ("Liq:  ", liq), ("Vol:  ", vol)]:
        draw.text((tx, y0), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=whi)
        y0 += 42

    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


def _call_style_2(symbol: str, mc: str, liq: str, vol: str,
                  chain: str, theme: dict) -> Image.Image:
    """Style 2 — Neon hunter: right-side panel, big ticker, accent stripes."""
    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.52, 246)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 36, int(W * 0.50) - 36
    ticker_col = theme["ticker"] + (255,)
    accent_c   = theme["accent"] + (255,)

    # Top stripe
    draw.rectangle([0, 0, int(W * 0.52), 5], fill=accent_c)

    _draw_channel_logo(draw, tx, 20, theme["accent"])

    # Big ticker
    sym_sz = _fit(draw, f"${symbol.upper()}", lim, 96, 44)
    draw.text((tx, 72), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=ticker_col)

    # ALPHA SIGNAL sub-label
    draw.text((tx, 72 + sym_sz + 8), "🔔 ALPHA SIGNAL",
              font=_font(36, bold=True), fill=(255, 255, 255, 230))

    # Chain tag
    y1 = 72 + sym_sz + 58
    draw.text((tx, y1), f"SOL / ${symbol.upper()}",
              font=_font(30, bold=True), fill=accent_c)

    fn, fb = _font(27), _font(27, bold=True)
    dim, whi = (150, 150, 155, 215), (220, 220, 225, 255)
    y0 = y1 + 50
    for lbl, val in [("MC:   ", mc), ("Liq:  ", liq), ("Vol:  ", vol)]:
        draw.text((tx, y0), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=whi)
        y0 += 40

    # Bottom stripe
    draw.rectangle([0, H - 48, int(W * 0.52), H - 43], fill=accent_c)
    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


def _call_style_3(symbol: str, mc: str, liq: str, vol: str,
                  chain: str, theme: dict) -> Image.Image:
    """Style 3 — Amber terminal: scanlines, monospace feel, left accent bar."""
    bg = Image.new("RGBA", (W, H), (4, 7, 4, 255))
    draw = ImageDraw.Draw(bg)
    for y in range(0, H, 5):
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, 28))
    draw.rectangle([0, 0, 6, H], fill=theme["accent"] + (255,))
    char = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.50, 240)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 36, int(W * 0.48) - 36
    amber   = theme["ticker"] + (255,)
    accent_c = theme["accent"] + (255,)
    green   = (0, 220, 80, 255)
    dim     = (100, 140, 100, 200)

    _draw_channel_logo(draw, tx, 28, theme["accent"])
    draw.text((tx, 74), "[ INSIDER CALL ]",
              font=_font(30, bold=True), fill=amber)

    sym_sz = _fit(draw, f"${symbol.upper()}", lim, 90, 42)
    draw.text((tx, 120), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=green)

    fn, fb = _font(29), _font(29, bold=True)
    whi = (215, 215, 215, 255)
    y0 = 120 + sym_sz + 16
    rows = [("> MC:        ", mc), ("> LIQUIDITY: ", liq), ("> VOLUME:    ", vol)]
    for lbl, val in rows:
        draw.text((tx, y0), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=whi)
        y0 += 46

    draw.text((tx, H - 82), "⚡ not posting this elsewhere. move fast.",
              font=_font(24), fill=amber)
    _draw_username_badge(draw, tx, H - 84 + 34, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


def _call_style_4(symbol: str, mc: str, liq: str, vol: str,
                  chain: str, theme: dict) -> Image.Image:
    """Style 4 — Alert stamp: bold banner, centred ticker."""
    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.50, 250)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 40, int(W * 0.48) - 40
    accent_c = theme["accent"] + (255,)
    ticker_col = theme["ticker"] + (255,)

    # Bold top banner
    draw.rectangle([0, 0, int(W * 0.52), 62], fill=accent_c)
    draw.text((tx, 14), "⚡  NEW GEM ALERT", font=_font(32, bold=True),
              fill=(255, 255, 255, 255))

    _draw_channel_logo(draw, tx, 78, theme["accent"])

    sym_sz = _fit(draw, f"${symbol.upper()}", lim, 92, 44)
    draw.text((tx, 122), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=ticker_col)

    draw.text((tx, 122 + sym_sz + 8), f"SOL / ${symbol.upper()}",
              font=_font(30, bold=True), fill=(200, 200, 200, 220))

    fn, fb = _font(28), _font(28, bold=True)
    dim, whi = (150, 150, 155, 210), (215, 215, 220, 255)
    y0 = 122 + sym_sz + 58
    draw.text((tx, y0),
              f"Mcap : {mc}", font=fb, fill=ticker_col)
    y0 += 44
    draw.text((tx, y0), f"Liq  : {liq}", font=fn, fill=dim)
    y0 += 40
    draw.text((tx, y0), f"Vol  : {vol}", font=fn, fill=dim)

    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


# ══════════════════════════════════════════════════════════════════════════════
#  UPDATE CARD STYLES (gain milestones)
# ══════════════════════════════════════════════════════════════════════════════

def _update_style_1(symbol: str, mult: float, entry_mc: str,
                    t_str: str, theme: dict) -> Image.Image:
    """Style 1 — Solana100xCall exact: logo, ticker green, HUGE white mult."""
    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.51, 248)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 44, int(W * 0.49) - 44
    ticker_col = theme["ticker"] + (255,)
    accent_c   = theme["accent"] + (255,)

    _draw_channel_logo(draw, tx, 32, theme["accent"])

    # Ticker name
    draw.text((tx, 80), f"${symbol.upper()}",
              font=_font(52, bold=True), fill=ticker_col)

    # Giant multiplier
    mt  = f"{mult:.2f}X" if mult < 10 else f"{mult:.1f}X"
    sz  = _fit(draw, mt, lim, 220, 80)
    mf  = _font(sz, bold=True)
    mh  = mf.getbbox(mt)[3]
    # Shadow
    for ox, oy in [(-3, 3), (3, -3)]:
        draw.text((tx + ox, 148 + oy), mt, font=mf, fill=(0, 50, 20, 90))
    draw.text((tx, 148), mt, font=mf, fill=(255, 255, 255, 255))

    # Called at + time
    y2 = 148 + mh + 12
    fn = _font(26)
    draw.text((tx, y2), f"Called at {entry_mc}",
              font=fn, fill=(170, 170, 175, 210))
    dot_x = tx + _tw(draw, f"Called at {entry_mc}", fn) + 10
    draw.text((dot_x, y2), f"• {t_str}", font=fn, fill=(140, 140, 145, 190))

    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


def _update_style_2(symbol: str, mult: float, entry_mc: str,
                    t_str: str, theme: dict) -> Image.Image:
    """Style 2 — Green mult on right panel, symbol + stats left."""
    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.52, 246)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 36, int(W * 0.50) - 36
    ticker_col = theme["ticker"] + (255,)
    accent_c   = theme["accent"] + (255,)

    draw.rectangle([0, 0, int(W * 0.53), 5], fill=accent_c)
    _draw_channel_logo(draw, tx, 18, theme["accent"])

    sym_sz = _fit(draw, symbol.upper(), lim, 90, 38)
    draw.text((tx, 66), symbol.upper(),
              font=_font(sym_sz, bold=True), fill=(255, 255, 255, 255))
    draw.text((tx, 66 + sym_sz + 6), f"called at {entry_mc}",
              font=_font(24), fill=(165, 165, 170, 200))

    mt  = f"{mult:.2f}X" if mult < 10 else f"{mult:.1f}X"
    sz  = _fit(draw, mt, lim, 180, 70)
    mf  = _font(sz, bold=True)
    my  = 66 + sym_sz + 50
    draw.text((tx, my), mt, font=mf, fill=ticker_col)
    mh  = mf.getbbox(mt)[3]
    draw.text((tx, my + mh + 10), f"🕐 {t_str} since entry",
              font=_font(26), fill=(155, 155, 160, 200))

    draw.rectangle([0, H - 48, int(W * 0.53), H - 43], fill=accent_c)
    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


def _update_style_3(symbol: str, mult: float, entry_mc: str,
                    t_str: str, theme: dict) -> Image.Image:
    """Style 3 — Gains beast: full-width dark bg, centred giant X."""
    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    scrim  = Image.new("RGBA", (W, H), (5, 7, 10, 205))
    canvas = Image.alpha_composite(bg, scrim)
    draw   = ImageDraw.Draw(canvas)

    accent_c   = theme["accent"] + (255,)
    ticker_col = theme["ticker"] + (255,)

    # Top banner
    draw.rectangle([0, 0, W, 64], fill=accent_c)
    banner = f"ALPHA_X_CALLS  ⚡  GAIN UPDATE"
    draw.text((32, 14), banner, font=_font(34, bold=True), fill=(0, 0, 0, 255))

    mt = f"{mult:.2f}X" if mult < 10 else f"{mult:.1f}X"
    sz = _fit(draw, mt, W - 80, 280, 110)
    mf = _font(sz, bold=True)
    mw = _tw(draw, mt, mf)
    mx = (W - mw) // 2
    my = 80
    for ox, oy in [(-5, 5), (5, -5), (-5, -5), (5, 5)]:
        draw.text((mx + ox, my + oy), mt, font=mf, fill=(0, 40, 15, 80))
    draw.text((mx, my), mt, font=mf, fill=ticker_col)

    mh = mf.getbbox(mt)[3]
    y2 = my + mh + 18

    sym_f  = _font(46, bold=True)
    sym_t  = f"${symbol.upper()}"
    sw     = _tw(draw, sym_t, sym_f)
    draw.text(((W - sw) // 2, y2), sym_t,
              font=sym_f, fill=(255, 255, 255, 255))
    y2 += 58

    info = f"Called at {entry_mc}   •   {t_str} hold"
    iw   = _tw(draw, info, _font(27))
    draw.text(((W - iw) // 2, y2), info,
              font=_font(27), fill=(155, 155, 160, 210))

    # Bottom bar
    draw.rectangle([0, H - 52, W, H], fill=(0, 0, 0, 190))
    uw = _tw(draw, CHANNEL_TAG, _font(27, bold=True))
    draw.text(((W - uw) // 2, H - 40), CHANNEL_TAG,
              font=_font(27, bold=True), fill=accent_c)
    return canvas


def _update_style_4(symbol: str, mult: float, entry_mc: str,
                    t_str: str, theme: dict) -> Image.Image:
    """Style 4 — Terminal scoreboard: scanlines, amber, bold multiplier."""
    bg = Image.new("RGBA", (W, H), (3, 6, 3, 255))
    draw = ImageDraw.Draw(bg)
    for y in range(0, H, 5):
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, 25))
    draw.rectangle([0, 0, 6, H], fill=theme["accent"] + (255,))
    char = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.50, 242)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 36, int(W * 0.48) - 36
    amber   = theme["ticker"] + (255,)
    accent_c = theme["accent"] + (255,)
    green   = (0, 220, 90, 255)
    dim     = (100, 135, 100, 200)

    _draw_channel_logo(draw, tx, 28, theme["accent"])
    draw.text((tx, 74), "[ GAIN UPDATE ]", font=_font(30, bold=True), fill=amber)
    draw.text((tx, 120), f"${symbol.upper()}", font=_font(52, bold=True), fill=green)

    mt  = f"{mult:.2f}X" if mult < 10 else f"{mult:.1f}X"
    sz  = _fit(draw, mt, lim, 200, 70)
    mf  = _font(sz, bold=True)
    mh  = mf.getbbox(mt)[3]
    draw.text((tx, 192), mt, font=mf, fill=(220, 225, 220, 255))
    y2  = 192 + mh + 14
    draw.text((tx, y2),
              f"called at {entry_mc}  •  {t_str} in",
              font=_font(26), fill=dim)

    draw.text((tx, H - 82), "don't fade alpha calls. never.",
              font=_font(24), fill=amber)
    _draw_username_badge(draw, tx, H - 84 + 36, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


# ══════════════════════════════════════════════════════════════════════════════
#  FOREX CARD
# ══════════════════════════════════════════════════════════════════════════════

def _forex_card(pair: str, direction: str, entry: str,
                tp1: str, tp2: str, sl: str, tf: str, rr: str) -> Image.Image:
    theme    = _pick_theme()
    is_long  = direction.upper() in ("LONG", "BUY")
    dir_col  = (0, 120, 60, 255)   if is_long else (160, 30, 30, 255)
    dir_text = (0, 220, 100, 255)  if is_long else (255, 90, 90, 255)
    accent_c = theme["accent"] + (255,)

    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.52, 250)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 36, int(W * 0.50) - 36

    # Accent bar
    draw.rectangle([0, 0, 6, H], fill=accent_c)

    _draw_channel_logo(draw, tx, 28, theme["accent"])

    # Signal header
    hdr = "FX SIGNAL" if "/" in pair else "TRADE SIGNAL"
    hw  = _tw(draw, hdr, _font(30, bold=True)) + 28
    draw.rounded_rectangle([tx, 72, tx + hw, 72 + 46], radius=8, fill=dir_col)
    draw.text((tx + 14, 82), hdr, font=_font(30, bold=True),
              fill=(255, 255, 255, 255))

    pair_sz = _fit(draw, pair.upper(), lim, 76, 36)
    draw.text((tx, 132), pair.upper(),
              font=_font(pair_sz, bold=True), fill=(255, 255, 255, 255))

    dw  = _tw(draw, direction.upper(), _font(34, bold=True)) + 32
    dy  = 132 + pair_sz + 10
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 48], radius=10, fill=dir_col)
    draw.text((tx + 14, dy + 8), direction.upper(),
              font=_font(34, bold=True), fill=dir_text)
    draw.text((tx + dw + 14, dy + 12), tf,
              font=_font(27), fill=(155, 155, 160, 200))

    fn, fb = _font(26), _font(26, bold=True)
    dim    = (145, 145, 150, 200)
    whi    = (215, 215, 220, 230)
    grn    = (0, 210, 90, 255)
    red    = (240, 80, 80, 255)
    y0, lh = dy + 66, 41

    for lbl, val, col in [
        ("Entry  ", entry, whi),
        ("TP 1   ", tp1,   grn),
        ("TP 2   ", tp2,   grn),
        ("SL     ", sl,    red),
        ("R/R    ", rr,    whi),
    ]:
        draw.text((tx, y0), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=col)
        y0 += lh

    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

_CALL_STYLES   = [_call_style_1,   _call_style_2,   _call_style_3,   _call_style_4]
_UPDATE_STYLES = [_update_style_1, _update_style_2, _update_style_3, _update_style_4]
_last_call_idx:   int = -1
_last_update_idx: int = -1


def _pick_fn(pool: list, last: int) -> tuple:
    choices = [i for i in range(len(pool)) if i != last]
    idx = random.choice(choices)
    return pool[idx], idx


def build_call_card(symbol: str, mcap_str: str, liq_str: str,
                    vol_str: str, chain: str = "SOL",
                    username: str = CHANNEL_TAG) -> bytes:
    global _last_call_idx
    fn, _last_call_idx = _pick_fn(_CALL_STYLES, _last_call_idx)
    theme  = _pick_theme()
    canvas = fn(symbol, mcap_str, liq_str, vol_str, chain, theme)
    return _save(canvas)


def build_update_card(symbol: str, multiplier: float, mcap_str: str,
                      time_str: str, username: str = CHANNEL_TAG) -> bytes:
    global _last_update_idx
    fn, _last_update_idx = _pick_fn(_UPDATE_STYLES, _last_update_idx)
    theme  = _pick_theme()
    canvas = fn(symbol, multiplier, mcap_str, time_str, theme)
    return _save(canvas)


def build_forex_card(pair: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str, username: str = CHANNEL_TAG) -> bytes:
    canvas = _forex_card(pair, direction, entry, tp1, tp2, sl, timeframe, rr)
    return _save(canvas)


# ══════════════════════════════════════════════════════════════════════════════
#  STOCK CARD — equities setup
# ══════════════════════════════════════════════════════════════════════════════

def _stock_card(ticker: str, name: str, direction: str, entry: str,
                tp1: str, tp2: str, sl: str, tf: str, rr: str) -> Image.Image:
    theme    = _pick_theme()
    is_long  = direction.upper() in ("LONG", "BUY")
    dir_col  = (0, 120, 60, 255)   if is_long else (160, 30, 30, 255)
    dir_text = (0, 220, 100, 255)  if is_long else (255, 90, 90, 255)
    accent_c = theme["accent"] + (255,)

    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    canvas = _dark_left_panel(bg, 0.54, 250)
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 36, int(W * 0.52) - 36

    # Accent bar
    draw.rectangle([0, 0, 6, H], fill=accent_c)
    _draw_channel_logo(draw, tx, 28, theme["accent"])

    hdr = "📈 STOCK SIGNAL"
    hw  = _tw(draw, hdr, _font(28, bold=True)) + 28
    draw.rounded_rectangle([tx, 70, tx + hw, 70 + 44], radius=8, fill=dir_col)
    draw.text((tx + 14, 80), hdr, font=_font(28, bold=True),
              fill=(255, 255, 255, 255))

    tk_sz = _fit(draw, ticker.upper(), lim, 88, 44)
    draw.text((tx, 128), ticker.upper(),
              font=_font(tk_sz, bold=True), fill=(255, 255, 255, 255))
    draw.text((tx, 128 + tk_sz + 6), name,
              font=_font(26), fill=(170, 170, 175, 220))

    dy  = 128 + tk_sz + 50
    dw  = _tw(draw, direction.upper(), _font(32, bold=True)) + 32
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 46], radius=10, fill=dir_col)
    draw.text((tx + 14, dy + 8), direction.upper(),
              font=_font(32, bold=True), fill=dir_text)
    draw.text((tx + dw + 14, dy + 12), tf,
              font=_font(26), fill=(155, 155, 160, 200))

    fn, fb = _font(25), _font(25, bold=True)
    dim    = (145, 145, 150, 200)
    whi    = (215, 215, 220, 230)
    grn    = (0, 210, 90, 255)
    red    = (240, 80, 80, 255)
    y0, lh = dy + 64, 38

    for lbl, val, col in [
        ("Entry  ", entry, whi),
        ("TP 1   ", tp1,   grn),
        ("TP 2   ", tp2,   grn),
        ("SL     ", sl,    red),
        ("R/R    ", rr,    whi),
    ]:
        draw.text((tx, y0), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=col)
        y0 += lh

    _draw_username_badge(draw, tx, H - 84, CHANNEL_TAG, theme["accent"])
    _draw_vip_bar(draw, theme)
    return canvas


def build_stock_card(ticker: str, name: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str) -> bytes:
    return _save(_stock_card(ticker, name, direction, entry, tp1, tp2, sl, timeframe, rr))


# ══════════════════════════════════════════════════════════════════════════════
#  WINNERS TEASER CARD — "$SYM — Xx VIP Winners"
# ══════════════════════════════════════════════════════════════════════════════

def _winners_card(symbol: str, mult: float, entry: str, ath: str) -> Image.Image:
    theme    = _pick_theme()
    accent_c = theme["accent"] + (255,)
    ticker_c = theme["ticker"] + (255,)

    bg     = _make_bg(theme["glow"])
    char   = _pick_char()
    _paste_char(bg, char)
    scrim  = Image.new("RGBA", (W, H), (4, 6, 10, 200))
    canvas = Image.alpha_composite(bg, scrim)
    draw   = ImageDraw.Draw(canvas)

    # Top banner
    draw.rectangle([0, 0, W, 64], fill=accent_c)
    hdr = "🔥 VIP WINNER  •  ALPHA_X_CALLS"
    draw.text((32, 14), hdr, font=_font(34, bold=True), fill=(0, 0, 0, 255))

    # Symbol
    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, W - 80, 110, 60)
    sym_f  = _font(sym_sz, bold=True)
    sw     = _tw(draw, sym_t, sym_f)
    draw.text(((W - sw) // 2, 90), sym_t, font=sym_f, fill=(255, 255, 255, 255))

    # Big mult
    mt = f"{int(mult)}X"
    sz = _fit(draw, mt, W - 80, 260, 110)
    mf = _font(sz, bold=True)
    mw = _tw(draw, mt, mf)
    mx = (W - mw) // 2
    my = 90 + sym_sz + 10
    for ox, oy in [(-5, 5), (5, -5), (-5, -5), (5, 5)]:
        draw.text((mx + ox, my + oy), mt, font=mf, fill=(0, 30, 12, 90))
    draw.text((mx, my), mt, font=mf, fill=ticker_c)

    mh   = mf.getbbox(mt)[3]
    info = f"${entry}  ➜  ${ath} MCAP"
    iw   = _tw(draw, info, _font(34, bold=True))
    draw.text(((W - iw) // 2, my + mh + 16),
              info, font=_font(34, bold=True), fill=(230, 230, 235, 255))

    free = "📊 CHART  •  🆓 FREE ENTRY"
    fw   = _tw(draw, free, _font(28, bold=True))
    draw.text(((W - fw) // 2, H - 72),
              free, font=_font(28, bold=True), fill=accent_c)

    draw.rectangle([0, H - 36, W, H], fill=(0, 0, 0, 200))
    tag = "ALPHA_X_CALLS  •  JOIN VIP"
    tw  = _tw(draw, tag, _font(22, bold=True))
    draw.text(((W - tw) // 2, H - 30),
              tag, font=_font(22, bold=True), fill=accent_c)
    return canvas


def build_winners_card(symbol: str, multiplier: float,
                       entry: str, ath: str) -> bytes:
    return _save(_winners_card(symbol, multiplier, entry, ath))


# ══════════════════════════════════════════════════════════════════════════════
#  AXIOM-STYLE PNL BRAG CARD — "$SYM +$X PNL +Y% Invested $Z Position $W"
# ══════════════════════════════════════════════════════════════════════════════

def build_pnl_brag_card(symbol: str, invested: int, position: int) -> bytes:
    pnl_usd = position - invested
    pnl_pct = (pnl_usd / invested) * 100 if invested > 0 else 0

    bg = Image.new("RGBA", (W, H), (8, 10, 14, 255))
    draw = ImageDraw.Draw(bg)
    # subtle blue accents
    for r in range(420, 0, -10):
        a = int(20 * (1 - r / 420) ** 1.4)
        if a < 1: continue
        draw.ellipse([W - 200 - r, 100 - r, W - 200 + r, 100 + r],
                     fill=(40, 80, 160, a))
    canvas = bg
    draw = ImageDraw.Draw(canvas)

    # AXIOM logo (top-right)
    draw.text((W - 240, 38), "AXIOM", font=_font(48, bold=True),
              fill=(255, 255, 255, 255))
    draw.text((W - 75, 62), "Pro", font=_font(24), fill=(160, 160, 165, 200))

    tx = 56
    draw.text((tx, 130), f"${symbol.upper()}",
              font=_font(56, bold=True), fill=(255, 255, 255, 255))

    # Big green PnL banner
    pnl_str = f"+${abs(pnl_usd) / 1000:,.2f}K" if abs(pnl_usd) >= 1000 else f"+${abs(pnl_usd):,}"
    pf  = _font(110, bold=True)
    pw  = _tw(draw, pnl_str, pf) + 60
    bx, by = tx, 200
    draw.rounded_rectangle([bx, by, bx + pw, by + 130], radius=8,
                           fill=(0, 230, 140, 255))
    draw.text((bx + 30, by + 8), pnl_str, font=pf, fill=(0, 0, 0, 255))

    # Stats
    fn, fb = _font(34), _font(34, bold=True)
    dim = (155, 160, 170, 230)
    whi = (235, 235, 240, 255)
    grn = (0, 230, 140, 255)
    y0  = by + 170
    rows = [
        ("PNL",      f"+{pnl_pct:,.2f}%", grn),
        ("Invested", f"${invested / 1000:,.2f}K" if invested >= 1000 else f"${invested:,}", whi),
        ("Position", f"${position / 1000:,.2f}K" if position >= 1000 else f"${position:,}", whi),
    ]
    for lbl, val, col in rows:
        draw.text((tx, y0), lbl, font=fn, fill=dim)
        draw.text((tx + 280, y0), val, font=fb, fill=col)
        y0 += 50

    # Footer
    draw.text((tx, H - 70), "🚩  @ALPHA_X_CALLS",
              font=_font(28, bold=True), fill=(220, 220, 225, 255))
    draw.text((tx, H - 38), "axiom.trade   Save 10% off fees",
              font=_font(20), fill=(150, 150, 155, 200))
    return _save(canvas)
