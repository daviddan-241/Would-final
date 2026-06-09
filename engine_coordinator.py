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

    # Legacy loop stubs (kept for compatibility — real work is in agents/)
    asyncio.create_task(growth_engine.start_organic_growth_loop(check_interval=90))

    logger.info("🏢 All agents online. Verizon Suite Operations is fully live.")
