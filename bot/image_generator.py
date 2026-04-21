"""
Alpha_X_Calls — image generator (TokenScan style only).

Single canonical card style based on the real TokenScan / chibi-pepe
template images:

  ┌────────────────────────────────────────────────────┐
  │ ▣ TokenScan                       (chibi character │
  │                                       on the right)│
  │ $SYMBOL                                            │
  │ 109x                                               │
  │                                                    │
  │ Called at $12.3k │ 3h                              │
  │                                                    │
  │ ▦ alpha_x_calls                                    │
  └────────────────────────────────────────────────────┘
            ALPHA_X_CALLS • JOIN VIP  (thin bottom bar)

No neon panels. No cyberpunk accents. Templates are used as the
background as-is so each post looks like an authentic TokenScan card.
"""

import io
import json
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Constants ─────────────────────────────────────────────────────────────────
W, H            = 1280, 720
ASSETS_DIR      = os.path.join(os.path.dirname(__file__), "assets")
TEMPLATES_DIR   = os.path.join(ASSETS_DIR, "templates")
CHANNEL_TAG     = "alpha_x_calls"
VIP_TAG         = "ALPHA_X_CALLS  •  JOIN VIP"
TS_GREEN        = (32, 224, 144, 255)
TS_GREEN_SOFT   = (40, 200, 130, 230)
WHITE           = (255, 255, 255, 255)
DIM             = (185, 188, 195, 220)


# ── PnL bases (random per-token) ──────────────────────────────────────────────
PNL_BASES = [50, 100, 100, 100, 200, 250, 500, 1000, 2530]


def random_pnl(multiplier: float) -> str:
    return pnl_for_base(random.choice(PNL_BASES), multiplier)


def pnl_for_base(base: int, multiplier: float) -> str:
    result  = round(base * multiplier)
    profit  = result - base
    return (
        f"📋 *Position PnL*\n"
        f"💵 ${base:,} ➜ ${result:,} (PnL + ${profit:,})"
    )


# ── Character cutouts (transparent PNGs) ──────────────────────────────────────
_CHARS = sorted([f for f in os.listdir(ASSETS_DIR)
                 if f.lower().endswith(".png")]) \
         if os.path.isdir(ASSETS_DIR) else []
_last_char: str = ""


def _pick_char_path() -> str:
    """Pick a character cutout, no consecutive repeats."""
    global _last_char
    if not _CHARS:
        return ""
    pool = [f for f in _CHARS if f != _last_char] or _CHARS
    pick = random.choice(pool)
    _last_char = pick
    return os.path.join(ASSETS_DIR, pick)


# ── Scene palettes (vary background hue per post — never neon) ────────────────
_SCENES = [
    {"top": (12, 30, 22),  "bot": (4,  10, 8)},   # forest dusk
    {"top": (28, 22, 38),  "bot": (8,  8,  16)},  # purple night
    {"top": (18, 28, 40),  "bot": (6,  10, 18)},  # blue night
    {"top": (35, 28, 22),  "bot": (10, 8,  6)},   # warm dusk
    {"top": (16, 26, 30),  "bot": (4,  8,  12)},  # teal night
    {"top": (22, 22, 28),  "bot": (6,  6,  10)},  # neutral
]
_last_scene: int = -1


def _pick_scene() -> dict:
    global _last_scene
    pool = [i for i in range(len(_SCENES)) if i != _last_scene]
    idx = random.choice(pool)
    _last_scene = idx
    return _SCENES[idx]


