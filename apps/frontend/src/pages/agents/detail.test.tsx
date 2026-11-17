import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AgentDetailPage } from "@/pages/agents/detail";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const AGENT_ID = "11111111-1111-4111-8111-111111111111";

const mockAgent = {
  id: AGENT_ID,
  slug: "avax-defi-analyst",
  name: "AVAX DeFi Analyst",
  description: "Phân tích thanh khoản DeFi trên Avalanche.",
  status: "active",
  is_public: true,
  llm_config: {
    provider: "anthropic",
    model: "claude-sonnet-5-5",
    system_prompt: "Analyze DeFi yields.",
    temperature: 0.2,
  },
  skills: ["defi-analytics", "avalanche-c-chain"],
  settlement_mode: "x402",
  price_atomic: 250_000,
  chain_id: 43113,
  erc8004_agent_id: 101,
  agent_uri: "http://localhost:8001/agents/avax-defi-analyst/.well-known/agent-card.json",
  wallet_address: "0x1000000000000000000000000000000000000101",
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
};

const mockWallet = {
  id: "22222222-2222-4222-8222-222222222222",
  provider: "turnkey",
  address: "0x1000000000000000000000000000000000000101",
  chain_id: 43113,
  turnkey_sub_org_id: "sub-org-1",
  turnkey_wallet_id: "wallet-1",
  policy: {
    max_value_per_call_atomic: 1_000_000,
    daily_budget_atomic: 5_000_000,
    allowed_recipients: [],
    allowed_contracts: [],
  },
  created_at: "2026-11-10T00:00:00Z",
};

const mockRegistration = {
  state: "registered",
  erc8004_agent_id: 101,
  agent_uri: mockAgent.agent_uri,
  tx_hash: `0x${"ab".repeat(32)}`,
  explorer_url: `https://testnet.snowtrace.io/tx/0x${"ab".repeat(32)}`,
};

describe("AgentDetailPage", () => {
  it("renders agent configuration, wallet policy, and supports pausing and editing", async () => {
    let current = { ...mockAgent };

    server.use(
      http.get(`*/api/v1/agents/${AGENT_ID}`, () => HttpResponse.json(current)),
      http.patch(`*/api/v1/agents/${AGENT_ID}`, async ({ request }) => {
        const patch = (await request.json()) as Record<string, unknown>;
        current = { ...current, ...patch } as typeof mockAgent;
        return HttpResponse.json(current);
      }),
      http.get(`*/api/v1/agents/${AGENT_ID}/wallet`, () => HttpResponse.json(mockWallet)),
      http.get(`*/api/v1/agents/${AGENT_ID}/wallet/balances`, () =>
        HttpResponse.json({
          address: mockWallet.address,
          chain_id: 43113,
          avax_wei: 500_000_000_000_000_000,
          payment_asset: "USDC",
          payment_asset_atomic: 1_250_000,
        }),
      ),
      http.get(`*/api/v1/agents/${AGENT_ID}/registration`, () => HttpResponse.json(mockRegistration)),
    );

    renderWithProviders(
      <Routes>
        <Route path="/agents/:id" element={<AgentDetailPage />} />
      </Routes>,
      { route: `/agents/${AGENT_ID}` },
    );

    expect(await screen.findByRole("heading", { name: "AVAX DeFi Analyst" })).toBeInTheDocument();
    expect(await screen.findByText(/Token #101/)).toBeInTheDocument();
    expect(await screen.findByText(/1.25 USDC/)).toBeInTheDocument();

    // Pause active agent
    await userEvent.click(screen.getByRole("button", { name: /Tạm dừng/ }));
    expect(await screen.findByRole("button", { name: /Kích hoạt lại/ })).toBeInTheDocument();

    // Edit price inline
    await userEvent.click(screen.getByRole("button", { name: /Chỉnh sửa/ }));
    const priceInput = screen.getByLabelText(/Giá mỗi job/);
    await userEvent.clear(priceInput);
    await userEvent.type(priceInput, "0.75");
    await userEvent.click(screen.getByRole("button", { name: /Lưu thay đổi/ }));

    expect(await screen.findByText("0.75 USDC")).toBeInTheDocument();
  });
});
