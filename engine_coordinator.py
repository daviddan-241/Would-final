"""
Engine Coordinator — Coordinates background loops for Account Mirroring, Ad Scheduling,
Automated Raiding campaigns, Unified Inbox DM auto-responders, and Organic Growth engines.
"""
import logging
import asyncio

import marketing_db
import mirror_engine
import ad_scheduler
import raid_engine
import dm_manager
import growth_engine

logger = logging.getLogger(__name__)


async def start_raid_watcher_loop(check_interval=10):
    """Periodically checks for newly registered 'Active' raids and triggers automated raiders."""
    logger.info("Auto-Raid campaign watcher started.")
    while True:
        try:
            db = marketing_db.load_db()
            active_raids = [r for r in db.get("raids", []) if r.get("status") == "Active"]
            
            for raid in active_raids:
                # Mark as processing to avoid double runs
                raid["status"] = "Processing"
                marketing_db.save_db()
                
                # Execute in background task so we don't block the loop
                asyncio.create_task(raid_engine.execute_automated_raid(raid["id"]))
                
        except Exception as e:
            logger.error(f"Error in auto-raid campaign loop: {e}")
            
        await asyncio.sleep(check_interval)


def start_all_smm_services(bot_instance=None):
    """
    Schedules all SMM operations (Mirroring, Ad posting, Raiding, Lead Inbox DMs, and Growth Hacks)
    as asynchronous tasks in the active event loop.
    """
    logger.info("Initializing SMM services...")
    
    # Ensure database is loaded
    marketing_db.load_db()
    
    # Schedule background SMM tasks
    # 1. Target Account Mirroring (every 5 minutes / 300s)
    asyncio.create_task(mirror_engine.start_mirror_loop(bot_instance, interval=300))
    
    # 2. Ad Scheduler (checks every 60 seconds)
    asyncio.create_task(ad_scheduler.start_ad_scheduler_loop(bot_instance, check_interval=60))
    
    # 3. Auto-Raid Watcher (checks every 10 seconds)
    asyncio.create_task(start_raid_watcher_loop(check_interval=10))
    
    # 4. Direct Messages (DM) Lead Simulator & Auto-Responder (checks every 30 seconds)
    asyncio.create_task(dm_manager.start_inbox_simulator_loop(check_interval=30))
    
    # 5. Organic Traffic Growth Hacking Engine (checks every 60 seconds)
    asyncio.create_task(growth_engine.start_organic_growth_loop(check_interval=60))
    
    logger.info("🚀 All SMM, Mirroring, Ad-Posting, Auto-Raid, Unified DMs & Organic Free Traffic services are ONLINE.")
