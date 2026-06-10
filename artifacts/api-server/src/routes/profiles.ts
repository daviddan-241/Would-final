import { Router } from "express";
import { db } from "@workspace/db";
import { profiles } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

router.get("/profiles", async (req, res) => {
  try {
    const rows = await db.select().from(profiles).orderBy(profiles.createdAt);
    res.json({ success: true, profiles: rows.map(toJson) });
  } catch (err) {
    req.log.error({ err }, "GET /profiles failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/profiles", async (req, res) => {
  try {
    const { name, niche = "casual", bio, cta_link = "", ai_tone = "casual", avatar = "", tg_bot_token = "", tg_chat_id = "" } = req.body as Record<string, string>;
    if (!name || !bio) {
      res.status(400).json({ success: false, error: "Missing name or biography" });
      return;
    }
    const id = `prof_${Date.now()}`;
    const avatarUrl = avatar || `https://api.dicebear.com/7.x/pixel-art/svg?seed=${encodeURIComponent(name)}`;
    const [row] = await db.insert(profiles).values({ id, name, niche, bio, ctaLink: cta_link, aiTone: ai_tone, avatar: avatarUrl, tgBotToken: tg_bot_token, tgChatId: tg_chat_id }).returning();
    res.json({ success: true, profile: toJson(row) });
  } catch (err) {
    req.log.error({ err }, "POST /profiles failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/profiles/delete", async (req, res) => {
  try {
    const { id } = req.body as { id: string };
    await db.delete(profiles).where(eq(profiles.id, id));
    res.json({ success: true });
  } catch (err) {
    logger.error({ err }, "POST /profiles/delete failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/profiles/toggle", async (req, res) => {
  try {
    const { id } = req.body as { id: string };
    const [current] = await db.select({ active: profiles.active }).from(profiles).where(eq(profiles.id, id));
    if (current) {
      await db.update(profiles).set({ active: !current.active }).where(eq(profiles.id, id));
    }
    res.json({ success: true });
  } catch (err) {
    logger.error({ err }, "POST /profiles/toggle failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

function toJson(p: typeof profiles.$inferSelect) {
  return {
    id: p.id,
    name: p.name,
    niche: p.niche,
    bio: p.bio,
    cta_link: p.ctaLink,
    ai_tone: p.aiTone,
    avatar: p.avatar,
    active: p.active,
    tg_bot_token: p.tgBotToken,
    tg_chat_id: p.tgChatId,
  };
}

export default router;
