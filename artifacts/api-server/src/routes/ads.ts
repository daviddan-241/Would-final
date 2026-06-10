import { Router } from "express";
import { db } from "@workspace/db";
import { ads } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

router.get("/ads", async (_req, res) => {
  const rows = await db.select().from(ads).orderBy(ads.createdAt);
  res.json({ success: true, ads: rows.map(toJson) });
});

router.post("/ads", async (req, res) => {
  try {
    const { platform = "telegram", content, interval_min = "30", image_url = "" } = req.body as Record<string, string>;
    if (!content) { res.status(400).json({ success: false, error: "Missing content" }); return; }
    const id = `ad_id_${Date.now()}`;
    const [row] = await db.insert(ads).values({ id, platform, content, intervalMin: Number(interval_min), imageUrl: image_url }).returning();
    res.json({ success: true, ad: toJson(row) });
  } catch (err) {
    logger.error({ err }, "POST /ads failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/ads/delete", async (req, res) => {
  const { id } = req.body as { id: string };
  await db.delete(ads).where(eq(ads.id, id));
  res.json({ success: true });
});

router.post("/ads/toggle", async (req, res) => {
  const { id } = req.body as { id: string };
  const [cur] = await db.select({ active: ads.active }).from(ads).where(eq(ads.id, id));
  if (cur) await db.update(ads).set({ active: !cur.active }).where(eq(ads.id, id));
  res.json({ success: true });
});

function toJson(a: typeof ads.$inferSelect) {
  return { id: a.id, platform: a.platform, content: a.content, interval_min: a.intervalMin, image_url: a.imageUrl, active: a.active, last_posted: a.lastPosted };
}

export default router;
