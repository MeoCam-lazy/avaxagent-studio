import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, ExternalLink, Loader2 } from "lucide-react";

import { ComingSoon } from "@/components/coming-soon";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useNetwork } from "@/hooks/use-network";
import { ApiError, api } from "@/lib/api";
import { formatAtomic, parseAtomic } from "@/lib/format";
import { cn } from "@/lib/utils";
import { WIZARD_STEPS, type WizardStep } from "@/lib/agent-setup";
import type { Agent, RegistrationStatus, SettlementMode, Wallet } from "@/lib/types";

/** Same rule as backend SLUG_PATTERN (agents/schemas.py). */
const SLUG_PATTERN = "^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$";

/** Defaults of the backend `LLMConfig` (agents/schemas.py). */
const DEFAULT_PROVIDER = "anthropic";
const DEFAULT_MODEL = "claude-sonnet-5-5";
const DEFAULT_TEMPERATURE = "0.2";

export function Stepper({ step }: { step: WizardStep }) {
  const current = step === "done" ? WIZARD_STEPS.length : WIZARD_STEPS.findIndex((s) => s.key === step);
  return (
    <ol className="flex flex-wrap items-center gap-2 text-sm" aria-label="Tiến trình tạo agent">
      {WIZARD_STEPS.map((s, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={s.key} className="flex items-center gap-2" aria-current={state === "current" ? "step" : undefined}>
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-medium",
                state === "done" && "bg-primary text-primary-foreground border-primary",
                state === "current" && "border-primary text-primary",
                state === "todo" && "text-muted-foreground",
              )}
            >
              {state === "done" ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span className={cn(state === "todo" && "text-muted-foreground", state === "current" && "font-medium")}>
              {s.label}
            </span>
            {i < WIZARD_STEPS.length - 1 && <span className="bg-border mx-1 hidden h-px w-10 sm:block" />}
          </li>
        );
      })}
    </ol>
  );
}

function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-destructive text-sm">
          {error}
        </p>
      ) : (
        hint && <p className="text-muted-foreground text-xs">{hint}</p>
      )}
    </div>
  );
}

const ERROR_MESSAGES: Record<string, string> = {
  wallet_required: "Agent chưa có ví. Quay lại bước tạo ví.",
  agent_not_found: "Không tìm thấy agent.",
};

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body as { reason?: unknown } | null;
    if (error.code === "feature_disabled" && typeof body?.reason === "string") {
      return `Server chưa bật tính năng này: ${body.reason}`;
    }
    if (error.code) return ERROR_MESSAGES[error.code] ?? `Lỗi: ${error.code}`;
    return `Lỗi máy chủ (HTTP ${error.status}).`;
  }
  return `Lỗi: ${error instanceof Error ? error.message : String(error)}`;
}

function ErrorText({ error, feature }: { error: unknown; feature: string }) {
  if (!error) return null;
  if (error instanceof ApiError && error.notImplemented) return <ComingSoon feature={feature} />;
  return <p className="text-destructive text-sm">{describeError(error)}</p>;
}

const selectClass = "border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm";

