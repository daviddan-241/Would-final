import { pgTable, serial, integer, doublePrecision, timestamp } from "drizzle-orm/pg-core";

export const analyticsTable = pgTable("analytics", {
  id: serial("id").primaryKey(),
  impressions: integer("impressions").notNull().default(0),
  clicks: integer("clicks").notNull().default(0),
  leads: integer("leads").notNull().default(0),
  conversionRate: doublePrecision("conversion_rate").notNull().default(0),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export type Analytics = typeof analyticsTable.$inferSelect;
