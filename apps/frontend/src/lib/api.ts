import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  EarningsSummary,
  FeeSchedule,
  Job,
  JobDeliverable,
  JobEvent,
  LedgerEntry,
  MarketplaceAgent,
  NetworkInfo,
  NonceResponse,
  Payout,
  PayoutCreate,
  RegistrationStatus,
  TokenResponse,
  User,
  VerifyRequest,
  Wallet,
  WalletBalances,
  WalletPolicy,
} from "@/lib/types";

const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export const TOKEN_STORAGE_KEY = "avaxagent.token";
export const AUTH_EXPIRED_EVENT = "auth:expired";
export const AUTH_CHANGE_EVENT = "auth:change";

export function getStoredToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    // Ignore storage errors
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(AUTH_CHANGE_EVENT));
  }
}

export function clearStoredToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore storage errors
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(AUTH_CHANGE_EVENT));
  }
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`API ${status}`);
    this.status = status;
    this.body = body;
  }

  /** Machine-readable error code from the backend body (`{"error": "slug_taken"}`). */
  get code(): string | undefined {
    const body = this.body as { error?: unknown } | null;
    return typeof body?.error === "string" ? body.error : undefined;
  }

  /** Backend route exists but has no logic yet (scaffold → HTTP 501). */
  get notImplemented() {
    return this.status === 501;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getStoredToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  });
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.status === 401) {
    clearStoredToken();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    }
  }
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

const post = (body?: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body ?? {}),
});

const patch = (body?: unknown): RequestInit => ({
  method: "PATCH",
  body: JSON.stringify(body ?? {}),
});

const put = (body?: unknown): RequestInit => ({
  method: "PUT",
  body: JSON.stringify(body ?? {}),
});

/** Typed client for the control-plane REST API (`apps/backend`). */
export const api = {
  network: () => request<NetworkInfo>("/network"),

  auth: {
    nonce: () => request<NonceResponse>("/auth/nonce", post()),
    verify: (body: VerifyRequest) => request<TokenResponse>("/auth/verify", post(body)),
    me: () => request<User>("/auth/me"),
  },

  agents: {
    list: () => request<Agent[]>("/agents"),
    get: (id: string) => request<Agent>(`/agents/${id}`),
    create: (body: AgentCreate) => request<Agent>("/agents", post(body)),
    update: (id: string, body: AgentUpdate) => request<Agent>(`/agents/${id}`, patch(body)),
    delete: (id: string) => request<void>(`/agents/${id}`, { method: "DELETE" }),
    wallet: (id: string) => request<Wallet>(`/agents/${id}/wallet`),
    provisionWallet: (id: string) => request<Wallet>(`/agents/${id}/wallet`, post()),
    updatePolicy: (id: string, body: WalletPolicy) =>
      request<Wallet>(`/agents/${id}/wallet/policy`, put(body)),
    balances: (id: string) => request<WalletBalances>(`/agents/${id}/wallet/balances`),
    registration: (id: string) => request<RegistrationStatus>(`/agents/${id}/registration`),
    register: (id: string) => request<RegistrationStatus>(`/agents/${id}/registration`, post()),
    refreshUri: (id: string) =>
      request<RegistrationStatus>(`/agents/${id}/registration/refresh-uri`, post()),
  },

  marketplace: (q?: string) =>
    request<MarketplaceAgent[]>(
      `/marketplace/agents${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),

  billing: {
    fees: () => request<FeeSchedule>("/billing/fees"),
    summary: () => request<EarningsSummary>("/billing/summary"),
    ledger: () => request<LedgerEntry[]>("/billing/ledger"),
    payouts: () => request<Payout[]>("/billing/payouts"),
    requestPayout: (body: PayoutCreate) => request<Payout>("/billing/payouts", post(body)),
  },

  jobs: {
    list: () => request<Job[]>("/jobs"),
    get: (id: string) => request<Job>(`/jobs/${id}`),
    events: (id: string) => request<JobEvent[]>(`/jobs/${id}/events`),
    deliverable: (id: string) => request<JobDeliverable>(`/jobs/${id}/deliverable`),
  },
};
