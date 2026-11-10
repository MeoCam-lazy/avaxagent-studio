import { useQuery } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { QueryState } from "@/components/query-state";
import { api } from "@/lib/api";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

function TestAgentsView() {
  const query = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  return (
    <QueryState query={query} feature="GET /agents">
      {(agents) => <div>Loaded {agents.length} agents</div>}
    </QueryState>
  );
}

describe("QueryState", () => {
  it('renders "Chưa implement" on HTTP 501', async () => {
    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ error: "not_implemented", feature: "agents" }, { status: 501 }),
      ),
    );

    renderWithProviders(<TestAgentsView />);

    expect(await screen.findByText("Chưa implement")).toBeInTheDocument();
    expect(screen.getByText("GET /agents")).toBeInTheDocument();
  });

  it("renders the error text on HTTP 500", async () => {
    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ error: "internal_error" }, { status: 500 }),
      ),
    );

    renderWithProviders(<TestAgentsView />);

    expect(await screen.findByText(/Lỗi tải dữ liệu: API 500/)).toBeInTheDocument();
  });

  it("renders its children on success", async () => {
    server.use(http.get("*/api/v1/agents", () => HttpResponse.json([])));

    renderWithProviders(<TestAgentsView />);

    expect(await screen.findByText("Loaded 0 agents")).toBeInTheDocument();
  });
});
