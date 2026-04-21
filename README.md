# Alpha_X_Calls — Telegram Signals Bot

Premium memecoin / forex / stocks signals bot for Telegram.
Posts TokenScan-style call cards, tracks tokens up to 200x with PnL brags,
runs forex + stock signal jobs, drops VIP "X winners" teasers, and
delivers a real Solana payment flow for VIP access.

Bot: **@dextrendiing_bot**
Channel: **Alpha_X_Calls**

---

## Features

- 🎯 **DEX Scanner** (every 3 min) — calls fresh Solana tokens with TokenScan-style cards
- 📈 **Gain Updates** — 20% → 200x ladder, fixed PnL base per token
- 💱 **Forex Signals** — EUR/USD, GBP/USD, XAU/USD, BTC/USDT, etc.
- 🏛 **Stock Signals** — NVDA, TSLA, AAPL, META, MSFT, SPY, QQQ, etc.
- 🔥 **VIP "X Winners" Teasers** — past wins as social proof
- 📢 **VIP Promos** — periodic CTAs with deep-link to payment bot
- 💳 **Real Solana Payment Flow** — wallet-watching, on-chain verification, instant VIP link delivery
- 🏥 **Health endpoint** for Render + UptimeRobot keep-alive

---

## Local Setup

```bash
cd bot
pip install -r requirements.txt
python bot.py
```

Required env vars (`.env` or Replit secrets):

- `TELEGRAM_TOKEN` — from @BotFather
- `CHAT_ID` — channel ID (`-100…`) where calls are posted
- `BOT_USERNAME` — bot username (no `@`), e.g. `dextrendiing_bot`

---

## Deploy on Render (free, 24/7)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint**.
3. Point Render at this repo — it auto-detects `render.yaml`.
4. Set the secrets in the Render dashboard:
   - `TELEGRAM_TOKEN`
   - `CHAT_ID`
   - `BOT_USERNAME`
5. Click **Apply** — Render will:
   - run `pip install -r requirements.txt` (build command)
   - run `python bot.py` (start command)
   - expose `/health` as the health check endpoint
6. Copy the live URL Render gives you (e.g. `https://alpha-x-calls-bot.onrender.com`).

---

## UptimeRobot (keep Render free tier alive)

Render free instances spin down after 15 min of inactivity. Use UptimeRobot to ping it every 5 min:

1. Sign up at [uptimerobot.com](https://uptimerobot.com).
2. **Add New Monitor** → type **HTTP(s)**.
3. URL: `https://YOUR-RENDER-URL.onrender.com/health`
4. Monitoring interval: **5 minutes**.
5. Save. The bot will stay live 24/7.

(Optional) Set `RENDER_EXTERNAL_URL` in Render env vars to the same URL — the bot will also self-ping every 13 minutes as a backup.

---

## Project Structure

```
bot/
  bot.py                 # main entry, scheduler, all post jobs
  payment_handler.py     # /pay /vip wallet-watching SOL flow
  image_generator.py     # all signal cards (call / update / forex / stock / winners / brag)
  blockchain_verify.py   # on-chain SOL/ETH/BNB tx verification
  dex_fetcher.py         # DexScreener API wrapper
  requirements.txt
  assets/                # character templates + brand assets
render.yaml              # Render Blueprint config
```
