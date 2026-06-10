import { pgTable, text, boolean, integer, bigint, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const ads = pgTable("ads", {
  id: text("id").primaryKey(),
  platform: text("platform").notNull().default("telegram"),
  content: text("content").notNull(),
  intervalMin: integer("interval_min").notNull().default(30),
  imageUrl: text("image_url").notNull().default(""),
  active: boolean("active").notNull().default(true),
  lastPosted: bigint("last_posted", { mode: "number" }).notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertAdSchema = createInsertSchema(ads).omit({ createdAt: true });
export type InsertAd = z.infer<typeof insertAdSchema>;
export type Ad = typeof ads.$inferSelect;