export function ConfigStep({ onCreated }: { onCreated: (agent: Agent) => void }) {
  const queryClient = useQueryClient();
  const { data: net } = useNetwork();
  const [mode, setMode] = useState<SettlementMode>("x402");
  const [fieldErrors, setFieldErrors] = useState<{ slug?: string; price?: string }>({});

  const create = useMutation({
    mutationFn: api.agents.create,
    onSuccess: (agent) => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      onCreated(agent);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "slug_taken") {
        setFieldErrors({ slug: "Slug này đã được dùng." });
      }
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    let priceAtomic: bigint;
    try {
      priceAtomic = parseAtomic(String(f.get("price") ?? ""));
    } catch (err) {
      setFieldErrors({ price: err instanceof Error ? err.message : String(err) });
      return;
    }
    if (priceAtomic > BigInt(Number.MAX_SAFE_INTEGER)) {
      setFieldErrors({ price: "Giá quá lớn." });
      return;
    }
    setFieldErrors({});
    create.mutate({
      slug: String(f.get("slug")),
      name: String(f.get("name")),
      description: String(f.get("description") ?? ""),
      skills: String(f.get("skills") ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      llm_config: {
        provider: DEFAULT_PROVIDER,
        model: String(f.get("model") || DEFAULT_MODEL),
        system_prompt: String(f.get("system_prompt") ?? ""),
        temperature: Number(f.get("temperature") || DEFAULT_TEMPERATURE),
      },
      settlement_mode: mode,
      price_atomic: Number(priceAtomic),
      is_public: f.get("is_public") === "on",
    });
  }

  const slugTaken = create.error instanceof ApiError && create.error.code === "slug_taken";

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Cấu hình</CardTitle>
        <CardDescription>Tên, slug, prompt và giá mỗi job. Có thể sửa lại sau.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="Tên" htmlFor="name">
            <Input id="name" name="name" required maxLength={128} />
          </Field>
          <Field
            label="Slug"
            htmlFor="slug"
            error={fieldErrors.slug}
            hint="Dùng trong URL A2A: /agents/{slug}/a2a. Chữ thường, số và dấu gạch ngang."
          >
            <Input
              id="slug"
              name="slug"
              required
              pattern={SLUG_PATTERN}
              placeholder="my-agent"
              aria-invalid={fieldErrors.slug ? true : undefined}
              aria-describedby={fieldErrors.slug ? "slug-error" : undefined}
              onChange={() => fieldErrors.slug && setFieldErrors((e) => ({ ...e, slug: undefined }))}
            />
          </Field>
          <Field label="Mô tả" htmlFor="description">
            <Textarea id="description" name="description" />
          </Field>
          <Field label="System prompt" htmlFor="system_prompt">
            <Textarea id="system_prompt" name="system_prompt" rows={4} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Model" htmlFor="model">
              <Input id="model" name="model" defaultValue={DEFAULT_MODEL} />
            </Field>
            <Field label="Temperature" htmlFor="temperature">
              <Input
                id="temperature"
                name="temperature"
                type="number"
                min={0}
                max={2}
                step="0.1"
                defaultValue={DEFAULT_TEMPERATURE}
              />
            </Field>
          </div>
          <Field label="Skills" htmlFor="skills" hint="Phân cách bằng dấu phẩy.">
            <Input id="skills" name="skills" placeholder="summarize, translate" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Settlement" htmlFor="mode">
              <select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as SettlementMode)}
                className={selectClass}
              >
                <option value="x402">x402 (USDC EIP-3009)</option>
                <option value="erc8183" disabled={!net?.erc8183_enabled}>
                  ERC-8183 escrow{net?.erc8183_enabled ? "" : " (chưa deploy trên Avalanche)"}
                </option>
              </select>
            </Field>
            <Field
              label={`Giá mỗi job (${net?.payment_asset ?? "USDC"})`}
              htmlFor="price"
              error={fieldErrors.price}
            >
              <Input
                id="price"
                name="price"
                inputMode="decimal"
                defaultValue="0"
                onChange={() => fieldErrors.price && setFieldErrors((e) => ({ ...e, price: undefined }))}
                aria-invalid={fieldErrors.price ? true : undefined}
                aria-describedby={fieldErrors.price ? "price-error" : undefined}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="is_public" /> Hiển thị trên Marketplace
          </label>

          {!slugTaken && <ErrorText error={create.error} feature="POST /agents" />}

          <Button type="submit" disabled={create.isPending}>
            {create.isPending && <Loader2 className="animate-spin" />}
            {create.isPending ? "Đang tạo…" : "Tạo agent"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export function WalletStep({ agentId, onProvisioned }: { agentId: string; onProvisioned: () => void }) {
  const queryClient = useQueryClient();
  const provision = useMutation({
    mutationFn: () => api.agents.provisionWallet(agentId),
    onSuccess: (wallet) => {
      queryClient.setQueryData(["agents", agentId, "wallet"], wallet);
      queryClient.setQueryData<Agent>(["agents", agentId], (prev) =>
        prev ? { ...prev, wallet_address: wallet.address } : prev,
      );
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      onProvisioned();
    },
    onError: (err) => {
      // Already provisioned (double submit, or resumed after a reload): just move on.
      if (err instanceof ApiError && (err.code === "wallet_exists" || err.code === "agent_not_in_draft")) {
        onProvisioned();
      }
    },
  });

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Ví Turnkey</CardTitle>
        <CardDescription>
          Mỗi agent có một sub-org Turnkey riêng với policy giới hạn chi tiêu. Studio không giữ private key.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ErrorText error={provision.error} feature="POST /agents/{id}/wallet" />
        <Button onClick={() => provision.mutate()} disabled={provision.isPending}>
          {provision.isPending && <Loader2 className="animate-spin" />}
          {provision.isPending ? "Đang tạo ví…" : "Tạo ví Turnkey"}
        </Button>
      </CardContent>
    </Card>
  );
}

const TERMINAL_STATES = new Set(["registered", "failed"]);

