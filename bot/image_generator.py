"""
Alpha_Calls card generator.
6 completely distinct visual styles — randomly selected per post so no two cards look alike.
Styles: A=TokenScan classic, B=Neon hunter, C=Terminal insider,
        D=Gains beast, E=Forex professional, F=Stamp alert.
"""

import io
import json
import math
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 640
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
TMPL_DIR   = os.path.join(ASSETS_DIR, "templates")
USERNAME   = "@Alpha_X_Calls"

# ── Load background templates ──────────────────────────────────────────────────
def _load_templates():
    mf = os.path.join(TMPL_DIR, "manifest.json")
    if not os.path.exists(mf):
        return [], []
    manifest = json.load(open(mf))
    left, right = [], []
    for fname, side in manifest.items():
        p = os.path.join(TMPL_DIR, fname)
        if os.path.exists(p):
            (left if side == "left" else right).append(p)
    return left, right

TS_TEMPLATES, AC_TEMPLATES = _load_templates()
ALL_TEMPLATES = TS_TEMPLATES + AC_TEMPLATES

# ── Font helpers ───────────────────────────────────────────────────────────────
_FONT_CACHE: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _FONT_CACHE[key] = f
                return f
            except Exception:
                pass
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f

def _tw(draw: ImageDraw.Draw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))

def _fit_size(draw: ImageDraw.Draw, text: str, max_w: int,
              mx: int = 220, mn: int = 54) -> int:
    for sz in range(mx, mn - 1, -4):
        if _tw(draw, text, _font(sz, bold=True)) <= max_w:
            return sz
    return mn

def _save(canvas: Image.Image) -> bytes:
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=94)
    buf.seek(0)
    return buf.read()

# ── Shared helpers ─────────────────────────────────────────────────────────────

def _load_bg(side: str = "left") -> Image.Image:
    pool = (TS_TEMPLATES if side == "left" else AC_TEMPLATES) or ALL_TEMPLATES
    if pool:
        path = random.choice(pool)
        return Image.open(path).convert("RGBA").resize((W, H))
    return Image.new("RGBA", (W, H), (8, 8, 14, 255))

def _solid_overlay(base: Image.Image, side: str, opacity: int = 248) -> Image.Image:
    ov  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drw = ImageDraw.Draw(ov)
    if side == "left":
        solid_end, fade_end = int(W * 0.44), int(W * 0.62)
        for px in range(W):
            if px <= solid_end:         a = opacity
            elif px <= fade_end:
                t = (px - solid_end) / (fade_end - solid_end)
                a = int(opacity * (1 - t ** 0.6))
            else:                        a = 0
            drw.line([(px, 0), (px, H)], fill=(4, 4, 8, a))
    else:
        solid_start, fade_start = int(W * 0.56), int(W * 0.38)
        for px in range(W):
            if px >= solid_start:        a = opacity
            elif px >= fade_start:
                t = (px - fade_start) / (solid_start - fade_start)
                a = int(opacity * t ** 0.6)
            else:                        a = 0
            drw.line([(px, 0), (px, H)], fill=(4, 4, 8, a))
    return Image.alpha_composite(base, ov)

def _badge(draw: ImageDraw.Draw, text: str, x: int, y: int,
           bg=(0, 185, 85, 255), fg=(255, 255, 255, 255)):
    font = _font(27, bold=True)
    bw   = _tw(draw, text, font) + 56
    bh   = 48
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=24, fill=bg)
    draw.ellipse([x + 5, y + 4, x + 40, y + 44],
                 fill=(255, 255, 255, 200), outline=(0, 0, 0, 30))
    draw.text((x + 44, y + 10), text, font=font, fill=fg)

