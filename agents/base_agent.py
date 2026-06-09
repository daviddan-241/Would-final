"""
Base Agent class for the Verizon Suite company agent system.
Every worker agent inherits from this for consistent tracking, logging, and status reporting.
"""
import time
import logging
import asyncio
from typing import Optional


class BaseAgent:
    def __init__(self, name: str, role: str, emoji: str = "🤖"):
        self.name = name
        self.role = role
        self.emoji = emoji
        self.status = "idle"
        self.tasks_completed = 0
        self.last_active = None
        self.started_at = time.time()
        self.error_count = 0
        self.log_buffer = []
        self.logger = logging.getLogger(f"agent.{name.lower().replace(' ', '_')}")

    def log(self, msg: str, level: str = "info"):
        entry = {"time": time.time(), "msg": msg, "level": level}
        self.log_buffer = self.log_buffer[-49:] + [entry]
        getattr(self.logger, level, self.logger.info)(f"[{self.name}] {msg}")

    def set_status(self, status: str):
        self.status = status
        self.last_active = time.time()

    def task_done(self):
        self.tasks_completed += 1
        self.last_active = time.time()

    def record_error(self, err: str):
        self.error_count += 1
        self.log(f"Error: {err}", "error")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "emoji": self.emoji,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "error_count": self.error_count,
            "last_active": self.last_active,
            "started_at": self.started_at,
            "uptime_s": int(time.time() - self.started_at),
            "recent_logs": self.log_buffer[-10:]
        }

    async def run(self):
        raise NotImplementedError("Each agent must implement run()")
