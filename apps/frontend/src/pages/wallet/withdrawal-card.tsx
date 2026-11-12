import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Check, Loader2 } from "lucide-react";

import { ComingSoon } from "@/components/coming-soon";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import { formatAtomic, parseAtomic, shortAddress } from "@/lib/format";
import type { Payout } from "@/lib/types";

const ADDRESS_PATTERN = /^0x[0-9a-fA-F]{40}$/;
const selectClass = "border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm";

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

export function WithdrawalCard({
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