def _ac_logo(draw: ImageDraw.Draw, x: int, y: int, accent=(0, 220, 100, 255)):
    """Alpha_Calls bar-chart logo + wordmark."""
    heights = [30, 18, 30, 22]
    bw, gap = 8, 4
    for i, bh in enumerate(heights):
        bx = x + i * (bw + gap)
        draw.rectangle([bx, y + (30 - bh), bx + bw, y + 30], fill=accent)
    draw.text((x + 4 * (bw + gap) + 10, y + 1),
              "Alpha_Calls", font=_font(29, bold=True), fill=(240, 240, 240, 255))

def _chain_pill(draw: ImageDraw.Draw, chain: str, x: int, y: int):
    colors = {
        "SOL": (153, 69, 255), "ETH": (100, 149, 237),
        "BNB": (243, 186, 47), "FX":  (0, 191, 255),
        "BTC": (247, 147, 26),
    }
    col = colors.get(chain.upper(), (130, 130, 130))
    draw.rounded_rectangle([x, y, x + 90, y + 36], radius=10, fill=col)
    draw.text((x + 12, y + 5), chain.upper(), font=_font(24, bold=True),
              fill=(255, 255, 255, 255))


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE A — TokenScan classic (dark left panel, green logo, big multiplier)
# ═══════════════════════════════════════════════════════════════════════════════
def _style_a_call(symbol: str, mc: str, liq: str, vol: str, chain: str) -> Image.Image:
    base   = _load_bg("left")
    canvas = _solid_overlay(base, "left")
    draw   = ImageDraw.Draw(canvas)
    tx, tw_lim = 44, int(W * 0.46) - 44

    _ac_logo(draw, tx, 34)
    _chain_pill(draw, chain, tx, 96)

    sym_sz = _fit_size(draw, f"${symbol.upper()}", tw_lim, 82, 42)
    draw.text((tx, 144), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=(0, 230, 118, 255))

    draw.text((tx, 144 + sym_sz + 8), "✦  NEW CALL",
              font=_font(42, bold=True), fill=(255, 214, 0, 255))

    fn, fb = _font(29), _font(29, bold=True)
    dim, whi = (160, 160, 160, 220), (225, 225, 225, 255)
    y0 = 144 + sym_sz + 66

    def stat(lbl, val, y):
        draw.text((tx, y), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y), val, font=fb, fill=whi)

    stat("MC:  ", mc, y0)
    stat("Liq: ", liq, y0 + 42)
    stat("Vol: ", vol, y0 + 84)
    _badge(draw, USERNAME, tx, H - 80)
    return canvas

