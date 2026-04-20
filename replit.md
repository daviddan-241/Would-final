# Workspace

## Overview

pnpm workspace monorepo using TypeScript + Python Telegram bot for Alpha Circle crypto auto-sender.

## Alpha Circle Telegram Bot (`bot/`)

Premium crypto + forex trading signal bot targeting whales, alpha traders, and professional forex traders.
Posts to channel -1003461143473 as @dextrendiing_bot. GitHub: github.com/daviddan-241/Would-final

### Features
- Scans DEX Screener every 3 min (Solana $10K–$800K MC range)
- Sends initial call cards (TokenScan exact style) + chart
- Tracks and posts gain updates at 20/50/100/200/300/500/1000% milestones
- EVERY gain update includes double VIP payment button (100%)
- 50% of new calls include VIP button
- Forex/macro signal job: posts EUR/USD, GBP/USD, BTC, ETH, XAU, SOL signals every ~4-5h
- VIP promo post every ~7h
- DM payment flow: SOL/ETH/BNB on-chain verification → group link
- Health server + Render self-ping for 24/7 deployment

### Card Design (TokenScan-exact)
- Dark near-black background with subtle radial glow
- LEFT panel: TokenScan logo (top-left) | $SYMBOL in neon green | HUGE white multiplier | "Called at $X | Xh Xm" | username badge (green pill)
- RIGHT panel: character image fading in from left (6 custom TokenScan characters + 4 pepe variants)
- 3 card types: `build_update_card`, `build_call_card`, `build_forex_card`

### Bot Files
- `bot/bot.py` — Main bot: DEX scan job + forex signal job + VIP promo job + payment handlers
- `bot/dex_fetcher.py` — DEX Screener API
- `bot/chart_generator.py` — Candlestick chart (dark DEX style)
- `bot/image_generator.py` — TokenScan-exact card generator
- `bot/assets/char_*.png` — 6 character images extracted from TokenScan reference cards
- `bot/blockchain_verify.py` — On-chain tx verification for SOL, ETH, BNB
- `bot/payment_handler.py` — ConversationHandler: chain→wallet→tx hash→group link
- `bot/render.yaml` — Render deployment config

### Payment Flow
All gain-update posts include a double VIP button (100%). 50% of new call posts include one.
VIP promo posts go out every ~7h standalone. Clicking any button opens a DM with the bot:
1. Shows SOL/ETH/BNB payment addresses
2. User picks chain
3. Bot asks for wallet address (paying from)
4. Bot asks for transaction hash
5. Bot verifies tx on-chain via public RPC
6. If valid → sends group link: https://t.me/+b7UesS3ulxxlZDdk

Payment addresses:
- SOL: 46ZKRuURaASKEcKBafnPZgMaTqBL8RK8TssZgZzFCBzn
- ETH: 0x479F8bdD340bD7276D6c7c9B3fF86EF2315f857A
- BNB: bnb189gjjucwltdpnlemrveakf0q6xg0smfqdh6869

### Image Variety
15 color themes (matrix, electric, neon_purple, fire, cyber, blood, gold, teal, pink, mint, chrome, amber, indigo, aqua, lava) × 12 background styles (gradient radial/diagonal/horizontal/corner, noise field, grid lines, hex pattern, circuit lines, particle dots, wave lines, star field, scan lines) = 180+ distinct visual combinations per card generation.

### Required Secrets
- TELEGRAM_TOKEN — your bot token from @BotFather
- CHAT_ID — your channel/group ID
- BOT_USERNAME — (optional) your bot's @username, needed for the VIP join button

### Running
`cd bot && python bot.py`

### Deploy on Render
1. Push to GitHub
2. New Web Service → Worker type
3. Set env vars: TELEGRAM_TOKEN, CHAT_ID, SUPPORT_USERNAME
4. Build: `pip install -r requirements.txt`
5. Start: `python bot.py`

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Structure

