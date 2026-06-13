"""
Server-Sent Events (SSE) Manager.
Maintains a list of live browser connections and pushes real-time events
(new messages, new conversations, analytics updates) to all of them instantly.
"""
import json
import queue
import threading
import logging

logger = logging.getLogger(__name__)

_clients: list = []
_lock = threading.Lock()


def add_client(q: queue.Queue):
    with _lock:
        _clients.append(q)
    logger.debug(f"[SSE] Client connected ({len(_clients)} total)")


def remove_client(q: queue.Queue):
    with _lock:
        if q in _clients:
            _clients.remove(q)
    logger.debug(f"[SSE] Client disconnected ({len(_clients)} remaining)")


def push_event(event_type: str, data: dict):
    """Broadcast an event to every connected browser tab instantly."""
    payload = {"type": event_type, **data}
    msg = json.dumps(payload)
    dead = []
    with _lock:
        for q in _clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
    for q in dead:
        remove_client(q)


def client_count() -> int:
    return len(_clients)
