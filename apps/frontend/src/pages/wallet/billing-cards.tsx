import type { UseQueryResult } from "@tanstack/react-query";

import { QueryState } from "@/components/query-state";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CHAIN_NAMES, formatAtomic, shortAddress } from "@/lib/format";
import type { EarningsSummary, FeeSchedule } from "@/lib/types";

export function EarningsSummaryCard({
  summary,
  fees,
  assetSymbol,
}: {
  summary: UseQueryResult<EarningsSummary>;
  fees: UseQueryResult<FeeSchedule>;
  assetSymbol: string;
}) {
  return (
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
                    Đang giữ cho lệnh rút chờ xử lý: {formatAtomic(pendingReserved)} {assetSymbol}
                  </p>
                )}
              </div>
            );
          }}
        </QueryState>
      </CardContent>
    </Card>
  );
}

export function FeeScheduleCard({ fees }: { fees: UseQueryResult<FeeSchedule> }) {
  return (
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
                    {f.payment_asset} {shortAddress(f.payment_asset_address)} · chain {f.chain_id}
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
