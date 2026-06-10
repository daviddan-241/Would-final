import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import { createProxyMiddleware } from "http-proxy-middleware";
import router from "./routes";
import { logger } from "./lib/logger";

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Own routes first (push notifications, healthz)
app.use("/api", router);

// Proxy all remaining /api/* calls to the Python bot server
const PYTHON_BOT_URL = process.env.PYTHON_BOT_URL;
if (PYTHON_BOT_URL) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: PYTHON_BOT_URL,
      changeOrigin: true,
      pathRewrite: { "^/api": "/api" },
      on: {
        error: (err, _req, res) => {
          logger.warn({ err }, "Python bot proxy error");
          (res as express.Response)
            .status(502)
            .json({ error: "Bot server unreachable" });
        },
      },
    }),
  );
  logger.info({ PYTHON_BOT_URL }, "Python bot proxy enabled");
} else {
  logger.info("PYTHON_BOT_URL not set — Python bot API proxy disabled");
}

export default app;
