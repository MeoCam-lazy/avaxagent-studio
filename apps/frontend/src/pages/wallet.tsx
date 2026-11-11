import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Check, ExternalLink, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/hooks/use-auth";
import { useNetwork } from "@/hooks/use-network";
import { ApiError, api } from "@/lib/api";
import {
  CHAIN_NAMES,
  PAYMENT_DECIMALS,
  assetLabel,
  formatAtomic,
  parseAtomic,
  shortAddress,
} from "@/lib/format";
import type { Agent, LedgerKind, Payout } from "@/lib/types";

/** How often payouts and balances refresh while a withdrawal is in flight. */
export const PAYOUT_POLL_MS = 3000;

const ACTIVE_PAYOUT_STATUSES = new Set<string>(["requested", "submitted"]);
const ADDRESS_PATTERN = /^0x[0-9a-fA-F]{40}$/;
const selectClass = "border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm";

const KIND_VARIANT: Record<LedgerKind, "default" | "secondary" | "destructive" | "outline"> = {
  income: "default",
  studio_fee: "secondary",
  payout: "outline",
  gas: "secondary",
};

const ERROR_MESSAGES: Record<string, string> = {
  agent_not_found: "Không tìm thấy agent.",
  insufficient_balance: "Số dư khả dụng không đủ để rút số tiền này.",
};

function describeError(error: unknown, assetSymbol: string): string {
  if (error instanceof ApiError) {
    const body = error.body as { reason?: unknown; withdrawable?: unknown } | null;
    if (error.code === "insufficient_balance") {
      if (typeof body?.withdrawable === "number") {
        return `Số dư khả dụng không đủ (tối đa ${formatAtomic(body.withdrawable)} ${assetSymbol}).`;
      }
      return ERROR_MESSAGES.insufficient_balance;
    }
    if (error.code === "feature_disabled" && typeof body?.reason === "string") {
      return `Server chưa bật tính năng này: ${body.reason}`;
    }
    if (error.code) return ERROR_MESSAGES[error.code] ?? `Lỗi: ${error.code}`;
    return `Lỗi máy chủ (HTTP ${error.status}).`;
  }
  return `Lỗi: ${error instanceof Error ? error.message : String(error)}`;
}

