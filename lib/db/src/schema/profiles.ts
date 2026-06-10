import { pgTable, text, boolean, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const profiles = pgTable("profiles", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  niche: text("niche").notNull().default("casual"),
  bio: text("bio").notNull().default(""),
  ctaLink: text("cta_link").notNull().default(""),
  aiTone: text("ai_tone").notNull().default("casual"),
  avatar: text("avatar").notNull().default(""),
  active: boolean("active").notNull().default(true),
  tgBotToken: text("tg_bot_token").notNull().default(""),
  tgChatId: text("tg_chat_id").notNull().default(""),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertProfileSchema = createInsertSchema(profiles).omit({ createdAt: true });
export type InsertProfile = z.infer<typeof insertProfileSchema>;
export type Profile = typeof profiles.$inferSelect;
