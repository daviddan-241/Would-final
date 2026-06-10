import { Router } from "express";
import { db } from "@workspace/db";
import { settingsTable } from "@workspace/db";
import { eq } from "drizzle-orm";

const router = Router();

async function getOrCreate() {
  const rows = await db.select().from(settingsTable).limit(1);
  if (rows.length > 0) return rows[0];
  const [row] = await db.insert(settingsTable).values({}).returning();
  return row;
}

router.get("/settings", async (_req, res) => {
  const s = await getOrCreate();
  res.json({ success: true, settings: toJson(s) });
});

router.post("/settings", async (req, res) => {
  try {
    const body = req.body as Record<string, unknown>;
    const s = await getOrCreate();
    await db.update(settingsTable)
      .set({
        openaiKey: (body.openai_key as string) ?? s.openaiKey,
        geminiKey: (body.gemini_key as string) ?? s.geminiKey,
        globalCtaLink: (body.global_cta_link as string) ?? s.globalCtaLink,
        autoMirrorEnabled: body.auto_mirror_enabled != null ? Boolean(body.auto_mirror_enabled) : s.autoMirrorEnabled,
        autoRaidEnabled: body.auto_raid_enabled != null ? Boolean(body.auto_raid_enabled) : s.autoRaidEnabled,
        autoPostEnabled: body.auto_post_enabled != null ? Boolean(body.auto_post_enabled) : s.autoPostEnabled,
        autoDmReplyEnabled: body.auto_dm_reply_enabled != null ? Boolean(body.auto_dm_reply_enabled) : s.autoDmReplyEnabled,
        growthHacksEnabled: body.growth_hacks_enabled != null ? Boolean(body.growth_hacks_enabled) : s.growthHacksEnabled,
        rewriteStyle: (body.rewrite_style as string) ?? s.rewriteStyle,
      })
      .where(eq(settingsTable.id, s.id));
    const updated = await getOrCreate();
    res.json({ success: true, settings: toJson(updated) });
  } catch (err) {
    res.status(500).json({ success: false, error: String(err) });
  }
});

function toJson(s: typeof settingsTable.$inferSelect) {
  return {
    openai_key: s.openaiKey,
    gemini_key: s.geminiKey,
    global_cta_link: s.globalCtaLink,
    auto_mirror_enabled: s.autoMirrorEnabled,
    auto_raid_enabled: s.autoRaidEnabled,
    auto_post_enabled: s.autoPostEnabled,
    auto_dm_reply_enabled: s.autoDmReplyEnabled,
    growth_hacks_enabled: s.growthHacksEnabled,
    rewrite_style: s.rewriteStyle,
    proxy_list: [],
  };
}

export default router;
