"""
Push notification sender for Aether SMM OS.
Uses pywebpush to send Web Push notifications to all stored subscribers.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.getenv(
    "VAPID_PUBLIC_KEY",
    "BKxxrJ2iB226pSmFEDKat4PGs7r3XlUCW6mipcVnssJLDJ7ib7rSZ_T45yf-AMBlRebPfOqJHy1yAp7MsOvvoyQ"
)
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.getenv("VAPID_EMAIL", "mailto:admin@aether-smm.app")


def send_push_to_all(title: str, body: str, url: str = "/", tag: str = "aether-alert") -> dict:
    """Send a push notification to all subscribed clients."""
    if not VAPID_PRIVATE_KEY:
        logger.debug("VAPID_PRIVATE_KEY not set — skipping push notifications")
        return {"sent": 0, "failed": 0}

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed — push notifications unavailable")
        return {"sent": 0, "failed": 0}

    import marketing_db
    subscriptions = marketing_db.get_push_subscriptions()
    if not subscriptions:
        return {"sent": 0, "failed": 0}

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    sent = 0
    failed = 0
    expired = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_EMAIL},
                ttl=86400,
            )
            sent += 1
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                expired.append(sub["endpoint"])
            else:
                logger.debug(f"Push send error: {e}")
            failed += 1

    if expired:
        for ep in expired:
            marketing_db.remove_push_subscription(ep)
        logger.info(f"Removed {len(expired)} expired push subscriptions")

    logger.info(f"Push notifications: sent={sent} failed={failed}")
    return {"sent": sent, "failed": failed}


def send_discord_coin_push(name: str, symbol: str, discord_link: str) -> dict:
    """Convenience wrapper: notify about a new Discord coin."""
    return send_push_to_all(
        title=f"🪙 New Discord Coin: {symbol}",
        body=f"{name} just launched with a Discord community! Tap to view.",
        url="/#live",
        tag="discord-coin",
    )
