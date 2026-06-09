"""
Analytics Agent — Computes and tracks REAL performance metrics from actual DB activity.
No fake numbers. Every stat comes from real conversations, messages, and events.
"""
import asyncio
import time

from agents.base_agent import BaseAgent
import marketing_db


class AnalyticsAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Analytics Director",
            role="Tracks real DM counts, response rates, active personas, and engagement metrics",
            emoji="📊"
        )
        self.snapshot = {}

    async def run(self, interval: int = 60):
        self.log("Analytics Director online. Computing real metrics every 60 seconds.")
        self.set_status("running")
        while True:
            try:
                self.set_status("computing")
                self.snapshot = self._compute_real_analytics()
                self._update_db_analytics(self.snapshot)
                self.task_done()
                self.log(
                    f"Metrics: {self.snapshot['total_conversations']} convs | "
                    f"{self.snapshot['total_messages']} msgs | "
                    f"{self.snapshot['response_rate']}% response rate"
                )
                self.set_status("idle")
            except Exception as e:
                self.record_error(str(e))
            await asyncio.sleep(interval)

    def _compute_real_analytics(self) -> dict:
        db = marketing_db.load_db()
        conversations = db.get("conversations", [])
        messages_store = db.get("messages", {})
        ads = db.get("ads", [])
        profiles = db.get("profiles", [])
        raids = db.get("raids", [])

        total_conversations = len(conversations)
        total_messages = sum(len(v) for v in messages_store.values())
        incoming = sum(1 for v in messages_store.values() for m in v if m.get("is_incoming", True))
        outgoing = sum(1 for v in messages_store.values() for m in v if not m.get("is_incoming", True))
        unread = sum(c.get("unread", 0) for c in conversations)
        active_profiles = sum(1 for p in profiles if p.get("active", True))
        active_ads = sum(1 for a in ads if a.get("active", True))
        completed_raids = sum(1 for r in raids if r.get("status") == "Completed")
        response_rate = round((outgoing / incoming) * 100, 1) if incoming > 0 else 0.0

        platforms = {}
        for conv in conversations:
            p = conv.get("platform", "unknown")
            platforms[p] = platforms.get(p, 0) + 1

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "incoming_messages": incoming,
            "outgoing_messages": outgoing,
            "unread_messages": unread,
            "response_rate": response_rate,
            "active_profiles": active_profiles,
            "active_ads": active_ads,
            "completed_raids": completed_raids,
            "conversations_by_platform": platforms,
            "computed_at": time.time()
        }

    def _update_db_analytics(self, snapshot: dict):
        db = marketing_db.load_db()
        if "analytics" not in db:
            db["analytics"] = {}
        db["analytics"].update({
            "total_conversations": snapshot["total_conversations"],
            "total_messages": snapshot["total_messages"],
            "incoming": snapshot["incoming_messages"],
            "outgoing": snapshot["outgoing_messages"],
            "response_rate": snapshot["response_rate"],
            "unread": snapshot["unread_messages"],
            "platforms": snapshot["conversations_by_platform"],
        })
        marketing_db.save_db()

    def get_snapshot(self) -> dict:
        if not self.snapshot:
            self.snapshot = self._compute_real_analytics()
        return self.snapshot
