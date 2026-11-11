# Pitch & Live Demo Video Guide

This guide provides a complete **3-minute pitch & live demo script**, pre-recording setup, and step-by-step walkthrough showcasing **Avaxagent Studio** on **Avalanche C-Chain**.

---

## 1. Pre-Recording Setup (1 Minute)

Before hitting record, run the following commands so the studio has all **3 reference agents**, completed sample jobs, deliverables, and withdrawable USDC balances ready:

```bash
# 1. Start PostgreSQL + Redis
make infra

# 2. Seed the 3 reference agents + demo jobs + ledger balances
#    (Optional: pass --owner 0xYourMetaMaskAddress so the seeded earnings belong to your wallet)
make seed

# 3. Start backend services & frontend
make api       # Terminal 1: Control Plane API (:8000)
make gateway   # Terminal 2: A2A + x402 Gateway (:8001)
make worker    # Terminal 3: LLM Job Worker
make web       # Terminal 4: React Frontend (http://localhost:5173)
```

Open these browser tabs before recording:
1. `http://localhost:5173/marketplace` — **Marketplace** with the 3 seeded reference agents.
2. `http://localhost:8001/agents/avax-defi-analyst/.well-known/agent-card.json` — Live **A2A Agent Card** with `x402` and `erc8004` extensions.
3. `http://localhost:5173` — **Studio Dashboard** (connected with Core Wallet / MetaMask on Avalanche Fuji `43113`).

---

## 2. 3-Minute Pitch & Demo Video Storyboard

| Time | Scene | Visual on Screen | Key Talking Points |
| --- | --- | --- | --- |
| **0:00 – 0:30** | **1. Hook & Architecture** | Architecture diagram in `README.md` + header badges (`Avalanche Fuji · 43113`, `ERC-8183 / x402`) | AI agents on Avalanche need three primitives: verifiable on-chain identity (**ERC-8004**), non-custodial policy-guarded wallets (**Turnkey sub-orgs**), and instant micropayments (**x402 USDC EIP-3009** + **ERC-8183 escrow**). **Avaxagent Studio** unifies all three into a single control & data plane. |
| **0:30 – 1:10** | **2. Creating & Registering an Agent** | `/agents/new` 3-Step Wizard (`Cấu hình` → `Ví Turnkey` → `Đăng ký ERC-8004`) | Show how an owner signs in with **SIWE**, configures an agent's LLM prompt, skills, and USDC price per call, provisions an isolated **Turnkey sub-org wallet** with spending guardrails, and mints an on-chain **ERC-8004 identity** on Avalanche C-Chain. |
| **1:10 – 2:00** | **3. Marketplace & Live x402 Pay-Per-Call** | `/marketplace` → `/marketplace/avax-defi-analyst` + `.well-known/agent-card.json` | Showcase the 3 reference agents (**AVAX DeFi Analyst**, **Solidity Security Auditor**, **Avalanche Ecosystem Concierge**). Open **AVAX DeFi Analyst** (`0.25 USDC / lần gọi`), enter a prompt, click **Trả 0.25 USDC và gửi**, sign the gasless **EIP-3009 `TransferWithAuthorization`** in the browser wallet, and watch the A2A task complete live. |
| **2:00 – 2:30** | **4. Verifiable Job Log & Deliverable** | `/jobs` → `/jobs/:id` | Open the job detail page showing the 4-step progress bar (`Thanh toán` → `Chạy LLM` → `Submit` → `Quyết toán`), the real-time event timeline with **Snowtrace** transaction links, and the stored deliverable with its `keccak256` hash. |
| **2:30 – 3:00** | **5. Earnings, Fee Breakdown & Payout** | `/wallet` (`Ví / Thu nhập`) | Open the **Wallet / Earnings** page: highlight the **Gross Income**, **5% Studio Fee (500 bps)**, **95% Net Agent Share**, and **Withdrawable USDC Balance**. Click **Tối đa**, submit **Rút tiền**, and show the payout status (`requested` → `confirmed`) with its Snowtrace explorer link. |

---

## 3. Step-by-Step Narration & Action Script

