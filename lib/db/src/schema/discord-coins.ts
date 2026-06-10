import { pgTable, serial, text, doublePrecision, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const discordCoins = pgTable("discord_coins", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  symbol: text("symbol").notNull(),
  mint: text("mint").notNull().unique(),
  chain: text("chain").notNull().default("solana"),
  discordLink: text("discord_link").notNull(),
  telegramLink: text("telegram_link").notNull().default(""),
  twitter: text("twitter").notNull().default(""),
  website: text("website").notNull().default(""),
  imageUrl: text("image_url").notNull().default(""),
  pairUrl: text("pair_url").notNull().default(""),
  source: text("source").notNull().default(""),
  foundAt: doublePrecision("found_at").notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertDiscordCoinSchema = createInsertSchema(discordCoins).omit({ id: true, createdAt: true });
export type InsertDiscordCoin = z.infer<typeof insertDiscordCoinSchema>;
export type DiscordCoin = typeof discordCoins.$inferSelect;
