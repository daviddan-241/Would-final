import io
import random
import time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as ticker

# Exact DEX Screener palette
DARK_BG    = "#0D1117"
PANEL_BG   = "#131722"
GRID       = "#1C2B3A"
UP         = "#26A69A"   # teal green
DOWN       = "#EF5350"   # red
TEXT_DIM   = "#787B86"
TEXT_MAIN  = "#D1D4DC"
TEXT_TITLE = "#ECEFF1"
PRICE_LINE = "#EF5350"   # red dashed current price


def generate_chart_image(token: dict, bars: list) -> bytes:
    if len(bars) < 5:
        bars = _make_bars(token, 60)
    bars = bars[-80:]
    return _dex_chart(token, bars)


def _dex_chart(token: dict, bars: list) -> bytes:
    n      = len(bars)
    xs     = list(range(n))
    opens  = [float(b["o"]) for b in bars]
    highs  = [float(b["h"]) for b in bars]
    lows   = [float(b["l"]) for b in bars]
    closes = [float(b["c"]) for b in bars]
    vols   = [float(b.get("v", 0)) for b in bars]

    fig = plt.figure(figsize=(11, 6.5), facecolor=DARK_BG)
    ax  = fig.add_axes([0.0, 0.20, 1.0, 0.72], facecolor=DARK_BG)
    axv = fig.add_axes([0.0, 0.04, 1.0, 0.14], facecolor=DARK_BG, sharex=ax)

    # ── Grid ──────────────────────────────────────────────────────────────
    for ax_ in (ax, axv):
        ax_.set_facecolor(DARK_BG)
        ax_.tick_params(colors=TEXT_DIM, labelsize=8, length=0)
        for spine in ax_.spines.values():
            spine.set_visible(False)
        ax_.grid(True, color=GRID, linewidth=0.4, alpha=0.7, zorder=0)

    # ── Candles ───────────────────────────────────────────────────────────
    w = 0.55
    for i in range(n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        col = UP if c >= o else DOWN
        # Wick
        ax.plot([i, i], [l, h], color=col, linewidth=0.8, alpha=0.95, zorder=2)
        # Body
        body_h = max(abs(c - o), (h - l) * 0.008)
        rect = FancyBboxPatch(
            (i - w/2, min(o, c)), w, body_h,
            boxstyle="square,pad=0",
            facecolor=col, edgecolor="none",
            linewidth=0, alpha=0.95, zorder=3
        )
        ax.add_patch(rect)

    # ── High / Low annotations ────────────────────────────────────────────
    max_i = int(np.argmax(highs))
    min_i = int(np.argmin(lows))

    ax.annotate(
        f"${_fp(highs[max_i])}",
        xy=(xs[max_i], highs[max_i]),
        xytext=(0, 14), textcoords="offset points",
        color="#4FC3F7", fontsize=7.5, fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="-|>", color="#4FC3F7", lw=0.9,
                        mutation_scale=6),
        zorder=5
    )
    ax.annotate(
        f"${_fp(lows[min_i])}",
        xy=(xs[min_i], lows[min_i]),
        xytext=(0, -16), textcoords="offset points",
        color=DOWN, fontsize=7.5, fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="-|>", color=DOWN, lw=0.9,
                        mutation_scale=6),
        zorder=5
    )

    # ── Current price dashed line + badge ─────────────────────────────────
    cur = closes[-1]
    chg = (cur - opens[0]) / opens[0] * 100 if opens[0] else 0
    badge_col = UP if chg >= 0 else DOWN

    ax.axhline(y=cur, color=badge_col, linewidth=0.9,
               linestyle=(0, (4, 3)), alpha=0.85, zorder=4)
    ax.text(
        n + 0.3, cur,
        f" {_fp(cur)} ",
        color="white", fontsize=7.5, fontweight="bold",
        va="center", ha="left",
        bbox=dict(facecolor=badge_col, edgecolor="none",
                  boxstyle="square,pad=0.35", alpha=0.95),
        zorder=6, clip_on=False
    )

    # ── Axes formatting ───────────────────────────────────────────────────
    pad = (max(highs) - min(lows)) * 0.05
    ax.set_ylim(min(lows) - pad, max(highs) + pad)
    ax.set_xlim(-1, n + 3)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: _fp(v)))
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_xticks([])
    axv.set_xticks([])

    # ── Volume ────────────────────────────────────────────────────────────
    vol_colors = [UP if closes[i] >= opens[i] else DOWN for i in range(n)]
    axv.bar(xs, vols, color=vol_colors, alpha=0.6, width=0.65, zorder=2)
    axv.set_xlim(-1, n + 3)
    axv.yaxis.tick_right()
    axv.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: _fv(v)))
    vol_total = sum(vols)
    axv.text(0.005, 0.80, f"Volume  {_fv(vol_total)}",
             transform=axv.transAxes, color="#4CAF50",
             fontsize=7.5, fontweight="bold", va="top")

    # ── Header ────────────────────────────────────────────────────────────
    symbol  = token.get("symbol", "???").upper()
    dex     = (token.get("dex", "") or "DEX").title()
    chain   = (token.get("chain", "SOL") or "SOL").upper()
    mc      = token.get("market_cap", 0)
    sign    = "+" if chg >= 0 else ""
    chg_col = UP if chg >= 0 else DOWN

    title_str = f"{symbol}/{chain} (Market Cap)  ·  {dex}  ·  15  ·  dexscreener.com"
    fig.text(0.012, 0.975, title_str, color=TEXT_TITLE, fontsize=8.5,
             fontweight="bold", va="top", ha="left")

    ohlc_str = (f"O{_fp(opens[0])}  H{_fp(max(highs))}  "
                f"L{_fp(min(lows))}  C{_fp(closes[-1])}  "
                f"MC:{_fmc(mc)}  {sign}{chg:.1f}%")
    fig.text(0.012, 0.955, ohlc_str, color=chg_col, fontsize=7.5,
             va="top", ha="left")

    # Live dot
    fig.text(0.985, 0.975, "●", color="#4CAF50", fontsize=11,
             va="top", ha="right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none", pad_inches=0.04)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _make_bars(token: dict, n: int = 60) -> list:
    seed  = token.get("price_usd") or random.uniform(0.000001, 0.01)
    price = seed * random.uniform(0.55, 0.85)
    ts    = int(time.time()) - n * 15 * 60
    trend = random.uniform(0.004, 0.018)
    bars  = []
    for i in range(n):
        noise = random.gauss(trend, 0.055)
        o = price
        c = price * (1 + noise)
        h = max(o, c) * (1 + abs(random.gauss(0, 0.018)))
        l = min(o, c) * (1 - abs(random.gauss(0, 0.018)))
        v = random.uniform(2000, 80000) * (1 + i / n)
        bars.append({"t": ts + i * 900, "o": o, "h": h, "l": l, "c": c, "v": v})
        price = c
    return bars


def _fp(v: float) -> str:
    if v == 0: return "0"
    if v >= 1: return f"{v:.2f}"
    if v >= 0.001: return f"{v:.4f}"
    if v >= 0.000001: return f"{v:.7f}"
    return f"{v:.2e}"


def _fv(v: float) -> str:
    if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
    if v >= 1_000:     return f"{v/1_000:.2f}K"
    return f"{v:.0f}"


def _fmc(v: float) -> str:
    if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
    if v >= 1_000:     return f"${v/1_000:.0f}K"
    return f"${v:.0f}"
