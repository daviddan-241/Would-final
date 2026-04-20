"""
Card generator using real TokenScan / Alpha Circle reference images as backgrounds.
Text is overlaid on the appropriate panel (left for TokenScan, right for Phanes style).
"""

import io
import json
import os
import random
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
ASSETS_DIR  = os.path.join(os.path.dirname(__file__), "assets")
TMPL_DIR    = os.path.join(ASSETS_DIR, "templates")
AVATAR_PATH = os.path.join(ASSETS_DIR, "pepe_suit.png")   # badge avatar fallback

# ── Load template manifest ─────────────────────────────────────────────────────
def _load_templates():
    manifest_path = os.path.join(TMPL_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        return []
    manifest = json.load(open(manifest_path))
    out = []
    for fname, side in manifest.items():
        path = os.path.join(TMPL_DIR, fname)
        if os.path.exists(path):
            out.append({"path": path, "side": side})
    return out

TEMPLATES = _load_templates()
TS_TEMPLATES = [t for t in TEMPLATES if t["side"] == "left"]   # TokenScan style
AC_TEMPLATES = [t for t in TEMPLATES if t["side"] == "right"]  # Alpha Circle style


# ── Fonts ──────────────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    reg_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in (bold_paths if bold else reg_paths):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── Helpers ────────────────────────────────────────────────────────────────────
def _text_w(draw: ImageDraw.Draw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))


def _draw_tokenscan_logo(draw: ImageDraw.Draw, x: int, y: int):
    """[||] TokenScan  — exact branding."""
    green = (0, 220, 100, 255)
    bar_w, bar_h, gap = 9, 30, 5
    heights = [bar_h, bar_h * 0.6, bar_h, bar_h * 0.75]
    for i, bh in enumerate(heights):
        bx = x + i * (bar_w + gap)
        by = y + (bar_h - int(bh))
        draw.rectangle([bx, by, bx + bar_w, y + bar_h], fill=green)
    lx = x + 4 * (bar_w + gap) + 10
    draw.text((lx, y), "TokenScan", font=_font(30, bold=True),
              fill=(240, 240, 240, 255))


def _draw_badge_ts(draw: ImageDraw.Draw, text: str, x: int, y: int):
    """Green pill badge with avatar circle — TokenScan style."""
    font = _font(28, bold=True)
    tw = _text_w(draw, text, font)
    pad_x, bh = 48, 48
    bw = tw + pad_x + 16
    r  = bh // 2
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=r,
                           fill=(0, 185, 90, 240))
    # avatar circle
    draw.ellipse([x + 4, y + 4, x + 40, y + 44],
                 fill=(255, 255, 255, 200), outline=(0, 0, 0, 60))
    draw.text((x + 46, y + 10), text, font=font, fill=(255, 255, 255, 255))


def _draw_badge_ac(draw: ImageDraw.Draw, text: str, x: int, y: int):
    """Alpha Circle badge — white dot + username."""
    font = _font(28, bold=True)
    draw.ellipse([x, y + 8, x + 20, y + 28], fill=(0, 255, 80))
    draw.text((x + 28, y + 8), text, font=font, fill=(255, 255, 255, 200))


def _called_at_row(draw: ImageDraw.Draw, mcap_str: str, time_str: str,
                   x: int, y: int):
    f_sm   = _font(28)
    f_bold = _font(28, bold=True)
    dim    = (200, 200, 200, 200)
    white  = (230, 230, 230, 220)
    draw.text((x, y), "Called at ", font=f_sm, fill=dim)
    ox = _text_w(draw, "Called at ", f_sm)
    draw.text((x + ox, y), mcap_str, font=f_bold, fill=white)
    ox2 = _text_w(draw, mcap_str, f_bold)
    draw.text((x + ox + ox2, y), f"  🕐 {time_str}", font=f_sm, fill=dim)


