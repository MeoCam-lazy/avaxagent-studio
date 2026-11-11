import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes, useParams } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { Agent, AgentCreate, RegistrationStatus, Wallet } from "@/lib/types";
import { NewAgentPage } from "@/pages/agents/new";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const AGENT_ID = "11111111-1111-4111-8111-111111111111";
const WALLET_ADDRESS = "0x00000000000000000000000000000000000000aa";

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: AGENT_ID,
    slug: "my-agent",
    name: "My Agent",
    description: "",
    status: "draft",
    is_public: false,
    llm_config: {
      provider: "anthropic",
      model: "claude-sonnet-5-5",
      system_prompt: "",
      temperature: 0.2,
    },
    skills: [],
    settlement_mode: "x402",
    price_atomic: 0,
    chain_id: 43113,
    erc8004_agent_id: null,
    agent_uri: null,
    wallet_address: null,
    created_at: "2026-11-11T00:00:00Z",
    updated_at: "2026-11-11T00:00:00Z",
    ...overrides,
  };
}

const wallet: Wallet = {
  id: "22222222-2222-4222-8222-222222222222",
  provider: "turnkey",
  address: WALLET_ADDRESS,
  chain_id: 43113,
  turnkey_sub_org_id: "sub-org",
  policy: {
    max_value_per_call_atomic: 1_000_000,
    daily_budget_atomic: 50_000_000,
    allowed_contracts: [],
    allow_erc8183: false,
  },
};

function registration(state: string, extra: Partial<RegistrationStatus> = {}): RegistrationStatus {
  return {
    chain_id: 43113,
    identity_registry: "0x8004A818BFB912233c491871b3d84c89A494BD9e",
    state,
    erc8004_agent_id: null,
    agent_uri: null,
    tx_hash: null,
    explorer_url: null,
    ...extra,
  };
}

const balances = {
  address: WALLET_ADDRESS,
  chain_id: 43113,
  avax_wei: 10 ** 17,
  payment_asset: "USDC",
  payment_asset_atomic: 0,
};

function DetailStub() {
  const { id } = useParams();
  return <p>detail page {id}</p>;
}

function renderWizard(route = "/agents/new") {
  return renderWithProviders(
    <Routes>
      <Route path="/agents/new" element={<NewAgentPage pollIntervalMs={10} />} />
      <Route path="/agents/:id" element={<DetailStub />} />
    </Routes>,
    { route },
  );
}

async function fillConfig(user: ReturnType<typeof userEvent.setup>, price = "0.25") {
  await user.type(screen.getByLabelText(/^Tên/), "My Agent");
  await user.type(screen.getByLabelText(/^Slug/), "my-agent");
  const priceInput = screen.getByLabelText(/^Giá mỗi job/);
  await user.clear(priceInput);
  await user.type(priceInput, price);
  await user.click(screen.getByRole("button", { name: "Tạo agent" }));
}

/** Registration endpoint that answers `states` in order, repeating the last one. */
function registrationHandlers(states: string[]) {
  const posts: unknown[] = [];
  let current = "not_registered";
  let polls = 0;
  return {
    posts,
    handlers: [
      http.post(`*/api/v1/agents/${AGENT_ID}/registration`, async ({ request }) => {
        posts.push(await request.json());
        current = "pending";
        polls = 0;
        return HttpResponse.json(registration("pending"), { status: 202 });
      }),
      http.get(`*/api/v1/agents/${AGENT_ID}/registration`, () => {
        if (current === "not_registered") return HttpResponse.json(registration(current));
        const state = states[Math.min(polls, states.length - 1)];
        polls += 1;
        return HttpResponse.json(
          registration(
            state,
            state === "registered" ? { erc8004_agent_id: 7, tx_hash: "0xabc" } : {},
          ),
        );
      }),
    ],
  };
}

function happyBackend(states: string[]) {
  const created: AgentCreate[] = [];
  const reg = registrationHandlers(states);
  server.use(
    http.post("*/api/v1/agents", async ({ request }) => {
      const body = (await request.json()) as AgentCreate;
      created.push(body);
      return HttpResponse.json(agent({ slug: body.slug, name: body.name }), { status: 201 });
    }),
    http.post(`*/api/v1/agents/${AGENT_ID}/wallet`, () =>
      HttpResponse.json(wallet, { status: 201 }),
    ),
    http.get(`*/api/v1/agents/${AGENT_ID}/wallet/balances`, () => HttpResponse.json(balances)),
    ...reg.handlers,
  );
  return { created, posts: reg.posts };
}

