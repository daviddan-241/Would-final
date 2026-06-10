"""
Enhanced HTTP Server - Admin Dashboard + REST APIs + Pump.fun Chat Proxy endpoints.
"""
import os
import json
import time
import urllib.parse
import urllib.request
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

import marketing_db
import dm_manager

logger = logging.getLogger(__name__)


def _resolve_meta_sender(sender_id: str, platform: str) -> str:
    accounts = marketing_db.get_accounts()
    token = next(
        (a.get("token_session", "") for a in accounts if a.get("platform") == platform and a.get("token_session")),
        ""
    )
    if token:
        try:
            url = f"https://graph.facebook.com/v18.0/{sender_id}?fields=name&access_token={token}"
            req = urllib.request.Request(url, headers={"User-Agent": "VerizonSuite/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                name = data.get("name", "").strip()
                if name:
                    return name
        except Exception as e:
            logger.debug(f"Graph API name lookup failed for {sender_id}: {e}")
    return f"{platform}_{sender_id}"

PORT = int(os.getenv("PORT", "5000"))
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Dashboard
        if self.path == "/" or self.path == "/dashboard":
            try:
                file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error loading dashboard: {e}".encode("utf-8"))
            return

          # PWA Static Assets (icons, manifest)
          _static_map = {
              "/manifest.json": ("manifest.json", "application/manifest+json"),
              "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
              "/icon-192.png": ("icon-192.png", "image/png"),
              "/icon-512.png": ("icon-512.png", "image/png"),
              "/favicon-32.png": ("favicon-32.png", "image/png"),
          }
          if self.path in _static_map:
              fname, ctype = _static_map[self.path]
              fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
              try:
                  with open(fpath, "rb") as _sf:
                      data = _sf.read()
                  self.send_response(200)
                  self.send_header("Content-Type", ctype)
                  self.send_header("Cache-Control", "public, max-age=86400")
                  self.end_headers()
                  self.wfile.write(data)
              except FileNotFoundError:
                  self.send_response(404)
                  self.end_headers()
                  self.wfile.write(b"Not found")
              return

  
        if self.path == "/api/agents":
            try:
                from agents.director import get_company_status
                status = get_company_status()
                self.send_json_response(200, {"success": True, **status})
            except Exception as e:
                self.send_json_response(200, {"success": False, "error": str(e), "agents": []})
            return

        if self.path == "/api/conversations":
            convs = marketing_db.get_conversations()
            self.send_json_response(200, {"success": True, "conversations": convs})
            return

        if self.path == "/api/data":
            data = marketing_db.load_db()
            data["profiles"] = marketing_db.get_profiles()
            self.send_json_response(200, data)
            return

        elif self.path.startswith("/api/messages") and not self.path.startswith("/api/messages/"):
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            conv_id = query_params.get("conv_id", [None])[0]
            if not conv_id:
                self.send_json_response(400, {"success": False, "error": "Missing conv_id"})
                return
            messages = marketing_db.get_conversation_messages(conv_id)
            marketing_db.mark_conversation_read(conv_id)
            self.send_json_response(200, {"success": True, "messages": messages})
            return

        # ── Pump.fun Chat API ───────────────────────────────────────────
        elif self.path.startswith("/api/chat/messages"):
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            mint = query_params.get("mint", [None])[0]
            since_ts = float(query_params.get("since", ["0"])[0])
            if not mint:
                self.send_json_response(400, {"success": False, "error": "Missing mint"})
                return
            try:
                import pumpfun_chat
                messages = pumpfun_chat.get_messages(mint, since_ts)
                status = pumpfun_chat.get_status(mint)
                self.send_json_response(200, {"success": True, "messages": messages, "status": status})
            except Exception as e:
                self.send_json_response(200, {"success": False, "messages": [], "status": "error", "error": str(e)})
            return

        elif self.path.startswith("/api/chat/status"):
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            mint = query_params.get("mint", [None])[0]
            if not mint:
                self.send_json_response(400, {"success": False, "error": "Missing mint"})
                return
            try:
                import pumpfun_chat
                status = pumpfun_chat.get_status(mint)
                active = pumpfun_chat.get_all_active()
                self.send_json_response(200, {"success": True, "status": status, "active_mints": active})
            except Exception as e:
                self.send_json_response(200, {"success": False, "status": "error"})
            return

        elif self.path.startswith("/api/chat/active"):
            try:
                import pumpfun_chat
                active = pumpfun_chat.get_all_active()
                self.send_json_response(200, {"success": True, "active_mints": active})
            except Exception as e:
                self.send_json_response(200, {"success": True, "active_mints": []})
            return

        # ── Discord coins feed ──────────────────────────────────────────
        elif self.path.startswith("/api/discord_coins"):
            try:
                db = marketing_db.load_db()
                coins = marketing_db.get_discord_coins(100)
                self.send_json_response(200, {"success": True, "coins": coins[-100:]})
            except Exception as e:
                self.send_json_response(200, {"success": True, "coins": []})
            return

        elif self.path.startswith("/api/webhooks/incoming"):
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            mode = query_params.get("hub.mode", [None])[0]
            token = query_params.get("hub.verify_token", [None])[0]
            challenge = query_params.get("hub.challenge", [None])[0]
            if mode == "subscribe" and VERIFY_TOKEN and token == VERIFY_TOKEN:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(challenge.encode("utf-8"))
            else:
                self.send_response(403)
                self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            params = json.loads(post_data.decode('utf-8')) if post_data else {}
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        if self.path == "/api/webhooks/incoming":
            logger.info(f"Incoming webhook: {params}")
            try:
                if params.get("object") in ["instagram", "page"]:
                    for entry in params.get("entry", []):
                        for messaging in entry.get("messaging", []):
                            sender_id = messaging.get("sender", {}).get("id")
                            message_data = messaging.get("message", {})
                            message_text = message_data.get("text", "")
                            if sender_id and message_text:
                                platform_name = "instagram" if params.get("object") == "instagram" else "facebook"
                                sender_handle = _resolve_meta_sender(sender_id, platform_name)
                                profiles = marketing_db.get_profiles()
                                active_profiles = [p for p in profiles if p.get("active", True)]
                                target_profile = active_profiles[0] if active_profiles else None
                                if target_profile:
                                    import asyncio
                                    loop = asyncio.get_event_loop()
                                    loop.create_task(dm_manager.handle_incoming_real_dm(
                                        platform=platform_name,
                                        sender_handle=sender_handle,
                                        message_text=message_text,
                                        profile_id=target_profile["id"]
                                    ))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"EVENT_RECEIVED")
                return
            except Exception as ex:
                logger.error(f"Webhook error: {ex}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ── Start pump.fun chat monitor ──────────────────────────────────
        if self.path == "/api/chat/start":
            mint = params.get("mint", "").strip()
            jwt_token = params.get("jwt", "").strip()
            if not mint:
                self.send_json_response(400, {"success": False, "error": "Missing mint address"})
                return
            try:
                import asyncio
                import pumpfun_chat
                loop = asyncio.get_event_loop()
                loop.create_task(pumpfun_chat.start_chat_monitor(mint, jwt_token))
                self.send_json_response(200, {"success": True, "message": f"Chat monitor started for {mint}"})
            except Exception as e:
                self.send_json_response(200, {"success": False, "error": str(e)})
            return

        if self.path == "/api/chat/stop":
            mint = params.get("mint", "").strip()
            if not mint:
                self.send_json_response(400, {"success": False, "error": "Missing mint address"})
                return
            try:
                import asyncio
                import pumpfun_chat
                loop = asyncio.get_event_loop()
                loop.create_task(pumpfun_chat.stop_chat_monitor(mint))
                self.send_json_response(200, {"success": True})
            except Exception as e:
                self.send_json_response(200, {"success": False, "error": str(e)})
            return

        if self.path == "/api/settings":
            updated = marketing_db.update_settings(params)
            self.send_json_response(200, {"success": True, "settings": updated})
            return

        elif self.path == "/api/profiles":
            name = params.get("name", "")
            niche = params.get("niche", "casual")
            bio = params.get("bio", "")
            cta_link = params.get("cta_link", "")
            ai_tone = params.get("ai_tone", "casual")
            avatar = params.get("avatar", "")
            tg_bot_token = params.get("tg_bot_token", "")
            tg_chat_id = params.get("tg_chat_id", "")
            if not name or not bio:
                self.send_json_response(400, {"success": False, "error": "Missing name or biography"})
                return
            new_prof = marketing_db.add_profile(name, niche, bio, cta_link, ai_tone, avatar, tg_bot_token, tg_chat_id)
            self.send_json_response(200, {"success": True, "profile": new_prof})
            return

        elif self.path == "/api/profiles/delete":
            marketing_db.delete_profile(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/profiles/toggle":
            marketing_db.toggle_profile(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/targets":
            platform = params.get("platform", "twitter")
            handle = params.get("handle", "")
            destination = params.get("destination", "TG_GROUP")
            if not handle:
                self.send_json_response(400, {"success": False, "error": "Missing handle"})
                return
            new_target = marketing_db.add_target(platform, handle, destination)
            self.send_json_response(200, {"success": True, "target": new_target})
            return

        elif self.path == "/api/targets/delete":
            marketing_db.delete_target(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/targets/toggle":
            marketing_db.toggle_target(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/ads":
            platform = params.get("platform", "telegram")
            content = params.get("content", "")
            interval_min = int(params.get("interval_min", 30))
            image_url = params.get("image_url", "")
            if not content:
                self.send_json_response(400, {"success": False, "error": "Missing content"})
                return
            new_ad = marketing_db.add_ad(platform, content, interval_min, image_url)
            self.send_json_response(200, {"success": True, "ad": new_ad})
            return

        elif self.path == "/api/ads/delete":
            marketing_db.delete_ad(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/ads/toggle":
            marketing_db.toggle_ad(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/raids":
            platform = params.get("platform", "twitter")
            url = params.get("url", "")
            caption = params.get("caption", "")
            if not url:
                self.send_json_response(400, {"success": False, "error": "Missing post URL"})
                return
            new_raid = marketing_db.add_raid(platform, url, caption)
            self.send_json_response(200, {"success": True, "raid": new_raid})
            return

        elif self.path == "/api/raids/delete":
            marketing_db.delete_raid(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/accounts":
            platform = params.get("platform", "twitter")
            username = params.get("username", "")
            token_session = params.get("token_session", "")
            if not username:
                self.send_json_response(400, {"success": False, "error": "Missing username"})
                return
            new_acc = marketing_db.add_account(platform, username, token_session=token_session)
            self.send_json_response(200, {"success": True, "account": new_acc})
            return

        elif self.path == "/api/accounts/delete":
            marketing_db.delete_account(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/messages/send":
            conv_id = params.get("conv_id")
            text = params.get("text", "")
            if not conv_id or not text:
                self.send_json_response(400, {"success": False, "error": "Missing conv_id or text"})
                return
            ok = dm_manager.execute_send_custom_dm(conv_id, text)
            self.send_json_response(200, {"success": ok})
            return

        elif self.path == "/api/auto_replies":
            keyword = params.get("keyword", "")
            reply_text = params.get("reply_text", "")
            if not keyword or not reply_text:
                self.send_json_response(400, {"success": False, "error": "Missing parameters"})
                return
            rule = marketing_db.add_auto_reply(keyword, reply_text)
            self.send_json_response(200, {"success": True, "rule": rule})
            return

        elif self.path == "/api/auto_replies/delete":
            marketing_db.delete_auto_reply(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/growth_campaigns":
            niche = params.get("niche", "solana")
            keywords = params.get("keywords", "")
            cta_link = params.get("cta_link", "")
            platform = params.get("platform", "all")
            if not keywords or not cta_link:
                self.send_json_response(400, {"success": False, "error": "Missing keywords or CTA link"})
                return
            camp = marketing_db.add_growth_campaign(niche, keywords, cta_link, platform)
            self.send_json_response(200, {"success": True, "campaign": camp})
            return

        elif self.path == "/api/growth_campaigns/delete":
            marketing_db.delete_growth_campaign(params.get("id"))
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/inject_dm":
            platform = params.get("platform", "telegram")
            sender = params.get("sender", "TestUser")
            text = params.get("text", "")
            if not text:
                self.send_json_response(400, {"success": False, "error": "Missing text"})
                return
            profiles = marketing_db.get_profiles()
            active = [p for p in profiles if p.get("active", True)]
            profile = active[0] if active else None
            if not profile:
                self.send_json_response(400, {"success": False, "error": "No active persona."})
                return
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(dm_manager.handle_incoming_real_dm(
                platform=platform, sender_handle=sender,
                message_text=text, profile_id=profile["id"]
            ))
            self.send_json_response(200, {"success": True, "message": "DM injected."})
            return

        self.send_json_response(404, {"success": False, "error": "Not Found"})

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Admin Dashboard & API Server started on port {PORT}")
