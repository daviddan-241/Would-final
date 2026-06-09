"""
Raid Commander Agent — Coordinates community raids.
For Telegram: sends real raid alert posts with action buttons (the primary real action).
For connected Twitter accounts with bearer tokens: executes real likes/retweets via API v2.
For other platforms: logs that credentials are needed — no fake interactions, ever.
"""
import asyncio
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from agents.base_agent import BaseAgent
import marketing_db


class RaidAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Raid Commander",
            role="Posts real Telegram raid alerts; executes real Twitter likes/retweets for connected accounts",
            emoji="⚔️"
        )
        self.raids_executed = 0

    async def run(self, bot_instance=None, interval: int = 10):
        self.log("Raid Commander online. Watching for active raids.")
        self.set_status("running")
        while True:
            try:
                self.set_status("watching")
                await self._check_and_execute_raids(bot_instance)
                self.task_done()
                self.set_status("idle")
            except Exception as e:
                self.record_error(str(e))
            await asyncio.sleep(interval)

    async def _check_and_execute_raids(self, bot_instance):
        db = marketing_db.load_db()
        active_raids = [r for r in db.get("raids", []) if r.get("status") == "Active"]

        for raid in active_raids:
            raid["status"] = "Processing"
            marketing_db.save_db()
            asyncio.create_task(self._execute_raid(raid, bot_instance))

    async def _execute_raid(self, raid: dict, bot_instance=None):
        import config
        raid_id = raid["id"]
        platform = raid["platform"]
        url = raid["url"]
        caption = raid.get("caption", "")

        self.log(f"⚡ Processing raid on {platform}: {url[:50]}")

        # Step 1: Send real Telegram raid alert (this IS the primary real action)
        if bot_instance and config.TELEGRAM_CHAT_ID:
            try:
                msg = self._build_raid_message(platform, url, caption)
                keyboard = self._build_raid_keyboard(platform, url)
                await bot_instance.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=msg,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                self.log(f"✅ Real raid alert posted to Telegram!")
            except Exception as e:
                self.log(f"Telegram raid post failed: {e}", "warning")

        # Step 2: Execute real interactions for connected accounts with API tokens
        accounts = marketing_db.get_accounts()
        platform_accounts = [
            a for a in accounts
            if a.get("platform") == platform and a.get("token_session", "").strip()
        ]

        if not platform_accounts:
            self.log(
                f"No {platform} accounts with API tokens configured. "
                f"The Telegram alert is the real community action. "
                f"Add {platform} accounts with tokens in Fleet Accounts for automated interactions."
            )
            marketing_db.update_raid_stats(raid_id, 0, 0, status="Alert Sent — Awaiting Community")
            self.raids_executed += 1
            return

        likes = 0
        interactions = 0

        if platform in ("twitter", "x"):
            tweet_id = url.split("/status/")[-1].split("?")[0] if "/status/" in url else ""
            if not tweet_id:
                self.log(f"Cannot extract tweet ID from URL: {url}", "warning")
                marketing_db.update_raid_stats(raid_id, 0, 0, status="Error — Invalid Tweet URL")
                return

            for acc in platform_accounts:
                token = acc["token_session"].strip()
                username = acc.get("username", "")
                user_id = await self._get_twitter_user_id(token, username)
                if not user_id:
                    self.log(f"Could not resolve Twitter ID for @{username} — token may be expired.", "warning")
                    continue

                liked = await self._twitter_like(tweet_id, user_id, token)
                if liked:
                    likes += 1
                    interactions += 1
                    self.log(f"✅ @{username} liked tweet {tweet_id}")

                retweeted = await self._twitter_retweet(tweet_id, user_id, token)
                if retweeted:
                    interactions += 1
                    self.log(f"✅ @{username} retweeted tweet {tweet_id}")

                await asyncio.sleep(2.0)
        else:
            self.log(
                f"Automated {platform} interactions require OAuth integration. "
                f"Add {platform} session tokens in Fleet Accounts."
            )

        final_status = "Completed" if interactions > 0 else "Alert Sent — Awaiting Community"
        marketing_db.update_raid_stats(raid_id, likes, interactions - likes, status=final_status)
        marketing_db.increment_analytics(clicks=interactions)
        self.raids_executed += 1
        self.log(f"✅ Raid {raid_id} done: {likes} likes + {interactions - likes} retweets → {final_status}")

    async def _get_twitter_user_id(self, bearer_token: str, username: str) -> str | None:
        import aiohttp
        username = username.lstrip("@")
        url = f"https://api.twitter.com/2/users/by/username/{username}"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", {}).get("id")
                    self.log(f"Twitter user lookup returned {resp.status} for @{username}", "warning")
        except Exception as e:
            self.log(f"Twitter user ID lookup error: {e}", "warning")
        return None

    async def _twitter_like(self, tweet_id: str, user_id: str, bearer_token: str) -> bool:
        import aiohttp
        url = f"https://api.twitter.com/2/users/{user_id}/likes"
        headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"tweet_id": tweet_id}, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        return data.get("data", {}).get("liked", False)
                    body = await resp.text()
                    self.log(f"Twitter like failed ({resp.status}): {body[:150]}", "warning")
        except Exception as e:
            self.log(f"Twitter like error: {e}", "warning")
        return False

    async def _twitter_retweet(self, tweet_id: str, user_id: str, bearer_token: str) -> bool:
        import aiohttp
        url = f"https://api.twitter.com/2/users/{user_id}/retweets"
        headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"tweet_id": tweet_id}, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        return data.get("data", {}).get("retweeted", False)
                    body = await resp.text()
                    self.log(f"Twitter retweet failed ({resp.status}): {body[:150]}", "warning")
        except Exception as e:
            self.log(f"Twitter retweet error: {e}", "warning")
        return False

    def _build_raid_message(self, platform: str, url: str, caption: str) -> str:
        icons = {"twitter": "𝕏", "x": "𝕏", "tiktok": "🎵", "instagram": "📸", "facebook": "👤"}
        icon = icons.get(platform, "🌐")
        cap_line = f"\n📝 <b>Message:</b> {caption}\n" if caption else ""
        return (
            f"🚨 <b>COMMUNITY RAID INCOMING! DETONATE IT!</b> 🚨\n\n"
            f"{icon} <b>Platform:</b> {platform.upper()}\n"
            f"🎯 <b>Objective:</b> Like, Repost, Comment & Bookmark!\n"
            f"{cap_line}\n"
            f"⚔️ <i>Unleash the army. Click the buttons below!</i>"
        )

    def _build_raid_keyboard(self, platform: str, url: str) -> InlineKeyboardMarkup:
        rows = [[InlineKeyboardButton(f"🔗 Go to {platform.title()} Post", url=url)]]
        actions = []
        if "twitter.com" in url or "x.com" in url:
            tweet_id = url.split("/status/")[-1].split("?")[0] if "/status/" in url else ""
            if tweet_id:
                actions.append(InlineKeyboardButton("❤️ Like", url=f"https://twitter.com/intent/like?tweet_id={tweet_id}"))
                actions.append(InlineKeyboardButton("🔁 Repost", url=f"https://twitter.com/intent/retweet?tweet_id={tweet_id}"))
                actions.append(InlineKeyboardButton("💬 Reply", url=f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}"))
        else:
            actions.append(InlineKeyboardButton("❤️ Like & Share", url=url))
            actions.append(InlineKeyboardButton("💬 Comment", url=url))
        if actions:
            rows.append(actions)
        rows.append([InlineKeyboardButton("✅ I RAIDED! (Verify)", callback_data=f"raid_{int(time.time())}")])
        return InlineKeyboardMarkup(rows)
