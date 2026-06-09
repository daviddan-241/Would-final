"""
Growth Engine — Shim that delegates to the real GrowthAgent.
Kept for backward compatibility with engine_coordinator.py.
"""
import logging
import asyncio

logger = logging.getLogger(__name__)


async def run_organic_growth_cycle():
    """Delegated to agents.growth_agent.GrowthAgent — real metrics only."""
    pass


async def start_organic_growth_loop(check_interval=90):
    """Kept for legacy compatibility. Real work done by GrowthAgent in agents/director.py."""
    logger.info("SMM Organic Growth Hacking & Lead Extraction loop started.")
    while True:
        await asyncio.sleep(check_interval)
