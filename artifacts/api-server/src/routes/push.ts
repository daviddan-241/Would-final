import { Router } from "express";
import webpush from "web-push";
import { db } from "@workspace/db";
import { pushSubscriptions } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../lib/logger";

const router = Router();

const VAPID_PUBLIC_KEY = process.env.VAPID_PUBLIC_KEY ?? "";
const VAPID_PRIVATE_KEY = process.env.VAPID_PRIVATE_KEY ?? "";
const VAPID_EMAIL = process.env.VAPID_EMAIL ?? "mailto:admin@aether-smm.app";

if (VAPID_PUBLIC_KEY && VAPID_PRIVATE_KEY) {
  webpush.setVapidDetails(VAPID_EMAIL, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);
}

router.get("/push/vapid-key", (req, res) => {
  res.json({ publicKey: VAPID_PUBLIC_KEY });
});

router.post("/push/subscribe", async (req, res) => {
  try {
    const { endpoint, keys } = req.body as { endpoint: string; keys: { p256dh: string; auth: string } };
    if (!endpoint || !keys?.p256dh || !keys?.auth) {
      res.status(400).json({ error: "Invalid subscription object" });
      return;
    }
    await db
      .insert(pushSubscriptions)
      .values({ endpoint, p256dh: keys.p256dh, auth: keys.auth })
      .onConflictDoNothing();
    req.log.info({ endpoint: endpoint.slice(-20) }, "Push subscription saved");
    res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "Failed to save push subscription");
    res.status(500).json({ error: "Failed to save subscription" });
  }
});

router.delete("/push/unsubscribe", async (req, res) => {
  try {
    const { endpoint } = req.body as { endpoint: string };
    await db.delete(pushSubscriptions).where(eq(pushSubscriptions.endpoint, endpoint));
    res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "Failed to remove push subscription");
    res.status(500).json({ error: "Failed to unsubscribe" });
  }
});

export async function sendPushToAll(payload: { title: string; body: string; url?: string; tag?: string }) {
  if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY) {
    logger.warn("VAPID keys not configured — skipping push notification");
    return { sent: 0, failed: 0 };
  }
  const subs = await db.select().from(pushSubscriptions);
  let sent = 0;
  let failed = 0;
  const expired: string[] = [];
  for (const sub of subs) {
    try {
      await webpush.sendNotification(
        { endpoint: sub.endpoint, keys: { p256dh: sub.p256dh, auth: sub.auth } },
        JSON.stringify(payload),
        { TTL: 86400 }
      );
      sent++;
    } catch (err: any) {
      if (err.statusCode === 410 || err.statusCode === 404) {
        expired.push(sub.endpoint);
      }
      failed++;
    }
  }
  if (expired.length) {
    for (const ep of expired) {
      await db.delete(pushSubscriptions).where(eq(pushSubscriptions.endpoint, ep));
    }
    logger.info({ removed: expired.length }, "Removed expired push subscriptions");
  }
  logger.info({ sent, failed }, "Push notifications dispatched");
  return { sent, failed };
}

router.post("/push/send", async (req, res) => {
  try {
    const { title, body, url, tag, secret } = req.body as {
      title: string; body: string; url?: string; tag?: string; secret?: string;
    };
    if (secret !== process.env.PUSH_WEBHOOK_SECRET && process.env.PUSH_WEBHOOK_SECRET) {
      res.status(401).json({ error: "Unauthorized" });
      return;
    }
    const result = await sendPushToAll({ title, body, url, tag });
    res.json({ success: true, ...result });
  } catch (err) {
    req.log.error({ err }, "Failed to send push notification");
    res.status(500).json({ error: "Failed to send push" });
  }
});

router.post("/push/test", async (req, res) => {
  try {
    const result = await sendPushToAll({
      title: "🛰 Aether SMM OS",
      body: "Push notifications are working!",
      url: "/",
      tag: "test"
    });
    res.json({ success: true, ...result });
  } catch (err) {
    req.log.error({ err }, "Test push failed");
    res.status(500).json({ error: "Test push failed" });
  }
});

export default router;
