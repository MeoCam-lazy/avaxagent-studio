import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { recoverTypedDataAddress } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MarketplaceAgentProfile } from "@/lib/types";
import type { X402Accept } from "@/lib/x402";
import { MarketplaceAgentPage } from "@/pages/marketplace-agent";
import { renderWithProviders } from "@/test/render";
import { defaultNetworkInfo, server } from "@/test/server";

// Throwaway key standing in for the browser wallet.
const payer = privateKeyToAccount(`0x${"22".repeat(32)}`);

const wallet = vi.hoisted(() => ({
  sign: vi.fn(),
  balance: 5_000_000n as bigint | undefined,
}));

vi.mock("wagmi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("wagmi")>();
  return {
    ...actual,
    useAccount: () => ({ address: payer.address, chainId: 43113, isConnected: true }),
    useConnect: () => ({ connectors: [], connectAsync: vi.fn() }),
    useSwitchChain: () => ({ switchChainAsync: vi.fn() }),
    useSignTypedData: () => ({ signTypedDataAsync: wallet.sign }),
    useReadContract: () => ({ data: wallet.balance }),
  };
});

const A2A = "http://gateway.test/agents/avax-analyst/a2a";
const PAY_TO = "0x00000000000000000000000000000000000000a1";
const TX = `0x${"cd".repeat(32)}`;
const TASK_ID = "55555555-5555-4555-8555-555555555555";

const profile: MarketplaceAgentProfile = {
  slug: "avax-analyst",
  name: "AVAX Analyst",
  description: "Phân tích dữ liệu on-chain Avalanche.",
  skills: ["defi-analytics"],
  settlement_mode: "x402",
  price_atomic: 250_000,
  chain_id: 43113,
  erc8004_agent_id: 7,
  agent_card_url: "http://gateway.test/agents/avax-analyst/.well-known/agent-card.json",
  a2a_url: A2A,
  created_at: "2026-11-01T00:00:00Z",
  jobs_completed: 12,
};

const accept: X402Accept = {
  scheme: "exact",
  network: "eip155:43113",
  asset: defaultNetworkInfo.payment_asset_address as `0x${string}`,
  payTo: PAY_TO,
  amount: "250000",
  maxTimeoutSeconds: 300,
  extra: { name: "USD Coin", version: "2" },
};

interface Rpc {
  method: string;
  params: Record<string, unknown>;
}

/** Fake gateway: 402 without X-PAYMENT, a task with it, then `taskStates` on tasks/get. */
function serveGateway({
  paidStatus = 200,
  paidBody,
  taskStates = ["working", "completed"],
}: { paidStatus?: number; paidBody?: Record<string, unknown>; taskStates?: string[] } = {}) {
  const seen = { paid: [] as { body: Rpc; payment: string }[], quotes: 0, polls: 0 };
  server.use(
    http.get("*/api/v1/marketplace/agents/avax-analyst", () => HttpResponse.json(profile)),
    http.post(A2A, async ({ request }) => {
      const body = (await request.json()) as Rpc;
      if (body.method === "tasks/get") {
        const state = taskStates[Math.min(seen.polls++, taskStates.length - 1)];
        return HttpResponse.json({
          jsonrpc: "2.0",
          result: {
            kind: "task",
            id: TASK_ID,
            status: { state },
            artifacts:
              state === "completed"
                ? [{ name: "deliverable", uri: "file:///x", parts: [{ kind: "text", text: "AVAX: L1s." }] }]
                : [],
          },
        });
      }
      const payment = request.headers.get("X-PAYMENT");
      if (!payment) {
        seen.quotes += 1;
        return HttpResponse.json(
          { x402Version: 1, error: "payment_required", accepts: [accept] },
          { status: 402 },
        );
      }
      seen.paid.push({ body, payment });
      if (paidStatus !== 200) return HttpResponse.json(paidBody, { status: paidStatus });
      const receipt = btoa(
        JSON.stringify({ success: true, transaction: TX, network: "eip155:43113", payer: payer.address }),
      );
      return HttpResponse.json(
        { jsonrpc: "2.0", result: { kind: "task", id: TASK_ID, status: { state: "submitted" } } },
        { headers: { "X-PAYMENT-RESPONSE": receipt } },
      );
    }),
  );
  return seen;
}

function renderProfile(slug = "avax-analyst") {
  return renderWithProviders(
    <Routes>
      <Route path="/marketplace/:slug" element={<MarketplaceAgentPage pollIntervalMs={10} />} />
    </Routes>,
    { route: `/marketplace/${slug}` },
  );
}

async function send(text: string) {
  await userEvent.type(await screen.findByLabelText("Yêu cầu"), text);
  await userEvent.click(screen.getByRole("button", { name: /Trả 0.25 USDC và gửi/ }));
}

beforeEach(() => {
  wallet.balance = 5_000_000n;
  wallet.sign.mockReset();
  // Sign like the wallet would: the requested typed data, with the wallet's own key.
  wallet.sign.mockImplementation((req) => payer.signTypedData({ ...req, account: undefined }));
});

