"""
Card generator — uses real TokenScan / Alpha Circle reference images as backgrounds.
Solid dark overlay covers the original text area; fresh text is drawn on top.
"""

import io
import json
import os
import random
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
TMPL_DIR   = os.path.join(ASSETS_DIR, "templates")


# ── Templates ──────────────────────────────────────────────────────────────────
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


# ── Fonts ──────────────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
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
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _tw(draw: ImageDraw.Draw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))


# ── Solid dark overlay — fully covers original card text ───────────────────────
def _apply_overlay(base: Image.Image, side: str) -> Image.Image:
    ov  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drw = ImageDraw.Draw(ov)

    if side == "left":
        solid_end = int(W * 0.42)
        fade_end  = int(W * 0.60)
        for px in range(W):
            if px <= solid_end:
                a = 252
            elif px <= fade_end:
                t = (px - solid_end) / (fade_end - solid_end)
                a = int(252 * (1 - t ** 0.65))
            else:
                a = 0
            drw.line([(px, 0), (px, H)], fill=(5, 5, 8, a))
    else:
        solid_start = int(W * 0.58)
        fade_start  = int(W * 0.40)
        for px in range(W):
            if px >= solid_start:
                a = 252
            elif px >= fade_start:
                t = (px - fade_start) / (solid_start - fade_start)
                a = int(252 * t ** 0.65)
            else:
                a = 0
            drw.line([(px, 0), (px, H)], fill=(5, 5, 8, a))

    return Image.alpha_composite(base.convert("RGBA"), ov)


# ── TokenScan logo ─────────────────────────────────────────────────────────────
def _draw_logo(draw: ImageDraw.Draw, x: int = 44, y: int = 34):
    green   = (0, 220, 100, 255)
    heights = [32, 19, 32, 24]
    bw, gap = 9, 5
    for i, bh in enumerate(heights):
        bx = x + i * (bw + gap)
        by = y + (32 - bh)
        draw.rectangle([bx, by, bx + bw, y + 32], fill=green)
    lx = x + 4 * (bw + gap) + 10
    draw.text((lx, y + 1), "TokenScan",
              font=_font(31, bold=True), fill=(240, 240, 240, 255))


# ── Username badge ─────────────────────────────────────────────────────────────
def _draw_badge(draw: ImageDraw.Draw, text: str, x: int, y: int):
    font = _font(28, bold=True)
    bw   = _tw(draw, text, font) + 60
    bh   = 50
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=bh // 2,
                           fill=(0, 185, 85, 255))
    draw.ellipse([x + 6, y + 5, x + 40, y + 45],
                 fill=(255, 255, 255, 220), outline=(0, 0, 0, 40))
    draw.text((x + 46, y + 11), text, font=font, fill=(255, 255, 255, 255))


# ── "Called at $X | 🕐 Xh Xm" row ────────────────────────────────────────────
def _called_row(draw: ImageDraw.Draw, mcap: str, time_s: str, x: int, y: int):
    fn  = _font(28)
    fb  = _font(28, bold=True)
    dim = (190, 190, 190, 230)
    whi = (230, 230, 230, 230)
    draw.text((x, y), "Called at ", font=fn, fill=dim)
    ox = _tw(draw, "Called at ", fn)
    draw.text((x + ox, y), mcap, font=fb, fill=whi)
    ox2 = _tw(draw, mcap, fb)
    draw.text((x + ox + ox2, y), f"  \U0001f550 {time_s}", font=fn, fill=dim)


# ── Best font size ─────────────────────────────────────────────────────────────
def _fit_size(draw: ImageDraw.Draw, text: str, max_w: int,
              mx: int = 230, mn: int = 72) -> int:
    for sz in range(mx, mn - 1, -4):
        if _tw(draw, text, _font(sz, bold=True)) <= max_w:
            return sz
    return mn


# ─────────────────────────────────────────────────────────────────────────────
#  GAIN / UPDATE card
# ─────────────────────────────────────────────────────────────────────────────
def build_update_card(symbol: str, multiplier: float, mcap_str: str,
                      time_str: str, username: str = "alpha_circle1") -> bytes:
    side = "left"
    tmpl = None
    if ALL_TEMPLATES:
        tmpl = random.choice(ALL_TEMPLATES)
        side = "left" if tmpl in TS_TEMPLATES else "right"

    base   = Image.open(tmpl).convert("RGBA") if tmpl else Image.new("RGBA", (W, H), (8, 8, 14, 255))
    canvas = _apply_overlay(base, side)
    draw   = ImageDraw.Draw(canvas)

    if side == "left":
        tx     = 44
        tw_lim = int(W * 0.48) - tx

        _draw_logo(draw, tx, 34)
        draw.text((tx, 100), f"${symbol.upper()}",
                  font=_font(54, bold=True), fill=(0, 230, 118, 255))

        mult_text = f"{multiplier:.1f}x"
        sz  = _fit_size(draw, mult_text, tw_lim, 230, 72)
        mf  = _font(sz, bold=True)
        for dx, dy in [(-2, 2), (2, -2)]:
            draw.text((tx + dx, 170 + dy), mult_text,
                      font=mf, fill=(0, 70, 35, 100))
        draw.text((tx, 170), mult_text, font=mf, fill=(255, 255, 255, 255))
        mh = mf.getbbox(mult_text)[3]
        _called_row(draw, mcap_str, time_str, tx, 170 + mh + 16)
        _draw_badge(draw, f"@{username}", tx, H - 82)

    else:
        rx     = int(W * 0.50)
        tw_lim = W - rx - 28

        sym_sz = _fit_size(draw, symbol.upper(), tw_lim, 100, 44)
        draw.text((rx, 58), symbol.upper(),
                  font=_font(sym_sz, bold=True), fill=(255, 255, 255, 255))
        draw.text((rx, 58 + sym_sz + 6), f"called at {mcap_str}",
                  font=_font(28), fill=(190, 190, 190, 200))

        mult_text = f"{multiplier:.1f}X"
        sz = _fit_size(draw, mult_text, tw_lim, 190, 72)
        mf = _font(sz, bold=True)
        my = 58 + sym_sz + 54
        draw.text((rx, my), mult_text, font=mf, fill=(0, 255, 80, 255))
        mh = mf.getbbox(mult_text)[3]
        draw.text((rx, my + mh + 8), f"\U0001f550 {time_str}",
                  font=_font(30), fill=(170, 170, 170, 200))
        draw.text((rx, H - 80), f"@{username}",
                  font=_font(30, bold=True), fill=(255, 255, 255, 200))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=93)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
