"""
Ad Scheduler Agent — Posts REAL scheduled promotional ads to Telegram groups/channels
at configured intervals. Tracks actual sends and delivery stats.
"""
import asyncio
import time

from agents.base_agent import BaseAgent
import marketing_db


class AdAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Ad Scheduler",
            role="Posts real scheduled promotional ads to Telegram at configured intervals",
            emoji="📣"
        )
        self.ads_sent = 0

    async def run(self, bot_instance=None, interval: int = 60):
        self.log("Ad Scheduler online. Checking ad queue every 60 seconds.")
        self.set_status("running")
        while True:
            try:
                self.set_status("checking")
                sent = await self._post_due_ads(bot_instance)
                if sent:
                    self.log(f"📣 Sent {sent} real scheduled ad(s) to Telegram.")
                self.task_done()
                self.set_status("idle")
            except Exception as e:
                self.record_error(str(e))
            await asyncio.sleep(interval)

    async def _post_due_ads(self, bot_instance) -> int:
        import config
        settings = marketing_db.get_settings()
        if not settings.get("auto_post_enabled", True):
            return 0

        ads = marketing_db.get_ads()
        now = time.time()
        sent_count = 0

        for ad in ads:
            if not ad.get("active", True):
                continue

            interval_sec = ad.get("interval_min", 30) * 60
            last_posted = ad.get("last_posted", 0)
            if (now - last_posted) < interval_sec:
                continue

            platform = ad.get("platform", "telegram")
            content = ad.get("content", "")
            image_url = ad.get("image_url", "")

            if platform == "telegram" and bot_instance and config.TELEGRAM_CHAT_ID:
                try:
                    if image_url:
                        await bot_instance.send_photo(
                            chat_id=config.TELEGRAM_CHAT_ID,
                            photo=image_url,
                            caption=content,
                            parse_mode="HTML"
                        )
                    else:
                        await bot_instance.send_message(
                            chat_id=config.TELEGRAM_CHAT_ID,
                            text=content,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                    ad["last_posted"] = now
                    ad["total_sends"] = ad.get("total_sends", 0) + 1
                    marketing_db.save_db()
                    marketing_db.increment_analytics(impressions=1)
                    self.ads_sent += 1
                    sent_count += 1
                    self.log(f"✅ Ad posted to Telegram: '{content[:50]}...'")
                except Exception as e:
                    self.record_error(f"Ad send failed: {e}")

        return sent_count
