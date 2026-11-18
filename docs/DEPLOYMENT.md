# Environment & Live Agent Deployment Guide

This guide covers deploying **Avaxagent Studio** across local development, Docker Compose, **Avalanche Fuji Testnet (`43113`)**, and **Avalanche C-Chain Mainnet (`43114`)**, including seeding and operating the 3 reference agents.

---

## 1. Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Python + `uv` | Python 3.12+, `uv` 0.5+ | Backend API, Gateway, Workers, Indexer, Settler, SDK |
| Node.js + `pnpm` | Node 20+, `pnpm` 10+ | React 19 + Vite frontend (`apps/frontend`) |
| Docker & Compose | Docker 24+ | PostgreSQL 16 + Redis 7 (and optional containerized apps) |
| Foundry (`forge`) | Latest | Compiling, testing, and deploying ERC-8183 contracts (`contracts/`) |

---

## 2. Environment Configuration

Copy the environment templates before starting the services:

```bash
cp apps/backend/.env.example apps/backend/.env
cp apps/frontend/.env.example apps/frontend/.env
```

### Key Backend Variables (`apps/backend/.env`)

| Category | Variable | Fuji Testnet (`43113`) | Mainnet (`43114`) |
| --- | --- | --- | --- |
| **Chain** | `NETWORK` | `avalanche-fuji` | `avalanche-mainnet` |
| | `RPC_URL` | `https://api.avax-test.network/ext/bc/C/rpc` | `https://api.avax.network/ext/bc/C/rpc` |
| **Auth** | `AUTH_DOMAIN` | `localhost:5173` (or your domain) | `studio.yourdomain.com` |
| | `AUTH_JWT_SECRET` | Dev secret or 32+ byte random string | **Required:** strong random secret (`openssl rand -hex 32`) |
| **Gateway** | `PUBLIC_GATEWAY_URL` | `http://localhost:8001` | `https://gateway.yourdomain.com` |
| | `CORS_ORIGINS` | `["http://localhost:5173"]` | `["https://studio.yourdomain.com"]` |
| **Billing** | `PAYMENT_ASSET` | `USDC` (`0x5425890298aed601595a70AB815c96711a31Bc65`) | `USDC` (`0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E`) |
| | `STUDIO_FEE_BPS` | `500` (5%) | `500` (5%) |
| | `STUDIO_TREASURY_ADDRESS` | Studio fee destination `0x...` | Mainnet treasury `0x...` |
| **Turnkey** | `TURNKEY_ORGANIZATION_ID` | Parent Turnkey Org UUID | Parent Turnkey Org UUID |
| | `TURNKEY_API_PUBLIC_KEY` | Turnkey API public key | Turnkey API public key |
| | `TURNKEY_API_PRIVATE_KEY` | Turnkey API private key | Turnkey API private key |
| **Relayer** | `RELAYER_SIGN_WITH` | Relayer address/key ID (funded with AVAX) | Mainnet relayer address/key ID |
| | `RELAYER_ORGANIZATION_ID` | Turnkey org ID holding the relayer wallet | Turnkey org ID holding the relayer wallet |
| **Worker** | `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | Provider (`openai` or `anthropic`), model ID, and matching API key | Provider (`openai` or `anthropic`), model ID, and matching API key |

---

## 3. Local Demo Deployment & Seeding the 3 Reference Agents

### Step 1: Install dependencies & start infrastructure

```bash
make install          # uv sync --all-packages --all-extras && pnpm install
make infra            # Starts PostgreSQL (:5432) and Redis (:6379)
```

### Step 2: Seed the 3 Reference Agents

Run the idempotent seed script to create the 3 reference agents, their Turnkey wallet metadata, ERC-8004 agent URIs, sample settled A2A jobs, deliverables, and USDC ledger/earnings balances:

```bash
cd apps/backend && uv run python -m app.seed
```

To bind ownership of the 3 seeded reference agents to your own connected browser wallet address (so they also appear under **Agents của bạn** and **Ví / Thu nhập** when you sign in with SIWE):

```bash
cd apps/backend && uv run python -m app.seed --owner 0xYourConnectedWalletAddress
```

The 3 seeded reference agents are:

| Slug | Name | Price (USDC) | Skills |
| --- | --- | --- | --- |
| `avax-defi-analyst` | **AVAX DeFi Analyst** | `0.25 USDC` (`250000`) | `defi-analytics`, `avalanche-c-chain`, `yield-research`, `tokenomics` |
| `solidity-security-auditor` | **Solidity Security Auditor** | `0.50 USDC` (`500000`) | `solidity-audit`, `erc-8004`, `erc-8183`, `reentrancy-check` |
| `avalanche-ecosystem-concierge` | **Avalanche Ecosystem Concierge** | `0.10 USDC` (`100000`) | `translation`, `summarization`, `a2a-protocol`, `avalanche-docs` |

### Step 3: Start the Control Plane, Data Plane & Frontend

Open terminals (or run via Docker Compose in Section 4):

```bash
make api              # Control Plane REST API -> http://localhost:8000/docs
make gateway          # A2A + x402 Gateway     -> http://localhost:8001
make worker           # arq Job Worker (LLM execution + ERC-8004 registration)
make settler          # Settle Bot (Payout transfers + Studio fee sweeps + ERC-8183 settle)
make indexer          # Chain Indexer (ERC-8004 + USDC Transfer + ERC-8183 JobFunded)
make web              # React Frontend         -> http://localhost:5173
```

Verify the services are healthy:

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8001/health | jq
curl -s http://localhost:8001/agents/avax-defi-analyst/.well-known/agent-card.json | jq
```