#  NEW CALL card
# ─────────────────────────────────────────────────────────────────────────────
def build_call_card(symbol: str, mcap_str: str, liq_str: str,
                    vol_str: str, chain: str = "SOL",
                    username: str = "alpha_circle1") -> bytes:
    pool   = TS_TEMPLATES or ALL_TEMPLATES
    tmpl   = random.choice(pool) if pool else None
    base   = Image.open(tmpl).convert("RGBA") if tmpl else Image.new("RGBA", (W, H), (8, 8, 14, 255))
    canvas = _apply_overlay(base, "left")
    draw   = ImageDraw.Draw(canvas)
    tx     = 44
    tw_lim = int(W * 0.48) - tx

    _draw_logo(draw, tx, 34)

    chain_col = {"SOL": (153, 69, 255), "ETH": (100, 149, 237),
                 "BNB": (243, 186, 47),  "FX":  (0, 191, 255)
                 }.get(chain.upper(), (140, 140, 140))
    draw.rounded_rectangle([tx, 98, tx + 92, 134], radius=14, fill=chain_col)
    draw.text((tx + 16, 103), chain.upper(),
              font=_font(26, bold=True), fill=(255, 255, 255, 255))

    sym_sz = _fit_size(draw, f"${symbol.upper()}", tw_lim, 82, 44)
    draw.text((tx, 148), f"${symbol.upper()}",
              font=_font(sym_sz, bold=True), fill=(0, 230, 118, 255))

    draw.text((tx, 148 + sym_sz + 10), "\u2746  NEW CALL",
              font=_font(44, bold=True), fill=(255, 214, 0, 255))

    fn  = _font(30)
    fb  = _font(30, bold=True)
    dim = (165, 165, 165, 230)
    whi = (225, 225, 225, 255)
    y0  = 148 + sym_sz + 76

    def stat(lbl: str, val: str, y: int):
        draw.text((tx, y), lbl, font=fn, fill=dim)
        lw = _tw(draw, lbl, fn)
        draw.text((tx + lw, y), val, font=fb, fill=whi)

    stat("MC:   ", mcap_str, y0)
    stat("Liq:  ", liq_str,  y0 + 42)
    stat("Vol:  ", vol_str,  y0 + 84)

    _draw_badge(draw, f"@{username}", tx, H - 82)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=93)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
#  FOREX / MACRO signal card
# ─────────────────────────────────────────────────────────────────────────────
def build_forex_card(pair: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str, username: str = "alpha_circle1") -> bytes:
    pool   = TS_TEMPLATES or ALL_TEMPLATES
    tmpl   = random.choice(pool) if pool else None
    base   = Image.open(tmpl).convert("RGBA") if tmpl else Image.new("RGBA", (W, H), (8, 8, 14, 255))
    canvas = _apply_overlay(base, "left")
    draw   = ImageDraw.Draw(canvas)
    tx     = 44
    tw_lim = int(W * 0.48) - tx

    is_long = direction.upper() in ("LONG", "BUY")
    dir_col = (0, 230, 118, 255) if is_long else (255, 80, 80, 255)
    dir_bg  = (0, 110, 50)       if is_long else (130, 30, 30)

    _draw_logo(draw, tx, 34)

    pair_sz = _fit_size(draw, pair.upper(), tw_lim, 86, 40)
    draw.text((tx, 92), pair.upper(),
              font=_font(pair_sz, bold=True), fill=(255, 255, 255, 255))

    df  = _font(38, bold=True)
    dw  = _tw(draw, direction.upper(), df) + 42
    dy  = 92 + pair_sz + 10
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 56], radius=14, fill=dir_bg)
    draw.text((tx + 14, dy + 10), direction.upper(), font=df, fill=dir_col)
    draw.text((tx + dw + 14, dy + 14), timeframe,
              font=_font(32), fill=(170, 170, 170, 200))

    y0, lh = dy + 78, 46
    fn  = _font(29)
    fb  = _font(29, bold=True)
    dim = (165, 165, 165, 200)
    whi = (225, 225, 225, 230)
    grn = (0, 220, 110, 255)
    red = (255, 90, 90, 255)

    def row(lbl: str, val: str, col, y: int):
        draw.text((tx, y), lbl, font=fn, fill=dim)
        lw = _tw(draw, lbl, fn)
        draw.text((tx + lw, y), val, font=fb, fill=col)

    row("Entry:  ", entry, whi, y0)
    row("TP 1:   ", tp1,   grn, y0 + lh)
    row("TP 2:   ", tp2,   grn, y0 + lh * 2)
    row("SL:     ", sl,    red, y0 + lh * 3)
    row("R/R:    ", rr,    whi, y0 + lh * 4)

    _draw_badge(draw, f"@{username}", tx, H - 82)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=93)
    buf.seek(0)
    return buf.read()