def _best_size(draw, text: str, max_w: int,
               mx: int = 220, mn: int = 80) -> int:
    for sz in range(mx, mn - 1, -4):
        if _text_w(draw, text, _font(sz, bold=True)) <= max_w:
            return sz
    return mn


# ── Dark overlay panel ─────────────────────────────────────────────────────────
def _overlay(canvas: Image.Image, side: str) -> Image.Image:
    """Add semi-transparent dark panel over the text area."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d  = ImageDraw.Draw(ov)
    if side == "left":
        # Gradient from solid-dark left to transparent right
        panel_w = int(W * 0.56)
        for px in range(panel_w):
            alpha = int(185 * (1 - (px / panel_w) ** 0.55))
            d.line([(px, 0), (px, H)], fill=(0, 0, 0, alpha))
    else:  # right (Phanes style)
        panel_start = int(W * 0.46)
        fade_w = 120
        for px in range(panel_start, W):
            rel = px - panel_start
            if rel < fade_w:
                alpha = int(175 * (rel / fade_w) ** 0.6)
            else:
                alpha = 175
            d.line([(px, 0), (px, H)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(canvas.convert("RGBA"), ov)


# ── GAIN / UPDATE card ─────────────────────────────────────────────────────────
def build_update_card(symbol: str, multiplier: float, mcap_str: str,
                      time_str: str, username: str = "alpha_circle1") -> bytes:
    tmpl = random.choice(TEMPLATES) if TEMPLATES else None
    if tmpl:
        base = Image.open(tmpl["path"]).convert("RGBA")
        side = tmpl["side"]
    else:
        base = Image.new("RGBA", (W, H), (10, 10, 16, 255))
        side = "left"

    canvas = _overlay(base, side)
    draw   = ImageDraw.Draw(canvas)

    if side == "left":
        tx = 42
        _draw_tokenscan_logo(draw, tx, 32)
        sym_y = 94
        draw.text((tx, sym_y), f"${symbol.upper()}", font=_font(52, bold=True),
                  fill=(0, 230, 118, 255))
        mult_text = f"{multiplier:.1f}x"
        max_w = int(W * 0.54) - tx - 10
        sz = _best_size(draw, mult_text, max_w, 240, 80)
        mf = _font(sz, bold=True)
        mult_y = sym_y + 62
        # Subtle shadow
        for dx, dy in [(-2, 2), (2, -2)]:
            draw.text((tx + dx, mult_y + dy), mult_text, font=mf,
                      fill=(0, 80, 40, 120))
        draw.text((tx, mult_y), mult_text, font=mf, fill=(255, 255, 255, 255))
        mh = mf.getbbox(mult_text)[3]
        _called_at_row(draw, mcap_str, time_str, tx, mult_y + mh + 14)
        _draw_badge_ts(draw, f"@{username}", tx, H - 78)

    else:  # right (Phanes style)
        rx = int(W * 0.50)
        max_w = W - rx - 30
        # symbol
        sym_text = symbol.upper()
        sz_sym = _best_size(draw, sym_text, max_w, 110, 48)
        draw.text((rx, 60), sym_text, font=_font(sz_sym, bold=True),
                  fill=(255, 255, 255, 255))
        draw.text((rx, 60 + sz_sym + 4), f"called at {mcap_str}",
                  font=_font(30), fill=(200, 200, 200, 200))
        mult_text = f"{multiplier:.1f}X"
        sz = _best_size(draw, mult_text, max_w, 200, 80)
        mf = _font(sz, bold=True)
        mult_y = 60 + sz_sym + 50
        draw.text((rx, mult_y), mult_text, font=mf, fill=(0, 255, 80, 255))
        mh = mf.getbbox(mult_text)[3]
        draw.text((rx, mult_y + mh + 10), f"🕐 {time_str}",
                  font=_font(30), fill=(180, 180, 180, 200))
        _draw_badge_ac(draw, f"@{username}", rx, H - 70)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=93)
    buf.seek(0)
    return buf.read()


# ── NEW CALL card ──────────────────────────────────────────────────────────────
def build_call_card(symbol: str, mcap_str: str, liq_str: str,
                    vol_str: str, chain: str = "SOL",
                    username: str = "alpha_circle1") -> bytes:
    # Prefer TokenScan templates for call cards
    pool = TS_TEMPLATES or TEMPLATES
    tmpl = random.choice(pool) if pool else None
    if tmpl:
        base = Image.open(tmpl["path"]).convert("RGBA")
        side = tmpl["side"]
    else:
        base = Image.new("RGBA", (W, H), (10, 10, 16, 255))
        side = "left"

    canvas = _overlay(base, side)
    draw   = ImageDraw.Draw(canvas)

    if side == "left":
        tx = 42
        _draw_tokenscan_logo(draw, tx, 32)
        # Chain pill
        chain_col = {
            "SOL": (153, 69, 255), "ETH": (100, 149, 237),
            "BNB": (243, 186, 47), "FX":  (0, 191, 255),
        }.get(chain.upper(), (160, 160, 160))
        draw.rounded_rectangle([tx, 94, tx + 88, 128], radius=14,
                               fill=chain_col)
        draw.text((tx + 14, 99), chain.upper(), font=_font(26, bold=True),
                  fill=(255, 255, 255, 255))
        draw.text((tx, 144), f"${symbol.upper()}", font=_font(80, bold=True),
                  fill=(0, 230, 118, 255))
        draw.text((tx, 240), "★  NEW CALL", font=_font(44, bold=True),
                  fill=(255, 214, 0, 255))
        # Stats
        f_sm = _font(30)
        f_b  = _font(30, bold=True)
        dim, white = (160, 160, 160, 230), (220, 220, 220, 255)
        def stat(lbl, val, y):
            draw.text((tx, y), lbl, font=f_sm, fill=dim)
            lw = _text_w(draw, lbl, f_sm)
            draw.text((tx + lw, y), val, font=f_b, fill=white)
        stat("Mkt Cap:  ", mcap_str, 316)
        stat("Liq:      ", liq_str,  358)
        stat("Vol 1H:   ", vol_str,  400)
        _draw_badge_ts(draw, f"@{username}", tx, H - 78)
    else:
        rx = int(W * 0.50)
        max_w = W - rx - 30
        sym_text = f"${symbol.upper()}"
        sz_sym = _best_size(draw, sym_text, max_w, 90, 40)
        draw.text((rx, 60), sym_text, font=_font(sz_sym, bold=True),
                  fill=(0, 255, 80, 255))
        draw.text((rx, 60 + sz_sym + 8), "★  NEW CALL",
                  font=_font(44, bold=True), fill=(255, 214, 0, 255))
        f_sm = _font(30)
        f_b  = _font(30, bold=True)
        dim, white = (160, 160, 160, 230), (220, 220, 220, 255)
        def stat(lbl, val, y):
            draw.text((rx, y), lbl, font=f_sm, fill=dim)
            lw = _text_w(draw, lbl, f_sm)
            draw.text((rx + lw, y), val, font=f_b, fill=white)
        stat("MC:  ", mcap_str, 240)
        stat("Liq: ", liq_str,  285)
        stat("Vol: ", vol_str,  330)
        _draw_badge_ac(draw, f"@{username}", rx, H - 70)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=93)
    buf.seek(0)
    return buf.read()


# ── FOREX / MACRO signal card ──────────────────────────────────────────────────
def build_forex_card(pair: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str, username: str = "alpha_circle1") -> bytes:
    tmpl = random.choice(TEMPLATES) if TEMPLATES else None
    if tmpl:
        base = Image.open(tmpl["path"]).convert("RGBA")
        side = tmpl["side"]
    else:
        base = Image.new("RGBA", (W, H), (10, 10, 16, 255))
        side = "left"

    canvas = _overlay(base, side)
    draw   = ImageDraw.Draw(canvas)
    is_long = direction.upper() in ("LONG", "BUY")
    dir_col = (0, 230, 118, 255) if is_long else (255, 80, 80, 255)
    dir_bg  = (0, 110, 50)       if is_long else (130, 30, 30)

    if side == "left":
        tx = 42
        _draw_tokenscan_logo(draw, tx, 32)
        pair_sz = _best_size(draw, pair.upper(), int(W * 0.52) - tx - 10, 90, 44)
        draw.text((tx, 88), pair.upper(), font=_font(pair_sz, bold=True),
                  fill=(255, 255, 255, 255))
        # Direction badge
        df = _font(38, bold=True)
        dw = _text_w(draw, direction.upper(), df) + 40
        draw.rounded_rectangle([tx, 88 + pair_sz + 8, tx + dw,
                                 88 + pair_sz + 58], radius=14, fill=dir_bg)
        draw.text((tx + 14, 88 + pair_sz + 14), direction.upper(),
                  font=df, fill=dir_col)
        tf_x = tx + dw + 16
        draw.text((tf_x, 88 + pair_sz + 18), timeframe,
                  font=_font(32), fill=(170, 170, 170, 200))
        y0, lh = 88 + pair_sz + 80, 46
        f_sm = _font(29)
        f_b  = _font(29, bold=True)
        dim, white = (160, 160, 160, 200), (220, 220, 220, 230)
        green, red = (0, 220, 110, 255), (255, 90, 90, 255)
        def row(lbl, val, col, y):
            draw.text((tx, y), lbl, font=f_sm, fill=dim)
            lw = _text_w(draw, lbl, f_sm)
            draw.text((tx + lw, y), val, font=f_b, fill=col)
        row("Entry:  ", entry, white, y0)
        row("TP 1:   ", tp1,   green, y0 + lh)
        row("TP 2:   ", tp2,   green, y0 + lh * 2)
        row("SL:     ", sl,    red,   y0 + lh * 3)
        row("R/R:    ", rr,    white, y0 + lh * 4)
        _draw_badge_ts(draw, f"@{username}", tx, H - 78)

    else:
        rx = int(W * 0.50)
        max_w = W - rx - 30
        pair_sz = _best_size(draw, pair.upper(), max_w, 80, 40)
        draw.text((rx, 60), pair.upper(), font=_font(pair_sz, bold=True),
                  fill=(255, 255, 255, 255))
        df = _font(36, bold=True)
        dw = _text_w(draw, direction.upper(), df) + 32
        draw.rounded_rectangle([rx, 60 + pair_sz + 8, rx + dw,
                                 60 + pair_sz + 52], radius=12, fill=dir_bg)
        draw.text((rx + 12, 60 + pair_sz + 14), direction.upper(),
                  font=df, fill=dir_col)
        y0, lh = 60 + pair_sz + 72, 44
        f_sm = _font(28); f_b = _font(28, bold=True)
        dim, white = (160, 160, 160, 200), (220, 220, 220, 230)
        green, red = (0, 220, 110, 255), (255, 90, 90, 255)
        def row(lbl, val, col, y):
            draw.text((rx, y), lbl, font=f_sm, fill=dim)
            lw = _text_w(draw, lbl, f_sm)
            draw.text((rx + lw, y), val, font=f_b, fill=col)
        row("Entry: ", entry, white, y0)
        row("TP 1:  ", tp1,   green, y0 + lh)
        row("TP 2:  ", tp2,   green, y0 + lh * 2)
        row("SL:    ", sl,    red,   y0 + lh * 3)
        row("R/R:   ", rr,    white, y0 + lh * 4)
        _draw_badge_ac(draw, f"@{username}", rx, H - 70)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=93)
    buf.seek(0)
    return buf.read()
