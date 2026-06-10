import { pgTable, serial, text, boolean, timestamp } from "drizzle-orm/pg-core";

export const settingsTable = pgTable("settings", {
  id: serial("id").primaryKey(),
  openaiKey: text("openai_key").notNull().default(""),
  geminiKey: text("gemini_key").notNull().default(""),
  globalCtaLink: text("global_cta_link").notNull().default(""),
  autoMirrorEnabled: boolean("auto_mirror_enabled").notNull().default(true),
  autoRaidEnabled: boolean("auto_raid_enabled").notNull().default(true),
  autoPostEnabled: boolean("auto_post_enabled").notNull().default(true),
  autoDmReplyEnabled: boolean("auto_dm_reply_enabled").notNull().default(true),
  growthHacksEnabled: boolean("growth_hacks_enabled").notNull().default(true),
  rewriteStyle: text("rewrite_style").notNull().default("bullish_crypto_enthusiast"),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export type Settings = typeof settingsTable.$inferSelect;
