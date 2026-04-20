import io
import math
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1280, 640

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SWAMP_BG   = os.path.join(ASSETS_DIR, "swamp_bg.png")
PEPE_VARIANTS = [
    os.path.join(ASSETS_DIR, "pepe_sunglasses.png"),
    os.path.join(ASSETS_DIR, "pepe_suit.png"),
    os.path.join(ASSETS_DIR, "pepe_moon.png"),
    os.path.join(ASSETS_DIR, "pepe_happy.png"),
]

COLOR_THEMES = [
    {"bg": (4, 14, 8),   "accent": (0, 255, 80),   "glow": (0, 140, 30),   "border": (0, 255, 85),   "label": (100, 210, 130), "sub": (70, 145, 100),  "name": "matrix"},
    {"bg": (8, 10, 28),  "accent": (80, 130, 255),  "glow": (30, 60, 200),  "border": (60, 100, 255), "label": (120, 160, 255), "sub": (70, 100, 180),  "name": "electric"},
    {"bg": (20, 6, 28),  "accent": (200, 80, 255),  "glow": (120, 0, 200),  "border": (180, 60, 255), "label": (180, 120, 240), "sub": (120, 70, 170),  "name": "neon_purple"},
    {"bg": (28, 10, 4),  "accent": (255, 140, 0),   "glow": (200, 80, 0),   "border": (255, 160, 30), "label": (255, 190, 80),  "sub": (180, 120, 40),  "name": "fire"},
    {"bg": (6, 22, 28),  "accent": (0, 220, 255),   "glow": (0, 120, 200),  "border": (0, 200, 240),  "label": (80, 220, 240),  "sub": (50, 150, 180),  "name": "cyber"},
    {"bg": (28, 4, 10),  "accent": (255, 60, 100),  "glow": (180, 0, 50),   "border": (255, 40, 80),  "label": (255, 100, 130), "sub": (180, 50, 80),   "name": "blood"},
    {"bg": (18, 16, 4),  "accent": (230, 220, 0),   "glow": (160, 150, 0),  "border": (240, 230, 20), "label": (240, 220, 80),  "sub": (170, 155, 40),  "name": "gold"},
    {"bg": (4, 20, 24),  "accent": (0, 255, 200),   "glow": (0, 150, 120),  "border": (0, 240, 190),  "label": (80, 240, 200),  "sub": (50, 170, 140),  "name": "teal"},
    {"bg": (24, 8, 20),  "accent": (255, 100, 200), "glow": (180, 20, 140), "border": (255, 80, 200), "label": (255, 140, 210), "sub": (180, 80, 150),  "name": "pink"},
    {"bg": (8, 24, 16),  "accent": (60, 255, 140),  "glow": (20, 180, 80),  "border": (40, 240, 120), "label": (100, 255, 160), "sub": (60, 175, 100),  "name": "mint"},
    {"bg": (10, 10, 10), "accent": (255, 255, 255),  "glow": (150, 150, 150),"border": (220, 220, 220),"label": (200, 200, 200), "sub": (130, 130, 130), "name": "chrome"},
    {"bg": (28, 18, 0),  "accent": (255, 180, 0),   "glow": (200, 110, 0),  "border": (255, 200, 20), "label": (255, 210, 100), "sub": (190, 140, 20),  "name": "amber"},
    {"bg": (6, 6, 24),   "accent": (120, 80, 255),  "glow": (60, 20, 200),  "border": (100, 60, 240), "label": (150, 110, 255), "sub": (90, 60, 180),   "name": "indigo"},
    {"bg": (0, 20, 20),  "accent": (0, 200, 200),   "glow": (0, 100, 100),  "border": (0, 180, 180),  "label": (60, 200, 200),  "sub": (30, 140, 140),  "name": "aqua"},
    {"bg": (26, 6, 6),   "accent": (255, 80, 20),   "glow": (200, 30, 0),   "border": (255, 100, 40), "label": (255, 130, 80),  "sub": (190, 80, 30),   "name": "lava"},
]

