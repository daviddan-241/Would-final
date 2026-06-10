import { Router } from "express";
import { db } from "@workspace/db";
import { growthCampaigns } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

router.get("/growth_campaigns", async (_req, res) => {
  const rows = await db.select().from(growthCampaigns).orderBy(growthCampaigns.createdAt);
  res.json({ success: true, campaigns: rows.map(toJson) });
});

router.post("/growth_campaigns", async (req, res) => {
  try {
    const { niche, keywords = "", cta_link = "", platform = "telegram" } = req.body as Record<string, string>;
    if (!niche) { res.status(400).json({ success: false, error: "Missing niche" }); return; }
    const id = `camp_${Date.now()}`;
    const keywordsArr = keywords.split(",").map((k: string) => k.trim().toLowerCase()).filter(Boolean);
    const [row] = await db.insert(growthCampaigns).values({ id, niche, keywords: keywordsArr.join(","), ctaLink: cta_link, platform }).returning();
    res.json({ success: true, campaign: toJson(row) });
  } catch (err) {
    logger.error({ err }, "POST /growth_campaigns failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/growth_campaigns/delete", async (req, res) => {
  const { id } = req.body as { id: string };
  await db.delete(growthCampaigns).where(eq(growthCampaigns.id, id));
  res.json({ success: true });
});

function toJson(c: typeof growthCampaigns.$inferSelect) {
  return {
    id: c.id, niche: c.niche,
    keywords: c.keywords ? c.keywords.split(",").filter(Boolean) : [],
    cta_link: c.ctaLink, platform: c.platform, status: c.status,
    impressions_generated: c.impressionsGenerated,
    clicks_generated: c.clicksGenerated,
    leads_captured: c.leadsCaptured,
  };
}

export default router;
