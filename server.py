"""
Real-time HTTP Server — serves the dashboard and handles all social platform webhooks.
Supports: Meta (Instagram/Facebook), Twitter CRC, TikTok, and generic DM webhooks.
Uses SSE (Server-Sent Events) to push real-time inbox updates to the browser instantly.
"""
import os
import json
import queue
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse
import logging
import hashlib
import hmac

import marketing_db
import dm_manager
import sse_manager

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "5000"))
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "my_smm_verify_token_123")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET", "")


def _run_dm_async(coro):
    """Run an async coroutine from the sync HTTP handler."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        import threading
        def _t():
            asyncio.run(coro)
        threading.Thread(target=_t, daemon=True).start()


class HealthHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # ── Dashboard ──────────────────────────────────────────────────────────
        if path in ("/", "/dashboard"):
            try:
                fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            except Exception as e:
                self._send_text(500, f"Error: {e}")
            return

        # ── REST: full DB snapshot ─────────────────────────────────────────────
        if path == "/api/data":
            data = marketing_db.load_db()
            data["profiles"] = marketing_db.get_profiles()
            data["analytics"] = marketing_db.get_analytics()
            self._send_json(200, data)
            return

        # ── REST: messages for a conversation ─────────────────────────────────
        if path == "/api/messages":
            conv_id = params.get("conv_id", [None])[0]
            if not conv_id:
                self._send_json(400, {"success": False, "error": "Missing conv_id"})
                return
            messages = marketing_db.get_conversation_messages(conv_id)
            marketing_db.mark_conversation_read(conv_id)
            self._send_json(200, {"success": True, "messages": messages})
            return

        # ── SSE: real-time event stream ────────────────────────────────────────
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            q = queue.Queue(maxsize=50)
            sse_manager.add_client(q)
            try:
                while True:
                    try:
                        msg = q.get(timeout=20)
                        self.wfile.write(f"data: {msg}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                sse_manager.remove_client(q)
            return

        # ── Meta Webhook Verification ──────────────────────────────────────────
        if path.startswith("/api/webhooks/incoming"):
            mode = params.get("hub.mode", [None])[0]
            token = params.get("hub.verify_token", [None])[0]
            challenge = params.get("hub.challenge", [None])[0]
            if mode == "subscribe" and token == VERIFY_TOKEN:
                logger.info("✅ Meta Webhook verified!")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(challenge.encode())
            else:
                logger.warning("❌ Meta Webhook verification failed")
                self.send_response(403)
                self.end_headers()
            return

        # ── Twitter CRC Challenge ──────────────────────────────────────────────
        if path == "/api/webhooks/twitter":
            crc_token = params.get("crc_token", [None])[0]
            if crc_token and TWITTER_CONSUMER_SECRET:
                secret = TWITTER_CONSUMER_SECRET.encode("utf-8")
                sig = hmac.new(secret, crc_token.encode("utf-8"), hashlib.sha256).digest()
                import base64
                response_token = "sha256=" + base64.b64encode(sig).decode()
                self._send_json(200, {"response_token": response_token})
            else:
                self._send_json(200, {"response_token": "sha256="})
            return

        # Fallback
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Verizon Suite running")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            params = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json(400, {"success": False, "error": "Invalid JSON"})
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # ── Meta (Instagram / Facebook) Webhook ───────────────────────────────
        if path == "/api/webhooks/incoming":
            obj = params.get("object", "")
            if obj in ("instagram", "page"):
                platform = "instagram" if obj == "instagram" else "facebook"
                for entry in params.get("entry", []):
                    for msg in entry.get("messaging", []):
                        sender_id = msg.get("sender", {}).get("id", "")
                        text = msg.get("message", {}).get("text", "")
                        if sender_id and text:
                            logger.info(f"📬 [Meta/{platform}] DM from {sender_id}: '{text[:60]}'")
                            handle = f"@user_{sender_id}"
                            _run_dm_async(dm_manager.handle_incoming_real_dm(
                                platform=platform,
                                sender_handle=handle,
                                message_text=text,
                                profile_url=f"https://www.facebook.com/{sender_id}",
                                source_url=f"https://www.facebook.com/{sender_id}"
                            ))
            # Respond 200 immediately (Meta requires fast ACK)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"EVENT_RECEIVED")
            return

        # ── Twitter DM Webhook ─────────────────────────────────────────────────
        if path == "/api/webhooks/twitter":
            for event in params.get("direct_message_events", []):
                if event.get("type") != "message_create":
                    continue
                mc = event.get("message_create", {})
                sender_id = mc.get("sender_id", "")
                text = mc.get("message_data", {}).get("text", "")
                users = params.get("users", {})
                sender = users.get(sender_id, {})
                handle = "@" + sender.get("screen_name", sender_id)
                if text:
                    logger.info(f"📬 [Twitter] DM from {handle}: '{text[:60]}'")
                    _run_dm_async(dm_manager.handle_incoming_real_dm(
                        platform="twitter",
                        sender_handle=handle,
                        message_text=text,
                        profile_url=f"https://twitter.com/{handle.lstrip('@')}",
                        source_url=f"https://twitter.com/{handle.lstrip('@')}"
                    ))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ── TikTok Webhook ─────────────────────────────────────────────────────
        if path == "/api/webhooks/tiktok":
            event_type = params.get("event", "")
            if event_type == "direct_message":
                msg = params.get("message", {})
                sender = params.get("sender", {})
                handle = "@" + sender.get("unique_id", sender.get("user_id", "unknown"))
                text = msg.get("text", "")
                if text:
                    logger.info(f"📬 [TikTok] DM from {handle}: '{text[:60]}'")
                    _run_dm_async(dm_manager.handle_incoming_real_dm(
                        platform="tiktok",
                        sender_handle=handle,
                        message_text=text,
                        profile_url=f"https://www.tiktok.com/@{handle.lstrip('@')}",
                        source_url=f"https://www.tiktok.com/@{handle.lstrip('@')}"
                    ))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ── Settings ───────────────────────────────────────────────────────────
        if path == "/api/settings":
            updated = marketing_db.update_settings(params)
            self._send_json(200, {"success": True, "settings": updated})
            return

        # ── Profiles ──────────────────────────────────────────────────────────
        if path == "/api/profiles":
            name = params.get("name", "")
            if not name:
                self._send_json(400, {"success": False, "error": "Missing name"})
                return
            p = marketing_db.add_profile(
                params.get("name"), params.get("niche","casual"),
                params.get("bio",""), params.get("cta_link",""),
                params.get("ai_tone","casual"), params.get("avatar",""),
                params.get("tg_bot_token",""), params.get("tg_chat_id","")
            )
            self._send_json(200, {"success": True, "profile": p})
            return

        if path == "/api/profiles/delete":
            marketing_db.delete_profile(params.get("id"))
            self._send_json(200, {"success": True})
            return

        if path == "/api/profiles/toggle":
            marketing_db.toggle_profile(params.get("id"))
            self._send_json(200, {"success": True})
            return

        # ── Targets ────────────────────────────────────────────────────────────
        if path == "/api/targets":
            if not params.get("handle"):
                self._send_json(400, {"success": False, "error": "Missing handle"})
                return
            t = marketing_db.add_target(params.get("platform","twitter"), params.get("handle"), params.get("destination","TG_GROUP"))
            self._send_json(200, {"success": True, "target": t})
            return

        if path == "/api/targets/delete":
            marketing_db.delete_target(params.get("id"))
            self._send_json(200, {"success": True})
            return

        if path == "/api/targets/toggle":
            marketing_db.toggle_target(params.get("id"))
            self._send_json(200, {"success": True})
            return

        # ── Ads ────────────────────────────────────────────────────────────────
        if path == "/api/ads":
            if not params.get("content"):
                self._send_json(400, {"success": False, "error": "Missing content"})
                return
            a = marketing_db.add_ad(params.get("platform","telegram"), params.get("content"), int(params.get("interval_min",30)), params.get("image_url",""))
            self._send_json(200, {"success": True, "ad": a})
            return

        if path == "/api/ads/delete":
            marketing_db.delete_ad(params.get("id"))
            self._send_json(200, {"success": True})
            return

        if path == "/api/ads/toggle":
            marketing_db.toggle_ad(params.get("id"))
            self._send_json(200, {"success": True})
            return

        # ── Raids ──────────────────────────────────────────────────────────────
        if path == "/api/raids":
            if not params.get("url"):
                self._send_json(400, {"success": False, "error": "Missing URL"})
                return
            r = marketing_db.add_raid(params.get("platform","twitter"), params.get("url"), params.get("caption",""))
            self._send_json(200, {"success": True, "raid": r})
            return

        if path == "/api/raids/delete":
            marketing_db.delete_raid(params.get("id"))
            self._send_json(200, {"success": True})
            return

        # ── Accounts ───────────────────────────────────────────────────────────
        if path == "/api/accounts":
            if not params.get("username"):
                self._send_json(400, {"success": False, "error": "Missing username"})
                return
            a = marketing_db.add_account(
                params.get("platform","twitter"),
                params.get("username"),
                token_session=params.get("token_session",""),
                niche=params.get("niche",""),
                cta_link=params.get("cta_link",""),
                outreach_enabled=str(params.get("outreach_enabled","false")).lower() == "true",
                cookies={
                    "auth_token": params.get("auth_token",""),
                    "ct0": params.get("ct0",""),
                    "sessionid": params.get("sessionid",""),
                    "ttwid": params.get("ttwid",""),
                    "c_user": params.get("c_user",""),
                    "xs": params.get("xs",""),
                }
            )
            self._send_json(200, {"success": True, "account": a})
            return

        if path == "/api/accounts/delete":
            marketing_db.delete_account(params.get("id"))
            self._send_json(200, {"success": True})
            return

        # ── Send DM ────────────────────────────────────────────────────────────
        if path == "/api/messages/send":
            conv_id = params.get("conv_id")
            text = params.get("text", "")
            if not conv_id or not text:
                self._send_json(400, {"success": False, "error": "Missing conv_id or text"})
                return
            ok = dm_manager.execute_send_custom_dm(conv_id, text)
            self._send_json(200, {"success": ok})
            return

        # ── Auto Replies ───────────────────────────────────────────────────────
        if path == "/api/auto_replies":
            if not params.get("keyword") or not params.get("reply_text"):
                self._send_json(400, {"success": False, "error": "Missing params"})
                return
            r = marketing_db.add_auto_reply(params.get("keyword"), params.get("reply_text"))
            self._send_json(200, {"success": True, "rule": r})
            return

        if path == "/api/auto_replies/delete":
            marketing_db.delete_auto_reply(params.get("id"))
            self._send_json(200, {"success": True})
            return

        # ── Growth Campaigns ───────────────────────────────────────────────────
        if path == "/api/growth_campaigns":
            if not params.get("keywords") or not params.get("cta_link"):
                self._send_json(400, {"success": False, "error": "Missing params"})
                return
            c = marketing_db.add_growth_campaign(params.get("niche","solana"), params.get("keywords"), params.get("cta_link"), params.get("platform","all"))
            self._send_json(200, {"success": True, "campaign": c})
            return

        if path == "/api/growth_campaigns/delete":
            marketing_db.delete_growth_campaign(params.get("id"))
            self._send_json(200, {"success": True})
            return

        self._send_json(404, {"success": False, "error": "Not Found"})

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status, text):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, fmt, *args):
        pass


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_health_server():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Admin Dashboard & API Server successfully started on port {PORT}")
