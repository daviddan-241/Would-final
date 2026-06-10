"""
Pump.fun Livestream Chat Proxy
Connects to pump.fun's Socket.io and proxies messages to website visitors.
Messages are stored in memory and served via REST polling endpoints.
"""
import asyncio
import logging
import time
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory message store: mint -> list of message dicts
_chat_rooms: dict[str, list[dict]] = {}
_active_connections: dict[str, asyncio.Task] = {}
_room_status: dict[str, str] = {}  # mint -> "connecting" | "live" | "error" | "no_stream"

MAX_MESSAGES_PER_ROOM = 300
PUMPFUN_API = "https://frontend-api-v3.pump.fun"

HEADERS = {
    "Accept": "application/json",
    "Origin": "https://pump.fun",
    "Referer": "https://pump.fun/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def get_messages(mint: str, since_ts: float = 0.0) -> list[dict]:
    """Return messages for a mint newer than since_ts."""
    msgs = _chat_rooms.get(mint, [])
    if since_ts:
        msgs = [m for m in msgs if m.get("ts", 0) > since_ts]
    return msgs


def get_status(mint: str) -> str:
    """Return connection status for a mint."""
    return _room_status.get(mint, "idle")


def get_all_active() -> list[str]:
    """Return list of mint addresses currently being monitored."""
    return list(_active_connections.keys())


def _store_message(mint: str, msg: dict):
    if mint not in _chat_rooms:
        _chat_rooms[mint] = []
    msg["ts"] = time.time()
    _chat_rooms[mint].append(msg)
    if len(_chat_rooms[mint]) > MAX_MESSAGES_PER_ROOM:
        _chat_rooms[mint] = _chat_rooms[mint][-MAX_MESSAGES_PER_ROOM:]


async def start_chat_monitor(mint: str, jwt_token: str = ""):
    """Start monitoring pump.fun chat for a specific mint address."""
    if mint in _active_connections:
        task = _active_connections[mint]
        if not task.done():
            logger.info(f"Chat monitor already running for {mint}")
            return

    logger.info(f"Starting chat monitor for mint: {mint}")
    task = asyncio.create_task(_monitor_chat(mint, jwt_token))
    _active_connections[mint] = task


async def stop_chat_monitor(mint: str):
    """Stop monitoring a mint's chat."""
    if mint in _active_connections:
        task = _active_connections.pop(mint)
        task.cancel()
        _room_status[mint] = "idle"
        logger.info(f"Stopped chat monitor for {mint}")


async def _monitor_chat(mint: str, jwt_token: str = ""):
    """Core chat monitoring loop using Socket.io protocol."""
    _room_status[mint] = "connecting"

    try:
        import socketio
        sio = socketio.AsyncClient(logger=False, engineio_logger=False)

        @sio.on("connect")
        async def on_connect():
            _room_status[mint] = "live"
            logger.info(f"Connected to pump.fun chat for {mint}")
            _store_message(mint, {
                "type": "system",
                "text": f"Connected to live chat for {mint[:8]}...",
                "user": "System",
                "avatar": "",
            })
            # Join the chat room for this mint
            await sio.emit("join-room", {"mint": mint})
            await sio.emit("subscribe", {"mint": mint})

        @sio.on("disconnect")
        async def on_disconnect():
            _room_status[mint] = "disconnected"
            logger.info(f"Disconnected from pump.fun chat for {mint}")

        @sio.on("connect_error")
        async def on_error(data):
            _room_status[mint] = "error"
            logger.warning(f"Chat connect error for {mint}: {data}")

        # Listen for various chat event names pump.fun might use
        for event_name in ["message", "chat_message", "new_message", "chat", "comment", "live_message"]:
            @sio.on(event_name)
            async def on_message(data, _event=event_name):
                msg = _parse_chat_message(data)
                if msg:
                    _store_message(mint, msg)

        connect_headers = {"Origin": "https://pump.fun", "Referer": "https://pump.fun/"}
        if jwt_token:
            connect_headers["Authorization"] = f"Bearer {jwt_token}"

        await sio.connect(
            "https://frontend-api-v3.pump.fun",
            headers=connect_headers,
            transports=["websocket"],
            wait_timeout=15,
            socketio_path="/socket.io/",
        )

        await sio.wait()

    except ImportError:
        logger.error("python-socketio not installed. Run: pip install python-socketio[asyncio]")
        _room_status[mint] = "error"
        _store_message(mint, {
            "type": "error",
            "text": "Chat proxy requires python-socketio. Run: pip install 'python-socketio[asyncio]'",
            "user": "System",
            "avatar": "",
        })
    except asyncio.CancelledError:
        _room_status[mint] = "idle"
        raise
    except Exception as e:
        logger.warning(f"Socket.io connection failed for {mint}: {e}. Falling back to API polling.")
        _room_status[mint] = "polling"
        await _poll_chat_fallback(mint, jwt_token)


async def _poll_chat_fallback(mint: str, jwt_token: str = ""):
    """
    Fallback: poll pump.fun REST API for chat messages.
    Uses GET /livestreams/{mint} to check for live stream, then polls messages.
    """
    _store_message(mint, {
        "type": "system",
        "text": f"Connecting to pump.fun chat via API for {mint[:8]}...",
        "user": "System",
        "avatar": "",
    })

    headers = {**HEADERS}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    poll_url = f"{PUMPFUN_API}/livestreams/{mint}/comments"
    livestream_url = f"{PUMPFUN_API}/livestreams/{mint}"

    async with aiohttp.ClientSession() as session:
        # Check if stream exists
        try:
            async with session.get(livestream_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _room_status[mint] = "live"
                    _store_message(mint, {
                        "type": "system",
                        "text": f"Live stream found: {data.get('title', 'Untitled')}",
                        "user": "System",
                        "avatar": "",
                    })
                elif resp.status == 404:
                    _room_status[mint] = "no_stream"
                    _store_message(mint, {
                        "type": "system",
                        "text": "No active livestream found for this token. Make sure the coin is currently live on pump.fun.",
                        "user": "System",
                        "avatar": "",
                    })
                    return
                elif resp.status == 401:
                    _room_status[mint] = "auth_required"
                    _store_message(mint, {
                        "type": "system",
                        "text": "Authentication required. Please provide your pump.fun JWT token in the settings.",
                        "user": "System",
                        "avatar": "",
                    })
                    return
        except Exception as e:
            logger.debug(f"Livestream check error for {mint}: {e}")

        # Poll for comments
        seen_ids: set[str] = set()
        while True:
            try:
                async with session.get(poll_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        comments = data if isinstance(data, list) else data.get("comments", [])
                        for comment in comments:
                            msg_id = str(comment.get("id", "") or comment.get("timestamp", ""))
                            if msg_id and msg_id in seen_ids:
                                continue
                            if msg_id:
                                seen_ids.add(msg_id)
                            msg = _parse_chat_message(comment)
                            if msg:
                                _store_message(mint, msg)
                    elif resp.status == 401:
                        _room_status[mint] = "auth_required"
                        _store_message(mint, {
                            "type": "system",
                            "text": "JWT token expired or invalid. Please refresh your pump.fun JWT.",
                            "user": "System",
                            "avatar": "",
                        })
                        return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"Chat poll error for {mint}: {e}")

            await asyncio.sleep(3)


def _parse_chat_message(data: dict | str | None) -> dict | None:
    """Normalize a pump.fun chat message from various formats."""
    if not data:
        return None

    if isinstance(data, str):
        return {"type": "message", "text": data, "user": "Unknown", "avatar": ""}

    if not isinstance(data, dict):
        return None

    # Extract text from various field names
    text = (
        data.get("message") or data.get("text") or data.get("content") or
        data.get("body") or data.get("msg") or ""
    )
    if not text:
        return None

    # Extract user info
    user = (
        data.get("username") or data.get("user") or data.get("name") or
        data.get("display_name") or data.get("sender") or "Anonymous"
    )
    if isinstance(user, dict):
        user = user.get("username") or user.get("name") or "Anonymous"

    avatar = data.get("profile_image") or data.get("avatar") or data.get("image") or ""
    if not avatar and isinstance(data.get("user"), dict):
        avatar = data["user"].get("profile_image") or data["user"].get("avatar") or ""

    wallet = data.get("user_public_key") or data.get("wallet") or data.get("address") or ""

    return {
        "type": "message",
        "text": str(text)[:500],
        "user": str(user)[:50],
        "avatar": str(avatar)[:200],
        "wallet": str(wallet)[:50],
    }
