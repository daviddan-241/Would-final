import { Router } from "express";
import { db } from "@workspace/db";
import { accounts } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

router.get("/accounts", async (_req, res) => {
  const rows = await db.select().from(accounts).orderBy(accounts.createdAt);
  res.json({ success: true, accounts: rows.map(toJson) });
});

router.post("/accounts", async (req, res) => {
  try {
    const { platform, username, password = "", token_session = "", status = "Active" } = req.body as Record<string, string>;
    if (!platform || !username) { res.status(400).json({ success: false, error: "Missing platform or username" }); return; }
    const id = `acc_${Date.now()}`;
    const [row] = await db.insert(accounts).values({ id, platform, username, password, tokenSession: token_session, status }).returning();
    res.json({ success: true, account: toJson(row) });
  } catch (err) {
    logger.error({ err }, "POST /accounts failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/accounts/delete", async (req, res) => {
  const { id } = req.body as { id: string };
  await db.delete(accounts).where(eq(accounts.id, id));
  res.json({ success: true });
});

function toJson(a: typeof accounts.$inferSelect) {
  return { id: a.id, platform: a.platform, username: a.username, status: a.status };
}

export default router;
