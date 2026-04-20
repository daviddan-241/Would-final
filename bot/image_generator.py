"""
TokenScan-exact card generator for Alpha Circle.
Layout: dark BG | left panel (logo + symbol + HUGE multiplier + called-at + username badge)
                | right panel (character, faded in from left)
"""

import io
import os
import random
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1280, 640
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# Character images (right-side panel) — extracted from reference TokenScan cards
CHARACTER_IMAGES = [p for p in [
    os.path.join(ASSETS_DIR, "char_chef.png"),
    os.path.join(ASSETS_DIR, "char_angry.png"),
    os.path.join(ASSETS_DIR, "char_toilet.png"),
    os.path.join(ASSETS_DIR, "char_toilet2.png"),
    os.path.join(ASSETS_DIR, "char_grey.png"),
    os.path.join(ASSETS_DIR, "char_sunglasses.png"),
    os.path.join(ASSETS_DIR, "pepe_sunglasses.png"),
    os.path.join(ASSETS_DIR, "pepe_suit.png"),
    os.path.join(ASSETS_DIR, "pepe_moon.png"),
    os.path.join(ASSETS_DIR, "pepe_happy.png"),
] if os.path.exists(p)]

# ── fonts ─────────────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False):
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    pool = candidates_bold if bold else candidates_reg
    for path in pool:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── background ────────────────────────────────────────────────────────────────
def _make_bg() -> Image.Image:
    """Radial dark background — near-black charcoal like TokenScan."""
    bg = Image.new("RGBA", (W, H), (10, 10, 16, 255))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # subtle radial glow from top-left
    for r in range(320, 0, -4):
        alpha = int(25 * (1 - r / 320))
        draw.ellipse((-r + 60, -r + 60, r + 60, r + 60),
                     fill=(0, 60, 30, alpha))
    bg = Image.alpha_composite(bg, overlay)
    return bg


# ── gradient fade (left edge of character panel) ─────────────────────────────
def _fade_mask(width: int, height: int, fade_px: int = 200) -> Image.Image:
    mask = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(mask)
    for x in range(fade_px):
        alpha = int(255 * (x / fade_px) ** 1.4)
        draw.line([(x, 0), (x, height)], fill=alpha)
    return mask


