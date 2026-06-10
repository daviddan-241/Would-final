import { Router } from "express";
import { db } from "@workspace/db";
import { targets } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

router.get("/targets", async (_req, res) => {
  const rows = await db.select().from(targets).orderBy(targets.createdAt);
  res.json({ success: true, targets: rows.map(toJson) });
});

router.post("/targets", async (req, res) => {
  try {
    const { platform = "twitter", handle, destination = "TG_GROUP" } = req.body as Record<string, string>;
    if (!handle) { res.status(400).json({ success: false, error: "Missing handle" }); return; }
    const id = `target_${Date.now()}`;
    const [row] = await db.insert(targets).values({ id, platform, handle, destination }).returning();
    res.json({ success: true, target: toJson(row) });
  } catch (err) {
    logger.error({ err }, "POST /targets failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/targets/delete", async (req, res) => {
  const { id } = req.body as { id: string };
  await db.delete(targets).where(eq(targets.id, id));
  res.json({ success: true });
});

router.post("/targets/toggle", async (req, res) => {
  const { id } = req.body as { id: string };
  const [cur] = await db.select({ active: targets.active }).from(targets).where(eq(targets.id, id));
  if (cur) await db.update(targets).set({ active: !cur.active }).where(eq(targets.id, id));
  res.json({ success: true });
});

function toJson(t: typeof targets.$inferSelect) {
  return { id: t.id, platform: t.platform, handle: t.handle, destination: t.destination, active: t.active, last_post_id: t.lastPostId, last_checked: t.lastChecked, created_at: t.createdAt?.getTime?.() ? t.createdAt.getTime() / 1000 : 0 };
}

export default router;
