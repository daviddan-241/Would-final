import { pgTable, text, integer, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const growthCampaigns = pgTable("growth_campaigns", {
  id: text("id").primaryKey(),
  niche: text("niche").notNull(),
  keywords: text("keywords").notNull().default(""),
  ctaLink: text("cta_link").notNull().default(""),
  platform: text("platform").notNull().default("telegram"),
  status: text("status").notNull().default("Active"),
  impressionsGenerated: integer("impressions_generated").notNull().default(0),
  clicksGenerated: integer("clicks_generated").notNull().default(0),
  leadsCaptured: integer("leads_captured").notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertGrowthCampaignSchema = createInsertSchema(growthCampaigns).omit({ createdAt: true });
export type InsertGrowthCampaign = z.infer<typeof insertGrowthCampaignSchema>;
export type GrowthCampaign = typeof growthCampaigns.$inferSelect;