### Scene 1 — Introduction (0:00 – 0:30)
> *"Welcome to Avaxagent Studio — the full-stack platform for creating, registering, and monetizing autonomous AI agents on Avalanche C-Chain. Every agent created in the studio gets an on-chain ERC-8004 identity, its own isolated Turnkey sub-organization wallet with spending policies, and an A2A-compliant gateway that accepts gasless USDC micropayments via x402 EIP-3009 or on-chain ERC-8183 escrow."*

### Scene 2 — 3 Reference Agents & A2A Agent Card (0:30 – 1:15)
1. Click **Marketplace** in the sidebar (`/marketplace`).
2. Point out the 3 seeded reference agents:
   - **AVAX DeFi Analyst** (`0.25 USDC` / call) — On-chain DeFi & liquidity research.
   - **Solidity Security Auditor** (`0.50 USDC` / call) — EVM, EIP-3009 & ERC-8183 smart-contract auditing.
   - **Avalanche Ecosystem Concierge** (`0.10 USDC` / call) — Bilingual developer guide for A2A & Avalanche.
3. Use the search bar (`Tìm agent`) to filter by skill (e.g., `solidity-audit` or `defi-analytics`).
4. Click into **AVAX DeFi Analyst** (`/marketplace/avax-defi-analyst`) and click **`agent-card.json`** to show the standard A2A metadata advertising `extensions.x402` (`eip155:43113`, USDC token address, `payTo` agent wallet) and `extensions.erc8004` (`agentId: #101`).

### Scene 3 — Browser x402 Pay-Per-Call Flow (1:15 – 2:00)
1. On `/marketplace/avax-defi-analyst`, type in the **Yêu cầu** box:
   ```text
   Summarize USDC liquidity and yield opportunities on Avalanche C-Chain.
   ```
2. Click **`Trả 0.25 USDC và gửi`**:
   - The browser calls `POST /agents/avax-defi-analyst/a2a` and receives an `HTTP 402 Payment Required` challenge.
   - Your wallet prompts you to sign an **EIP-712 `TransferWithAuthorization` (EIP-3009)** — **zero AVAX gas** required from the caller!
   - The gateway settles the USDC payment on-chain, enqueues the job, and polls `tasks/get` until the deliverable output renders right on the page.

### Scene 4 — Job Log & Deliverable Verification (2:00 – 2:30)
1. Click **Log job** (`/jobs`) in the sidebar and select the latest job.
2. Highlight:
   - The 4-stage progression (`Thanh toán` → `Chạy LLM` → `Submit` → `Quyết toán`).
   - The **Timeline** showing `Đã nhận thanh toán`, `Đang chạy LLM`, `Đã lưu deliverable`, and `Đã quyết toán` with clickable **Snowtrace** transaction links.
   - The **Deliverable** card displaying the markdown report, storage URI, and `keccak256` content hash.

### Scene 5 — Studio Fee Breakdown & Owner Withdrawal (2:30 – 3:00)
1. Click **Ví / Thu nhập** (`/wallet`) in the sidebar.
2. Point out the **Số dư có thể rút** card (`Gross`, `Phí studio (5%)`, `Thu nhập ròng (Net)`, `Đã rút`) and the **Phí studio** card (`Agent nhận 95% · Phí vận hành studio 5% (500 bps)`).
3. In the **Rút tiền** card:
   - Select **AVAX DeFi Analyst (`avax-defi-analyst`)**.
   - Click **`Tối đa`** to populate the full withdrawable USDC balance.
   - Click **`Rút tiền`** (`POST /api/v1/billing/payouts`).
4. Show the new row in **Lịch sử rút tiền** transitioning to `confirmed` as the Settle Bot transfers USDC from the agent's Turnkey wallet to the owner's address.

---

## 4. Optional Terminal Demo (A2A + HTTP 402 via `curl`)

You can also show the raw A2A protocol challenge in a terminal during the demo:

```bash
# 1. Inspect the A2A Agent Card
curl -s http://localhost:8001/agents/avax-defi-analyst/.well-known/agent-card.json | jq

# 2. Call the A2A endpoint without payment -> receives HTTP 402 Payment Required with x402 terms
curl -i -X POST http://localhost:8001/agents/avax-defi-analyst/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "demo-1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Analyze Avalanche USDC liquidity"}]
      }
    }
  }'
```
