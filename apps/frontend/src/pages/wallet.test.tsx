import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type {
  Agent,
  EarningsSummary,
  FeeSchedule,
  LedgerEntry,
  Payout,
  PayoutCreate,
} from "@/lib/types";
import { WalletPage } from "@/pages/wallet";
import { renderWithProviders } from "@/test/render";
import { defaultNetworkInfo, server } from "@/test/server";

const AGENT_ID = "11111111-1111-4111-8111-111111111111";
const AGENT_2_ID = "22222222-2222-4222-8222-222222222222";
const OWNER_DEST = "0x000000000000000000000000000000000000dEaD";
const TX_HASH = "0x" + "ab".repeat(32);

const demoAgent: Agent = {
  id: AGENT_ID,
  slug: "avax-bot",
  name: "AVAX Bot",
  description: "Demo agent",
  status: "active",
  is_public: true,
  llm_config: {
    provider: "anthropic",
    model: "claude-sonnet-5-5",
    system_prompt: "",
    temperature: 0.2,
  },
  skills: [],
  settlement_mode: "x402",
  price_atomic: 1_000_000,
  chain_id: 43113,
  erc8004_agent_id: 1,
  agent_uri: null,
  wallet_address: "0x00000000000000000000000000000000000000a1",
  created_at: "2026-11-11T00:00:00Z",
  updated_at: "2026-11-11T00:00:00Z",
};

const demoFees: FeeSchedule = {
  studio_fee_bps: 500,
  payment_asset: "USDC",
  payment_asset_address: "0x5425890298aed601595a70AB815c96711a31Bc65",
  chain_id: 43113,
};

const demoSummary: EarningsSummary = {
  agent_id: null,
  gross_income_atomic: 10_000_000, // 10 USDC
  studio_fees_atomic: 500_000, // 0.5 USDC (5%)
  paid_out_atomic: 2_000_000, // 2 USDC
  withdrawable_atomic: 7_500_000, // 7.5 USDC
};

const demoLedger: LedgerEntry[] = [
  {
    id: "33333333-3333-4333-8333-333333333331",
    agent_id: AGENT_ID,
    job_id: "44444444-4444-4444-8444-444444444444",
    kind: "income",
    asset: demoFees.payment_asset_address,
    amount_atomic: 10_000_000,
    tx_hash: TX_HASH,
    created_at: "2026-11-11T10:00:00Z",
  },
  {
    id: "33333333-3333-4333-8333-333333333332",
    agent_id: AGENT_ID,
    job_id: "44444444-4444-4444-8444-444444444444",
    kind: "studio_fee",
    asset: demoFees.payment_asset_address,
    amount_atomic: 500_000,
    tx_hash: TX_HASH,
    created_at: "2026-11-11T10:00:00Z",
  },
];

function serveBilling({
  agents = [demoAgent],
  fees = demoFees,
  summary = demoSummary,
  ledger = demoLedger,
  payouts = [] as Payout[],
}: {
  agents?: Agent[];
  fees?: FeeSchedule;
  summary?: EarningsSummary;
  ledger?: LedgerEntry[];
  payouts?: Payout[];
} = {}) {
  const createdPayouts: PayoutCreate[] = [];
  const summaryQueries: (string | null)[] = [];
  let currentSummary = { ...summary };
  let currentPayouts = [...payouts];

  server.use(
    http.get("*/api/v1/agents", () => HttpResponse.json(agents)),
    http.get("*/api/v1/billing/fees", () => HttpResponse.json(fees)),
    http.get("*/api/v1/billing/summary", ({ request }) => {
      const aid = new URL(request.url).searchParams.get("agent_id");
      summaryQueries.push(aid);
      return HttpResponse.json(currentSummary);
    }),
    http.get("*/api/v1/billing/ledger", () => HttpResponse.json(ledger)),
    http.get("*/api/v1/billing/payouts", () => HttpResponse.json(currentPayouts)),
    http.post("*/api/v1/billing/payouts", async ({ request }) => {
      const body = (await request.json()) as PayoutCreate;
      createdPayouts.push(body);
      if (body.amount_atomic > currentSummary.withdrawable_atomic) {
        return HttpResponse.json(
          { error: "insufficient_balance", withdrawable: currentSummary.withdrawable_atomic },
          { status: 422 },
        );
      }
      const created: Payout = {
        id: "99999999-9999-4999-8999-999999999999",
        agent_id: body.agent_id,
        destination: body.destination,
        asset: fees.payment_asset_address,
        amount_atomic: body.amount_atomic,
        status: "confirmed",
        tx_hash: TX_HASH,
        created_at: "2026-11-11T12:00:00Z",
      };
      currentSummary = {
        ...currentSummary,
        paid_out_atomic: currentSummary.paid_out_atomic + body.amount_atomic,
        withdrawable_atomic: currentSummary.withdrawable_atomic - body.amount_atomic,
      };
      currentPayouts = [created, ...currentPayouts];
      return HttpResponse.json(created, { status: 202 });
    }),
  );

  return { createdPayouts, summaryQueries };
}