```text
artifacts-monorepo/
├── artifacts/              # Deployable applications
│   └── api-server/         # Express API server
├── lib/                    # Shared libraries
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── scripts/                # Utility scripts (single workspace package)
│   └── src/                # Individual .ts scripts, run via `pnpm --filter @workspace/scripts run <script>`
├── pnpm-workspace.yaml     # pnpm workspace (artifacts/*, lib/*, lib/integrations/*, scripts)
├── tsconfig.base.json      # Shared TS options (composite, bundler resolution, es2022)
├── tsconfig.json           # Root TS project references
└── package.json            # Root package with hoisted devDeps
```

## TypeScript & Composite Projects

Every package extends `tsconfig.base.json` which sets `composite: true`. The root `tsconfig.json` lists all packages as project references. This means:

- **Always typecheck from the root** — run `pnpm run typecheck` (which runs `tsc --build --emitDeclarationOnly`). This builds the full dependency graph so that cross-package imports resolve correctly. Running `tsc` inside a single package will fail if its dependencies haven't been built yet.
- **`emitDeclarationOnly`** — we only emit `.d.ts` files during typecheck; actual JS bundling is handled by esbuild/tsx/vite...etc, not `tsc`.
- **Project references** — when package A depends on package B, A's `tsconfig.json` must list B in its `references` array. `tsc --build` uses this to determine build order and skip up-to-date packages.

## Root Scripts

- `pnpm run build` — runs `typecheck` first, then recursively runs `build` in all packages that define it
- `pnpm run typecheck` — runs `tsc --build --emitDeclarationOnly` using project references

## Packages

### `artifacts/api-server` (`@workspace/api-server`)

Express 5 API server. Routes live in `src/routes/` and use `@workspace/api-zod` for request and response validation and `@workspace/db` for persistence.

- Entry: `src/index.ts` — reads `PORT`, starts Express
- App setup: `src/app.ts` — mounts CORS, JSON/urlencoded parsing, routes at `/api`
- Routes: `src/routes/index.ts` mounts sub-routers; `src/routes/health.ts` exposes `GET /health` (full path: `/api/health`)
- Depends on: `@workspace/db`, `@workspace/api-zod`
- `pnpm --filter @workspace/api-server run dev` — run the dev server
- `pnpm --filter @workspace/api-server run build` — production esbuild bundle (`dist/index.cjs`)
- Build bundles an allowlist of deps (express, cors, pg, drizzle-orm, zod, etc.) and externalizes the rest

### `lib/db` (`@workspace/db`)

Database layer using Drizzle ORM with PostgreSQL. Exports a Drizzle client instance and schema models.

- `src/index.ts` — creates a `Pool` + Drizzle instance, exports schema
- `src/schema/index.ts` — barrel re-export of all models
- `src/schema/<modelname>.ts` — table definitions with `drizzle-zod` insert schemas (no models definitions exist right now)
- `drizzle.config.ts` — Drizzle Kit config (requires `DATABASE_URL`, automatically provided by Replit)
- Exports: `.` (pool, db, schema), `./schema` (schema only)

Production migrations are handled by Replit when publishing. In development, we just use `pnpm --filter @workspace/db run push`, and we fallback to `pnpm --filter @workspace/db run push-force`.

### `lib/api-spec` (`@workspace/api-spec`)

Owns the OpenAPI 3.1 spec (`openapi.yaml`) and the Orval config (`orval.config.ts`). Running codegen produces output into two sibling packages:

1. `lib/api-client-react/src/generated/` — React Query hooks + fetch client
2. `lib/api-zod/src/generated/` — Zod schemas

Run codegen: `pnpm --filter @workspace/api-spec run codegen`

### `lib/api-zod` (`@workspace/api-zod`)

Generated Zod schemas from the OpenAPI spec (e.g. `HealthCheckResponse`). Used by `api-server` for response validation.

### `lib/api-client-react` (`@workspace/api-client-react`)

Generated React Query hooks and fetch client from the OpenAPI spec (e.g. `useHealthCheck`, `healthCheck`).

### `scripts` (`@workspace/scripts`)

Utility scripts package. Each script is a `.ts` file in `src/` with a corresponding npm script in `package.json`. Run scripts via `pnpm --filter @workspace/scripts run <script>`. Scripts can import any workspace package (e.g., `@workspace/db`) by adding it as a dependency in `scripts/package.json`.
