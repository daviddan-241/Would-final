import { Router } from "express";
import { db } from "@workspace/db";
import { profiles } from "@workspace/db";

const router = Router();

router.get("/agents", async (_req, res) => {
  try {
    const allProfiles = await db.select({ id: profiles.id, name: profiles.name, niche: profiles.niche, active: profiles.active }).from(profiles);
    const agentList = allProfiles.map(p => ({
      id: p.id,
      name: `${p.name} Agent`,
      type: p.niche,
      status: p.active ? "Running" : "Paused",
      tasks_today: 0,
      messages_sent: 0,
      profile_id: p.id,
    }));
    res.json({
      success: true,
      agents: agentList,
      director: { status: "Ready", active_profiles: allProfiles.filter(p => p.active).length },
    });
  } catch {
    res.json({ success: false, agents: [] });
  }
});

export default router;
