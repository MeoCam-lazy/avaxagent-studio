import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { DashboardPage } from "@/pages/dashboard";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const base = {
  description: "",
  is_public: false,
  llm_config: { provider: "anthropic", model: "m", system_prompt: "", temperature: 0.2 },
  skills: [],
  settlement_mode: "x402",
  price_atomic: 0,
  chain_id: 43113,
  erc8004_agent_id: null,
  agent_uri: null,
  wallet_address: null,
  created_at: "2026-11-11T00:00:00Z",
  updated_at: "2026-11-11T00:00:00Z",
};

describe("DashboardPage", () => {
  it("lists unfinished agents with a resume link", async () => {
    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json([
          { ...base, id: "a1", slug: "live", name: "Live Agent", status: "active" },
          { ...base, id: "a2", slug: "draft", name: "Draft Agent", status: "draft" },
          { ...base, id: "a3", slug: "broken", name: "Broken Agent", status: "failed" },
        ]),
      ),
      http.get("*/api/v1/billing/summary", () => HttpResponse.json({}, { status: 501 })),
    );
    renderWithProviders(<DashboardPage />);

    const pending = await screen.findByRole("list");
    expect(within(pending).queryByText("Live Agent")).not.toBeInTheDocument();
    const links = within(pending).getAllByRole("link", { name: /Tiếp tục thiết lập/ });
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/agents/new?id=a2",
      "/agents/new?id=a3",
    ]);
  });

  it("offers to create the first agent when there are none", async () => {
    server.use(
      http.get("*/api/v1/agents", () => HttpResponse.json([])),
      http.get("*/api/v1/billing/summary", () => HttpResponse.json({}, { status: 501 })),
    );
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText(/Chưa có agent nào/)).toBeInTheDocument();
  });
});