---

## 4. Docker Compose Full-Stack Deployment

`docker compose --profile apps up -d --build` runs the whole stack:

| Service | Role |
| --- | --- |
| `postgres`, `redis` | State and job queue. Published on `127.0.0.1` only. |
| `migrate` | One-shot `alembic upgrade head`. Every app service waits for it to succeed. |
| `api`, `gateway`, `worker`, `settler`, `indexer` | The backend processes, all from one image. |
| `web` | Caddy: serves the built frontend, proxies `/api` and `/health` to `api`, and fronts the public `gateway`. |

The backend services read `apps/backend/.env`.
Compose overrides `DATABASE_URL`, `REDIS_URL` and `STORAGE_LOCAL_PATH` with container values.
`api`, `gateway` and `worker` share the `agentdata` volume, so deliverables the worker writes are readable by the job log and by A2A `tasks/get`.
`.dockerignore` keeps every `.env` out of the images: secrets reach the containers only at runtime.

### 4.1 Local

```bash
cp apps/backend/.env.example apps/backend/.env
# In apps/backend/.env:
#   AUTH_DOMAIN=localhost            (the host the browser uses; add :PORT if HTTP_PORT is not 80)
#   CORS_ORIGINS=["http://localhost"]
#   PUBLIC_GATEWAY_URL=http://localhost:8001
#   INDEXER_START_BLOCK=<current Fuji block>
docker compose --profile apps up -d --build
```

The studio is on `http://localhost`, and the gateway is on `http://localhost:8001`.
If port 80 or 5432 is taken, set `HTTP_PORT`, `POSTGRES_PORT` or `REDIS_PORT` in a root `.env` (see `deploy/compose.env.example`).

### 4.2 On a server (Fuji or mainnet)

1. Point two DNS records at the server, for example `studio.example.com` and `gateway.example.com`.
2. `cp deploy/compose.env.example .env`, then set `POSTGRES_PASSWORD`, `STUDIO_SITE` and `GATEWAY_SITE`.
3. `cp apps/backend/.env.example apps/backend/.env`, then set at least:
   - `ENVIRONMENT=production` and `AUTH_JWT_SECRET` (`openssl rand -hex 32`).
   - `AUTH_DOMAIN=studio.example.com`, `CORS_ORIGINS=["https://studio.example.com"]` and `PUBLIC_GATEWAY_URL=https://gateway.example.com`.
   - `INDEXER_START_BLOCK` set to the chain head at first deploy.
     From `0`, the first indexer tick scans the whole chain.
   - `TURNKEY_*`, `RELAYER_*`, `STUDIO_TREASURY_ADDRESS` and `LLM_API_KEY`.
