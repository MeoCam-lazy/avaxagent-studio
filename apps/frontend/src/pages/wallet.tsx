import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/hooks/use-auth";
import { useNetwork } from "@/hooks/use-network";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { EarningsSummaryCard, FeeScheduleCard } from "@/pages/wallet/billing-cards";
import { LedgerTableCard, PayoutsTableCard } from "@/pages/wallet/billing-tables";
import { WithdrawalCard } from "@/pages/wallet/withdrawal-card";

/** How often payouts and balances refresh while a withdrawal is in flight. */
export const PAYOUT_POLL_MS = 3000;

const ACTIVE_PAYOUT_STATUSES = new Set<string>(["requested", "submitted"]);
const ADDRESS_PATTERN = /^0x[0-9a-fA-F]{40}$/;
const selectClass = "border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm";

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
        <EarningsSummaryCard summary={summary} fees={fees} assetSymbol={assetSymbol} />
        <FeeScheduleCard fees={fees} />
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

      <PayoutsTableCard
        payouts={payouts}
        hasActivePayout={hasActivePayout}
        agentsById={agentsById}
        assetMeta={assetMeta}
        explorerUrl={net?.explorer_url}
      />

      <LedgerTableCard
        ledger={ledger}
        assetMeta={assetMeta}
        explorerUrl={net?.explorer_url}
      />
    </>
  );
}