describe("WalletPage", () => {
  it("shows withdrawable balance, fee breakdowns, and ledger entries with explorer links", async () => {
    serveBilling();
    renderWithProviders(<WalletPage />);

    expect(await screen.findByTestId("withdrawable-balance")).toHaveTextContent("7.5 USDC");
    expect(screen.getByText("10 USDC")).toBeInTheDocument();
    expect(screen.getByText("0.5 USDC")).toBeInTheDocument();
    expect(screen.getByText("9.5 USDC")).toBeInTheDocument();
    expect(screen.getByText("2 USDC")).toBeInTheDocument();

    // Studio fee schedule breakdown (5% = 500 bps, 95% net to agent)
    expect(await screen.findByText("5% (500 bps)")).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();

    // Ledger shows token symbol and links tx_hash to the network explorer
    expect(await screen.findByText("income")).toBeInTheDocument();
    expect(screen.getByText("studio_fee")).toBeInTheDocument();
    const txLinks = screen.getAllByRole("link", { name: /0xabab/ });
    expect(txLinks[0]).toHaveAttribute("href", `${defaultNetworkInfo.explorer_url}/tx/${TX_HASH}`);
  });

  it("submits a withdrawal request and refreshes balances and payout history", async () => {
    const user = userEvent.setup();
    const { createdPayouts } = serveBilling();
    renderWithProviders(<WalletPage />);

    expect(await screen.findByTestId("withdrawable-balance")).toHaveTextContent("7.5 USDC");

    const destInput = screen.getByLabelText("Địa chỉ nhận");
    await user.clear(destInput);
    await user.type(destInput, OWNER_DEST);

    // Click "Tối đa" to fill 7.5 USDC, or type a custom amount
    await user.click(screen.getByRole("button", { name: "Tối đa" }));
    expect(screen.getByLabelText(/Số tiền/)).toHaveValue("7.5");

    await user.clear(screen.getByLabelText(/Số tiền/));
    await user.type(screen.getByLabelText(/Số tiền/), "2.5");
    await user.click(screen.getByRole("button", { name: "Rút tiền" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Đã tạo yêu cầu rút 2.5 USDC");
    expect(createdPayouts).toEqual([
      {
        agent_id: AGENT_ID,
        destination: OWNER_DEST,
        amount_atomic: 2_500_000,
      },
    ]);

    // Summary and payout history refreshed
    await waitFor(() =>
      expect(screen.getByTestId("withdrawable-balance")).toHaveTextContent("5 USDC"),
    );
    expect(await screen.findByText("confirmed")).toBeInTheDocument();
  });

  it("displays an insufficient_balance error when requesting more than withdrawable", async () => {
    const user = userEvent.setup();
    serveBilling();
    renderWithProviders(<WalletPage />);

    await screen.findByTestId("withdrawable-balance");

    await user.type(screen.getByLabelText("Địa chỉ nhận"), OWNER_DEST);
    await user.type(screen.getByLabelText(/Số tiền/), "20");
    await user.click(screen.getByRole("button", { name: "Rút tiền" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Số dư khả dụng không đủ (tối đa 7.5 USDC).");
    expect(screen.getByLabelText(/Số tiền/)).toHaveAttribute("aria-invalid", "true");
  });

  it("validates destination address and decimal precision before calling the API", async () => {
    const user = userEvent.setup();
    const { createdPayouts } = serveBilling();
    renderWithProviders(<WalletPage />);

    await screen.findByTestId("withdrawable-balance");

    await user.type(screen.getByLabelText("Địa chỉ nhận"), "not-an-address");
    await user.type(screen.getByLabelText(/Số tiền/), "1.1234567");
    await user.click(screen.getByRole("button", { name: "Rút tiền" }));

    expect(await screen.findByText(/Địa chỉ nhận phải có dạng 0x/)).toBeInTheDocument();
    expect(screen.getByText(/tối đa 6 chữ số thập phân/)).toBeInTheDocument();
    expect(createdPayouts).toHaveLength(0);
  });

  it("polls payouts while a withdrawal is requested or submitted and stops when confirmed", async () => {
    const stages: Payout[][] = [
      [
        {
          id: "99999999-9999-4999-8999-999999999999",
          agent_id: AGENT_ID,
          destination: OWNER_DEST,
          asset: demoFees.payment_asset_address,
          amount_atomic: 1_000_000,
          status: "requested",
          tx_hash: null,
          created_at: "2026-11-11T12:00:00Z",
        },
      ],
      [
        {
          id: "99999999-9999-4999-8999-999999999999",
          agent_id: AGENT_ID,
          destination: OWNER_DEST,
          asset: demoFees.payment_asset_address,
          amount_atomic: 1_000_000,
          status: "confirmed",
          tx_hash: TX_HASH,
          created_at: "2026-11-11T12:00:00Z",
        },
      ],
    ];
    let polls = 0;
    serveBilling();
    server.use(
      http.get("*/api/v1/billing/payouts", () => {
        const res = stages[Math.min(polls, stages.length - 1)];
        polls += 1;
        return HttpResponse.json(res);
      }),
    );

    renderWithProviders(<WalletPage pollIntervalMs={15} />);

    expect(await screen.findByText("confirmed")).toBeInTheDocument();
    const afterConfirmed = polls;
    await new Promise((r) => setTimeout(r, 80));
    expect(polls).toBe(afterConfirmed);
  });

  it("filters summary and ledger by selected agent", async () => {
    const user = userEvent.setup();
    const secondAgent: Agent = { ...demoAgent, id: AGENT_2_ID, slug: "second-bot", name: "Second Bot" };
    const { summaryQueries } = serveBilling({ agents: [demoAgent, secondAgent] });

    renderWithProviders(<WalletPage />);
    await screen.findByTestId("withdrawable-balance");

    await user.selectOptions(screen.getByLabelText("Lọc theo agent"), AGENT_2_ID);
    await waitFor(() => expect(summaryQueries).toContain(AGENT_2_ID));
  });
});