def _style_a_update(symbol: str, mult: float, entry_mc: str, t_str: str) -> Image.Image:
    base   = _load_bg("left")
    canvas = _solid_overlay(base, "left")
    draw   = ImageDraw.Draw(canvas)
    tx, tw_lim = 44, int(W * 0.46) - 44

    _ac_logo(draw, tx, 34)
    draw.text((tx, 96), f"${symbol.upper()}",
              font=_font(52, bold=True), fill=(0, 230, 118, 255))

    mt = f"{mult:.1f}x"
    sz = _fit_size(draw, mt, tw_lim, 220, 72)
    mf = _font(sz, bold=True)
    for dx, dy in [(-2, 2), (2, -2)]:
        draw.text((tx + dx, 164 + dy), mt, font=mf, fill=(0, 60, 30, 90))
    draw.text((tx, 164), mt, font=mf, fill=(255, 255, 255, 255))
    mh = mf.getbbox(mt)[3]

    fn = _font(27)
    y2 = 164 + mh + 14
    draw.text((tx, y2), "Called at ", font=fn, fill=(160, 160, 160, 210))
    ox = _tw(draw, "Called at ", fn)
    draw.text((tx + ox, y2), entry_mc, font=_font(27, bold=True), fill=(220, 220, 220, 220))
    ox2 = _tw(draw, entry_mc, _font(27, bold=True))
    draw.text((tx + ox + ox2, y2), f"  🕐 {t_str}", font=fn, fill=(160, 160, 160, 210))

    _badge(draw, USERNAME, tx, H - 80)
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE B — Neon hunter (real bg right-side, neon accent stripe, huge ticker)
# ═══════════════════════════════════════════════════════════════════════════════
def _style_b_call(symbol: str, mc: str, liq: str, vol: str, chain: str) -> Image.Image:
    base   = _load_bg("right")
    canvas = _solid_overlay(base, "right", opacity=244)
    draw   = ImageDraw.Draw(canvas)
    rx, tw_lim = int(W * 0.50), W - int(W * 0.50) - 24

    # Neon top stripe
    draw.rectangle([rx, 0, W, 6], fill=(0, 255, 140, 255))

    _ac_logo(draw, rx, 22)
    _chain_pill(draw, chain, rx, 72)

    sym_sz = _fit_size(draw, f"${symbol.upper()}", tw_lim, 88, 40)
    draw.text((rx, 120), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=(255, 255, 255, 255))

    draw.text((rx, 120 + sym_sz + 10), "🔔 ALPHA CALL",
              font=_font(38, bold=True), fill=(0, 230, 118, 255))

    fn, fb = _font(28), _font(28, bold=True)
    dim, whi = (155, 155, 155, 220), (220, 220, 220, 255)
    y0 = 120 + sym_sz + 64

    def stat(lbl, val, y):
        draw.text((rx, y), lbl, font=fn, fill=dim)
        draw.text((rx + _tw(draw, lbl, fn), y), val, font=fb, fill=whi)

    stat("MC:  ", mc, y0)
    stat("Liq: ", liq, y0 + 40)
    stat("Vol: ", vol, y0 + 80)

    draw.rectangle([rx, H - 6, W, H], fill=(0, 255, 140, 255))
    _badge(draw, USERNAME, rx, H - 74, bg=(20, 20, 20, 220))
    return canvas

def _style_b_update(symbol: str, mult: float, entry_mc: str, t_str: str) -> Image.Image:
    base   = _load_bg("right")
    canvas = _solid_overlay(base, "right", opacity=244)
    draw   = ImageDraw.Draw(canvas)
    rx, tw_lim = int(W * 0.50), W - int(W * 0.50) - 24

    draw.rectangle([rx, 0, W, 6], fill=(0, 255, 140, 255))
    _ac_logo(draw, rx, 22)

    sym_sz = _fit_size(draw, symbol.upper(), tw_lim, 90, 40)
    draw.text((rx, 72), symbol.upper(),
              font=_font(sym_sz, bold=True), fill=(255, 255, 255, 255))
    draw.text((rx, 72 + sym_sz + 6), f"called at {entry_mc}",
              font=_font(26), fill=(170, 170, 170, 200))

    mt = f"{mult:.1f}X"
    sz = _fit_size(draw, mt, tw_lim, 180, 66)
    mf = _font(sz, bold=True)
    my = 72 + sym_sz + 50
    draw.text((rx, my), mt, font=mf, fill=(0, 255, 80, 255))
    mh = mf.getbbox(mt)[3]
    draw.text((rx, my + mh + 8), f"🕐 {t_str}",
              font=_font(28), fill=(160, 160, 160, 200))

    draw.rectangle([rx, H - 6, W, H], fill=(0, 255, 140, 255))
    _badge(draw, USERNAME, rx, H - 74, bg=(20, 20, 20, 220))
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE C — Terminal / Insider (pure black bg, amber/green monospace feel)
# ═══════════════════════════════════════════════════════════════════════════════
def _style_c_call(symbol: str, mc: str, liq: str, vol: str, chain: str) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (4, 6, 4, 255))
    draw   = ImageDraw.Draw(canvas)

    # Scanline texture — subtle horizontal lines
    for y in range(0, H, 4):
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, 35))

    # Left accent bar
    draw.rectangle([0, 0, 5, H], fill=(0, 200, 60, 255))

    amber  = (255, 185, 0, 255)
    green  = (0, 230, 90, 255)
    dimgr  = (100, 140, 100, 220)
    white  = (220, 225, 220, 255)

    _ac_logo(draw, 36, 30, accent=amber)

    draw.text((36, 82), f"[ INSIDER CALL ]",
              font=_font(32, bold=True), fill=amber)
    _chain_pill(draw, chain, 36, 128)

    sym_sz = _fit_size(draw, f"${symbol.upper()}", 540, 96, 44)
    draw.text((36, 174), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=green)

    fb = _font(30, bold=True)
    fn = _font(30)
    y0 = 174 + sym_sz + 16

    rows = [
        ("> MC_CAP:    ", mc,  white),
        ("> LIQUIDITY: ", liq, white),
        ("> VOL_24H:   ", vol, white),
    ]
    for lbl, val, col in rows:
        draw.text((36, y0), lbl, font=fn, fill=dimgr)
        draw.text((36 + _tw(draw, lbl, fn), y0), val, font=fb, fill=col)
        y0 += 46

    draw.text((36, H - 58), "⚡ not posting this elsewhere. move.",
              font=_font(26), fill=amber)
    draw.text((36, H - 28), USERNAME,
              font=_font(24, bold=True), fill=green)
    return canvas