describe("MarketplaceAgentPage", () => {
  it("shows the public profile with price and track record", async () => {
    serveGateway();
    renderProfile();

    expect(await screen.findByRole("heading", { name: "AVAX Analyst" })).toBeInTheDocument();
    expect(screen.getByText("Job hoàn thành").nextSibling).toHaveTextContent("12");
    expect(screen.getByText("#7")).toBeInTheDocument();
    expect(screen.getByText(A2A)).toBeInTheDocument();
  });

  it("pays with a signed EIP-3009 authorization and shows the agent output", async () => {
    const seen = serveGateway();
    renderProfile();
    await send("Tóm tắt roadmap AVAX");

    const result = await screen.findByRole("region", { name: "Kết quả" });
    expect(await within(result).findByText("AVAX: L1s.")).toBeInTheDocument();
    expect(within(result).getByRole("link", { name: /Thanh toán/ })).toHaveAttribute(
      "href",
      `${defaultNetworkInfo.explorer_url}/tx/${TX}`,
    );

    expect(seen.quotes).toBe(1);
    expect(seen.paid).toHaveLength(1);
    const { body, payment } = seen.paid[0];
    expect(body.params.message).toMatchObject({
      role: "user",
      parts: [{ kind: "text", text: "Tóm tắt roadmap AVAX" }],
    });
    // The header is what the gateway verifies: right payee and amount, signed by the payer.
    const envelope = JSON.parse(atob(payment));
    const auth = envelope.payload.authorization;
    expect(auth).toMatchObject({ from: payer.address, to: PAY_TO, value: "250000" });
    const signer = await recoverTypedDataAddress({
      domain: { name: "USD Coin", version: "2", chainId: 43113, verifyingContract: accept.asset },
      types: {
        TransferWithAuthorization: [
          { name: "from", type: "address" },
          { name: "to", type: "address" },
          { name: "value", type: "uint256" },
          { name: "validAfter", type: "uint256" },
          { name: "validBefore", type: "uint256" },
          { name: "nonce", type: "bytes32" },
        ],
      },
      primaryType: "TransferWithAuthorization",
      message: {
        ...auth,
        value: BigInt(auth.value),
        validAfter: BigInt(auth.validAfter),
        validBefore: BigInt(auth.validBefore),
      },
      signature: envelope.payload.signature,
    });
    expect(signer).toBe(payer.address);
  });

  it("does not pay when the wallet rejects the signature", async () => {
    const seen = serveGateway();
    wallet.sign.mockRejectedValue(Object.assign(new Error("User rejected"), { name: "UserRejectedRequestError" }));
    renderProfile();
    await send("hello");

    expect(await screen.findByRole("alert")).toHaveTextContent("Bạn đã từ chối yêu cầu trong ví.");
    expect(seen.paid).toHaveLength(0);
    expect(screen.queryByRole("region", { name: "Kết quả" })).not.toBeInTheDocument();
  });

  it("explains a failed on-chain settlement", async () => {
    serveGateway({ paidStatus: 502, paidBody: { error: "settlement_failed" } });
    renderProfile();
    await send("hello");

    expect(await screen.findByRole("alert")).toHaveTextContent(/không quyết toán được/);
  });

  it("shows the failure reason of a failed task", async () => {
    serveGateway({ taskStates: ["failed"] });
    server.use(
      http.post(A2A, async ({ request }) => {
        const body = (await request.clone().json()) as Rpc;
        if (body.method !== "tasks/get") return undefined;
        return HttpResponse.json({
          jsonrpc: "2.0",
          result: { kind: "task", id: TASK_ID, status: { state: "failed" }, artifacts: [], error: "upstream down" },
        });
      }),
    );
    renderProfile();
    await send("hello");

    const result = await screen.findByRole("region", { name: "Kết quả" });
    expect(await within(result).findByText("upstream down")).toBeInTheDocument();
  });

  it("warns when the wallet balance is below the price", async () => {
    wallet.balance = 100_000n;
    serveGateway();
    renderProfile();

    expect(await screen.findByText(/Không đủ để trả lần gọi này/)).toBeInTheDocument();
    expect(screen.getByText(/số dư 0.1 USDC/)).toBeInTheDocument();
  });

  it("does not offer a browser call for ERC-8183 agents", async () => {
    server.use(
      http.get("*/api/v1/marketplace/agents/avax-analyst", () =>
        HttpResponse.json({ ...profile, settlement_mode: "erc8183" }),
      ),
    );
    renderProfile();

    expect(await screen.findByText(/escrow ERC-8183/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Yêu cầu")).not.toBeInTheDocument();
  });

  it("shows an error for an unlisted agent", async () => {
    server.use(
      http.get("*/api/v1/marketplace/agents/nope", () =>
        HttpResponse.json({ error: "agent_not_found" }, { status: 404 }),
      ),
    );
    renderProfile("nope");
    expect(await screen.findByText(/Lỗi tải dữ liệu/)).toBeInTheDocument();
  });
});
