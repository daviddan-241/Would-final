import { pgTable, text, integer, boolean, doublePrecision, serial, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const conversations = pgTable("conversations", {
  id: text("id").primaryKey(),
  profileId: text("profile_id").default(""),
  platform: text("platform").notNull().default("telegram"),
  senderHandle: text("sender_handle").notNull(),
  avatar: text("avatar").notNull().default(""),
  unread: integer("unread").notNull().default(0),
  lastMessageText: text("last_message_text").notNull().default(""),
  lastMessageTime: doublePrecision("last_message_time").notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

export const messages = pgTable("messages", {
  id: serial("id").primaryKey(),
  convId: text("conv_id").notNull().references(() => conversations.id),
  sender: text("sender").notNull(),
  text: text("text").notNull(),
  timestamp: doublePrecision("timestamp").notNull(),
  isIncoming: boolean("is_incoming").notNull().default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const autoReplies = pgTable("auto_replies", {
  id: text("id").primaryKey(),
  keyword: text("keyword").notNull(),
  replyText: text("reply_text").notNull(),
  active: boolean("active").notNull().default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertConversationSchema = createInsertSchema(conversations).omit({ createdAt: true });
export const insertMessageSchema = createInsertSchema(messages).omit({ id: true, createdAt: true });
export const insertAutoReplySchema = createInsertSchema(autoReplies).omit({ createdAt: true });

export type Conversation = typeof conversations.$inferSelect;
export type Message = typeof messages.$inferSelect;
export type AutoReply = typeof autoReplies.$inferSelect;
export type InsertConversation = z.infer<typeof insertConversationSchema>;
export type InsertMessage = z.infer<typeof insertMessageSchema>;
export type InsertAutoReply = z.infer<typeof insertAutoReplySchema>;
