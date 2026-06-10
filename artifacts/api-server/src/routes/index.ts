import { Router, type IRouter } from "express";
import healthRouter from "./health";
import pushRouter from "./push";
import dataRouter from "./data";
import profilesRouter from "./profiles";
import targetsRouter from "./targets";
import adsRouter from "./ads";
import accountsRouter from "./accounts";
import discordCoinsRouter from "./discord-coins";
import settingsRouter from "./settings-route";
import campaignsRouter from "./campaigns";
import agentsRouter from "./agents";
import chatRouter from "./chat";
import inboxRouter from "./inbox";

const router: IRouter = Router();

router.use(healthRouter);
router.use(pushRouter);
router.use(dataRouter);
router.use(profilesRouter);
router.use(targetsRouter);
router.use(adsRouter);
router.use(accountsRouter);
router.use(discordCoinsRouter);
router.use(settingsRouter);
router.use(campaignsRouter);
router.use(agentsRouter);
router.use(chatRouter);
router.use(inboxRouter);

export default router;
