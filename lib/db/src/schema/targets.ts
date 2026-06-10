import { pgTable, text, boolean, bigint, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const targets = pgTable("targets", {
  id: text("id").primaryKey(),
  platform: text("platform").notNull().default("twitter"),
  handle: text("handle").notNull(),
  destination: text("destination").notNull().default("TG_GROUP"),
  active: boolean("active").notNull().default(true),
  lastPostId: text("last_post_id").notNull().default(""),
  lastChecked: bigint("last_checked", { mode: "number" }).notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertTargetSchema = createInsertSchema(targets).omit({ createdAt: true });
export type InsertTarget = z.infer<typeof insertTargetSchema>;
export type Target = typeof targets.$inferSelect;
