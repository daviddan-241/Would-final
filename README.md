# 🚀 Cross-Platform SMM Raid Engine (Verizon Suite)

An advanced, enterprise-grade Cross-Platform Social Media Marketing (SMM) Auto-Posting, Comment Scraping, Mirroring, Ad Scheduling, and Community/Automated Raid Engine.

It runs automated SMM campaigns across **Twitter (X), TikTok, Instagram, and Facebook** — including **searching posts in your niche and dropping comments to attract DMs**, with a integrated Telegram Bot for remote commands, notifications, and alerts.

---

## 🌟 Key Features

### 1. 🔄 Cross-Platform Comment Scraping & Outreach (NEW!)
The outreach agent runs **full auto-pilot comment scraping** across ALL platforms:

- **Twitter / X**: Searches niche keywords → finds recent tweets → drops engaging comments → people DM you
- **Instagram**: Searches hashtags & user profiles → finds posts → drops niche-relevant comments → attracts DMs
- **TikTok**: Searches trending videos in your niche → drops natural-looking comments → drives DMs to your inbox
- **Facebook**: Searches public posts matching your niche → comments with engaging text → attracts leads

**How it works:**
1. You add your account session cookies in the dashboard (F12 → Application → Cookies)
2. The agent auto-searches posts in your niche every 30 minutes
3. It drops natural, human-sounding comments on relevant posts
4. People see your comment → visit your profile → DM you
5. The AI Responder auto-replies to every DM with your CTA link
6. You get real DMs in your inbox — fully automated

### 2. 🛡️ Spam & Bot Filtering
- **Bot username detection** — filters out generated/bot accounts before engaging
- **Spam DM detection** — blocks scam messages, "airdrop claim", "send crypto" etc.
- **Quality target filtering** — only engages with real, active accounts
- **Niche-specific comments** — comments match the platform and topic naturally

### 3. 📱 Session Cookie DM Agent
Reads **real DMs** from your connected accounts using browser session cookies — **no paid API needed**:
- **Twitter/X**: auth_token + ct0 cookies
- **Instagram**: sessionid cookie
- **TikTok**: sessionid + ttwid cookies
- **Facebook**: c_user + xs cookies

### 4. 🤖 AI Auto-Responder
Automatically replies to every incoming DM using:
1. **OpenAI GPT** (if API key provided)
2. **Google Gemini** (if API key provided)
3. **Smart niche templates** (always available, no key needed)

Replies sound 100% human, match the niche tone, and always include your CTA link.

### 5. 🔄 Target Account Mirroring
- Monitors target influencers on X, Instagram, TikTok, and Facebook.
- AI rewrites cloned posts in customizable tones (Bullish, Hype, Professional, Casual).
- Auto-broadcasts rewritten content to your Telegram group.

### 6. ⚡ Multi-Platform Raid Coordinator
- Instantly triggers community raids via Telegram with action buttons.
- Generates deep links (Like, Repost, Comment) for one-click raiding.
- Connected accounts auto-like and comment using session cookies.

### 7. 📣 Ad Scheduler
- Schedule recurring ads to Telegram, Twitter, Instagram, or all platforms.
- Connected accounts auto-post at your configured interval.

### 8. 💻 Web Admin Dashboard
- Responsive dark-mode dashboard on your service port (default: `10000`).
- **Unified Inbox**: see all DMs from all platforms in one place, reply directly
- **Account Fleet Manager**: add session cookies for Twitter, IG, TikTok, Facebook
- **Growth Campaign Manager**: set up niche targeting, view real analytics
- **Live SSE updates**: new messages appear in real-time

---

## 🛠️ Setup & Deployment

### Free Hosting Options

**Option 1: Render.com (Recommended — Free Tier)**
1. Fork this repo to your GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set Runtime to **Docker**
5. Add environment variables (see below)
6. Deploy — free tier gives you 750 hours/month

**Option 2: Railway.app (Free Trial)**
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Add env vars → Deploy

**Option 3: Koyeb.com (Free Tier)**
1. Go to [koyeb.com](https://koyeb.com)
2. Create App → Docker → connect repo
3. Add env vars → Deploy

**Option 4: Your own VPS (cheapest long-term)**
```bash
git clone https://github.com/YOUR_USERNAME/Would-final.git
cd Would-final
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your tokens
python bot.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Yes | Your Telegram group ID (e.g. `-100...`) |
| `PORT` | No | Web dashboard port (default: `5000`) |
| `OPENAI_API_KEY` | No | For AI-powered auto-replies |
| `GEMINI_API_KEY` | No | Alternative AI for auto-replies |

### How to Get Session Cookies (30 seconds per platform)

1. Open your browser, log into your account
2. Press **F12** → **Application** tab → **Cookies**
3. Copy these values:

| Platform | Cookies Needed |
|----------|---------------|
| **Twitter/X** | `auth_token` + `ct0` |
| **Instagram** | `sessionid` |
| **TikTok** | `sessionid` + `ttwid` |
| **Facebook** | `c_user` + `xs` |

4. Paste them into the Account Fleet in the web dashboard
5. Check "Enable outreach posts" — the agent starts immediately

---

## 🤖 Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | View available commands |
| `/status` | System health & SMM stats |
| `/raid [url] [caption]` | Launch a community raid |
| `/mirror [platform] [handle]` | Clone & rewrite content |
| `/schedule_ad [min] [text]` | Schedule recurring ads |
| `/accounts` | Show connected account fleet |

---

## 📊 What Happens When You Add Session Cookies

1. **Every 60s**: DM Agent polls your account for new incoming DMs → AI auto-replies
2. **Every 30 min**: Outreach Agent:
   - Posts niche content (Twitter, Instagram)
   - Searches for posts in your niche (Twitter + IG + TikTok + FB)
   - Drops 2-3 natural comments per platform per cycle
   - Sends 1 proactive DM per cycle
   - Filters spam/bots before engaging
3. **Every 20s**: AI Responder checks for unreplied DMs → instant personalized reply
4. **Every 90s**: Growth Engine scrapes Reddit for real humans in your niche → injects as leads
5. **Real-time**: Web dashboard shows all activity via SSE (no page refresh needed)

---

## 🔒 All Real — No Fake Data

Every component uses real APIs, real session cookies, and real network requests:
- DM agent reads real inbox messages via session cookies
- Outreach agent posts real comments on real posts
- AI responder generates contextual replies (not canned responses)
- Analytics are computed from actual conversation data (starts at zero)
- Growth engine finds real humans on Reddit (not bots)
