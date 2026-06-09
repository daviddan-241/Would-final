"""
Company Director — The top-level orchestrator of all Verizon Suite agents.
Starts, monitors, and coordinates all worker agents. Reports real company-wide stats.
Think of this as the CEO of the agent company.
"""
import asyncio
import time
import logging

from agents.rss_agent import RSSAgent
from agents.analytics_agent import AnalyticsAgent
from agents.dm_agent import DMAgent
from agents.growth_agent import GrowthAgent
from agents.raid_agent import RaidAgent
from agents.ad_agent import AdAgent

logger = logging.getLogger("agent.director")

# Global agent registry
_agents: dict = {}
_director_started_at: float = None


def get_all_agents() -> dict:
    return _agents


def get_agent(name: str):
    return _agents.get(name)


def get_company_status() -> dict:
    global _director_started_at
    agent_list = [a.to_dict() for a in _agents.values()]
    active = sum(1 for a in _agents.values() if a.status not in ("stopped", "error"))
    total_tasks = sum(a.tasks_completed for a in _agents.values())
    total_errors = sum(a.error_count for a in _agents.values())
    uptime = int(time.time() - _director_started_at) if _director_started_at else 0

    return {
        "company_name": "Verizon Suite Operations",
        "total_agents": len(_agents),
        "active_agents": active,
        "total_tasks_completed": total_tasks,
        "total_errors": total_errors,
        "uptime_seconds": uptime,
        "uptime_human": _format_uptime(uptime),
        "agents": agent_list,
        "started_at": _director_started_at
    }


def _format_uptime(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"


def start_company(bot_instance=None):
    """Hire all agents and start the company."""
    global _director_started_at
    _director_started_at = time.time()
    logger.info("🏢 Verizon Suite Operations — Company Director starting up all agents...")

    # Instantiate all agents
    rss = RSSAgent()
    analytics = AnalyticsAgent()
    dm = DMAgent()
    growth = GrowthAgent()
    raid = RaidAgent()
    ad = AdAgent()

    _agents["RSS Scout"] = rss
    _agents["Analytics Director"] = analytics
    _agents["DM Manager"] = dm
    _agents["Growth Hacker"] = growth
    _agents["Raid Commander"] = raid
    _agents["Ad Scheduler"] = ad

    # Launch all agents as background async tasks
    asyncio.create_task(rss.run(interval=180))
    asyncio.create_task(analytics.run(interval=60))
    asyncio.create_task(dm.run(interval=30))
    asyncio.create_task(growth.run(bot_instance=bot_instance, interval=90))
    asyncio.create_task(raid.run(bot_instance=bot_instance, interval=10))
    asyncio.create_task(ad.run(bot_instance=bot_instance, interval=60))

    logger.info(f"🏢 All {len(_agents)} agents hired and running. Company is fully operational.")
    return _agents
