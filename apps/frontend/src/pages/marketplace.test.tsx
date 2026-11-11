import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { MarketplaceAgent } from "@/lib/types";
import { MarketplacePage } from "@/pages/marketplace";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const demo: MarketplaceAgent = {
  slug: "avax-analyst",
  name: "AVAX Analyst",
  description: "Phân tích dữ liệu on-chain Avalanche.",
  skills: ["defi-analytics"],
  settlement_mode: "x402",
  price_atomic: 250_000,
  chain_id: 43113,
  erc8004_agent_id: 7,
  agent_card_url: "http://gateway.test/agents/avax-analyst/.well-known/agent-card.json",
  a2a_url: "http://gateway.test/agents/avax-analyst/a2a",
};

function serveMarketplace(rows: MarketplaceAgent[]) {
  const queries: string[] = [];
  server.use(
    http.get("*/api/v1/marketplace/agents", ({ request }) => {
      queries.push(new URL(request.url).searchParams.get("q") ?? "");
      return HttpResponse.json(rows);
    }),
  );
  return queries;
}

describe("MarketplacePage", () => {
  it("shows pricing cards that link to the agent profile", async () => {
    serveMarketplace([demo]);
    renderWithProviders(<MarketplacePage />);

    const link = await screen.findByRole("link", { name: /AVAX Analyst/ });
    expect(link).toHaveAttribute("href", "/marketplace/avax-analyst");
    expect(link).toHaveTextContent("0.25");
    await waitFor(() => expect(link).toHaveTextContent("USDC / lần gọi"));
  });

  it("test search debounced single request", async () => {
    const queries = serveMarketplace([demo]);
    renderWithProviders(<MarketplacePage />);
    await screen.findByRole("link", { name: /AVAX Analyst/ });

    await userEvent.type(screen.getByRole("searchbox", { name: "Tìm agent" }), "defi");
    await waitFor(() => expect(queries).toContain("defi"));
    // One request for the initial list and one for the final term, none per keystroke.
    expect(queries).toEqual(["", "defi"]);
  });

  it("explains an empty search", async () => {
    serveMarketplace([]);
    renderWithProviders(<MarketplacePage />);
    expect(await screen.findByText(/Chưa có agent public nào/)).toBeInTheDocument();
  });
});