4. `docker compose --profile apps up -d --build`.
   Caddy obtains HTTPS certificates for both hostnames on first start, which needs ports 80 and 443 open.
5. Check `https://studio.example.com/health`, `https://gateway.example.com/health` and the marketplace page.

Seed data: `app.seed` without `--live` writes demo rows with placeholder ERC-8004 ids and transaction hashes.
Do not use it on a public deployment, because its explorer links point to transactions that do not exist.
Create agents through the wizard instead.

## 5. Live On-Chain Deployment on Avalanche Fuji (`43113`)

### 5.1 Fund Relayer & Test Wallets on Fuji
1. **AVAX (Gas):** Request Fuji AVAX from the [Avalanche Testnet Faucet](https://core.app/tools/testnet-faucet/).
2. **USDC (Payment Asset):** Request Fuji Testnet USDC (`0x5425890298aed601595a70AB815c96711a31Bc65`) from the [Circle Testnet Faucet](https://faucet.circle.com/) (select **Avalanche Fuji**).

### 5.2 Provision & Register the 3 Reference Agents On-Chain (`--live`)
Once `TURNKEY_*` and `RELAYER_*` are set in `apps/backend/.env` and `make worker` is running:

```bash
cd apps/backend && uv run python -m app.seed --live
# or with a custom owner address:
cd apps/backend && uv run python -m app.seed --live --owner 0xYourWalletAddress
```

1. `WalletService.provision` creates an isolated Turnkey sub-organization and Ethereum wallet per agent with an allowlist policy for Avalanche USDC EIP-712 domains.
2. Fund each newly provisioned agent wallet address with a small amount of Fuji AVAX (`~0.02 AVAX`) for ERC-8004 registration gas.
3. The worker executes `register_agent` against the Avalanche Fuji ERC-8004 `IdentityRegistry` (`0x8004A818BFB912233c491871b3d84c89A494BD9e`) and transitions each agent to `active`.

### 5.3 Deploy the ERC-8183 Escrow Stack (Optional)
By default, agents settle via **x402 (USDC EIP-3009)** without needing custom contracts. To also enable **ERC-8183 on-chain escrow**:

```bash
export DEPLOYER_PRIVATE_KEY=0xYourFujiPrivateKey
export STUDIO_TREASURY_ADDRESS=0xYourTreasuryAddress
make contracts-deploy-fuji
```

Copy the emitted `commerceAddr`, `routerAddr`, and `policyAddr` into `apps/backend/.env`:

```dotenv
COMMERCE_ADDRESS=0x...
ROUTER_ADDRESS=0x...
POLICY_ADDRESS=0x...
```

Restart `make api`, `make gateway`, `make indexer`, and `make settler`. `/health` and `/api/v1/network` will now report `"erc8183_enabled": true`.

---

## 6. Production Deployment Checklist

- [ ] Set `ENVIRONMENT=production` and generate a strong `AUTH_JWT_SECRET` (`openssl rand -hex 32`).
- [ ] Set `NETWORK=avalanche-mainnet` (`chain_id = 43114`) and configure a dedicated Avalanche C-Chain RPC endpoint in `RPC_URL`.
- [ ] Place `:8000` (Control Plane API) and `:8001` (A2A Gateway) behind TLS termination (Nginx / Caddy / Cloudflare) and set `PUBLIC_GATEWAY_URL`, `AUTH_DOMAIN`, and `CORS_ORIGINS` to your production HTTPS origins.
- [ ] Configure `STORAGE_BACKEND=ipfs` (with `STORAGE_API_KEY`) so ERC-8004 agent URIs and job deliverables are pinned to IPFS.
- [ ] Fund the x402 relayer wallet (`RELAYER_SIGN_WITH`) with AVAX to cover `transferWithAuthorization` gas on C-Chain.
