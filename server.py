"""
Enhanced HTTP Server to keep Render alive and serve a gorgeous, fully-featured
interactive Admin Web Dashboard, REST APIs, Live DMs messaging, and official Meta/TikTok live API Webhook receivers.
"""
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import threading
import logging

import marketing_db
import dm_manager

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "10000"))

# Meta Webhook Verification Token (Configure in Meta Developer App)
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "my_smm_verify_token_123")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Dashboard View
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

        # 2. REST API: GET Data
        if self.path == "/api/data":
            data = marketing_db.load_db()
            data["profiles"] = marketing_db.get_profiles()
            self.send_json_response(200, data)
            return

        # 3. REST API: GET DM Messages
        elif self.path.startswith("/api/messages"):
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

        # 4. OFFICIAL META WEBHOOK VERIFICATION (GET /api/webhooks/incoming)
        # When setting up your Facebook/Instagram Developer App, Meta sends a GET request to verify this URL.
        elif self.path.startswith("/api/webhooks/incoming"):
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            mode = query_params.get("hub.mode", [None])[0]
            token = query_params.get("hub.verify_token", [None])[0]
            challenge = query_params.get("hub.challenge", [None])[0]
            
            if mode == "subscribe" and token == VERIFY_TOKEN:
                logger.info("✅ Meta Webhook successfully verified and linked!")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(challenge.encode("utf-8"))
            else:
                logger.warning("❌ Meta Webhook verification failed! Token mismatch.")
                self.send_response(403)
                self.end_headers()
            return

        # Fallback to health check
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
            logger.error(f"Failed to parse JSON post parameters: {e}")
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        # 1. LIVE META / INSTAGRAM / TIKTOK WEBHOOK RECEIVER (POST /api/webhooks/incoming)
        # Parses incoming real-world direct messages pushed from Meta's servers.
        if self.path == "/api/webhooks/incoming":
            logger.info(f"Incoming live webhook payload received: {params}")
            
            try:
                # Handle standard Meta (Instagram/Facebook) messenger webhook structure
                if params.get("object") in ["instagram", "page"]:
                    for entry in params.get("entry", []):
                        for messaging in entry.get("messaging", []):
                            sender_id = messaging.get("sender", {}).get("id")
                            message_data = messaging.get("message", {})
                            message_text = message_data.get("text", "")
                            
                            if sender_id and message_text:
                                # Trigger SMM response loop for this real-world user
                                logger.info(f"📬 [LIVE-WEBHOOK] Real DM received from ID {sender_id}: '{message_text}'")
                                
                                # Fetch profiles to choose correct responder
                                profiles = marketing_db.get_profiles()
                                active_profiles = [p for p in profiles if p.get("active", True)]
                                target_profile = active_profiles[0] if active_profiles else None
                                
                                if target_profile:
                                    # Parse sender details & write into the unified dashboard
                                    conv, new_msg = marketing_db.add_incoming_message(
                                        platform="instagram" if params.get("object") == "instagram" else "facebook",
                                        sender_handle=f"User_{sender_id}",
                                        text=message_text,
                                        profile_id=target_profile["id"]
                                    )
                                    # Trigger asynchronous AI response typing loop
                                    import asyncio
                                    loop = asyncio.get_event_loop()
                                    loop.create_task(dm_manager.simulate_incoming_direct_message())
                                    
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"EVENT_RECEIVED")
                    return
            except Exception as ex:
                logger.error(f"Error parsing live webhook payload: {ex}")
                
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # --- Settings Update ---
        if self.path == "/api/settings":
            updated = marketing_db.update_settings(params)
            self.send_json_response(200, {"success": True, "settings": updated})
            return

        # --- Multi-Profile Personas Endpoints ---
        elif self.path == "/api/profiles":
            name = params.get("name", "")
            niche = params.get("niche", "casual")
            bio = params.get("bio", "")
            cta_link = params.get("cta_link", "")
            ai_tone = params.get("ai_tone", "casual")
            avatar = params.get("avatar", "")
            
            if not name or not bio:
                self.send_json_response(400, {"success": False, "error": "Missing name or biography"})
                return
                
            new_prof = marketing_db.add_profile(name, niche, bio, cta_link, ai_tone, avatar)
            self.send_json_response(200, {"success": True, "profile": new_prof})
            return

        elif self.path == "/api/profiles/delete":
            prof_id = params.get("id")
            marketing_db.delete_profile(prof_id)
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/profiles/toggle":
            prof_id = params.get("id")
            marketing_db.toggle_profile(prof_id)
            self.send_json_response(200, {"success": True})
            return

        # --- Targets Endpoints ---
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
            target_id = params.get("id")
            marketing_db.delete_target(target_id)
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/targets/toggle":
            target_id = params.get("id")
            marketing_db.toggle_target(target_id)
            self.send_json_response(200, {"success": True})
            return

        # --- Ads Endpoints ---
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
            ad_id = params.get("id")
            marketing_db.delete_ad(ad_id)
            self.send_json_response(200, {"success": True})
            return

        elif self.path == "/api/ads/toggle":
            ad_id = params.get("id")
            marketing_db.toggle_ad(ad_id)
            self.send_json_response(200, {"success": True})
            return

        # --- Raids Endpoints ---
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
            raid_id = params.get("id")
            marketing_db.delete_raid(raid_id)
            self.send_json_response(200, {"success": True})
            return

        # --- Accounts Endpoints ---
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
            acc_id = params.get("id")
            marketing_db.delete_account(acc_id)
            self.send_json_response(200, {"success": True})
            return

        # --- Direct Message Sender ---
        elif self.path == "/api/messages/send":
            conv_id = params.get("conv_id")
            text = params.get("text", "")
            if not conv_id or not text:
                self.send_json_response(400, {"success": False, "error": "Missing conv_id or text"})
                return
                
            ok = dm_manager.execute_send_custom_dm(conv_id, text)
            self.send_json_response(200, {"success": ok})
            return

        # --- Auto Responder Chatbot Rules ---
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
            rule_id = params.get("id")
            marketing_db.delete_auto_reply(rule_id)
            self.send_json_response(200, {"success": True})
            return

        # --- Organic Growth Campaigns Endpoints ---
        elif self.path == "/api/growth_campaigns":
            niche = params.get("niche", "solana")
            keywords = params.get("keywords", "")
            cta_link = params.get("cta_link", "")
            platform = params.get("platform", "all")
            
            if not keywords or not cta_link:
                self.send_json_response(400, {"success": False, "error": "Missing keywords or redirect CTA link"})
                return
                
            camp = marketing_db.add_growth_campaign(niche, keywords, cta_link, platform)
            self.send_json_response(200, {"success": True, "campaign": camp})
            return

        elif self.path == "/api/growth_campaigns/delete":
            camp_id = params.get("id")
            marketing_db.delete_growth_campaign(camp_id)
            self.send_json_response(200, {"success": True})
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
    logger.info(f"Admin Dashboard & API Server successfully started on port {PORT}")