# ── Fonts ─────────────────────────────────────────────────────────────────────
_FONT_CACHE: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/nix/store/share/fonts/truetype/DejaVuSans-Bold.ttf",
    ]
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/nix/store/share/fonts/truetype/DejaVuSans.ttf",
    ]
    for p in (candidates_bold if bold else candidates):
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            _FONT_CACHE[key] = f
            return f
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _tw(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


def _fit(draw, text, max_w, start_size, min_size, bold=True):
    sz = start_size
    while sz > min_size:
        if _tw(draw, text, _font(sz, bold=bold)) <= max_w:
            return sz
        sz -= 2
    return min_size


# ── Background helpers ────────────────────────────────────────────────────────
def _gradient_bg(scene: dict | None = None) -> Image.Image:
    """Soft dark vertical gradient based on a scene palette."""
    if scene is None:
        scene = {"top": (16, 22, 30), "bot": (4, 8, 14)}
    t_r, t_g, t_b = scene["top"]
    b_r, b_g, b_b = scene["bot"]
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        r = int(t_r + (b_r - t_r) * t)
        g = int(t_g + (b_g - t_g) * t)
        b = int(t_b + (b_b - t_b) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b, 255))
    # subtle starfield in upper area
    rng = random.Random(scene["top"][0] * 7 + scene["bot"][2])
    for _ in range(120):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, int(H * 0.55))
        a = rng.randint(40, 140)
        d.point((x, y), fill=(255, 255, 255, a))
    return bg


def _paste_char(canvas: Image.Image, char_path: str) -> Image.Image:
    """Paste transparent character cutout on the right side."""
    if not char_path or not os.path.exists(char_path):
        return canvas
    try:
        ch = Image.open(char_path).convert("RGBA")
    except Exception:
        return canvas
    # Scale character to ~92% of canvas height
    target_h = int(H * 0.95)
    ratio = target_h / ch.height
    nw = int(ch.width * ratio)
    ch = ch.resize((nw, target_h), Image.LANCZOS)
    # Anchor: right edge sits roughly 6% inside the canvas
    x = W - nw + int(nw * 0.05)
    y = H - target_h + int(target_h * 0.02)
    canvas.alpha_composite(ch, dest=(max(x, int(W * 0.42)), y))
    return canvas


def _left_scrim(canvas: Image.Image, frac: float = 0.62, alpha: int = 210) -> Image.Image:
    """Dark vignette on the left so text stays legible over the character."""
    w_scrim = int(W * frac)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(w_scrim):
        t = x / w_scrim
        a = int(alpha * (1 - t * 0.55))
        d.line([(x, 0), (x, H)], fill=(4, 8, 12, a))
    return Image.alpha_composite(canvas, overlay)


def _bottom_bar(canvas: Image.Image) -> Image.Image:
    """Thin bottom 'ALPHA_X_CALLS • JOIN VIP' bar."""
    bar_h = 44
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, H - bar_h, W, H], fill=(0, 0, 0, 235))
    f = _font(22, bold=True)
    tw = _tw(d, VIP_TAG, f)
    d.text(((W - tw) // 2, H - bar_h + 10), VIP_TAG, font=f, fill=TS_GREEN)
    return Image.alpha_composite(canvas, overlay)


# ── Building blocks ───────────────────────────────────────────────────────────
def _draw_tokenscan_logo(draw: ImageDraw.ImageDraw, x: int, y: int):
    """Top-left  ▣ TokenScan  badge."""
    # Square mark
    sq = 36
    draw.rounded_rectangle([x, y, x + sq, y + sq], radius=8,
                           fill=(20, 24, 30, 255), outline=TS_GREEN, width=3)
    # inner brackets
    cx, cy = x + sq // 2, y + sq // 2
    for dx in (-9, 9):
        draw.rectangle([cx + dx - 2, cy - 8, cx + dx + 2, cy + 8],
                       fill=TS_GREEN)
    # "TokenScan" text
    draw.text((x + sq + 14, y + 2),
              "TokenScan", font=_font(30, bold=True), fill=WHITE)


def _draw_username_badge(draw: ImageDraw.ImageDraw, x: int, y: int,
                         username: str = CHANNEL_TAG):
    """Bottom-left green pill with @username."""
    f = _font(26, bold=True)
    pad_x, pad_y = 18, 10
    av  = 38
    tw  = _tw(draw, username, f)
    bw  = av + 8 + tw + pad_x * 2
    bh  = av + pad_y * 2
    # pill
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=bh // 2,
                           fill=TS_GREEN_SOFT)
    # avatar circle
    draw.ellipse([x + pad_x, y + pad_y, x + pad_x + av, y + pad_y + av],
                 fill=(255, 220, 160, 255))
    draw.ellipse([x + pad_x + 6, y + pad_y + 6,
                  x + pad_x + av - 6, y + pad_y + av - 6],
                 fill=(60, 200, 130, 255))
    # text
    draw.text((x + pad_x + av + 8, y + pad_y + 4),
              username, font=f, fill=(0, 0, 0, 255))


# ══════════════════════════════════════════════════════════════════════════════
#  CARD BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _save(canvas: Image.Image) -> bytes:
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=92, optimize=True)
    return buf.getvalue()


