import { Router } from "express";
import { db } from "@workspace/db";
import { conversations, messages, autoReplies } from "@workspace/db";
import { eq, desc } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

router.get("/conversations", async (_req, res) => {
  const rows = await db.select().from(conversations).orderBy(desc(conversations.lastMessageTime));
  res.json({ success: true, conversations: rows.map(convToJson) });
});

router.get("/messages", async (req, res) => {
  const { conv_id } = req.query as { conv_id: string };
  if (!conv_id) { res.status(400).json({ success: false, error: "Missing conv_id" }); return; }
  const msgs = await db.select().from(messages).where(eq(messages.convId, conv_id)).orderBy(messages.timestamp);
  await db.update(conversations).set({ unread: 0 }).where(eq(conversations.id, conv_id));
  res.json({ success: true, messages: msgs.map(msgToJson) });
});

router.post("/messages/send", async (req, res) => {
  try {
    const { conv_id, text, profile_id } = req.body as { conv_id: string; text: string; profile_id?: string };
    if (!conv_id || !text) { res.status(400).json({ success: false, error: "Missing conv_id or text" }); return; }
    const now = Date.now() / 1000;
    const [msg] = await db.insert(messages).values({ convId: conv_id, sender: profile_id ?? "Admin", text, timestamp: now, isIncoming: false }).returning();
    await db.update(conversations).set({ lastMessageText: text, lastMessageTime: now, unread: 0 }).where(eq(conversations.id, conv_id));
    res.json({ success: true, message: msgToJson(msg) });
  } catch (err) {
    logger.error({ err }, "POST /messages/send failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/inject_dm", async (req, res) => {
  try {
    const { platform = "telegram", sender_handle, text, avatar = "", profile_id = "" } = req.body as Record<string, string>;
    if (!sender_handle || !text) { res.status(400).json({ success: false, error: "Missing sender_handle or text" }); return; }
    const now = Date.now() / 1000;
    const convId = `conv_${platform}_${sender_handle.replace(/\W/g, "_")}`;
    const existing = await db.select().from(conversations).where(eq(conversations.id, convId));
    if (existing.length === 0) {
      await db.insert(conversations).values({ id: convId, profileId: profile_id, platform, senderHandle: sender_handle, avatar, unread: 1, lastMessageText: text, lastMessageTime: now });
    } else {
      await db.update(conversations).set({ unread: (existing[0].unread ?? 0) + 1, lastMessageText: text, lastMessageTime: now }).where(eq(conversations.id, convId));
    }
    const [msg] = await db.insert(messages).values({ convId, sender: sender_handle, text, timestamp: now, isIncoming: true }).returning();
    res.json({ success: true, message: msgToJson(msg) });
  } catch (err) {
    logger.error({ err }, "POST /inject_dm failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.get("/auto_replies", async (_req, res) => {
  const rows = await db.select().from(autoReplies).orderBy(autoReplies.createdAt);
  res.json({ success: true, rules: rows.map(r => ({ id: r.id, keyword: r.keyword, reply_text: r.replyText, active: r.active })) });
});

router.post("/auto_replies", async (req, res) => {
  try {
    const { keyword, reply_text } = req.body as { keyword: string; reply_text: string };
    if (!keyword || !reply_text) { res.status(400).json({ success: false, error: "Missing keyword or reply_text" }); return; }
    const id = `rule_${Date.now()}`;
    const [row] = await db.insert(autoReplies).values({ id, keyword: keyword.toLowerCase().trim(), replyText: reply_text }).returning();
    res.json({ success: true, rule: { id: row.id, keyword: row.keyword, reply_text: row.replyText, active: row.active } });
  } catch (err) {
    logger.error({ err }, "POST /auto_replies failed");
    res.status(500).json({ success: false, error: "DB error" });
  }
});

router.post("/auto_replies/delete", async (req, res) => {
  const { id } = req.body as { id: string };
  await db.delete(autoReplies).where(eq(autoReplies.id, id));
  res.json({ success: true });
});

function convToJson(c: typeof conversations.$inferSelect) {
  return { id: c.id, profile_id: c.profileId, platform: c.platform, sender_handle: c.senderHandle, avatar: c.avatar, unread: c.unread, last_message_text: c.lastMessageText, last_message_time: c.lastMessageTime };
}

function msgToJson(m: typeof messages.$inferSelect) {
  return { id: m.id, conv_id: m.convId, sender: m.sender, text: m.text, timestamp: m.timestamp, is_incoming: m.isIncoming };
}

export default router;