BACKGROUND_STYLES = [
    "gradient_radial",
    "gradient_diagonal",
    "gradient_horizontal",
    "gradient_corner",
    "noise_field",
    "grid_lines",
    "hex_pattern",
    "circuit_lines",
    "particle_dots",
    "wave_lines",
    "star_field",
    "scan_lines",
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    import subprocess
    paths = []
    try:
        style = "Bold" if bold else "Regular"
        r = subprocess.run(["fc-list", f":style={style}", "--format=%{file}\n"],
                           capture_output=True, text=True, timeout=3)
        for line in r.stdout.strip().split("\n"):
            fp = line.strip()
            if fp and os.path.exists(fp) and ".ttf" in fp.lower():
                paths.append(fp)
    except Exception:
        pass
    fallbacks = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSans.ttf"]
    )
    for fp in paths + fallbacks:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def _fmt(v: float) -> str:
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _make_gradient_bg(theme: dict, style: str, seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H), theme["bg"])
    pixels = img.load()
    bg = theme["bg"]
    acc = theme["accent"]

    if style == "gradient_radial":
        cx = rng.randint(W // 4, 3 * W // 4)
        cy = rng.randint(H // 4, 3 * H // 4)
        max_r = math.sqrt(W**2 + H**2) * 0.7
        for y in range(H):
            for x in range(W):
                d = math.sqrt((x - cx)**2 + (y - cy)**2)
                t = min(1.0, d / max_r)
                r = int(bg[0] * t + acc[0] * (1 - t) * 0.25)
                g = int(bg[1] * t + acc[1] * (1 - t) * 0.25)
                b = int(bg[2] * t + acc[2] * (1 - t) * 0.25)
                pixels[x, y] = (
                    min(255, max(0, r)),
                    min(255, max(0, g)),
                    min(255, max(0, b))
                )

    elif style == "gradient_diagonal":
        for y in range(H):
            for x in range(W):
                t = (x / W + y / H) / 2
                t = t ** 1.5
                r = int(bg[0] + (acc[0] - bg[0]) * (1 - t) * 0.3)
                g = int(bg[1] + (acc[1] - bg[1]) * (1 - t) * 0.3)
                b = int(bg[2] + (acc[2] - bg[2]) * (1 - t) * 0.3)
                pixels[x, y] = (
                    min(255, max(0, r)),
                    min(255, max(0, g)),
                    min(255, max(0, b))
                )

    elif style == "gradient_horizontal":
        for x in range(W):
            t = (x / W) ** 1.2
            r = int(bg[0] * t + acc[0] * (1 - t) * 0.2)
            g = int(bg[1] * t + acc[1] * (1 - t) * 0.2)
            b = int(bg[2] * t + acc[2] * (1 - t) * 0.2)
            col = (min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b)))
            for y in range(H):
                pixels[x, y] = col

    elif style == "gradient_corner":
        corner_x = 0 if rng.random() < 0.5 else W
        corner_y = 0 if rng.random() < 0.5 else H
        max_d = math.sqrt(W**2 + H**2)
        for y in range(H):
            for x in range(W):
                d = math.sqrt((x - corner_x)**2 + (y - corner_y)**2)
                t = min(1.0, d / (max_d * 0.8))
                r = int(acc[0] * (1 - t) * 0.35 + bg[0] * t)
                g = int(acc[1] * (1 - t) * 0.35 + bg[1] * t)
                b = int(acc[2] * (1 - t) * 0.35 + bg[2] * t)
                pixels[x, y] = (
                    min(255, max(0, r)),
                    min(255, max(0, g)),
                    min(255, max(0, b))
                )

    draw = ImageDraw.Draw(img, "RGBA")

    if style == "grid_lines":
        step = rng.randint(40, 90)
        line_col = tuple(min(255, c + 18) for c in bg) + (80,)
        for x in range(0, W, step):
            draw.line([(x, 0), (x, H)], fill=line_col, width=1)
        for y in range(0, H, step):
            draw.line([(0, y), (W, y)], fill=line_col, width=1)

    elif style == "circuit_lines":
        line_col = tuple(min(255, c + 30) for c in bg) + (90,)
        for _ in range(rng.randint(8, 18)):
            x1 = rng.randint(0, W)
            y1 = rng.randint(0, H)
            for _ in range(rng.randint(3, 8)):
                direction = rng.choice(["h", "v"])
                length = rng.randint(40, 200)
                if direction == "h":
                    x2 = min(W, max(0, x1 + rng.choice([-1, 1]) * length))
                    draw.line([(x1, y1), (x2, y1)], fill=line_col, width=1)
                    x1 = x2
                else:
                    y2 = min(H, max(0, y1 + rng.choice([-1, 1]) * length))
                    draw.line([(x1, y1), (x1, y2)], fill=line_col, width=1)
                    y1 = y2
                draw.ellipse([x1 - 3, y1 - 3, x1 + 3, y1 + 3], fill=line_col)

    elif style == "particle_dots":
        for _ in range(rng.randint(60, 150)):
            x = rng.randint(0, W)
            y = rng.randint(0, H)
            r_dot = rng.randint(1, 4)
            alpha = rng.randint(40, 150)
            dot_col = (acc[0], acc[1], acc[2], alpha)
            draw.ellipse([x - r_dot, y - r_dot, x + r_dot, y + r_dot], fill=dot_col)

    elif style == "star_field":
        for _ in range(rng.randint(80, 200)):
            x = rng.randint(0, W)
            y = rng.randint(0, H)
            size = rng.randint(1, 3)
            alpha = rng.randint(50, 200)
            v = rng.randint(180, 255)
            draw.ellipse([x - size, y - size, x + size, y + size],
                         fill=(v, v, v, alpha))

    elif style == "scan_lines":
        for y in range(0, H, 4):
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, 40), width=1)

    elif style == "wave_lines":
        num_waves = rng.randint(5, 12)
        for i in range(num_waves):
            amp = rng.randint(20, 60)
            freq = rng.uniform(0.005, 0.02)
            phase = rng.uniform(0, math.pi * 2)
            base_y = int(H * (i + 1) / (num_waves + 1))
            alpha = rng.randint(25, 70)
            points = []
            for x in range(0, W, 4):
                y = int(base_y + amp * math.sin(freq * x + phase))
                points.append((x, y))
            if len(points) > 1:
                draw.line(points, fill=(acc[0], acc[1], acc[2], alpha), width=1)

    elif style == "noise_field":
        for _ in range(rng.randint(200, 500)):
            x = rng.randint(0, W)
            y = rng.randint(0, H)
            alpha = rng.randint(10, 50)
            draw.point((x, y), fill=(acc[0], acc[1], acc[2], alpha))

    elif style == "hex_pattern":
        hex_r = rng.randint(30, 60)
        col = tuple(min(255, c + 20) for c in bg) + (60,)
        for row in range(-1, H // hex_r + 2):
            for col_i in range(-1, W // hex_r + 2):
                cx_h = col_i * hex_r * 1.7
                cy_h = row * hex_r * 2 + (hex_r if col_i % 2 else 0)
                pts = []
                for angle in range(0, 360, 60):
                    rad = math.radians(angle)
                    pts.append((
                        int(cx_h + hex_r * 0.85 * math.cos(rad)),
                        int(cy_h + hex_r * 0.85 * math.sin(rad))
                    ))
                draw.polygon(pts, outline=col, fill=None)

    return img


def _load_bg_with_theme(theme: dict, style: str) -> Image.Image:
    seed = random.randint(0, 99999)
    try:
        if os.path.exists(SWAMP_BG) and random.random() < 0.35:
            bg = Image.open(SWAMP_BG).convert("RGB")
            bg = bg.resize((W, H), Image.LANCZOS)
            bg = ImageEnhance.Brightness(bg).enhance(0.5)
            overlay = Image.new("RGB", (W, H), theme["bg"])
            bg = Image.blend(bg, overlay, alpha=0.55)
            return bg
    except Exception:
        pass
    return _make_gradient_bg(theme, style, seed)


def _make_card_base(theme: dict, style: str) -> Image.Image:
    bg = _load_bg_with_theme(theme, style)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    for x in range(W):
        t = x / W
        if t < 0.05:
            a = 240
        elif t < 0.48:
            a = int(240 * (1 - (t - 0.05) / 0.43) ** 1.3)
        else:
            a = 0
        if a > 0:
            od.line([(x, 0), (x, H)], fill=(0, 0, 0, a))

    for x in range(int(W * 0.44), W):
        t = max(0.0, (x - W * 0.44) / (W * 0.56))
        a = int(180 * t ** 0.6)
        od.line([(x, 0), (x, H)], fill=(0, 0, 0, a))

    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    return bg


def _paste_pepe(img: Image.Image, pepe_path: str) -> Image.Image:
    if not os.path.exists(pepe_path):
        return img
    pepe = Image.open(pepe_path).convert("RGBA")
    target_h = int(H * 0.96)
    target_w = int(W * 0.46)
    pw, ph = pepe.size
    ratio = min(target_w / pw, target_h / ph)
    new_w = int(pw * ratio)
    new_h = int(ph * ratio)
    pepe = pepe.resize((new_w, new_h), Image.LANCZOS)

    hue_shift = random.random() < 0.4
    if hue_shift:
        r, g, b, a = pepe.split()
        channels = [r, g, b]
        random.shuffle(channels)
        channels.append(a)
        pepe = Image.merge("RGBA", channels)

    px = int(W * 0.01)
    py = H - new_h - 4
    canvas = img.convert("RGBA")
    canvas.paste(pepe, (px, py), pepe)
    return canvas.convert("RGB")


def _draw_border(img: Image.Image, theme: dict, style_idx: int) -> Image.Image:
    border = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    r = random.choice([16, 20, 28, 36])
    acc = theme["border"]

    border_styles = ["solid", "double", "glow_only", "dashed_corner"]
    bstyle = border_styles[style_idx % len(border_styles)]

    if bstyle in ("solid", "glow_only"):
        colors = [
            (acc[0], acc[1], acc[2], 220),
            (acc[0] // 2, acc[1] // 2, acc[2] // 2, 160),
            (acc[0] // 3, acc[1] // 3, acc[2] // 3, 90),
            (acc[0] // 4, acc[1] // 4, acc[2] // 4, 40),
        ]
        for i, col in enumerate(colors):
            m = i * 2
            bd.rounded_rectangle([m, m, W - 1 - m, H - 1 - m],
                                  radius=max(4, r - m),
                                  outline=col, width=2)
    elif bstyle == "double":
        bd.rounded_rectangle([2, 2, W - 3, H - 3], radius=r,
                              outline=(acc[0], acc[1], acc[2], 255), width=2)
        bd.rounded_rectangle([8, 8, W - 9, H - 9], radius=max(4, r - 6),
                              outline=(acc[0] // 2, acc[1] // 2, acc[2] // 2, 140), width=1)
    elif bstyle == "dashed_corner":
        corner_size = 60
        for corners in [
            [(2, 2), (corner_size, 2), (2, corner_size)],
            [(W - 2, 2), (W - corner_size, 2), (W - 2, corner_size)],
            [(2, H - 2), (corner_size, H - 2), (2, H - corner_size)],
            [(W - 2, H - 2), (W - corner_size, H - 2), (W - 2, H - corner_size)],
        ]:
            bd.line([corners[0], corners[1]], fill=(acc[0], acc[1], acc[2], 255), width=3)
            bd.line([corners[0], corners[2]], fill=(acc[0], acc[1], acc[2], 255), width=3)

    blurred = border.filter(ImageFilter.GaussianBlur(3))
    result = Image.alpha_composite(img.convert("RGBA"), blurred)
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sharp)
    if bstyle != "dashed_corner":
        sd.rounded_rectangle([3, 3, W - 4, H - 4], radius=r,
                              outline=(acc[0], acc[1], acc[2], 255), width=2)
    result = Image.alpha_composite(result, sharp)
    return result.convert("RGB")


def _glow_text(draw, pos, text, font, fill, glow_color, spread=8):
    x, y = pos
    for dx in range(-spread, spread + 1):
        for dy in range(-spread, spread + 1):
            d = math.sqrt(dx * dx + dy * dy)
            if d == 0 or d > spread:
                continue
            a = max(0.0, 1.0 - d / spread) ** 1.5
            gc = tuple(int(c * a) for c in glow_color)
            draw.text((x + dx, y + dy), text, fill=gc, font=font)
    draw.text((x + 3, y + 4), text, fill=(0, 0, 0, 110), font=font)
    draw.text((x, y), text, fill=fill, font=font)


def _shadow_text(draw, pos, text, font, fill):
    x, y = pos
    draw.text((x + 2, y + 3), text, fill=(0, 0, 0, 140), font=font)
    draw.text((x, y), text, fill=fill, font=font)


def _draw_coin_icon(draw, symbol: str, cx: int, cy: int, r: int, theme: dict):
    acc = theme["accent"]
    draw.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3],
                 fill=tuple(max(0, c - 80) for c in acc), outline=None)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 fill=theme["bg"], outline=acc, width=2)
    sym = symbol[:4].upper()
    f = _font(max(10, r - 8))
    bb = draw.textbbox((0, 0), sym, font=f)
    tw = bb[2] - bb[0]; th = bb[3] - bb[1]
    draw.text((cx - tw // 2, cy - th // 2), sym, fill=acc, font=f)


def _draw_sol_badge(draw, theme: dict):
    sx, sy, sr = W - 44, 34, 18
    draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                 fill=(30, 10, 100), outline=(80, 50, 200), width=2)
    f = _font(15)
    bb = draw.textbbox((0, 0), "◎", font=f)
    tw = bb[2] - bb[0]; th = bb[3] - bb[1]
    draw.text((sx - tw // 2, sy - th // 2), "◎", fill=(200, 185, 255), font=f)


def _draw_decorative_elements(draw, theme: dict, seed: int):
    rng = random.Random(seed)
    acc = theme["accent"]
    alpha = 60

    num_shapes = rng.randint(3, 8)
    for _ in range(num_shapes):
        shape_type = rng.choice(["circle", "line", "diamond"])
        x = rng.randint(int(W * 0.5), W - 20)
        y = rng.randint(20, H - 20)
        size = rng.randint(4, 20)

        if shape_type == "circle":
            draw.ellipse([x - size, y - size, x + size, y + size],
                         outline=(acc[0], acc[1], acc[2], alpha), width=1)
        elif shape_type == "line":
            length = rng.randint(30, 100)
            angle = rng.uniform(0, math.pi)
            x2 = int(x + length * math.cos(angle))
            y2 = int(y + length * math.sin(angle))
            draw.line([(x, y), (x2, y2)],
                      fill=(acc[0], acc[1], acc[2], alpha), width=1)
        elif shape_type == "diamond":
            pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
            draw.polygon(pts, outline=(acc[0], acc[1], acc[2], alpha))


def _build_card(token: dict, mode: str,
                gain_pct: float = 0,
                called_at: str = "",
                elapsed_str: str = "") -> bytes:

    card_seed = random.randint(0, 9999)
    theme = random.choice(COLOR_THEMES)
    bg_style = random.choice(BACKGROUND_STYLES)
    border_style_idx = random.randint(0, 3)

    img = _make_card_base(theme, bg_style)

    available = [p for p in PEPE_VARIANTS if os.path.exists(p)]
    if available:
        img = _paste_pepe(img, random.choice(available))

    img = _draw_border(img, theme, border_style_idx)

    draw = ImageDraw.Draw(img)
    _draw_decorative_elements(draw, theme, card_seed)

    symbol = token.get("symbol", "???").upper()
    mc     = token.get("market_cap", 0)
    liq    = token.get("liquidity_usd", 0)
    vol    = token.get("volume_24h", 0)
    ca     = token.get("address", "")
    short  = ca[:8] + "…" + ca[-4:] if len(ca) > 12 else ca

    _draw_coin_icon(draw, symbol, W // 2, 36, r=32, theme=theme)
    _draw_sol_badge(draw, theme)

    rx = int(W * 0.47)
    rw = W - rx - 50

    if mode == "call":
        name_sz = 110
        while name_sz > 32:
            if _tw(draw, symbol, _font(name_sz)) <= rw:
                break
            name_sz -= 5
        name_y = 60
        _glow_text(draw, (rx, name_y), symbol,
                   _font(name_sz), (255, 255, 255), theme["glow"], 5)

        y = name_y + name_sz + 20
        lf = _font(26)
        vf = _font(26, bold=False)
        gap = 44
        label_w = 85
        pairs = [
            ("MC:",  _fmt(mc)),
            ("Liq:", _fmt(liq)),
            ("Vol:", _fmt(vol)),
        ]
        for i, (label, val) in enumerate(pairs):
            _shadow_text(draw, (rx, y + i * gap), label, lf, theme["label"])
            _shadow_text(draw, (rx + label_w, y + i * gap), val, vf, (240, 255, 245))

        draw.text((rx, y + gap * 3 + 6), f"CA: {short}",
                  fill=theme["sub"], font=_font(17, bold=False))

        badge_x = rx
        badge_y = y + gap * 3 + 48

        badge_variants = [
            ("🟢  NEW CALL", theme["accent"]),
            ("🚀  EARLY ENTRY", (0, 180, 255)),
            ("💎  GEM FOUND", (200, 100, 255)),
            ("⚡  ALPHA PLAY", (255, 180, 0)),
        ]
        badge_text, badge_fill = random.choice(badge_variants)
        badge_f = _font(22)
        bw = _tw(draw, badge_text, badge_f) + 28
        bh = 40
        bg_col = tuple(max(0, c - 150) for c in badge_fill)
        draw.rounded_rectangle([badge_x, badge_y, badge_x + bw, badge_y + bh],
                                radius=10, fill=bg_col + (200,))
        draw.text((badge_x + 14, badge_y + 9), badge_text,
                  fill=(255, 255, 255), font=badge_f)

    else:
        name_sz = 110
        while name_sz > 32:
            if _tw(draw, symbol, _font(name_sz)) <= rw:
                break
            name_sz -= 5
        name_y = 52
        _glow_text(draw, (rx, name_y), symbol,
                   _font(name_sz), (255, 255, 255), theme["glow"], 5)

        sub_y = name_y + name_sz + 6
        _shadow_text(draw, (rx, sub_y), f"called at {called_at}",
                     _font(28, bold=False), theme["label"])

        if gain_pct >= 100:
            gain_str = f"{gain_pct / 100 + 1:.1f}X"
        else:
            gain_str = f"{gain_pct:.0f}%"

        g_sz = 200
        while g_sz > 60:
            if _tw(draw, gain_str, _font(g_sz)) <= rw:
                break
            g_sz -= 8

        gy = sub_y + 46
        _glow_text(draw, (rx, gy), gain_str,
                   _font(g_sz), theme["accent"], theme["glow"], 12)

        info_y = gy + g_sz + 18
        info_f  = _font(26)
        time_f  = _font(24, bold=False)
        _shadow_text(draw, (rx, info_y),      "👤  Alpha Circle",               info_f, (215, 245, 225))
        _shadow_text(draw, (rx, info_y + 42), f"🕐  {elapsed_str or called_at}", time_f, theme["label"])

        intel_variants = [
            "🔐  private intel group",
            "⚡  intel group",
            "🔥  alpha intel",
            "💎  VIP intel group",
        ]
        _shadow_text(draw, (rx, info_y + 88),
                     random.choice(intel_variants),
                     _font(22, bold=False), theme["sub"])

    draw.line([(18, H - 50), (W - 18, H - 50)], fill=tuple(max(0, c - 150) for c in theme["accent"]), width=1)
    bf = _font(16, bold=False)
    draw.text((28,      H - 38), "t.me/AlphaCirclle",  fill=theme["sub"], font=bf)
    draw.text((W - 220, H - 38), "@AlphaCirclle",       fill=theme["sub"], font=bf)

    quality = random.choice([85, 90, 92, 95])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def generate_initial_call_image(token: dict) -> bytes:
    return _build_card(token, mode="call")


def generate_kol_card(token: dict, gain_pct: float,
                      entry_mc: float, called_at: str,
                      elapsed_str: str = "") -> bytes:
    return _build_card(token, mode="update",
                       gain_pct=gain_pct, called_at=called_at,
                       elapsed_str=elapsed_str)
