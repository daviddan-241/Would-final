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
# also fold templates/* into the character pool for more variety
_TEMPLATE_CHARS = sorted([
    os.path.join("templates", f)
    for f in (os.listdir(TEMPLATES_DIR) if os.path.isdir(TEMPLATES_DIR) else [])
    if f.lower().endswith((".png", ".jpg", ".jpeg"))
    and not f.lower().startswith("manifest")
])
_ALL_CHARS = _CHARS + _TEMPLATE_CHARS
_recent_chars: list = []
_RECENT_WINDOW = 5  # never repeat any of the last 5 characters


def _pick_char_path() -> str:
    """Pick a character cutout, avoiding the last 5 picks."""
    global _recent_chars
    if not _ALL_CHARS:
        return ""
    pool = [f for f in _ALL_CHARS if f not in _recent_chars] or _ALL_CHARS
    pick = random.choice(pool)
    _recent_chars.append(pick)
    if len(_recent_chars) > min(_RECENT_WINDOW, max(1, len(_ALL_CHARS) - 1)):
        _recent_chars.pop(0)
    return os.path.join(ASSETS_DIR, pick)


# ── Scene palettes (vary background hue per post — never neon) ────────────────
_SCENES = [
    {"top": (12, 30, 22),  "bot": (4,  10, 8)},   # forest dusk
    {"top": (28, 22, 38),  "bot": (8,  8,  16)},  # purple night
    {"top": (18, 28, 40),  "bot": (6,  10, 18)},  # blue night
    {"top": (35, 28, 22),  "bot": (10, 8,  6)},   # warm dusk
    {"top": (16, 26, 30),  "bot": (4,  8,  12)},  # teal night
    {"top": (22, 22, 28),  "bot": (6,  6,  10)},  # neutral charcoal
    {"top": (10, 18, 30),  "bot": (2,  4,  10)},  # midnight blue
    {"top": (38, 16, 26),  "bot": (12, 4,  10)},  # crimson dusk
    {"top": (14, 32, 30),  "bot": (4,  10, 12)},  # emerald deep
    {"top": (24, 18, 34),  "bot": (8,  4,  14)},  # indigo
    {"top": (30, 30, 18),  "bot": (10, 10, 4)},   # olive nightlight
    {"top": (8,  20, 26),  "bot": (2,  6,  10)},  # ocean
]
_recent_scenes: list = []


def _pick_scene() -> dict:
    global _recent_scenes
    win = max(1, min(4, len(_SCENES) - 1))
    pool = [i for i in range(len(_SCENES)) if i not in _recent_scenes] \
           or list(range(len(_SCENES)))
    idx = random.choice(pool)
    _recent_scenes.append(idx)
    if len(_recent_scenes) > win:
        _recent_scenes.pop(0)
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


# ── Initial CALL card  (3 distinct styles, rotated) ───────────────────────────

_recent_call_styles: list = []

def _pick_style(n: int, recent: list, window: int = 2) -> int:
    pool = [i for i in range(n) if i not in recent] or list(range(n))
    pick = random.choice(pool)
    recent.append(pick)
    if len(recent) > min(window, max(1, n - 1)):
        recent.pop(0)
    return pick


def _stat_pill(draw, x, y, label, value, label_col=DIM, val_col=WHITE,
               fn=None, fb=None):
    fn = fn or _font(28)
    fb = fb or _font(28, bold=True)
    draw.text((x, y), label, font=fn, fill=label_col)
    draw.text((x + _tw(draw, label, fn), y), value, font=fb, fill=val_col)


def _draw_chain_chip(draw, x, y, chain_t, fill=(50, 60, 220, 255)):
    cf = _font(24, bold=True)
    cw = _tw(draw, chain_t, cf) + 24
    draw.rounded_rectangle([x, y, x + cw, y + 36], radius=8, fill=fill)
    draw.text((x + 12, y + 5), chain_t, font=cf, fill=WHITE)
    return cw


def _chain_color(chain: str):
    return {
        "SOL":      (153, 69, 255, 255),
        "SOLANA":   (153, 69, 255, 255),
        "ETH":      (114, 137, 218, 255),
        "ETHEREUM": (114, 137, 218, 255),
        "BSC":      (243, 186, 47, 255),
        "BNB":      (243, 186, 47, 255),
        "BASE":     (0, 82, 255, 255),
    }.get(chain.upper(), (50, 60, 220, 255))


