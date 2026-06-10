import { Router } from "express";
import { db } from "@workspace/db";
import { discordCoins } from "@workspace/db";
import { desc, eq } from "drizzle-orm";

const router = Router();

router.get("/discord_coins", async (_req, res) => {
  try {
    const coins = await db.select().from(discordCoins).orderBy(desc(discordCoins.foundAt)).limit(100);
    res.json({ success: true, coins: coins.map(toJson) });
  } catch {
    res.json({ success: true, coins: [] });
  }
});

router.post("/discord_coins", async (req, res) => {
  try {
    const { name, symbol, mint, chain = "solana", discord_link, telegram_link = "", twitter = "", website = "", image_url = "", pair_url = "", source = "" } = req.body as Record<string, string>;
    if (!mint || !discord_link) { res.status(400).json({ success: false, error: "Missing mint or discord_link" }); return; }
    const existing = await db.select({ id: discordCoins.id }).from(discordCoins).where(eq(discordCoins.mint, mint));
    if (existing.length > 0) { res.json({ success: true, duplicate: true }); return; }
    const [row] = await db.insert(discordCoins).values({ name, symbol, mint, chain, discordLink: discord_link, telegramLink: telegram_link, twitter, website, imageUrl: image_url, pairUrl: pair_url, source, foundAt: Date.now() / 1000 }).returning();
    res.json({ success: true, coin: toJson(row) });
  } catch (err) {
    res.status(500).json({ success: false, error: String(err) });
  }
});

function toJson(c: typeof discordCoins.$inferSelect) {
  return { id: c.id, name: c.name, symbol: c.symbol, mint: c.mint, chain: c.chain, discord_link: c.discordLink, telegram_link: c.telegramLink, twitter: c.twitter, website: c.website, image_url: c.imageUrl, pair_url: c.pairUrl, source: c.source, found_at: c.foundAt };
}

export default router;
