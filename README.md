# 🚀 Telegram Coin Scanner & Cross-Platform SMM Raid Engine (Verizon Suite)

An advanced, enterprise-grade Telegram Coin Scanner Bot tightly integrated with a **Cross-Platform Social Media Marketing (SMM) Auto-Posting, Mirroring, Ad Scheduling, and Community/Automated Raid Engine**. 

It scans DexScreener, GeckoTerminal, Pump.fun, and trending pools every 15 seconds for brand-new tokens with valid Telegram links, while simultaneously running automated campaigns across **Twitter (X), TikTok, Instagram, and Facebook**.

---

## 🌟 Key Upgraded Features

### 1. 🔍 Token Scanner
- Scans `Pump.fun`, `DexScreener`, `GeckoTerminal`, and extra sources.
- Uses **strict validation** on Telegram links to filters out scam redirect links.
- Uses SQLite/Local DB cache to guarantee zero double-posting.

### 2. 🔄 Target Account Mirroring & Cloning
- **Cross-Platform Mirroring**: Monitors successful targets/influencers on X/Twitter, Instagram, TikTok, and Facebook.
- **AI Rewriting Engine**: Uses **OpenAI GPT** or **Google Gemini** APIs to dynamically rewrite cloned posts in customizable tones (Bullish, Hype, Professional, Casual) to look 100% natural and "all real".
- **Local Fallback**: Features a rich rule-based synonym & slang rewriter if no API keys are provided.
- **Auto Broadcast**: Immediately broadcasts rewritten posts to your Telegram group or your linked automated accounts.

### 3. ⚡ Multi-Platform Raid Coordinator
- **Raid Alerts**: Instantly triggers community raids via Telegram with beautiful layout alerts.
- **Community Deep Links**: Generates direct one-click quick action buttons (**Like**, **Repost**, **Comment**) so your group members can raid with maximum efficiency.
- **Automated Raiders Fleet**: Configures a fleet of automated accounts (Self-Bots) with rotating proxies to automatically like, comment, and repost behind the scenes to pump engagement safely and naturally.

### 4. 📣 Automated Ad Scheduler
- Schedule recurring promotional banners and text advertisements.
- Set customizable intervals (e.g., every 30 minutes) to automatically broadcast to Telegram groups, Twitter channels, and other platforms.

### 5. 💻 Gorgeous Web Admin Control Panel
- Features a responsive modern **Dark-Mode Web Dashboard** hosted directly on your service port (e.g. `10000`).
- **Interactive Graphs & Live Log Stream**: Track active raids, scheduled ads, cloned targets, and connected accounts with real-time updates.
- **Full Form Controllers**: Manage targets, schedule new ads, register fleet accounts, view progress bars, and adjust AI parameters instantly from any browser.

---

## 🛠️ Web Dashboard Preview

When running, open your web browser and navigate to:
```
http://localhost:10000
```
*(Or your deployed domain name e.g. `https://your-service.onrender.com`)*

You will gain access to the **SMM Command Center**:
- **Account Mirroring Panel**: Set up profiles to clone.
- **Raid Campaign Launchpad**: Enter any post link to trigger automated & community raids.
- **Ad Scheduler Grid**: Manage active promotional campaigns.
- **Self-Bot Fleet Manager**: Add account cookies, session tokens, and configure **Rotating Proxies** to prevent shadow-bans.

---

## 🤖 Enhanced Telegram Bot Commands

Send `/start` to the bot inside your group to see available controls:

### 📡 Core Scans
- `/start` — View main scanner options and information.
- `/status` — Get high-fidelity stats on scanner performance and active SMM metrics.
- `/scan` — Triggers an immediate manual coin scan.
- `/clear` — Empties the seen-token database cache.

### 🔥 SMM & Raids
- `/raid [url] [optional_caption]` — Instantly detonates a community raid for the pasted X, Instagram, Facebook, or TikTok URL. Generates action deep-links.
- `/mirror [platform] [handle]` — Sets up automatic crawling, AI-rewriting, and cloning of a target influencer.
- `/schedule_ad [interval_minutes] [text]` — Schedules a recurring ad that automatically broadcasts to the group at your chosen interval.
- `/accounts` — Displays health and registration status of your connected automated account fleet.

---

## 🚀 Deployment Instructions

### Option A: Deploy on Render (Background Worker / Web Service)
1. Create a **Web Service** (not Background Worker, so the web dashboard is accessible!) on Render.
2. Connect your cloned GitHub repository.
3. Set the runtime environment to **Docker** (using the pre-configured `Dockerfile` included).
4. Add your Environment Variables:
   - `TELEGRAM_BOT_TOKEN` — Gotten from `@BotFather`
   - `TELEGRAM_CHAT_ID` — Your group ID (e.g. `-100...`)
   - `OPENAI_API_KEY` or `GEMINI_API_KEY` *(Optional)* — For AI-powered post rewriting.
   - `PORT` — Set to `10000`

### Option B: Local Running
1. Clone the repository and navigate into the folder:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   ```
2. Edit `.env` with your bot token and chat ID.
3. Run the application:
   ```bash
   python bot.py
   ```
4. Open `http://localhost:10000` to access your admin dashboard!