export function RegisterStep({
  agentId,
  pollIntervalMs,
  onRegistered,
}: {
  agentId: string;
  pollIntervalMs: number;
  onRegistered: (status: RegistrationStatus) => void;
}) {
  const queryClient = useQueryClient();
  const { data: net } = useNetwork();
  const agent = useQuery({ queryKey: ["agents", agentId], queryFn: () => api.agents.get(agentId) });
  // The agent read already carries the address; the wallet read is only a fallback.
  const wallet = useQuery({
    queryKey: ["agents", agentId, "wallet"],
    queryFn: () => api.agents.wallet(agentId),
    enabled: agent.isSuccess && !agent.data.wallet_address,
  });
  const address =
    agent.data?.wallet_address ??
    wallet.data?.address ??
    queryClient.getQueryData<Wallet>(["agents", agentId, "wallet"])?.address;
  const balances = useQuery({
    queryKey: ["agents", agentId, "wallet", "balances"],
    queryFn: () => api.agents.balances(agentId),
  });
  const status = useQuery({
    queryKey: ["agents", agentId, "registration"],
    queryFn: () => api.agents.registration(agentId),
    refetchInterval: (q) => (q.state.data?.state === "pending" ? pollIntervalMs : false),
  });
  const register = useMutation({
    mutationFn: () => api.agents.register(agentId),
    onSuccess: (s) => queryClient.setQueryData(["agents", agentId, "registration"], s),
    onError: (err) => {
      // Registration already started elsewhere: show the real state instead of an error.
      if (err instanceof ApiError && err.code === "agent_not_provisioning") {
        queryClient.invalidateQueries({ queryKey: ["agents", agentId, "registration"] });
      }
    },
  });

  const state = status.data?.state;
  useEffect(() => {
    if (state === "registered" && status.data) onRegistered(status.data);
  }, [state, status.data, onRegistered]);

  const busy = register.isPending || state === "pending";
  const noGas = balances.data != null && BigInt(balances.data.avax_wei) === 0n;

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Đăng ký ERC-8004</CardTitle>
        <CardDescription>
          Agent tự ký tx đăng ký identity trên Identity Registry, nên ví agent cần một ít AVAX để trả gas.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-4 border-b py-1.5 sm:col-span-2">
            <dt className="text-muted-foreground">Ví agent</dt>
            <dd className="font-mono text-xs break-all">{address ?? (agent.isPending ? "…" : "—")}</dd>
          </div>
          <div className="flex justify-between gap-4 border-b py-1.5">
            <dt className="text-muted-foreground">AVAX (gas)</dt>
            <dd className="font-mono text-xs">
              {balances.data ? formatAtomic(balances.data.avax_wei, 18) : balances.isError ? "—" : "…"}
            </dd>
          </div>
          <div className="flex justify-between gap-4 border-b py-1.5">
            <dt className="text-muted-foreground">{net?.payment_asset ?? "USDC"}</dt>
            <dd className="font-mono text-xs">
              {balances.data ? formatAtomic(balances.data.payment_asset_atomic) : balances.isError ? "—" : "…"}
            </dd>
          </div>
        </dl>
        {balances.isError && (
          <p className="text-muted-foreground text-xs">
            Không đọc được số dư ví. {describeError(balances.error)}
          </p>
        )}

        {noGas && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <p>
              Ví agent chưa có AVAX nên tx đăng ký sẽ thất bại. Gửi một ít AVAX vào địa chỉ trên rồi bấm
              đăng ký.
              {net?.network === "avalanche-fuji" && (
                <>
                  {" "}
                  Testnet:{" "}
                  <a
                    href="https://core.app/tools/testnet-faucet/"
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    Fuji faucet
                  </a>
                  .
                </>
              )}
            </p>
          </div>
        )}

        {state === "failed" && (
          <p className="text-destructive text-sm">
            Đăng ký thất bại. Kiểm tra số dư AVAX của ví agent rồi thử lại.
          </p>
        )}
        {state === "pending" && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" /> Đang chờ tx đăng ký được xác nhận…
          </p>
        )}
        {!(register.error instanceof ApiError && register.error.code === "agent_not_provisioning") && (
          <ErrorText error={register.error} feature="POST /agents/{id}/registration" />
        )}
        <ErrorText error={status.error} feature="GET /agents/{id}/registration" />

        {state !== "pending" && state !== "registered" && (
          <Button onClick={() => register.mutate()} disabled={busy || status.isPending}>
            {register.isPending && <Loader2 className="animate-spin" />}
            {state === "failed" ? "Thử lại" : "Đăng ký ERC-8004"}
          </Button>
        )}
        {status.data?.explorer_url && TERMINAL_STATES.has(state ?? "") && (
          <a
            href={status.data.explorer_url}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground inline-flex items-center gap-1 text-sm underline"
          >
            Xem tx <ExternalLink className="size-3.5" />
          </a>
        )}
      </CardContent>
    </Card>
  );
}
