import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, Plus } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useNetwork } from "@/hooks/use-network";
import { api } from "@/lib/api";
import { formatAtomic, shortAddress } from "@/lib/format";
import { needsSetup } from "@/lib/agent-setup";
import type { Agent } from "@/lib/types";

export function DashboardPage() {
  const network = useNetwork();
  const summary = useQuery({ queryKey: ["billing", "summary"], queryFn: api.billing.summary });
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Tạo, đăng ký và vận hành AI agent trên Avalanche C-Chain."
        actions={
          <Button asChild>
            <Link to="/agents/new">
              <Plus /> Tạo agent
            </Link>
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Agents của bạn</CardTitle>
          <CardDescription>Agent chưa hoàn tất thiết lập sẽ hiện ở đây để làm tiếp.</CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState query={agents} feature="GET /agents">
            {(rows) => <AgentsOverview agents={rows} />}
          </QueryState>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Network</CardTitle>
          <CardDescription>GET /api/v1/network</CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState query={network} feature="GET /network">
            {(n) => (
              <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                <Item k="Network" v={`${n.network} (${n.chain_id})`} />
                <Item k="Identity Registry (ERC-8004)" v={shortAddress(n.identity_registry)} />
                <Item k="Payment asset" v={`${n.payment_asset} ${shortAddress(n.payment_asset_address)}`} />
                <Item k="Settlement" v={n.erc8183_enabled ? "x402 + ERC-8183" : "x402 (USDC EIP-3009)"} />
              </dl>
            )}
          </QueryState>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Thu nhập</CardTitle>
          <CardDescription>GET /api/v1/billing/summary</CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState query={summary} feature="GET /billing/summary">
            {(s) => (
              <div className="grid gap-4 sm:grid-cols-4">
                <Stat label="Gross" value={formatAtomic(s.gross_income_atomic)} />
                <Stat label="Phí studio" value={formatAtomic(s.studio_fees_atomic)} />
                <Stat label="Đã rút" value={formatAtomic(s.paid_out_atomic)} />
                <Stat label="Có thể rút" value={formatAtomic(s.withdrawable_atomic)} />
              </div>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </>
  );
}

function AgentsOverview({ agents }: { agents: Agent[] }) {
  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 text-sm">
        <p className="text-muted-foreground">Chưa có agent nào. Tạo agent đầu tiên trong 3 bước.</p>
        <Button asChild size="sm">
          <Link to="/agents/new">
            <Plus /> Tạo agent
          </Link>
        </Button>
      </div>
    );
  }
  const active = agents.filter((a) => a.status === "active").length;
  const pending = agents.filter(needsSetup);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Tổng" value={String(agents.length)} />
        <Stat label="Đang hoạt động" value={String(active)} />
        <Stat label="Cần thiết lập" value={String(pending.length)} />
      </div>
      {pending.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {pending.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <Link to={`/agents/${a.id}`} className="truncate font-medium hover:underline">
                  {a.name}
                </Link>
                <StatusBadge status={a.status} />
              </div>
              <Button asChild size="sm" variant="outline">
                <Link to={`/agents/new?id=${a.id}`}>
                  Tiếp tục thiết lập <ArrowRight />
                </Link>
              </Button>
            </li>
          ))}
        </ul>
      )}
      <Link to="/agents" className="text-muted-foreground inline-block text-sm hover:underline">
        Xem tất cả agents
      </Link>
    </div>
  );
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b py-1.5">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono text-xs">{v}</dd>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}