def _style_c_update(symbol: str, mult: float, entry_mc: str, t_str: str) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (4, 6, 4, 255))
    draw   = ImageDraw.Draw(canvas)
    for y in range(0, H, 4):
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, 35))
    draw.rectangle([0, 0, 5, H], fill=(0, 200, 60, 255))

    amber  = (255, 185, 0, 255)
    green  = (0, 230, 90, 255)
    dimgr  = (100, 140, 100, 220)
    white  = (220, 225, 220, 255)

    _ac_logo(draw, 36, 30, accent=amber)
    draw.text((36, 82), "[ GAIN UPDATE ]", font=_font(32, bold=True), fill=amber)
    draw.text((36, 128), f"${symbol.upper()}", font=_font(56, bold=True), fill=green)

    mt = f"{mult:.1f}x"
    sz = _fit_size(draw, mt, 560, 200, 72)
    draw.text((36, 196), mt, font=_font(sz, bold=True), fill=white)
    draw.text((36, 196 + _font(sz, bold=True).getbbox(mt)[3] + 12),
              f"called at {entry_mc}  •  {t_str} in", font=_font(28), fill=dimgr)
    draw.text((36, H - 58), "not everyone catches these. you did.",
              font=_font(26), fill=amber)
    draw.text((36, H - 28), USERNAME, font=_font(24, bold=True), fill=green)
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE D — Gains beast (big bg, centered giant X, scoreboard feel)
# ═══════════════════════════════════════════════════════════════════════════════
def _style_d_update(symbol: str, mult: float, entry_mc: str, t_str: str) -> Image.Image:
    tmpl = random.choice(ALL_TEMPLATES) if ALL_TEMPLATES else None
    if tmpl:
        bg = Image.open(tmpl).convert("RGBA").resize((W, H))
        # Full dark scrim
        scrim = Image.new("RGBA", (W, H), (6, 6, 10, 210))
        canvas = Image.alpha_composite(bg, scrim)
    else:
        canvas = Image.new("RGBA", (W, H), (6, 6, 10, 255))
    draw = ImageDraw.Draw(canvas)

    # Bold top banner
    draw.rectangle([0, 0, W, 70], fill=(0, 185, 80, 255))
    draw.text((32, 14), "ALPHA_CALLS  ⚡  GAIN UPDATE",
              font=_font(36, bold=True), fill=(255, 255, 255, 255))

    # Giant multiplier — center
    mt = f"{mult:.1f}X"
    sz = _fit_size(draw, mt, W - 80, 280, 120)
    mf = _font(sz, bold=True)
    mw = _tw(draw, mt, mf)
    mx = (W - mw) // 2
    my = 90
    # Drop shadow
    for ox, oy in [(-4, 4), (4, -4), (-4, -4), (4, 4)]:
        draw.text((mx + ox, my + oy), mt, font=mf, fill=(0, 60, 20, 100))
    draw.text((mx, my), mt, font=mf, fill=(0, 230, 100, 255))

    mh = mf.getbbox(mt)[3]
    y2 = my + mh + 18

    # Symbol + info row
    sym_font = _font(44, bold=True)
    sym_text = f"${symbol.upper()}"
    sw = _tw(draw, sym_text, sym_font)
    draw.text(((W - sw) // 2, y2), sym_text,
              font=sym_font, fill=(255, 255, 255, 255))
    y2 += 56

    info = f"Called at {entry_mc}   •   {t_str} hold"
    iw   = _tw(draw, info, _font(29))
    draw.text(((W - iw) // 2, y2), info,
              font=_font(29), fill=(160, 160, 160, 210))

    # Bottom bar
    draw.rectangle([0, H - 58, W, H], fill=(0, 0, 0, 180))
    uw = _tw(draw, USERNAME, _font(28, bold=True))
    draw.text(((W - uw) // 2, H - 44), USERNAME,
              font=_font(28, bold=True), fill=(0, 230, 100, 255))
    return canvas

def _style_d_call(symbol: str, mc: str, liq: str, vol: str, chain: str) -> Image.Image:
    tmpl = random.choice(ALL_TEMPLATES) if ALL_TEMPLATES else None
    if tmpl:
        bg = Image.open(tmpl).convert("RGBA").resize((W, H))
        scrim = Image.new("RGBA", (W, H), (6, 6, 10, 215))
        canvas = Image.alpha_composite(bg, scrim)
    else:
        canvas = Image.new("RGBA", (W, H), (6, 6, 10, 255))
    draw = ImageDraw.Draw(canvas)

    # Banner
    draw.rectangle([0, 0, W, 70], fill=(0, 185, 80, 255))
    draw.text((32, 14), "ALPHA_CALLS  🎯  NEW CALL",
              font=_font(36, bold=True), fill=(255, 255, 255, 255))

    # Centered ticker
    sym_sz = _fit_size(draw, f"${symbol.upper()}", W - 80, 130, 60)
    sf = _font(sym_sz, bold=True)
    sw = _tw(draw, f"${symbol.upper()}", sf)
    draw.text(((W - sw) // 2, 86), f"${symbol.upper()}",
              font=sf, fill=(0, 230, 118, 255))
    sh = sf.getbbox(f"${symbol.upper()}")[3]

    # Chain pill centered
    cpx = (W - 90) // 2
    _chain_pill(draw, chain, cpx, 90 + sh + 10)

    # Stats row
    fn, fb = _font(30), _font(30, bold=True)
    dim, whi = (155, 155, 155, 210), (220, 220, 220, 255)
    y0 = 90 + sh + 66

    def stat_center(lbl, val, y):
        full = lbl + val
        fw = _tw(draw, lbl, fn) + _tw(draw, val, fb)
        sx = (W - fw) // 2
        draw.text((sx, y), lbl, font=fn, fill=dim)
        draw.text((sx + _tw(draw, lbl, fn), y), val, font=fb, fill=whi)

    stat_center("MC: ", mc, y0)
    stat_center("Liq: ", liq, y0 + 48)
    stat_center("Vol: ", vol, y0 + 96)

    draw.rectangle([0, H - 58, W, H], fill=(0, 0, 0, 180))
    uw = _tw(draw, USERNAME, _font(28, bold=True))
    draw.text(((W - uw) // 2, H - 44), USERNAME,
              font=_font(28, bold=True), fill=(0, 230, 100, 255))
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE E — Forex professional (clean blue/white left panel, right bg visible)
# ═══════════════════════════════════════════════════════════════════════════════
def _style_e_forex(pair: str, direction: str, entry: str,
                    tp1: str, tp2: str, sl: str, tf: str, rr: str) -> Image.Image:
    is_long = direction.upper() in ("LONG", "BUY")
    accent  = (0, 200, 100, 255)   if is_long else (220, 60, 60, 255)
    dir_bg  = (0, 110, 55, 255)    if is_long else (140, 30, 30, 255)

    base   = _load_bg("left")
    canvas = _solid_overlay(base, "left", opacity=250)
    draw   = ImageDraw.Draw(canvas)
    tx, tw_lim = 36, int(W * 0.46) - 36

    # Left accent stripe
    draw.rectangle([0, 0, 6, H], fill=accent)

    _ac_logo(draw, tx, 30)

    # Signal header badge
    header = "FX SIGNAL" if "/" in pair and not any(c.isdigit() for c in pair[:3]) else "TRADE SIGNAL"
    hw = _tw(draw, header, _font(32, bold=True)) + 32
    draw.rounded_rectangle([tx, 78, tx + hw, 78 + 50], radius=8, fill=dir_bg)
    draw.text((tx + 16, 88), header, font=_font(32, bold=True), fill=(255, 255, 255, 255))

    # Pair name
    pair_sz = _fit_size(draw, pair.upper(), tw_lim, 80, 38)
    draw.text((tx, 140), pair.upper(),
              font=_font(pair_sz, bold=True), fill=(255, 255, 255, 255))

    # Direction + TF side by side
    df  = _font(36, bold=True)
    dw  = _tw(draw, direction.upper(), df) + 36
    dy  = 140 + pair_sz + 10
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 52], radius=10, fill=dir_bg)
    draw.text((tx + 14, dy + 9), direction.upper(), font=df, fill=accent)
    draw.text((tx + dw + 14, dy + 13), tf,
              font=_font(30), fill=(160, 160, 160, 200))

    y0, lh = dy + 70, 44
    fn, fb = _font(28), _font(28, bold=True)
    dim = (150, 150, 150, 200)
    whi = (220, 220, 220, 230)
    grn = (0, 215, 100, 255)
    red = (240, 80, 80, 255)

    def row(lbl, val, col, y):
        draw.text((tx, y), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y), val, font=fb, fill=col)

    row("Entry   ", entry, whi, y0)
    row("TP 1    ", tp1,   grn, y0 + lh)
    row("TP 2    ", tp2,   grn, y0 + lh * 2)
    row("SL      ", sl,    red, y0 + lh * 3)
    row("R/R     ", rr,    whi, y0 + lh * 4)

    _badge(draw, USERNAME, tx, H - 76, bg=(20, 20, 20, 220))
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLE F — Stamp / Alert (bold bg tint, massive pill badge, raw alert style)
# ═══════════════════════════════════════════════════════════════════════════════
def _style_f_call(symbol: str, mc: str, liq: str, vol: str, chain: str) -> Image.Image:
    base   = _load_bg("left")
    # Heavier tint — deep navy
    canvas = _solid_overlay(base, "left", opacity=252)
    draw   = ImageDraw.Draw(canvas)
    tx, tw_lim = 44, int(W * 0.46) - 44

    # Top colored banner
    is_purple = random.random() > 0.5
    banner_col = (100, 30, 200, 255) if is_purple else (0, 140, 80, 255)
    draw.rectangle([0, 0, W // 2, 72], fill=banner_col)
    draw.text((tx, 16), "⚡  ALPHA CALL", font=_font(34, bold=True),
              fill=(255, 255, 255, 255))

    _ac_logo(draw, tx, 86, accent=(180, 100, 255, 255) if is_purple else (0, 220, 100, 255))
    _chain_pill(draw, chain, tx, 132)

    sym_sz = _fit_size(draw, f"${symbol.upper()}", tw_lim, 100, 48)
    highlight = (185, 100, 255, 255) if is_purple else (0, 230, 118, 255)
    draw.text((tx, 178), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=highlight)

    fn, fb = _font(30), _font(30, bold=True)
    dim, whi = (150, 150, 150, 200), (215, 215, 215, 255)
    y0 = 178 + sym_sz + 18

    def stat(lbl, val, y):
        draw.text((tx, y), lbl, font=fn, fill=dim)
        draw.text((tx + _tw(draw, lbl, fn), y), val, font=fb, fill=whi)

    stat("MC:  ", mc,  y0)
    stat("Liq: ", liq, y0 + 44)
    stat("Vol: ", vol, y0 + 88)

    _badge(draw, USERNAME, tx, H - 78,
           bg=(100, 30, 200, 255) if is_purple else (0, 185, 85, 255))
    return canvas

def _style_f_update(symbol: str, mult: float, entry_mc: str, t_str: str) -> Image.Image:
    base   = _load_bg("right")
    canvas = _solid_overlay(base, "right", opacity=252)
    draw   = ImageDraw.Draw(canvas)
    rx, tw_lim = int(W * 0.50), W - int(W * 0.50) - 24

    draw.rectangle([rx, 0, W, 72], fill=(0, 160, 70, 255))
    draw.text((rx + 18, 16), "🏆  GAIN UPDATE", font=_font(34, bold=True),
              fill=(255, 255, 255, 255))

    _ac_logo(draw, rx, 86)

    sym_sz = _fit_size(draw, symbol.upper(), tw_lim, 84, 38)
    draw.text((rx, 130), symbol.upper(),
              font=_font(sym_sz, bold=True), fill=(255, 255, 255, 255))

    mt = f"{mult:.1f}x"
    sz = _fit_size(draw, mt, tw_lim, 190, 72)
    mf = _font(sz, bold=True)
    draw.text((rx, 130 + sym_sz + 14), mt, font=mf, fill=(0, 230, 100, 255))
    mh = mf.getbbox(mt)[3]

    fn = _font(27)
    y2 = 130 + sym_sz + 14 + mh + 16
    draw.text((rx, y2), f"Called at {entry_mc}",
              font=fn, fill=(160, 160, 160, 200))
    draw.text((rx, y2 + 38), f"🕐 {t_str} in the trade",
              font=fn, fill=(160, 160, 160, 200))

    _badge(draw, USERNAME, rx, H - 78)
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API — randomly pick from available styles per card type
# ═══════════════════════════════════════════════════════════════════════════════

_CALL_STYLES   = [_style_a_call,   _style_b_call,   _style_c_call,
                  _style_d_call,   _style_f_call]
_UPDATE_STYLES = [_style_a_update, _style_b_update, _style_c_update,
                  _style_d_update, _style_f_update]

# Track last used style index to prevent consecutive repeats
_last_call_idx:   int = -1
_last_update_idx: int = -1


def _pick_style(pool: list, last_idx: int) -> tuple:
    choices = [i for i in range(len(pool)) if i != last_idx]
    idx = random.choice(choices)
    return pool[idx], idx


def build_call_card(symbol: str, mcap_str: str, liq_str: str,
                    vol_str: str, chain: str = "SOL",
                    username: str = "Alpha_Calls") -> bytes:
    global _last_call_idx
    fn, idx = _pick_style(_CALL_STYLES, _last_call_idx)
    _last_call_idx = idx
    canvas = fn(symbol, mcap_str, liq_str, vol_str, chain)
    return _save(canvas)


def build_update_card(symbol: str, multiplier: float, mcap_str: str,
                      time_str: str, username: str = "Alpha_Calls") -> bytes:
    global _last_update_idx
    fn, idx = _pick_style(_UPDATE_STYLES, _last_update_idx)
    _last_update_idx = idx
    canvas = fn(symbol, multiplier, mcap_str, time_str)
    return _save(canvas)


def build_forex_card(pair: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str, username: str = "Alpha_Calls") -> bytes:
    # Forex always uses Style E (professional) with slight variation
    canvas = _style_e_forex(pair, direction, entry, tp1, tp2, sl, timeframe, rr)
    return _save(canvas)