describe("NewAgentPage wizard", () => {
  it("test full happy path reaches done", async () => {
    const user = userEvent.setup();
    const { created, posts } = happyBackend(["pending", "pending", "registered"]);
    renderWizard();

    await fillConfig(user);
    await user.click(await screen.findByRole("button", { name: "Tạo ví Turnkey" }));
    expect(await screen.findByText(WALLET_ADDRESS)).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Đăng ký ERC-8004" }));
    expect(await screen.findByText(`detail page ${AGENT_ID}`)).toBeInTheDocument();
    expect(created).toHaveLength(1);
    expect(posts).toHaveLength(1);
  });

  it("test slug_taken shows field error", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/v1/agents", () =>
        HttpResponse.json({ error: "slug_taken" }, { status: 409 }),
      ),
    );
    renderWizard();

    await fillConfig(user);

    const slug = screen.getByLabelText(/^Slug/);
    expect(await screen.findByText("Slug này đã được dùng.")).toBeInTheDocument();
    expect(slug).toHaveAttribute("aria-invalid", "true");
    // Still on the config step.
    expect(screen.getByRole("button", { name: "Tạo agent" })).toBeInTheDocument();
  });

  it("test registration failed shows retry", async () => {
    const user = userEvent.setup();
    const { posts } = happyBackend(["pending", "failed"]);
    renderWizard();

    await fillConfig(user);
    await user.click(await screen.findByRole("button", { name: "Tạo ví Turnkey" }));
    await user.click(await screen.findByRole("button", { name: "Đăng ký ERC-8004" }));

    const retry = await screen.findByRole("button", { name: "Thử lại" });
    expect(screen.getByText(/Đăng ký thất bại/)).toBeInTheDocument();

    server.use(...registrationHandlers(["registered"]).handlers);
    await user.click(retry);
    expect(await screen.findByText(`detail page ${AGENT_ID}`)).toBeInTheDocument();
    expect(posts).toHaveLength(1); // the retry went to the fresh handler
  });

  it("test price converts to atomic", async () => {
    const user = userEvent.setup();
    const { created } = happyBackend(["registered"]);
    renderWizard();

    await fillConfig(user, "0.25");

    await screen.findByRole("button", { name: "Tạo ví Turnkey" });
    expect(created[0]?.price_atomic).toBe(250_000);
    expect(created[0]?.llm_config?.model).toBe("claude-sonnet-5-5");
  });

  it("rejects a price with more than 6 decimals without calling the API", async () => {
    const user = userEvent.setup();
    const { created } = happyBackend(["registered"]);
    renderWizard();

    await fillConfig(user, "1.0000001");

    expect(await screen.findByText(/tối đa 6 chữ số thập phân/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Giá mỗi job/)).toHaveAttribute("aria-invalid", "true");
    expect(created).toHaveLength(0);
  });

  it("resumes a draft agent at the wallet step", async () => {
    happyBackend(["registered"]);
    server.use(http.get(`*/api/v1/agents/${AGENT_ID}`, () => HttpResponse.json(agent())));
    renderWizard(`/agents/new?id=${AGENT_ID}`);

    expect(await screen.findByRole("button", { name: "Tạo ví Turnkey" })).toBeInTheDocument();
  });

  it("resumes a failed agent at the register step with retry", async () => {
    server.use(
      http.get(`*/api/v1/agents/${AGENT_ID}`, () =>
        HttpResponse.json(agent({ status: "failed", wallet_address: WALLET_ADDRESS })),
      ),
      http.get(`*/api/v1/agents/${AGENT_ID}/registration`, () =>
        HttpResponse.json(registration("failed")),
      ),
      http.get(`*/api/v1/agents/${AGENT_ID}/wallet/balances`, () => HttpResponse.json(balances)),
    );
    renderWizard(`/agents/new?id=${AGENT_ID}`);

    expect(await screen.findByRole("button", { name: "Thử lại" })).toBeInTheDocument();
  });

  it("warns when the agent wallet has no AVAX for gas", async () => {
    const user = userEvent.setup();
    happyBackend(["registered"]);
    server.use(
      http.get(`*/api/v1/agents/${AGENT_ID}/wallet/balances`, () =>
        HttpResponse.json({ ...balances, avax_wei: 0 }),
      ),
    );
    renderWizard();

    await fillConfig(user);
    await user.click(await screen.findByRole("button", { name: "Tạo ví Turnkey" }));

    await waitFor(() => expect(screen.getByText(/chưa có AVAX/)).toBeInTheDocument());
  });
});

describe("NewAgentPage wizard errors", () => {
  it("explains a disabled backend feature in words", async () => {
    const user = userEvent.setup();
    happyBackend(["registered"]);
    server.use(
      http.post(`*/api/v1/agents/${AGENT_ID}/wallet`, () =>
        HttpResponse.json(
          { error: "feature_disabled", feature: "turnkey", reason: "TURNKEY_* not configured" },
          { status: 409 },
        ),
      ),
    );
    renderWizard();

    await fillConfig(user);
    await user.click(await screen.findByRole("button", { name: "Tạo ví Turnkey" }));

    expect(
      await screen.findByText("Server chưa bật tính năng này: TURNKEY_* not configured"),
    ).toBeInTheDocument();
  });

  it("moves on when the wallet already exists", async () => {
    const user = userEvent.setup();
    happyBackend(["registered"]);
    server.use(
      http.post(`*/api/v1/agents/${AGENT_ID}/wallet`, () =>
        HttpResponse.json({ error: "wallet_exists" }, { status: 409 }),
      ),
      http.get(`*/api/v1/agents/${AGENT_ID}/wallet`, () => HttpResponse.json(wallet)),
    );
    renderWizard();

    await fillConfig(user);
    await user.click(await screen.findByRole("button", { name: "Tạo ví Turnkey" }));

    expect(await screen.findByRole("button", { name: "Đăng ký ERC-8004" })).toBeInTheDocument();
  });
});

describe("NewAgentPage register step reads", () => {
  it("shows the address from the agent and explains unreadable balances", async () => {
    server.use(
      http.get(`*/api/v1/agents/${AGENT_ID}`, () =>
        HttpResponse.json(agent({ status: "provisioning", wallet_address: WALLET_ADDRESS })),
      ),
      http.get(`*/api/v1/agents/${AGENT_ID}/registration`, () =>
        HttpResponse.json(registration("not_registered")),
      ),
      http.get(`*/api/v1/agents/${AGENT_ID}/wallet/balances`, () =>
        HttpResponse.json(
          { error: "feature_disabled", feature: "turnkey", reason: "TURNKEY_* not configured" },
          { status: 409 },
        ),
      ),
    );
    renderWizard(`/agents/new?id=${AGENT_ID}`);

    expect(await screen.findByText(WALLET_ADDRESS)).toBeInTheDocument();
    expect(await screen.findByText(/Không đọc được số dư ví/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đăng ký ERC-8004" })).toBeInTheDocument();
  });
});