# ── paste character on right panel ───────────────────────────────────────────
def _paste_character(canvas: Image.Image, char_path: str):
    char_panel_x = int(W * 0.52)   # character starts here
    char_panel_w = W - char_panel_x
    char_panel_h = H

    try:
        ch = Image.open(char_path).convert("RGBA")
    except Exception:
        return

    # Scale to fill panel height, keeping aspect
    scale = char_panel_h / ch.height
    new_w = int(ch.width * scale)
    new_h = char_panel_h
    ch = ch.resize((new_w, new_h), Image.LANCZOS)

    # Center horizontally in char panel, slight right-shift so it bleeds edge
    paste_x = char_panel_x + max(0, (char_panel_w - new_w) // 2) - 20
    paste_y = (H - new_h) // 2

    # Apply left-side fade mask
    fade = _fade_mask(new_w, new_h, fade_px=min(180, new_w // 2))
    r, g, b, a = ch.split()
    new_alpha = Image.composite(a, Image.new("L", (new_w, new_h), 0), fade)
    ch.putalpha(new_alpha)

    canvas.paste(ch, (paste_x, paste_y), ch)


# ── TokenScan logo (top-left) ─────────────────────────────────────────────────
def _draw_logo(draw: ImageDraw.Draw, x: int = 40, y: int = 32):
    green = (0, 230, 118)
    # Bars icon  ≡  (simplified, 4 vertical bars)
    bar_w, bar_h, gap = 8, 28, 5
    for i in range(4):
        bx = x + i * (bar_w + gap)
        draw.rectangle([bx, y + 2, bx + bar_w, y + 2 + bar_h], fill=green)
    # "TokenScan" label
    lx = x + 4 * (bar_w + gap) + 10
    font = _font(28, bold=True)
    draw.text((lx, y), "TokenScan", font=font, fill=(240, 240, 240, 255))


# ── username badge (pill shape, bottom-left) ──────────────────────────────────
def _draw_badge(draw: ImageDraw.Draw, text: str, x: int, y: int):
    font = _font(28, bold=True)
    tw = draw.textlength(text, font=font)
    pad_x, pad_y = 22, 10
    bw = int(tw) + pad_x * 2
    bh = 46
    r = bh // 2
    # Pill background
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=r, fill=(0, 200, 100, 255))
    # "●" avatar dot
    draw.ellipse([x + 8, y + bh // 2 - 10, x + 8 + 20, y + bh // 2 + 10],
                 fill=(255, 255, 255, 200))
    # Text
    draw.text((x + 36, y + pad_y), text, font=font, fill=(255, 255, 255, 255))


# ── called-at row ─────────────────────────────────────────────────────────────
def _draw_called_at(draw: ImageDraw.Draw, mcap_str: str, time_str: str,
                    x: int, y: int):
    font_sm = _font(30)
    dim = (160, 160, 160, 255)
    white = (220, 220, 220, 255)
    draw.text((x, y), "Called at ", font=font_sm, fill=dim)
    offset = int(draw.textlength("Called at ", font=font_sm))
    draw.text((x + offset, y), mcap_str, font=_font(30, bold=True), fill=white)
    offset2 = int(draw.textlength(mcap_str, font=_font(30, bold=True)))
    timer_text = f"  ⏱ {time_str}"
    draw.text((x + offset + offset2, y), timer_text, font=font_sm, fill=dim)


# ── adaptive multiplier size ──────────────────────────────────────────────────
def _best_mult_size(draw: ImageDraw.Draw, text: str, max_w: int,
                    max_size: int = 230, min_size: int = 100) -> int:
    for sz in range(max_size, min_size - 1, -4):
        f = _font(sz, bold=True)
        if draw.textlength(text, font=f) <= max_w:
            return sz
    return min_size


# ── MAIN CARD: GAIN / UPDATE ──────────────────────────────────────────────────
def build_update_card(
    symbol: str,
    multiplier: float,
    mcap_str: str,
    time_str: str,
    username: str = "alpha_circle1",
) -> bytes:
    canvas = _make_bg()
    draw = ImageDraw.Draw(canvas)

    # Choose & paste character
    char = random.choice(CHARACTER_IMAGES) if CHARACTER_IMAGES else None
    if char:
        _paste_character(canvas, char)

    # Re-acquire draw after paste
    draw = ImageDraw.Draw(canvas)

    # ── Logo ──
    _draw_logo(draw, x=40, y=30)

    # ── Symbol ──
    sym_text = f"${symbol.upper()}"
    sym_font = _font(52, bold=True)
    draw.text((40, 96), sym_text, font=sym_font, fill=(0, 230, 118, 255))

    # ── Multiplier (HUGE) ──
    mult_text = f"{multiplier:.1f}x"
    left_panel_w = int(W * 0.54) - 60
    mult_size = _best_mult_size(draw, mult_text, left_panel_w,
                                 max_size=240, min_size=90)
    mult_font = _font(mult_size, bold=True)
    # Shadow / glow
    for dx, dy in [(-3, -3), (3, 3), (-3, 3), (3, -3)]:
        draw.text((40 + dx, 160 + dy), mult_text, font=mult_font,
                  fill=(0, 120, 60, 120))
    draw.text((40, 160), mult_text, font=mult_font, fill=(255, 255, 255, 255))

    mult_h = mult_font.getbbox(mult_text)[3]

    # ── Called-at ──
    called_y = 160 + mult_h + 14
    _draw_called_at(draw, mcap_str, time_str, x=40, y=called_y)

    # ── Username badge ──
    badge_y = H - 80
    _draw_badge(draw, f"@{username}", x=40, y=badge_y)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=92)
    buf.seek(0)
    return buf.read()


# ── CALL CARD: NEW SIGNAL ──────────────────────────────────────────────────────
def build_call_card(
    symbol: str,
    mcap_str: str,
    liq_str: str,
    vol_str: str,
    chain: str = "SOL",
    username: str = "alpha_circle1",
) -> bytes:
    canvas = _make_bg()

    char = random.choice(CHARACTER_IMAGES) if CHARACTER_IMAGES else None
    if char:
        _paste_character(canvas, char)

    draw = ImageDraw.Draw(canvas)

    # Logo
    _draw_logo(draw, x=40, y=30)

    # Chain badge (top right of left panel)
    chain_font = _font(26, bold=True)
    chain_color = {
        "SOL": (153, 69, 255),
        "ETH": (100, 149, 237),
        "BNB": (243, 186, 47),
        "FX":  (0, 191, 255),
    }.get(chain.upper(), (160, 160, 160))
    draw.rounded_rectangle([40, 96, 40 + 90, 130], radius=14, fill=chain_color)
    draw.text((58, 100), chain.upper(), font=chain_font, fill=(255, 255, 255, 255))

    # Symbol — large
    sym_font = _font(88, bold=True)
    sym_text = f"${symbol.upper()}"
    draw.text((40, 140), sym_text, font=sym_font, fill=(0, 230, 118, 255))

    # "NEW CALL" stamp
    nc_font = _font(44, bold=True)
    nc_text = "★ NEW CALL"
    draw.text((42, 246), nc_text, font=nc_font, fill=(255, 214, 0, 255))

    # Stats row
    stats_y = 316
    stat_font = _font(30, bold=False)
    stat_bold = _font(30, bold=True)
    dim = (150, 150, 150, 255)
    white = (220, 220, 220, 255)

    def stat_line(label, value, y):
        draw.text((40, y), label, font=stat_font, fill=dim)
        lw = int(draw.textlength(label, font=stat_font))
        draw.text((40 + lw, y), value, font=stat_bold, fill=white)

    stat_line("Mkt Cap:  ", mcap_str, stats_y)
    stat_line("Liq:      ", liq_str,  stats_y + 40)
    stat_line("Vol 1H:   ", vol_str,  stats_y + 80)

    # Username badge
    badge_y = H - 80
    _draw_badge(draw, f"@{username}", x=40, y=badge_y)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=92)
    buf.seek(0)
    return buf.read()


# ── FOREX / WHALE SIGNAL CARD ──────────────────────────────────────────────────
def build_forex_card(
    pair: str,
    direction: str,           # "LONG" or "SHORT"
    entry: str,
    tp1: str,
    tp2: str,
    sl: str,
    timeframe: str,
    rr: str,
    username: str = "alpha_circle1",
) -> bytes:
    canvas = _make_bg()

    char = random.choice(CHARACTER_IMAGES) if CHARACTER_IMAGES else None
    if char:
        _paste_character(canvas, char)

    draw = ImageDraw.Draw(canvas)
    _draw_logo(draw, x=40, y=30)

    # Direction color
    dir_color = (0, 230, 118, 255) if direction.upper() in ("LONG", "BUY") else (255, 80, 80, 255)
    dir_bg    = (0, 120, 60)       if direction.upper() in ("LONG", "BUY") else (140, 30, 30)

    # Pair name
    pair_font = _font(80, bold=True)
    draw.text((40, 88), pair.upper(), font=pair_font, fill=(255, 255, 255, 255))

    # Direction badge
    dir_font = _font(40, bold=True)
    dw = int(draw.textlength(direction.upper(), font=dir_font)) + 44
    draw.rounded_rectangle([40, 188, 40 + dw, 244], radius=14, fill=dir_bg)
    draw.text((58, 194), direction.upper(), font=dir_font, fill=dir_color)

    # TF badge
    tf_x = 40 + dw + 16
    tf_font = _font(34, bold=False)
    draw.text((tf_x, 196), timeframe, font=tf_font, fill=(180, 180, 180, 255))

    # Entry / TP / SL grid
    y0 = 272
    lh = 48
    stat_font  = _font(30)
    stat_bold  = _font(30, bold=True)
    dim   = (150, 150, 150, 255)
    white = (220, 220, 220, 255)
    green = (0, 220, 110, 255)
    red   = (255, 90, 90, 255)

    def row(label, val, col, y):
        draw.text((40, y), label, font=stat_font, fill=dim)
        lw = int(draw.textlength(label, font=stat_font))
        draw.text((40 + lw, y), val, font=stat_bold, fill=col)

    row("Entry:  ", entry, white, y0)
    row("TP 1:   ", tp1,   green, y0 + lh)
    row("TP 2:   ", tp2,   green, y0 + lh * 2)
    row("SL:     ", sl,    red,   y0 + lh * 3)
    row("R/R:    ", rr,    white, y0 + lh * 4)

    _draw_badge(draw, f"@{username}", x=40, y=H - 80)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=92)
    buf.seek(0)
    return buf.read()
