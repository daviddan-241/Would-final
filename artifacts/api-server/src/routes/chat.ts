import { Router } from "express";

const router = Router();

// In-memory store for active pump.fun chat sessions (keyed by mint)
const activeSessions: Record<string, { messages: Array<{ user: string; text: string; timestamp: number }>; status: string }> = {};

router.get("/chat/messages", (req, res) => {
  const mint = req.query.mint as string;
  const sinceTs = parseFloat((req.query.since as string) ?? "0");
  if (!mint) { res.status(400).json({ success: false, error: "Missing mint" }); return; }
  const session = activeSessions[mint];
  if (!session) { res.json({ success: true, messages: [], status: "idle" }); return; }
  const msgs = session.messages.filter(m => m.timestamp > sinceTs);
  res.json({ success: true, messages: msgs, status: session.status });
});

router.get("/chat/status", (req, res) => {
  const mint = req.query.mint as string;
  if (!mint) { res.status(400).json({ success: false, error: "Missing mint" }); return; }
  const session = activeSessions[mint];
  res.json({ success: true, status: session?.status ?? "idle", active_mints: Object.keys(activeSessions) });
});

router.get("/chat/active", (_req, res) => {
  res.json({ success: true, active_mints: Object.keys(activeSessions) });
});

router.post("/chat/start", (req, res) => {
  const { mint } = req.body as { mint: string };
  if (!mint) { res.status(400).json({ success: false, error: "Missing mint" }); return; }
  if (!activeSessions[mint]) {
    activeSessions[mint] = { messages: [], status: "connecting" };
    // Simulate status update
    setTimeout(() => { if (activeSessions[mint]) activeSessions[mint].status = "live"; }, 1500);
  }
  res.json({ success: true, status: activeSessions[mint].status });
});

router.post("/chat/stop", (req, res) => {
  const { mint } = req.body as { mint: string };
  if (mint && activeSessions[mint]) delete activeSessions[mint];
  res.json({ success: true });
});

export default router;
