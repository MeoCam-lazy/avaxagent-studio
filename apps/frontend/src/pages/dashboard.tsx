import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Coins,
  DollarSign,
  Plus,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";

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
  const summary = useQuery({
    queryKey: ["billing", "summary"],
    queryFn: () => api.billing.summary(),
  });
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Tạo, đăng ký và vận hành AI agent trên Avalanche C-Chain."
        actions={
          <Button asChild className="bg-[#E84142] hover:bg-[#D33738] text-white shadow-sm font-semibold">
            <Link to="/agents/new">
              <Plus /> Tạo agent
            </Link>
          </Button>
        }
      />

      {/* 1. Top Financial & Operations Overview */}
      <Card className="border-slate-200/90 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold text-slate-900">
                Tổng quan Thu nhập & Kinh tế Agent
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Hạch toán thu nhập 2 sổ Idempotent và phân rã 5% phí sàn giao thức
              </CardDescription>
            </div>
            <Button asChild variant="outline" size="sm" className="h-8 text-xs font-medium">
              <Link to="/wallet">
                Ví & Rút tiền <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <QueryState query={summary} feature="GET /billing/summary">
            {(s) => (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Tổng doanh thu (Gross)"
                  value={`${formatAtomic(s.gross_income_atomic)} USDC`}
                  sub="Tích lũy từ mọi job hoàn tất"
                  icon={DollarSign}
                  color="emerald"
                />
                <MetricCard
                  label="Khả dụng rút (Available)"
                  value={`${formatAtomic(s.withdrawable_atomic)} USDC`}
                  sub="Sẵn sàng rút về ví chủ sở hữu"
                  icon={Wallet}
                  color="red"
                />
                <MetricCard
                  label="Phí Studio (500 bps)"
                  value={`${formatAtomic(s.studio_fees_atomic)} USDC`}
                  sub="Trích 5% về Treasury sàn"
                  icon={ShieldCheck}
                  color="indigo"
                />
                <MetricCard
                  label="Đã rút thành công"
                  value={`${formatAtomic(s.paid_out_atomic)} USDC`}
                  sub="Đã kết chuyển on-chain"
                  icon={Coins}
                  color="slate"
                />
              </div>
            )}
          </QueryState>
        </CardContent>
      </Card>

      {/* 2. Agents Overview */}
      <Card className="border-slate-200/90 shadow-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold text-slate-900">Agents của bạn</CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Agent chưa hoàn tất thiết lập sẽ hiện ở đây để làm tiếp.
              </CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm" className="h-8 text-xs text-slate-600 hover:text-slate-900">
              <Link to="/agents">
                Xem tất cả agents <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <QueryState query={agents} feature="GET /agents">
            {(rows) => <AgentsOverview agents={rows} />}
          </QueryState>
        </CardContent>
      </Card>

      {/* 3. Avalanche Protocol Infrastructure */}
      <Card className="border-slate-200/90 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                Hạ tầng Giao thức Avalanche C-Chain
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200/60">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live 0.10s Finality
                </span>
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Thông số mạng lưới, hợp đồng định danh ERC-8004 và cổng thanh toán x402
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <QueryState query={network} feature="GET /network">
            {(n) => (
              <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                <Item k="Network" v={`${n.network} (${n.chain_id})`} />
                <Item k="Identity Registry (ERC-8004)" v={shortAddress(n.identity_registry)} />
                <Item k="Payment Asset" v={`${n.payment_asset} ${shortAddress(n.payment_asset_address)}`} />
                <Item k="Settlement Engine" v={n.erc8183_enabled ? "x402 Micropayment + ERC-8183 Escrow" : "x402 (USDC EIP-3009 TransferWithAuthorization)"} />
              </dl>
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
      <div className="flex flex-col items-start gap-3 text-sm py-4">
        <p className="text-muted-foreground">Chưa có agent nào. Tạo agent đầu tiên trong 3 bước.</p>
        <Button asChild size="sm" className="bg-[#E84142] hover:bg-[#D33738] text-white">
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
        <Stat label="Tổng" value={String(agents.length)} icon={Bot} />
        <Stat label="Đang hoạt động" value={String(active)} icon={Sparkles} color="emerald" />
        <Stat label="Cần thiết lập" value={String(pending.length)} icon={Activity} color={pending.length > 0 ? "amber" : "slate"} />
      </div>
      {pending.length > 0 && (
        <ul className="divide-y rounded-xl border border-slate-200/90 overflow-hidden bg-slate-50/50">
          {pending.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50 transition-colors">
              <div className="flex min-w-0 items-center gap-3">
                <div className="size-8 rounded-lg bg-red-50 text-[#E84142] border border-red-100 flex items-center justify-center shrink-0">
                  <Bot className="size-4" />
                </div>
                <div className="flex flex-col min-w-0">
                  <div className="flex items-center gap-2">
                    <Link to={`/agents/${a.id}`} className="truncate font-semibold text-slate-900 hover:text-[#E84142] transition-colors">
                      {a.name}
                    </Link>
                    <StatusBadge status={a.status} />
                  </div>
                  <span className="text-xs text-slate-500 truncate">
                    Chờ hoàn tất khởi tạo ví Turnkey & mint định danh ERC-8004
                  </span>
                </div>
              </div>
              <Button asChild size="sm" variant="outline" className="border-slate-200 font-medium hover:border-[#E84142] hover:text-[#E84142] shrink-0">
                <Link to={`/agents/new?id=${a.id}`}>
                  Tiếp tục thiết lập <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </Link>
              </Button>
            </li>
          ))}
        </ul>
      )}
      <Link to="/agents" className="text-muted-foreground inline-block text-xs font-medium hover:underline">
        Xem tất cả agents
      </Link>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ComponentType<{ className?: string }>;
  color: "emerald" | "red" | "indigo" | "slate";
}) {
  const colorMap = {
    emerald: "text-emerald-600 bg-emerald-50 border-emerald-100",
    red: "text-[#E84142] bg-red-50 border-red-100",
    indigo: "text-indigo-600 bg-indigo-50 border-indigo-100",
    slate: "text-slate-600 bg-slate-100 border-slate-200",
  };

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        <div className={`size-8 rounded-lg border flex items-center justify-center ${colorMap[color]}`}>
          <Icon className="size-4" />
        </div>
      </div>
      <p className="text-2xl font-black tracking-tight text-slate-900">{value}</p>
      <p className="text-[11px] text-slate-400 mt-1 truncate">{sub}</p>
    </div>
  );
}

function Stat({
  label,
  value,
  icon: Icon,
  color = "slate",
}: {
  label: string;
  value: string;
  icon?: React.ComponentType<{ className?: string }>;
  color?: "emerald" | "amber" | "slate";
}) {
  const badgeColors = {
    emerald: "text-emerald-600 bg-emerald-50 border-emerald-100",
    amber: "text-amber-600 bg-amber-50 border-amber-100",
    slate: "text-slate-600 bg-slate-50 border-slate-200",
  };

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <p className="text-slate-500 text-xs font-medium">{label}</p>
        {Icon && (
          <div className={`size-6 rounded-md border flex items-center justify-center ${badgeColors[color]}`}>
            <Icon className="size-3.5" />
          </div>
        )}
      </div>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between items-center gap-4 border-b border-slate-100 py-2">
      <dt className="text-slate-500 text-xs font-medium">{k}</dt>
      <dd className="font-mono text-xs font-semibold text-slate-800">{v}</dd>
    </div>
  );
}
