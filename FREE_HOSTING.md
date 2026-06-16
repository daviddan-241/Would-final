# 🆓 Free Hosting Guide — Run Everything 24/7 for $0

This bot needs **always-on** hosting because it runs background loops 24/7:
- Token scanner every 15s
- DM polling every 60s  
- AI auto-reply every 20s
- Outreach (comments/DMs) every 30min
- Growth engine every 90s

If the service sleeps, ALL loops stop. Here are the **best free options ranked**:

---

## 🥇 Option 1: Koyeb.com (BEST — No Sleep, No Credit Card)

**Why**: Free tier stays **always-on** (no sleep), Docker support, no credit card needed.

### Steps:
1. Go to **[koyeb.com](https://koyeb.com)** → Sign up (free, no CC)
2. Click **Create App** → **Docker**
3. Connect your GitHub: `daviddan-241/Would-final`
4. Settings:
   - **Dockerfile**: `Dockerfile` (auto-detected)
   - **Port**: `10000`
   - **Instance type**: `nano` (free)
5. **Environment Variables** — add these:
   ```
   TELEGRAM_BOT_TOKEN = your_token_from_botfather
   TELEGRAM_CHAT_ID = your_group_id
   PORT = 10000
   ```
6. Click **Deploy**
7. Wait 2-3 minutes → your dashboard is live at `https://your-app.koyeb.app`
8. Open dashboard → **Account Fleet** → Add your session cookies

**Result**: Runs 24/7 forever, free, no sleep.

---

## 🥈 Option 2: Render.com (Easy, 750hrs/month)

**Why**: Easiest setup, good free tier, Docker support.

**Note**: Free tier sleeps after 15min idle. The bot includes a **self-ping keep-alive** that wakes it every 10 minutes to keep loops running.

### Steps:
1. Go to **[render.com](https://render.com)** → Sign up (free, no CC)
2. Click **New** → **Web Service**
3. Connect GitHub: `daviddan-241/Would-final`
4. Settings:
   - **Runtime**: Docker
   - **Instance type**: Free
   - **Port**: `10000`
5. **Environment Variables**:
   ```
   TELEGRAM_BOT_TOKEN = your_token
   TELEGRAM_CHAT_ID = your_group_id
   PORT = 10000
   RENDER_EXTERNAL_URL = https://your-app.onrender.com
   ```
6. Click **Create Web Service**
7. Wait 3-5 minutes for first deploy
8. Open `https://your-app.onrender.com` → Add session cookies

**Result**: Runs ~23.5hrs/day (brief sleeps between pings), 750hrs/month free.

---

## 🥉 Option 3: Oracle Cloud Always Free (TRUE forever-free VM)

**Why**: Full Linux VM, **truly free forever** (no expiry), runs Docker or Python directly. Most powerful free option.

### Steps:
1. Go to **[cloud.oracle.com](https://cloud.oracle.com)** → Sign up (needs CC for verification, never charged)
2. Create a **VM Instance**:
   - **Image**: Ubuntu 22.04 or 24.04
   - **Shape**: VM.Standard.E2.1.Micro (Always Free eligible)
   - **RAM**: 1GB
   - Download your SSH key
3. SSH into your VM:
   ```bash
   ssh -i your-key.key ubuntu@YOUR_VM_IP
   ```
4. Install Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io git
   sudo systemctl enable docker && sudo systemctl start docker
   ```
5. Clone and run:
   ```bash
   git clone https://github.com/daviddan-241/Would-final.git
   cd Would-final
   cp .env.example .env
   nano .env  # Add your tokens
   sudo docker build -t verizon .
   sudo docker run -d --restart always -p 80:10000 --env-file .env --name verizon verizon
   ```
6. Open `http://YOUR_VM_IP` in browser → Add session cookies

**Result**: Runs 24/7 forever, no limits, full control. Best long-term option.

---

## Option 4: Fly.io (3 Free VMs)

**Why**: 3 always-on VMs for free. Needs credit card for signup but never charged.

### Steps:
1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. `fly auth signup` (needs CC for verification)
3. In the repo directory:
   ```bash
   fly launch --no-deploy
   fly secrets set TELEGRAM_BOT_TOKEN=your_token TELEGRAM_CHAT_ID=your_chat_id
   fly deploy
   ```
4. Open `https://your-app.fly.dev` → Add session cookies

---

## 🔧 After Deploying — Add Your Accounts

1. Open your dashboard URL
2. Go to **Account Fleet** section
3. Add accounts (you can add **MULTIPLE** per platform):

### TikTok Account:
- Platform: `tiktok`
- Username: `your_tiktok_username`
- Cookies:
  - `sessionid`: *(F12 → Application → Cookies → tiktok.com → sessionid)*
  - `ttwid`: *(same location → ttwid)*
- ✅ Check **Enable outreach posts**
- Niche: `crypto` / `celeb` / `lifestyle` / etc.
- CTA Link: `https://t.me/your_channel` or any link

### Instagram Account:
- Platform: `instagram`
- Username: `your_ig_username`
- Cookies:
  - `sessionid`: *(F12 → Application → Cookies → instagram.com → sessionid)*
- ✅ Check **Enable outreach posts**
- Niche + CTA Link

### Facebook Account:
- Platform: `facebook`
- Username: `your_fb_name`
- Cookies:
  - `c_user`: *(F12 → Application → Cookies → facebook.com → c_user)*
  - `xs`: *(same → xs)*
- ✅ Check **Enable outreach posts**

### Twitter/X Account:
- Platform: `twitter`
- Username: `your_twitter_handle`
- Cookies:
  - `auth_token`: *(F12 → Application → Cookies → twitter.com → auth_token)*
  - `ct0`: *(same → ct0)*
- ✅ Check **Enable outreach posts**

---

## ✅ What Happens After You Add Cookies

| Interval | What Happens |
|----------|-------------|
| **Every 60s** | Reads real DMs from all accounts |
| **Every 20s** | AI generates reply + **sends it back on the platform** |
| **Every 30min** | Searches niche posts → drops 2-3 comments per platform |
| **Every 30min** | Sends 1 proactive DM per account |
| **Every 90s** | Scrapes Reddit for real leads in your niche |
| **Every 15s** | Scans new tokens (Pump.fun, DexScreener, etc.) |
| **Every 60s** | Posts scheduled ads if any are configured |
| **Real-time** | Dashboard shows everything via live updates |

**Walk away. Come back to real DMs. Everything is real.**
