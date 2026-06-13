"""
Growth Agent — Drives REAL organic lead discovery by running the growth engine's
Reddit + Nitter scraper, injecting real leads into the unified inbox, and tracking
genuine DM-growth metrics. No fake counters or simulated actions.
"""
import asyncio
import time

from agents.base_agent import BaseAgent
import marketing_db


class GrowthAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Growth Hacker",
            role="Finds real leads on Reddit & Twitter and routes them into your inbox",
            emoji="🌱"
        )
        self.leads_discovered = 0

    async def run(self, bot_instance=None, interval: int = 120):
        self.log("Growth Hacker online. Scanning Reddit & Twitter for real leads every 2 minutes.")
        self.set_status("running")
        while True:
            try:
                self.set_status("scanning")
                await self._run_growth_cycle()
                self.task_done()
                self.set_status("idle")
            except Exception as e:
                self.record_error(str(e))
                self.set_status("idle")
            await asyncio.sleep(interval)

    async def _run_growth_cycle(self):
        import growth_engine
        campaigns = marketing_db.get_growth_campaigns()
        if not campaigns:
            return

        db = marketing_db.load_db()
        before = len(db.get("conversations", []))

        await growth_engine.run_organic_growth_cycle()

        db = marketing_db.load_db()
        after = len(db.get("conversations", []))
        new_leads = after - before

        if new_leads > 0:
            self.leads_discovered += new_leads
            self.log(f"🎯 {new_leads} new real leads discovered and routed to inbox!")

    def get_growth_summary(self) -> dict:
        db = marketing_db.load_db()
        return {
            "total_real_leads": len(db.get("conversations", [])),
            "leads_this_session": self.leads_discovered,
            "tasks_completed": self.tasks_completed
        }