def _base_canvas(use_char: bool = True) -> Image.Image:
    scene = _pick_scene()
    bg = _gradient_bg(scene)
    if use_char:
        bg = _paste_char(bg, _pick_char_path())
    return _left_scrim(bg)


# ── Initial CALL card ─────────────────────────────────────────────────────────

def build_call_card(symbol: str, mcap_str: str, liq_str: str,
                    vol_str: str, chain: str = "SOL",
                    username: str = CHANNEL_TAG) -> bytes:
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 56, int(W * 0.55) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, lim, 84, 44)
    draw.text((tx, 138), sym_t,
              font=_font(sym_sz, bold=True), fill=TS_GREEN)

    label_y = 138 + sym_sz + 14
    draw.text((tx, label_y), "NEW CALL",
              font=_font(46, bold=True), fill=WHITE)

    fn, fb = _font(30), _font(30, bold=True)
    rows = [
        ("MC:   ", mcap_str),
        ("Liq:  ", liq_str),
        ("Vol:  ", vol_str),
    ]
    y = label_y + 70
    for lbl, val in rows:
        draw.text((tx, y), lbl, font=fn, fill=DIM)
        draw.text((tx + _tw(draw, lbl, fn), y), val, font=fb, fill=WHITE)
        y += 44

    chain_t = chain.upper()
    cf = _font(24, bold=True)
    cw = _tw(draw, chain_t, cf) + 24
    draw.rounded_rectangle([tx, y + 8, tx + cw, y + 8 + 36],
                           radius=8, fill=(50, 60, 220, 255))
    draw.text((tx + 12, y + 13), chain_t, font=cf, fill=WHITE)

    _draw_username_badge(draw, tx, H - 130)
    canvas = _bottom_bar(canvas)
    return _save(canvas)


# ── UPDATE / gain card ────────────────────────────────────────────────────────

def build_update_card(symbol: str, multiplier: float, mcap_str: str,
                      time_str: str, username: str = CHANNEL_TAG) -> bytes:
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 56, int(W * 0.58) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, lim, 78, 40)
    draw.text((tx, 150), sym_t,
              font=_font(sym_sz, bold=True), fill=TS_GREEN)

    if multiplier >= 100:
        x_t = f"{int(multiplier)}x"
    elif multiplier >= 10:
        x_t = f"{multiplier:.1f}x"
    else:
        x_t = f"{multiplier:.1f}x"

    x_sz = _fit(draw, x_t, lim, 200, 110)
    xy   = 150 + sym_sz + 8
    draw.text((tx, xy), x_t, font=_font(x_sz, bold=True), fill=WHITE)

    info_y = xy + x_sz + 22
    fn = _font(28)
    label = "Called at "
    mcap_clean = mcap_str if mcap_str.startswith("$") else f"${mcap_str}"
    draw.text((tx, info_y), label, font=fn, fill=DIM)
    after_label = tx + _tw(draw, label, fn)
    draw.text((after_label, info_y), mcap_clean,
              font=_font(28, bold=True), fill=TS_GREEN)

    sep_x = after_label + _tw(draw, mcap_clean, _font(28, bold=True)) + 18
    draw.text((sep_x, info_y), "│", font=fn, fill=(120, 124, 132, 200))
    draw.text((sep_x + 28, info_y), time_str,
              font=_font(28), fill=DIM)

    _draw_username_badge(draw, tx, H - 130)
    canvas = _bottom_bar(canvas)
    return _save(canvas)


