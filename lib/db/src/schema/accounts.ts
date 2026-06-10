import { pgTable, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const accounts = pgTable("accounts", {
  id: text("id").primaryKey(),
  platform: text("platform").notNull(),
  username: text("username").notNull(),
  password: text("password").notNull().default(""),
  tokenSession: text("token_session").notNull().default(""),
  status: text("status").notNull().default("Active"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertAccountSchema = createInsertSchema(accounts).omit({ createdAt: true });
export type InsertAccount = z.infer<typeof insertAccountSchema>;
export type Account = typeof accounts.$inferSelect;