export function WalletPage({ pollIntervalMs = PAYOUT_POLL_MS }: { pollIntervalMs?: number }) {
  const queryClient = useQueryClient();
  const { data: net } = useNetwork();
  const { address: connectedAddress } = useAuth();
  const [filterAgentId, setFilterAgentId] = useState<string>("");

  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  const fees = useQuery({ queryKey: ["billing", "fees"], queryFn: api.billing.fees });
  const payouts = useQuery({
    queryKey: ["billing", "payouts"],
    queryFn: api.billing.payouts,
    refetchInterval: (q) =>
      q.state.data?.some((p) => ACTIVE_PAYOUT_STATUSES.has(p.status)) ? pollIntervalMs : false,
  });

  const hasActivePayout =
    payouts.data?.some((p) => ACTIVE_PAYOUT_STATUSES.has(p.status)) ?? false;

  const summary = useQuery({
    queryKey: filterAgentId ? ["billing", "summary", filterAgentId] : ["billing", "summary"],
    queryFn: () => api.billing.summary(filterAgentId || undefined),
    refetchInterval: () => (hasActivePayout ? pollIntervalMs : false),
  });
  const ledger = useQuery({
    queryKey: filterAgentId ? ["billing", "ledger", filterAgentId] : ["billing", "ledger"],
    queryFn: () => api.billing.ledger(filterAgentId || undefined),
    refetchInterval: () => (hasActivePayout ? pollIntervalMs : false),
  });

  // Refresh summary & ledger when a polled payout finishes confirming or failing.
  const confirmedOrFailedCount = useMemo(
    () =>
      payouts.data?.filter((p) => p.status === "confirmed" || p.status === "failed").length ?? 0,
    [payouts.data],
  );
  useEffect(() => {
    if (confirmedOrFailedCount > 0) {
      void queryClient.invalidateQueries({ queryKey: ["billing", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["billing", "ledger"] });
    }
  }, [confirmedOrFailedCount, queryClient]);

  const assetSymbol = fees.data?.payment_asset ?? net?.payment_asset ?? "USDC";
  const assetMeta = fees.data ?? net;

  const agentOptions = useMemo(() => {
    if (agents.data && agents.data.length > 0) {
      return agents.data.map((a) => ({ id: a.id, label: `${a.name} (${a.slug})` }));
    }
    const seen = new Set<string>();
    const fallback: { id: string; label: string }[] = [];
    const pushId = (id: string | null | undefined) => {
      if (id && !seen.has(id)) {
        seen.add(id);
        fallback.push({ id, label: id.slice(0, 8) });
      }
    };
    pushId(summary.data?.agent_id);
    ledger.data?.forEach((e) => pushId(e.agent_id));
    payouts.data?.forEach((p) => pushId(p.agent_id));
    return fallback;
  }, [agents.data, summary.data?.agent_id, ledger.data, payouts.data]);

  const agentsById = useMemo(() => {
    const map = new Map<string, Agent>();
    agents.data?.forEach((a) => map.set(a.id, a));
    return map;
  }, [agents.data]);

  return (
    <>
      <PageHeader
        title="Ví / Thu nhập"
        description="Thu nhập USDC của agent, phí studio và rút tiền."
        actions={
          agents.data && agents.data.length > 0 ? (
            <div className="w-full sm:w-56">
              <select
                aria-label="Lọc theo agent"
                value={filterAgentId}
                onChange={(e) => setFilterAgentId(e.target.value)}
                className={selectClass}
              >
                <option value="">Tất cả agents</option>
                {agents.data.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.slug})
                  </option>
                ))}
              </select>
            </div>
          ) : undefined
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Số dư có thể rút</CardTitle>
            <CardDescription>GET /api/v1/billing/summary</CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState query={summary} feature="GET /billing/summary">
              {(s) => {
                const netIncome = Math.max(0, s.gross_income_atomic - s.studio_fees_atomic);
                const pendingReserved = Math.max(
                  0,
                  netIncome - s.paid_out_atomic - s.withdrawable_atomic,
                );
                return (
                  <div className="space-y-4">
                    <div>
                      <p className="text-muted-foreground text-xs">Khả dụng để rút ngay</p>
                      <p className="text-2xl font-semibold" data-testid="withdrawable-balance">
                        {formatAtomic(s.withdrawable_atomic)} {assetSymbol}
                      </p>
                    </div>
                    <dl className="grid gap-3 sm:grid-cols-2">
                      <BreakdownStat
                        label="Tổng thu (Gross)"
                        value={`${formatAtomic(s.gross_income_atomic)} ${assetSymbol}`}
                      />
                      <BreakdownStat
                        label={
                          fees.data
                            ? `Phí studio (${fees.data.studio_fee_bps / 100}%)`
                            : "Phí studio"
                        }
                        value={`${formatAtomic(s.studio_fees_atomic)} ${assetSymbol}`}
                      />
                      <BreakdownStat
                        label="Thu nhập ròng (Net)"
                        value={`${formatAtomic(netIncome)} ${assetSymbol}`}
                      />
                      <BreakdownStat
                        label="Đã rút"
                        value={`${formatAtomic(s.paid_out_atomic)} ${assetSymbol}`}
                      />
                    </dl>
                    {pendingReserved > 0 && (
                      <p className="text-muted-foreground text-xs">
                        Đang giữ cho lệnh rút chờ xử lý: {formatAtomic(pendingReserved)}{" "}
                        {assetSymbol}
                      </p>
                    )}
                  </div>
                );
              }}
            </QueryState>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Phí studio</CardTitle>
            <CardDescription>GET /api/v1/billing/fees</CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState query={fees} feature="GET /billing/fees">
              {(f) => {
                const feePct = f.studio_fee_bps / 100;
                const ownerPct = Math.max(0, 100 - feePct);
                return (
                  <div className="space-y-4 text-sm">
                    <div>
                      <p className="text-2xl font-semibold">{feePct}%</p>
                      <p className="text-muted-foreground">
                        {f.payment_asset} {shortAddress(f.payment_asset_address)} · chain{" "}
                        {f.chain_id}
                        {CHAIN_NAMES[f.chain_id] ? ` (${CHAIN_NAMES[f.chain_id]})` : ""}
                      </p>
                    </div>
                    <dl className="divide-y rounded-lg border px-3">
                      <div className="flex justify-between gap-4 py-2">
                        <dt className="text-muted-foreground">Agent nhận (Net)</dt>
                        <dd className="font-medium">{ownerPct}%</dd>
                      </div>
                      <div className="flex justify-between gap-4 py-2">
                        <dt className="text-muted-foreground">Phí vận hành studio</dt>
                        <dd className="font-medium">
                          {feePct}% ({f.studio_fee_bps} bps)
                        </dd>
                      </div>
                      <div className="flex justify-between gap-4 py-2">
                        <dt className="text-muted-foreground">Token thanh toán</dt>
                        <dd className="font-mono text-xs">
                          {f.payment_asset} ({shortAddress(f.payment_asset_address)})
                        </dd>
                      </div>
                    </dl>
                  </div>
                );
              }}
            </QueryState>
          </CardContent>
        </Card>
      </div>

      <WithdrawalCard
        agentOptions={agentOptions}
        defaultAgentId={filterAgentId || agentOptions[0]?.id || ""}
        defaultDestination={
          connectedAddress && ADDRESS_PATTERN.test(connectedAddress) ? connectedAddress : ""
        }
        withdrawableAtomic={summary.data?.withdrawable_atomic}
        assetSymbol={assetSymbol}
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Lịch sử rút tiền</CardTitle>
              <CardDescription>GET /api/v1/billing/payouts</CardDescription>
            </div>
            {hasActivePayout && (
              <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                <Loader2 className="size-3 animate-spin" /> đang cập nhật trạng thái rút tiền
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <QueryState query={payouts} feature="GET /billing/payouts">
            {(rows) =>
              rows.length === 0 ? (
                <p className="text-muted-foreground p-6 text-center text-sm">
                  Chưa có yêu cầu rút tiền nào.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Thời gian</TableHead>
                      <TableHead>Agent</TableHead>
                      <TableHead>Địa chỉ nhận</TableHead>
                      <TableHead>Số tiền</TableHead>
                      <TableHead>Trạng thái</TableHead>
                      <TableHead>Tx</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((p) => {
                      const agent = agentsById.get(p.agent_id);
                      return (
                        <TableRow key={p.id}>
                          <TableCell>{new Date(p.created_at).toLocaleString()}</TableCell>
                          <TableCell>
                            <Link
                              to={`/agents/${p.agent_id}`}
                              className="font-medium hover:underline"
                            >
                              {agent ? agent.name : p.agent_id.slice(0, 8)}
                            </Link>
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {shortAddress(p.destination)}
                          </TableCell>
                          <TableCell>
                            {formatAtomic(p.amount_atomic)} {assetLabel(p.asset, assetMeta)}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={p.status} />
                          </TableCell>
                          <TableCell>
                            <TxCell hash={p.tx_hash} explorerUrl={net?.explorer_url} />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )
            }
          </QueryState>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sổ cái</CardTitle>
          <CardDescription>GET /api/v1/billing/ledger</CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState query={ledger} feature="GET /billing/ledger">
            {(rows) =>
              rows.length === 0 ? (
                <p className="text-muted-foreground p-6 text-center text-sm">
                  Chưa có giao dịch nào trong sổ cái.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Thời gian</TableHead>
                      <TableHead>Loại</TableHead>
                      <TableHead>Số tiền</TableHead>
                      <TableHead>Tx</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((e) => {
                      const decimals = e.asset === "AVAX" ? 18 : PAYMENT_DECIMALS;
                      return (
                        <TableRow key={e.id}>
                          <TableCell>{new Date(e.created_at).toLocaleString()}</TableCell>
                          <TableCell>
                            <Badge variant={KIND_VARIANT[e.kind] ?? "secondary"}>{e.kind}</Badge>
                          </TableCell>
                          <TableCell>
                            {formatAtomic(e.amount_atomic, decimals)}{" "}
                            {assetLabel(e.asset, assetMeta)}
                          </TableCell>
                          <TableCell>
                            <TxCell hash={e.tx_hash} explorerUrl={net?.explorer_url} />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )
            }
          </QueryState>
        </CardContent>
      </Card>
    </>
  );
}

function BreakdownStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-base font-semibold">{value}</dd>
    </div>
  );
}

function TxCell({ hash, explorerUrl }: { hash: string | null; explorerUrl?: string }) {
  if (!hash) return <span className="text-muted-foreground font-mono text-xs">—</span>;
  if (!explorerUrl) return <span className="font-mono text-xs">{shortAddress(hash)}</span>;
  return (
    <a
      href={`${explorerUrl}/tx/${hash}`}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 font-mono text-xs hover:underline"
    >
      {shortAddress(hash)} <ExternalLink className="size-3" />
    </a>
  );
}

function WithdrawalCard({
  agentOptions,
  defaultAgentId,
  defaultDestination,
  withdrawableAtomic,
  assetSymbol,
}: {
  agentOptions: { id: string; label: string }[];
  defaultAgentId: string;
  defaultDestination: string;
  withdrawableAtomic: number | undefined;
  assetSymbol: string;
}) {
  const queryClient = useQueryClient();
  const [agentId, setAgentId] = useState(defaultAgentId);
  const [destination, setDestination] = useState(defaultDestination);
  const [amount, setAmount] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    agent?: string;
    destination?: string;
    amount?: string;
  }>({});
  const [lastPayout, setLastPayout] = useState<Payout | null>(null);

  useEffect(() => {
    if (!agentId && defaultAgentId) setAgentId(defaultAgentId);
  }, [agentId, defaultAgentId]);

  useEffect(() => {
    if (!destination && defaultDestination) setDestination(defaultDestination);
  }, [destination, defaultDestination]);

  const requestPayout = useMutation({
    mutationFn: api.billing.requestPayout,
    onSuccess: (payout) => {
      setLastPayout(payout);
      setAmount("");
      setFieldErrors({});
      void queryClient.invalidateQueries({ queryKey: ["billing", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["billing", "ledger"] });
      void queryClient.invalidateQueries({ queryKey: ["billing", "payouts"] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "insufficient_balance") {
        setFieldErrors((prev) => ({
          ...prev,
          amount: describeError(err, assetSymbol),
        }));
      }
    },
  });

  function onFillMax() {
    if (withdrawableAtomic != null && withdrawableAtomic > 0) {
      setAmount(formatAtomic(withdrawableAtomic));
      setFieldErrors((prev) => ({ ...prev, amount: undefined }));
      setLastPayout(null);
    }
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLastPayout(null);

    const effectiveAgentId = (agentId || defaultAgentId).trim();
    const trimmedDest = destination.trim();
    const nextErrors: { agent?: string; destination?: string; amount?: string } = {};

    if (!effectiveAgentId) {
      nextErrors.agent = "Vui lòng chọn agent để rút tiền.";
    }
    if (!ADDRESS_PATTERN.test(trimmedDest)) {
      nextErrors.destination = "Địa chỉ nhận phải có dạng 0x theo sau bởi 40 ký tự hex.";
    }

    let amountAtomic = 0n;
    try {
      amountAtomic = parseAtomic(amount);
      if (amountAtomic <= 0n) {
        nextErrors.amount = "Số tiền rút phải lớn hơn 0.";
      } else if (amountAtomic > BigInt(Number.MAX_SAFE_INTEGER)) {
        nextErrors.amount = "Số tiền quá lớn.";
      }
    } catch (err) {
      nextErrors.amount = err instanceof Error ? err.message : String(err);
    }

    if (nextErrors.agent || nextErrors.destination || nextErrors.amount) {
      setFieldErrors(nextErrors);
      return;
    }

    setFieldErrors({});
    requestPayout.mutate({
      agent_id: effectiveAgentId,
      destination: trimmedDest,
      amount_atomic: Number(amountAtomic),
    });
  }

  const insufficientError =
    requestPayout.error instanceof ApiError && requestPayout.error.code === "insufficient_balance";
  const notImplemented =
    requestPayout.error instanceof ApiError && requestPayout.error.notImplemented;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rút tiền</CardTitle>
        <CardDescription>
          POST /api/v1/billing/payouts · Chuyển {assetSymbol} từ ví Turnkey của agent về địa chỉ ví
          của bạn (đã trừ phí studio).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="payout-agent">Agent</Label>
              {agentOptions.length > 0 ? (
                <select
                  id="payout-agent"
                  value={agentId || defaultAgentId}
                  onChange={(e) => {
                    setAgentId(e.target.value);
                    if (fieldErrors.agent) setFieldErrors((prev) => ({ ...prev, agent: undefined }));
                  }}
                  aria-invalid={fieldErrors.agent ? true : undefined}
                  className={selectClass}
                >
                  {agentOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id="payout-agent"
                  value={agentId}
                  onChange={(e) => {
                    setAgentId(e.target.value);
                    if (fieldErrors.agent) setFieldErrors((prev) => ({ ...prev, agent: undefined }));
                  }}
                  placeholder="UUID của agent…"
                  aria-invalid={fieldErrors.agent ? true : undefined}
                />
              )}
              {fieldErrors.agent && (
                <p className="text-destructive text-sm">{fieldErrors.agent}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="payout-destination">Địa chỉ nhận</Label>
              <Input
                id="payout-destination"
                value={destination}
                onChange={(e) => {
                  setDestination(e.target.value);
                  if (fieldErrors.destination) {
                    setFieldErrors((prev) => ({ ...prev, destination: undefined }));
                  }
                }}
                placeholder="0x…"
                aria-invalid={fieldErrors.destination ? true : undefined}
                aria-describedby={fieldErrors.destination ? "payout-destination-error" : undefined}
              />
              {fieldErrors.destination && (
                <p id="payout-destination-error" className="text-destructive text-sm">
                  {fieldErrors.destination}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="payout-amount">Số tiền ({assetSymbol})</Label>
                <button
                  type="button"
                  onClick={onFillMax}
                  disabled={!withdrawableAtomic || withdrawableAtomic <= 0}
                  className="text-primary text-xs font-medium hover:underline disabled:pointer-events-none disabled:opacity-50"
                >
                  Tối đa
                </button>
              </div>
              <Input
                id="payout-amount"
                inputMode="decimal"
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  if (fieldErrors.amount) {
                    setFieldErrors((prev) => ({ ...prev, amount: undefined }));
                  }
                }}
                placeholder="0.00"
                aria-invalid={fieldErrors.amount ? true : undefined}
                aria-describedby={fieldErrors.amount ? "payout-amount-error" : undefined}
              />
              {fieldErrors.amount ? (
                <p id="payout-amount-error" role="alert" className="text-destructive text-sm">
                  {fieldErrors.amount}
                </p>
              ) : (
                withdrawableAtomic != null && (
                  <p className="text-muted-foreground text-xs">
                    Khả dụng: {formatAtomic(withdrawableAtomic)} {assetSymbol}
                  </p>
                )
              )}
            </div>
          </div>

          {notImplemented && <ComingSoon feature="POST /billing/payouts" />}
          {requestPayout.isError && !insufficientError && !notImplemented && (
            <p role="alert" className="text-destructive text-sm">
              {describeError(requestPayout.error, assetSymbol)}
            </p>
          )}

          {lastPayout && (
            <p
              role="status"
              className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm"
            >
              <Check className="size-4 shrink-0 text-emerald-600" />
              Đã tạo yêu cầu rút {formatAtomic(lastPayout.amount_atomic)} {assetSymbol} về{" "}
              <span className="font-mono">{shortAddress(lastPayout.destination)}</span> (trạng thái:{" "}
              {lastPayout.status}).
            </p>
          )}

          <Button type="submit" disabled={requestPayout.isPending}>
            {requestPayout.isPending ? (
              <Loader2 className="animate-spin" />
            ) : (
              <ArrowUpRight className="size-4" />
            )}
            {requestPayout.isPending ? "Đang gửi yêu cầu…" : "Rút tiền"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
