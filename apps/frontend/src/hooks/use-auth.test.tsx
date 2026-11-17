import { act, renderHook, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { RequireAuth } from "@/components/require-auth";
import { useAuth } from "@/hooks/use-auth";
import { TOKEN_STORAGE_KEY, api } from "@/lib/api";
import { DashboardPage } from "@/pages/dashboard";
import { MarketplacePage } from "@/pages/marketplace";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/server";

const signMessageMock = vi.fn<({ message }: { message: string }) => Promise<`0x${string}`>>();

vi.mock("wagmi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("wagmi")>();
  return {
    ...actual,
    useAccount: () => ({
      address: "0x000000000000000000000000000000000000dEaD" as const,
      chainId: 43113,
      isConnected: true,
    }),
    useSignMessage: () => ({
      signMessageAsync: signMessageMock,
    }),
    useConnect: () => ({
      connectors: [],
      connectAsync: vi.fn(),
    }),
    useDisconnect: () => ({
      disconnect: vi.fn(),
    }),
    useSwitchChain: () => ({
      switchChainAsync: vi.fn(),
    }),
  };
});

describe("useAuth and route protection", () => {
  it("test login stores token and sends bearer", async () => {
    signMessageMock.mockResolvedValueOnce("0xdeadbeef");
    let capturedAuthHeader: string | null = null;

    server.use(
      http.post("*/api/v1/auth/nonce", () => HttpResponse.json({ nonce: "nonce-123" })),
      http.post("*/api/v1/auth/verify", () =>
        HttpResponse.json({
          access_token: "signed-jwt-token",
          token_type: "bearer",
          address: "0x000000000000000000000000000000000000dEaD",
        }),
      ),
      http.get("*/api/v1/agents", ({ request }) => {
        capturedAuthHeader = request.headers.get("authorization");
        return HttpResponse.json([]);
      }),
    );

    const { result } = renderHook(() => useAuth());
    expect(result.current.status).toBe("anon");

    await act(async () => {
      await result.current.login();
    });

    expect(result.current.status).toBe("authed");
    expect(result.current.token).toBe("signed-jwt-token");
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBe("signed-jwt-token");

    await api.agents.list();
    expect(capturedAuthHeader).toBe("Bearer signed-jwt-token");
  });

  it("test SIWE message has domain, chainId 43113, nonce", async () => {
    let signedMessage = "";
    signMessageMock.mockImplementationOnce(async ({ message }) => {
      signedMessage = message;
      return "0x123456";
    });

    server.use(
      http.post("*/api/v1/auth/nonce", () => HttpResponse.json({ nonce: "expected-nonce-99" })),
      http.post("*/api/v1/auth/verify", () =>
        HttpResponse.json({
          access_token: "tok",
          token_type: "bearer",
          address: "0x000000000000000000000000000000000000dEaD",
        }),
      ),
    );

    const { result } = renderHook(() => useAuth());
    await act(async () => {
      await result.current.login();
    });

    const expectedDomain = window.location.host || "localhost:5173";
    expect(signedMessage).toContain(
      `${expectedDomain} wants you to sign in with your Ethereum account:`,
    );
    expect(signedMessage).toContain("Chain ID: 43113");
    expect(signedMessage).toContain("Nonce: expected-nonce-99");
  });

  it("test 401 clears token", async () => {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, "stale-token");

    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ error: "token_expired" }, { status: 401 }),
      ),
    );

    const { result } = renderHook(() => useAuth());
    expect(result.current.status).toBe("authed");

    await act(async () => {
      await api.agents.list().catch(() => null);
    });

    await waitFor(() => {
      expect(result.current.status).toBe("anon");
    });
    expect(result.current.token).toBeNull();
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
  });

  it("test marketplace accessible anonymously while protected routes require auth", async () => {
    server.use(
      http.get("*/api/v1/marketplace/agents", () =>
        HttpResponse.json([
          {
            slug: "public-bot",
            name: "Public Bot",
            description: "Available to everyone",
            skills: ["translate"],
            settlement_mode: "x402",
            price_atomic: 100_000,
            chain_id: 43113,
            erc8004_agent_id: 1,
            agent_card_url: "http://localhost:8001/agents/public-bot/.well-known/agent-card.json",
          },
        ]),
      ),
    );

    const { unmount } = renderWithProviders(
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/" element={<DashboardPage />} />
        </Route>
        <Route path="/marketplace" element={<MarketplacePage />} />
      </Routes>,
      { route: "/marketplace" },
    );

    expect(await screen.findByText("Public Bot")).toBeInTheDocument();
    unmount();

    renderWithProviders(
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/" element={<DashboardPage />} />
        </Route>
        <Route path="/marketplace" element={<MarketplacePage />} />
      </Routes>,
      { route: "/" },
    );

    expect(screen.getByText("Kết nối ví")).toBeInTheDocument();
  });
});
