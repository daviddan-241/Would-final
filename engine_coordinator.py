"""
Engine Coordinator — Starts the full agent company via agents/director.py.
All real workers are managed by the Director. Legacy shim loops kept for compatibility.
"""
import logging
import asyncio

import marketing_db
import growth_engine

logger = logging.getLogger(__name__)


def start_all_smm_services(bot_instance=None):
    """
    Launches the full Verizon Suite agent company.
    All workers are real — no simulated data.
    """
    logger.info("Initializing Verizon Suite Operations — starting all agents...")

    # Ensure database is loaded
    marketing_db.load_db()

    # Start the real company director (manages all sub-agents)
    from agents.director import start_company
    start_company(bot_instance=bot_instance)

    # Real organic lead discovery loop (Reddit)
    asyncio.create_task(growth_engine.start_organic_growth_loop(check_interval=90))

    # Twitter / X DM poller via official API (Bearer Token path)
    from agents.twitter_agent import start_twitter_dm_loop
    asyncio.create_task(start_twitter_dm_loop(check_interval=60))

    # Session-cookie DM agent — reads real DMs from every account in the fleet (free, no API needed)
    from agents.session_dm_agent import start_session_dm_loop
    asyncio.create_task(start_session_dm_loop(check_interval=60))

    logger.info("🏢 All agents online. Verizon Suite Operations is fully live.")