# ── FOREX card (no neon — clean dark + small character) ───────────────────────

def build_forex_card(pair: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str, username: str = CHANNEL_TAG) -> bytes:
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 56, int(W * 0.58) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    is_long = direction.upper() in ("LONG", "BUY")
    dir_col = (0, 200, 110, 255) if is_long else (235, 70, 70, 255)

    hdr = "FX SIGNAL" if "/" in pair else "TRADE SIGNAL"
    hf  = _font(28, bold=True)
    hw  = _tw(draw, hdr, hf) + 28
    draw.rounded_rectangle([tx, 100, tx + hw, 100 + 44],
                           radius=8, fill=dir_col)
    draw.text((tx + 14, 110), hdr, font=hf, fill=(0, 0, 0, 255))

    pair_sz = _fit(draw, pair.upper(), lim, 76, 38)
    draw.text((tx, 156), pair.upper(),
              font=_font(pair_sz, bold=True), fill=WHITE)

    dy = 156 + pair_sz + 6
    df = _font(34, bold=True)
    dw = _tw(draw, direction.upper(), df) + 32
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 50], radius=10, fill=dir_col)
    draw.text((tx + 14, dy + 8), direction.upper(),
              font=df, fill=(0, 0, 0, 255))
    draw.text((tx + dw + 14, dy + 12), timeframe,
              font=_font(26), fill=DIM)

    fn, fb = _font(26), _font(26, bold=True)
    grn    = (0, 220, 120, 255)
    red    = (240, 80, 80, 255)
    y0, lh = dy + 70, 40

    for lbl, val, col in [
        ("Entry  ", entry, WHITE),
        ("TP 1   ", tp1,   grn),
        ("TP 2   ", tp2,   grn),
        ("SL     ", sl,    red),
        ("R/R    ", rr,    WHITE),
    ]:
        draw.text((tx, y0), lbl, font=fn, fill=DIM)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=col)
        y0 += lh

    _draw_username_badge(draw, tx, H - 130)
    canvas = _bottom_bar(canvas)
    return _save(canvas)


# ── STOCK card ────────────────────────────────────────────────────────────────

def build_stock_card(ticker: str, name: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str) -> bytes:
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 56, int(W * 0.58) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    is_long = direction.upper() in ("LONG", "BUY")
    dir_col = (0, 200, 110, 255) if is_long else (235, 70, 70, 255)

    hdr = "STOCK SIGNAL"
    hf  = _font(26, bold=True)
    hw  = _tw(draw, hdr, hf) + 28
    draw.rounded_rectangle([tx, 100, tx + hw, 100 + 42],
                           radius=8, fill=dir_col)
    draw.text((tx + 14, 110), hdr, font=hf, fill=(0, 0, 0, 255))

    tk_sz = _fit(draw, ticker.upper(), lim, 80, 42)
    draw.text((tx, 154), ticker.upper(),
              font=_font(tk_sz, bold=True), fill=WHITE)
    draw.text((tx, 154 + tk_sz + 4), name,
              font=_font(24), fill=DIM)

    dy = 154 + tk_sz + 50
    df = _font(30, bold=True)
    dw = _tw(draw, direction.upper(), df) + 30
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 46], radius=10, fill=dir_col)
    draw.text((tx + 14, dy + 8), direction.upper(),
              font=df, fill=(0, 0, 0, 255))
    draw.text((tx + dw + 14, dy + 12), timeframe,
              font=_font(24), fill=DIM)

    fn, fb = _font(24), _font(24, bold=True)
    grn    = (0, 220, 120, 255)
    red    = (240, 80, 80, 255)
    y0, lh = dy + 64, 36

    for lbl, val, col in [
        ("Entry  ", entry, WHITE),
        ("TP 1   ", tp1,   grn),
        ("TP 2   ", tp2,   grn),
        ("SL     ", sl,    red),
        ("R/R    ", rr,    WHITE),
    ]:
        draw.text((tx, y0), lbl, font=fn, fill=DIM)
        draw.text((tx + _tw(draw, lbl, fn), y0), val, font=fb, fill=col)
        y0 += lh

    _draw_username_badge(draw, tx, H - 130)
    canvas = _bottom_bar(canvas)
    return _save(canvas)


