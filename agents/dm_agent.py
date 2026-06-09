"""
DM Response Agent — Monitors the inbox, tracks pending unanswered DMs,
and escalates unread conversations. Works with the real Telegram DM handler.
"""
import asyncio
import time

from agents.base_agent import BaseAgent
import marketing_db


class DMAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="DM Manager",
            role="Monitors inbox, tracks unanswered DMs, flags hot leads, escalates unread conversations",
            emoji="💬"
        )
        self.hot_leads = []
        self.total_dms_handled = 0

    async def run(self, interval: int = 30):
        self.log("DM Manager online. Monitoring inbox every 30 seconds.")
        self.set_status("running")
        while True:
            try:
                self.set_status("monitoring")
                await self._check_inbox()
                self.task_done()
                self.set_status("idle")
            except Exception as e:
                self.record_error(str(e))
            await asyncio.sleep(interval)

    async def _check_inbox(self):
        db = marketing_db.load_db()
        conversations = db.get("conversations", [])
        messages_store = db.get("messages", {})

        unread_convs = [c for c in conversations if c.get("unread", 0) > 0]
        if unread_convs:
            self.log(f"📬 {len(unread_convs)} unread conversations detected.")

        # Flag conversations with no reply as hot leads
        self.hot_leads = []
        for conv in conversations:
            conv_id = conv["id"]
            msgs = messages_store.get(conv_id, [])
            if not msgs:
                continue
            has_reply = any(not m.get("is_incoming", True) for m in msgs)
            last_msg = msgs[-1]
            last_is_incoming = last_msg.get("is_incoming", True)
            if last_is_incoming and not has_reply:
                self.hot_leads.append({
                    "conv_id": conv_id,
                    "platform": conv.get("platform", "unknown"),
                    "sender": conv.get("sender_handle", "unknown"),
                    "last_message": last_msg.get("text", "")[:80],
                    "age_minutes": int((time.time() - last_msg.get("timestamp", time.time())) / 60)
                })

        if self.hot_leads:
            self.log(f"🔥 {len(self.hot_leads)} hot leads waiting for a reply!")

        self.total_dms_handled = sum(
            1 for v in messages_store.values()
            for m in v if not m.get("is_incoming", True)
        )

    def get_hot_leads(self):
        return self.hot_leads
