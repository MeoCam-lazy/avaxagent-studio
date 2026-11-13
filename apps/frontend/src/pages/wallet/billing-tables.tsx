import type { UseQueryResult } from "@tanstack/react-query";
import { ExternalLink, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import { QueryState } from "@/components/query-state";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PAYMENT_DECIMALS, assetLabel, formatAtomic, shortAddress } from "@/lib/format";
import type { Agent, LedgerEntry, LedgerKind, Payout } from "@/lib/types";

const KIND_VARIANT: Record<LedgerKind, "default" | "secondary" | "destructive" | "outline"> = {
  income: "default",
  studio_fee: "secondary",
  payout: "outline",
  gas: "secondary",
};

export function PayoutsTableCard({
  payouts,
  hasActivePayout,
  agentsById,
  assetMeta,
  explorerUrl,
}: {
  payouts: UseQueryResult<Payout[]>;
  hasActivePayout: boolean;
  agentsById: Map<string, Agent>;
  assetMeta?: { payment_asset: string; payment_asset_address: string };
  explorerUrl?: string;
}) {
  return (
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
                          <TxCell hash={p.tx_hash} explorerUrl={explorerUrl} />
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
  );
}

export function LedgerTableCard({
  ledger,
  assetMeta,
  explorerUrl,
}: {
  ledger: UseQueryResult<LedgerEntry[]>;
  assetMeta?: { payment_asset: string; payment_asset_address: string };
  explorerUrl?: string;
}) {
  return (
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
                          {formatAtomic(e.amount_atomic, decimals)} {assetLabel(e.asset, assetMeta)}
                        </TableCell>
                        <TableCell>
                          <TxCell hash={e.tx_hash} explorerUrl={explorerUrl} />
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