# ─── Style A — TokenScan green (anchored left) ───────────────────────────────
def _call_style_a(symbol, mcap_str, liq_str, vol_str, chain):
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)
    tx, lim = 56, int(W * 0.55) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, lim, 84, 44)
    draw.text((tx, 138), sym_t, font=_font(sym_sz, bold=True), fill=TS_GREEN)

    label_y = 138 + sym_sz + 14
    draw.text((tx, label_y), "NEW CALL", font=_font(46, bold=True), fill=WHITE)

    rows = [("MC:   ", mcap_str), ("Liq:  ", liq_str), ("Vol:  ", vol_str)]
    y = label_y + 70
    for lbl, val in rows:
        _stat_pill(draw, tx, y, lbl, val, fn=_font(30), fb=_font(30, bold=True))
        y += 44

    _draw_chain_chip(draw, tx, y + 8, chain.upper(), fill=_chain_color(chain))
    _draw_username_badge(draw, tx, H - 130)
    return _bottom_bar(canvas)


# ─── Style B — Centered Hero (massive ticker, ribbon header, side panel) ─────
def _call_style_b(symbol, mcap_str, liq_str, vol_str, chain):
    canvas = _base_canvas()
    draw   = ImageDraw.Draw(canvas)

    # top ribbon
    chip_col = _chain_color(chain)
    draw.rectangle([0, 0, W, 70], fill=(0, 0, 0, 220))
    draw.rectangle([0, 64, W, 70], fill=chip_col)
    rib = f"DESK ALERT  ·  {chain.upper()} CHAIN  ·  EARLY ENTRY"
    rf = _font(24, bold=True)
    draw.text(((W - _tw(draw, rib, rf)) // 2, 22), rib, font=rf, fill=WHITE)

    # giant centered symbol
    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, int(W * 0.78), 168, 90)
    sym_w  = _tw(draw, sym_t, _font(sym_sz, bold=True))
    sx = (W - sym_w) // 2
    draw.text((sx, 130), sym_t,
              font=_font(sym_sz, bold=True), fill=TS_GREEN)

    # subtitle
    sub = "LIVE CALL  •  desk verified"
    sf  = _font(28, bold=True)
    sw  = _tw(draw, sub, sf)
    draw.text(((W - sw) // 2, 130 + sym_sz + 14), sub, font=sf, fill=WHITE)

    # rounded stat panel (centered, full width)
    pn_y = 130 + sym_sz + 80
    pn_h = 180
    pad  = 60
    draw.rounded_rectangle([pad, pn_y, W - pad, pn_y + pn_h],
                           radius=20, fill=(0, 0, 0, 180),
                           outline=(60, 70, 80, 220), width=2)

    cells = [("MARKET CAP", mcap_str),
             ("LIQUIDITY",  liq_str),
             ("24H VOL",    vol_str)]
    cw = (W - pad * 2) // 3
    for i, (lbl, val) in enumerate(cells):
        cx = pad + cw * i
        lf = _font(22, bold=True)
        vf = _font(40, bold=True)
        lw = _tw(draw, lbl, lf)
        vw = _tw(draw, val, vf)
        draw.text((cx + (cw - lw) // 2, pn_y + 28), lbl, font=lf, fill=DIM)
        draw.text((cx + (cw - vw) // 2, pn_y + 70), val, font=vf, fill=TS_GREEN)
        if i < 2:
            draw.line([(cx + cw, pn_y + 30), (cx + cw, pn_y + pn_h - 30)],
                      fill=(70, 80, 90, 200), width=2)

    # CTA strip
    cta = "🔐  EARLY ACCESS LIVE INSIDE THE VIP  ·  alpha_x_calls"
    cf  = _font(24, bold=True)
    cw2 = _tw(draw, cta, cf)
    draw.rounded_rectangle([(W - cw2) // 2 - 24, pn_y + pn_h + 28,
                            (W + cw2) // 2 + 24, pn_y + pn_h + 28 + 50],
                           radius=14, fill=TS_GREEN_SOFT)
    draw.text(((W - cw2) // 2, pn_y + pn_h + 40), cta, font=cf,
              fill=(0, 0, 0, 255))

    return _bottom_bar(canvas)


# ─── Style C — Trade Ticket (split panel + chart line) ───────────────────────
def _call_style_c(symbol, mcap_str, liq_str, vol_str, chain):
    canvas = _base_canvas(use_char=False)
    draw   = ImageDraw.Draw(canvas)

    # split: left dossier panel, right ticker hero
    panel_w = 560
    draw.rectangle([0, 0, panel_w, H], fill=(8, 12, 18, 230))

    _draw_tokenscan_logo(draw, 36, 36)

    draw.text((36, 110), "DEAL TICKET",
              font=_font(28, bold=True), fill=DIM)

    sym_t  = f"${symbol.upper()}"
    sym_sz = _fit(draw, sym_t, panel_w - 72, 78, 38)
    draw.text((36, 150), sym_t,
              font=_font(sym_sz, bold=True), fill=TS_GREEN)

    # data rows
    rows = [
        ("CHAIN",       chain.upper()),
        ("MARKET CAP",  mcap_str),
        ("LIQUIDITY",   liq_str),
        ("24H VOLUME",  vol_str),
        ("STATUS",      "DESK ENTRY  ✓"),
    ]
    y = 150 + sym_sz + 40
    for lbl, val in rows:
        draw.text((36, y), lbl, font=_font(20, bold=True), fill=DIM)
        draw.text((36, y + 24), val,
                  font=_font(30, bold=True), fill=WHITE)
        y += 70

    _draw_username_badge(draw, 36, H - 130)

    # right side — big symbol & "stylised chart line" silhouette
    rng = random.Random(sum(ord(c) for c in symbol))
    pts = []
    base_y = int(H * 0.55)
    span_x = W - panel_w - 80
    n = 60
    val = 0
    for i in range(n):
        val += rng.uniform(-0.6, 1.0)
        pts.append((panel_w + 60 + int(span_x * i / (n - 1)),
                    int(base_y - val * 18)))
    # shaded fill under line
    poly = [(panel_w + 60, H - 70)] + pts + [(W - 20, H - 70)]
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon(poly, fill=(32, 224, 144, 50))
    canvas = Image.alpha_composite(canvas, overlay)
    draw   = ImageDraw.Draw(canvas)
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=TS_GREEN, width=4)

    # giant right-side symbol watermark
    sym_big = _font(220, bold=True)
    sw = _tw(draw, sym_t, sym_big)
    draw.text((panel_w + 60 + (W - panel_w - 60 - sw) // 2, 60),
              sym_t, font=sym_big, fill=(255, 255, 255, 30))

    # tag pill bottom-right
    tag = "EARLY  ·  desk verified"
    tf = _font(22, bold=True)
    tw = _tw(draw, tag, tf) + 28
    draw.rounded_rectangle([W - tw - 36, H - 130, W - 36, H - 130 + 44],
                           radius=12, fill=TS_GREEN_SOFT)
    draw.text((W - tw - 22, H - 130 + 10), tag, font=tf,
              fill=(0, 0, 0, 255))

    return _bottom_bar(canvas)


def build_call_card(symbol: str, mcap_str: str, liq_str: str,
                    vol_str: str, chain: str = "SOL",
                    username: str = CHANNEL_TAG) -> bytes:
    """Pick one of 3 distinct visual styles, never repeating recently."""
    styles = [_call_style_a, _call_style_b, _call_style_c]
    idx    = _pick_style(len(styles), _recent_call_styles, window=2)
    canvas = styles[idx](symbol, mcap_str, liq_str, vol_str, chain)
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


# ── FOREX card (2 styles, rotated) ────────────────────────────────────────────

_recent_forex_styles: list = []
_recent_stock_styles: list = []


def _trade_panel(canvas, draw, kind_label, asset, direction, timeframe,
                 entry, tp1, tp2, sl, rr, sub=None):
    """Style A: anchored-left, dark base, character on right (existing)."""
    tx, lim = 56, int(W * 0.58) - 56
    _draw_tokenscan_logo(draw, tx, 40)

    is_long = direction.upper() in ("LONG", "BUY")
    dir_col = (0, 200, 110, 255) if is_long else (235, 70, 70, 255)

    hf  = _font(28, bold=True)
    hw  = _tw(draw, kind_label, hf) + 28
    draw.rounded_rectangle([tx, 100, tx + hw, 100 + 44],
                           radius=8, fill=dir_col)
    draw.text((tx + 14, 110), kind_label, font=hf, fill=(0, 0, 0, 255))

    a_sz = _fit(draw, asset, lim, 76, 38)
    draw.text((tx, 156), asset,
              font=_font(a_sz, bold=True), fill=WHITE)
    sub_y = 156 + a_sz + 4
    if sub:
        draw.text((tx, sub_y), sub, font=_font(24), fill=DIM)
        sub_y += 30

    dy = sub_y + 6
    df = _font(34, bold=True)
    dw = _tw(draw, direction.upper(), df) + 32
    draw.rounded_rectangle([tx, dy, tx + dw, dy + 50], radius=10, fill=dir_col)
    draw.text((tx + 14, dy + 8), direction.upper(), font=df, fill=(0, 0, 0, 255))
    draw.text((tx + dw + 14, dy + 12), timeframe, font=_font(26), fill=DIM)

    fn, fb = _font(26), _font(26, bold=True)
    grn, red = (0, 220, 120, 255), (240, 80, 80, 255)
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
    return _bottom_bar(canvas)


def _trade_ticket(kind_label, asset, direction, timeframe, entry, tp1, tp2,
                  sl, rr, sub=None):
    """Style B: terminal/Bloomberg ticket — full bleed grid, dual columns."""
    canvas = _base_canvas(use_char=False)
    draw   = ImageDraw.Draw(canvas)

    is_long = direction.upper() in ("LONG", "BUY")
    dir_col = (0, 220, 130, 255) if is_long else (240, 80, 80, 255)

    # top ribbon
    draw.rectangle([0, 0, W, 80], fill=(8, 12, 18, 230))
    draw.rectangle([0, 76, W, 80], fill=dir_col)
    rib = f"{kind_label}  ·  {direction.upper()}  ·  {timeframe}"
    rf  = _font(28, bold=True)
    draw.text((40, 26), rib, font=rf, fill=WHITE)
    # right side desk tag
    tag = "ALPHA · X · DESK"
    tf  = _font(22, bold=True)
    tw  = _tw(draw, tag, tf)
    draw.text((W - tw - 40, 30), tag, font=tf, fill=DIM)

    # giant asset name centred
    asset_sz = _fit(draw, asset, int(W * 0.85), 150, 80)
    aw = _tw(draw, asset, _font(asset_sz, bold=True))
    draw.text(((W - aw) // 2, 110), asset,
              font=_font(asset_sz, bold=True), fill=WHITE)
    if sub:
        sf = _font(28)
        sw = _tw(draw, sub, sf)
        draw.text(((W - sw) // 2, 110 + asset_sz + 8), sub, font=sf, fill=DIM)

    # 2x3 grid panel
    py = 110 + asset_sz + (60 if sub else 30)
    ph = 280
    px = 60
    pw = W - 120
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=20,
                           fill=(0, 0, 0, 200),
                           outline=(60, 70, 80, 220), width=2)
    cells = [
        ("ENTRY", entry, WHITE),
        ("R/R",   rr,    WHITE),
        ("TP 1",  tp1,   (0, 220, 130, 255)),
        ("TP 2",  tp2,   (0, 220, 130, 255)),
        ("SL",    sl,    (240, 80, 80, 255)),
        ("BIAS",  direction.upper(), dir_col),
    ]
    cw = pw // 3
    rh = ph // 2
    lf = _font(20, bold=True)
    vf = _font(38, bold=True)
    for i, (lbl, val, col) in enumerate(cells):
        cx = px + cw * (i % 3)
        cy = py + rh * (i // 3)
        lw = _tw(draw, lbl, lf)
        vw = _tw(draw, val, vf)
        draw.text((cx + (cw - lw) // 2, cy + 24), lbl, font=lf, fill=DIM)
        draw.text((cx + (cw - vw) // 2, cy + 60), val, font=vf, fill=col)
        # dividers
        if i % 3 != 2:
            draw.line([(cx + cw, cy + 24), (cx + cw, cy + rh - 24)],
                      fill=(60, 70, 80, 200), width=2)
        if i < 3:
            draw.line([(cx + 24, cy + rh), (cx + cw - 24, cy + rh)],
                      fill=(60, 70, 80, 200), width=2)

    # footer CTA
    cta = "🔐  Live management inside VIP  ·  alpha_x_calls"
    cf  = _font(24, bold=True)
    cw2 = _tw(draw, cta, cf)
    draw.rounded_rectangle([(W - cw2) // 2 - 24, py + ph + 30,
                            (W + cw2) // 2 + 24, py + ph + 30 + 50],
                           radius=14, fill=TS_GREEN_SOFT)
    draw.text(((W - cw2) // 2, py + ph + 42), cta, font=cf,
              fill=(0, 0, 0, 255))
    return _bottom_bar(canvas)


def build_forex_card(pair: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str, username: str = CHANNEL_TAG) -> bytes:
    kind = "FX SIGNAL" if "/" in pair else "TRADE SIGNAL"
    idx = _pick_style(2, _recent_forex_styles, window=1)
    if idx == 0:
        canvas = _base_canvas()
        draw   = ImageDraw.Draw(canvas)
        canvas = _trade_panel(canvas, draw, kind, pair.upper(), direction,
                              timeframe, entry, tp1, tp2, sl, rr)
    else:
        canvas = _trade_ticket(kind, pair.upper(), direction, timeframe,
                               entry, tp1, tp2, sl, rr)
    return _save(canvas)


# ── STOCK card ────────────────────────────────────────────────────────────────

def build_stock_card(ticker: str, name: str, direction: str, entry: str,
                     tp1: str, tp2: str, sl: str, timeframe: str,
                     rr: str) -> bytes:
    idx = _pick_style(2, _recent_stock_styles, window=1)
    if idx == 0:
        canvas = _base_canvas()
        draw   = ImageDraw.Draw(canvas)
        canvas = _trade_panel(canvas, draw, "STOCK SIGNAL", ticker.upper(),
                              direction, timeframe, entry, tp1, tp2, sl, rr,
                              sub=name)
    else:
        canvas = _trade_ticket("EQUITY DESK", ticker.upper(), direction,
                               timeframe, entry, tp1, tp2, sl, rr, sub=name)
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


# ── PnL brag cards — 3 distinct styles with no-repeat rotation ────────────────

_recent_pnl_styles: list = []

def _pick_pnl_style(num_styles: int) -> int:
    global _recent_pnl_styles
    pool = [i for i in range(num_styles) if i not in _recent_pnl_styles] \
           or list(range(num_styles))
    pick = random.choice(pool)
    _recent_pnl_styles.append(pick)
    if len(_recent_pnl_styles) > max(1, num_styles - 1):
        _recent_pnl_styles.pop(0)
    return pick


def _fmt_money(v: float) -> str:
    if abs(v) >= 1000:
        return f"${v/1000:,.2f}K"
    return f"${int(v):,}"


def _fmt_signed(v: float) -> str:
    sign = "+" if v >= 0 else "-"
    return sign + _fmt_money(abs(v))


# Style A — AXIOM Pro (original clean dark)
def _pnl_axiom(symbol: str, invested: int, position: int) -> bytes:
    pnl_usd = position - invested
    pnl_pct = (pnl_usd / invested) * 100 if invested > 0 else 0

    bg = _gradient_bg()
    draw = ImageDraw.Draw(bg)
    draw.text((W - 260, 40), "AXIOM", font=_font(48, bold=True), fill=WHITE)
    draw.text((W -  85, 64), "Pro",   font=_font(24), fill=DIM)

    tx = 64
    draw.text((tx, 130), f"${symbol.upper()}",
              font=_font(56, bold=True), fill=WHITE)

    pnl_str = _fmt_signed(pnl_usd)
    pf  = _font(108, bold=True)
    pw  = _tw(draw, pnl_str, pf) + 60
    bx, by = tx, 210
    col = TS_GREEN if pnl_usd >= 0 else (235, 70, 70, 255)
    draw.rounded_rectangle([bx, by, bx + pw, by + 138], radius=10, fill=col)
    draw.text((bx + 30, by + 10), pnl_str, font=pf, fill=(0, 0, 0, 255))

    fn, fb = _font(32), _font(32, bold=True)
    y0 = by + 180
    for lbl, val, c in [
        ("PNL",      f"{'+' if pnl_pct>=0 else ''}{pnl_pct:,.2f}%", col),
        ("Invested", _fmt_money(invested), WHITE),
        ("Position", _fmt_money(position), WHITE),
    ]:
        draw.text((tx, y0), lbl, font=fn, fill=DIM)
        draw.text((tx + 280, y0), val, font=fb, fill=c)
        y0 += 50

    _draw_username_badge(draw, tx, H - 130)
    return _save(_bottom_bar(bg))


# Style B — Phanes-style PnL ticket (centred huge multiplier + percent banner)
def _pnl_phanes(symbol: str, invested: int, position: int) -> bytes:
    pnl_usd = position - invested
    pnl_pct = (pnl_usd / invested) * 100 if invested > 0 else 0
    mult    = position / invested if invested else 1
    is_win  = pnl_usd >= 0

    bg = _gradient_bg({"top": (8, 14, 22), "bot": (2, 4, 8)})
    draw = ImageDraw.Draw(bg)

    # Top brand bar
    draw.rectangle([0, 0, W, 64], fill=(0, 0, 0, 220))
    draw.text((34, 16), "Phanes  •  Live PnL",
              font=_font(28, bold=True), fill=TS_GREEN)
    draw.text((W - 220, 18), "alpha_x_calls",
              font=_font(24, bold=True), fill=WHITE)

    # Symbol
    sym_t = f"${symbol.upper()}"
    sf = _font(56, bold=True)
    sw = _tw(draw, sym_t, sf)
    draw.text(((W - sw) // 2, 100), sym_t, font=sf, fill=WHITE)

    # Centred huge multiplier
    mult_t = f"{mult:.2f}x" if mult < 100 else f"{int(mult)}x"
    mf = _font(220, bold=True)
    mw = _tw(draw, mult_t, mf)
    col = TS_GREEN if is_win else (235, 70, 70, 255)
    draw.text(((W - mw) // 2, 180), mult_t, font=mf, fill=col)

    # Centred percent banner
    pct_t = f"{'+' if is_win else ''}{pnl_pct:,.2f}%"
    pf = _font(64, bold=True)
    pw = _tw(draw, pct_t, pf) + 80
    px = (W - pw) // 2
    py = 420
    draw.rounded_rectangle([px, py, px + pw, py + 84], radius=14, fill=col)
    draw.text((px + 40, py + 8), pct_t, font=pf, fill=(0, 0, 0, 255))

    # Bottom row: invested → position
    rf = _font(30)
    rfb = _font(30, bold=True)
    line = f"{_fmt_money(invested)}  ➜  {_fmt_money(position)}   "
    diff = f"  ({_fmt_signed(pnl_usd)})"
    lw = _tw(draw, line, rf) + _tw(draw, diff, rfb)
    lx = (W - lw) // 2
    ly = py + 110
    draw.text((lx, ly), line, font=rf, fill=DIM)
    draw.text((lx + _tw(draw, line, rf), ly), diff, font=rfb, fill=col)

    return _save(_bottom_bar(bg))


# Style C — Trojan-style trade receipt (top-aligned data table)
def _pnl_trojan(symbol: str, invested: int, position: int) -> bytes:
    pnl_usd = position - invested
    pnl_pct = (pnl_usd / invested) * 100 if invested > 0 else 0
    is_win  = pnl_usd >= 0
    col = TS_GREEN if is_win else (235, 70, 70, 255)

    canvas = _base_canvas(use_char=True)
    draw   = ImageDraw.Draw(canvas)

    tx = 56
    # header pill
    hdr_t = "TROJAN  •  TRADE CLOSED"
    hf = _font(24, bold=True)
    hw = _tw(draw, hdr_t, hf) + 28
    draw.rounded_rectangle([tx, 40, tx + hw, 40 + 40], radius=8,
                           fill=(20, 24, 30, 235), outline=col, width=2)
    draw.text((tx + 14, 47), hdr_t, font=hf, fill=col)

    # symbol
    sym_t = f"${symbol.upper()}"
    draw.text((tx, 100), sym_t, font=_font(64, bold=True), fill=WHITE)

    # Big PnL
    pnl_t = _fmt_signed(pnl_usd)
    pf = _font(96, bold=True)
    draw.text((tx, 178), pnl_t, font=pf, fill=col)

    # subline
    sub = f"{'+' if is_win else ''}{pnl_pct:,.2f}% realised"
    draw.text((tx, 290), sub, font=_font(32, bold=True), fill=col)

    # rows
    fn, fb = _font(28), _font(28, bold=True)
    y0 = 360
    for lbl, val, c in [
        ("Invested", _fmt_money(invested),   WHITE),
        ("Closed at", _fmt_money(position),  WHITE),
        ("Net P&L",   _fmt_signed(pnl_usd),  col),
    ]:
        draw.text((tx, y0), lbl, font=fn, fill=DIM)
        draw.text((tx + 240, y0), val, font=fb, fill=c)
        y0 += 44

    _draw_username_badge(draw, tx, H - 130)
    return _save(_bottom_bar(canvas))


_PNL_STYLES = [_pnl_axiom, _pnl_phanes, _pnl_trojan]


def build_pnl_brag_card(symbol: str, invested: int, position: int) -> bytes:
    style_idx = _pick_pnl_style(len(_PNL_STYLES))
    return _PNL_STYLES[style_idx](symbol, invested, position)