# ── VIP "X winners" teaser card ───────────────────────────────────────────────

def build_winners_card(symbol: str, multiplier: float,
                       entry: str, ath: str) -> bytes:
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)

    tx, lim = 56, int(W * 0.58) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, lim, 76, 40)
    draw.text((tx, 130), sym_t,
              font=_font(sym_sz, bold=True), fill=TS_GREEN)

    x_t  = f"{int(multiplier)}x"
    x_sz = _fit(draw, x_t, lim, 200, 110)
    xy   = 130 + sym_sz + 4
    draw.text((tx, xy), x_t, font=_font(x_sz, bold=True), fill=WHITE)

    info_y = xy + x_sz + 16
    info   = f"VIP winners  ${entry} ➜ ${ath} MCAP"
    info_sz = _fit(draw, info, lim, 28, 20)
    draw.text((tx, info_y), info,
              font=_font(info_sz, bold=True), fill=DIM)

    cta = "📊 CHART  •  🆓 FREE ENTRY"
    draw.text((tx, info_y + info_sz + 16), cta,
              font=_font(28, bold=True), fill=TS_GREEN)

    _draw_username_badge(draw, tx, H - 130)
    canvas = _bottom_bar(canvas)
    return _save(canvas)


# ── AXIOM-style PnL brag card (clean dark, no template) ───────────────────────

def build_pnl_brag_card(symbol: str, invested: int, position: int) -> bytes:
    pnl_usd = position - invested
    pnl_pct = (pnl_usd / invested) * 100 if invested > 0 else 0

    bg = _gradient_bg()
    draw = ImageDraw.Draw(bg)

    # AXIOM brand top-right
    draw.text((W - 250, 40), "AXIOM",
              font=_font(48, bold=True), fill=WHITE)
    draw.text((W -  85, 64), "Pro", font=_font(24), fill=DIM)

    tx = 64
    draw.text((tx, 130), f"${symbol.upper()}",
              font=_font(56, bold=True), fill=WHITE)

    # Big green PnL banner
    pnl_str = (f"+${abs(pnl_usd) / 1000:,.2f}K"
               if abs(pnl_usd) >= 1000 else f"+${abs(pnl_usd):,}")
    pf  = _font(110, bold=True)
    pw  = _tw(draw, pnl_str, pf) + 60
    bx, by = tx, 210
    draw.rounded_rectangle([bx, by, bx + pw, by + 138],
                           radius=10, fill=TS_GREEN)
    draw.text((bx + 30, by + 10), pnl_str, font=pf, fill=(0, 0, 0, 255))

    fn, fb = _font(32), _font(32, bold=True)
    y0 = by + 180
    rows = [
        ("PNL",      f"+{pnl_pct:,.2f}%", TS_GREEN),
        ("Invested", (f"${invested / 1000:,.2f}K"
                     if invested >= 1000 else f"${invested:,}"), WHITE),
        ("Position", (f"${position / 1000:,.2f}K"
                     if position >= 1000 else f"${position:,}"), WHITE),
    ]
    for lbl, val, col in rows:
        draw.text((tx, y0), lbl, font=fn, fill=DIM)
        draw.text((tx + 280, y0), val, font=fb, fill=col)
        y0 += 50

    _draw_username_badge(draw, tx, H - 130)
    canvas = _bottom_bar(bg)
    return _save(canvas)
