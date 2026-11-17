import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Loader2, RefreshCw, Shield } from "lucide-react";

import { QueryState } from "@/components/query-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useNetwork } from "@/hooks/use-network";
import { api } from "@/lib/api";
import { formatAtomic, parseAtomic, shortAddress } from "@/lib/format";
import type { RegistrationStatus, Wallet } from "@/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

export function WalletAndPolicyCard({
  agentId,
  walletQuery,
}: {
  agentId: string;
  walletQuery: UseQueryResult<Wallet>;
}) {
  const queryClient = useQueryClient();
  const { data: net } = useNetwork();
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [policyError, setPolicyError] = useState<string | null>(null);

  const balances = useQuery({
    queryKey: ["agents", agentId, "wallet", "balances"],
    queryFn: () => api.agents.balances(agentId),
    enabled: walletQuery.isSuccess,
  });

  const updatePolicy = useMutation({
    mutationFn: (body: Wallet["policy"]) => api.agents.updatePolicy(agentId, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(["agents", agentId, "wallet"], updated);
      setEditing(false);
      setPolicyError(null);
    },
    onError: (err) => setPolicyError(err instanceof Error ? err.message : String(err)),
  });

  async function copyAddress(addr: string) {
    try {
      await navigator.clipboard.writeText(addr);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard unavailable
    }
  }

  function submitPolicy(e: FormEvent<HTMLFormElement>, current: Wallet["policy"]) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const cap = parseAtomic(String(f.get("cap") ?? "0"));
      const daily = parseAtomic(String(f.get("daily") ?? "0"));
      setPolicyError(null);
      updatePolicy.mutate({
        ...current,
        max_value_per_call_atomic: Number(cap),
        daily_budget_atomic: Number(daily),
      });
    } catch (err) {
      setPolicyError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <Card className="border-slate-200/90 shadow-sm">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base font-bold text-slate-900">
            Ví Turnkey & Hạn mức Chi tiêu
          </CardTitle>
          <CardDescription className="text-xs">
            Sub-organization tách biệt trên Turnkey MPC — không lưu trữ private key.
          </CardDescription>
        </div>
        {walletQuery.data && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setEditing((v) => !v)}
            className="h-8 text-xs"
          >
            <Shield className="size-3.5" />
            <span>{editing ? "Đóng" : "Chỉnh hạn mức"}</span>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <QueryState query={walletQuery} feature="GET /agents/{id}/wallet">
          {(w) => (
            <div className="space-y-4 text-sm">
              <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <span className="font-mono text-xs break-all text-slate-800">{w.address}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => copyAddress(w.address)}
                  className="h-7 shrink-0 px-2 text-xs"
                >
                  {copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                  <span>{copied ? "Đã chép" : shortAddress(w.address)}</span>
                </Button>
              </div>

              <dl className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                  <dt className="text-slate-500">Số dư AVAX (Gas)</dt>
                  <dd className="mt-0.5 font-mono text-sm font-semibold text-slate-900">
                    {balances.data ? `${formatAtomic(balances.data.avax_wei, 18)} AVAX` : "…"}
                  </dd>
                </div>
                <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                  <dt className="text-slate-500">Số dư {net?.payment_asset ?? "USDC"}</dt>
                  <dd className="mt-0.5 font-mono text-sm font-semibold text-[#E84142]">
                    {balances.data
                      ? `${formatAtomic(balances.data.payment_asset_atomic)} ${net?.payment_asset ?? "USDC"}`
                      : "…"}
                  </dd>
                </div>
                <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                  <dt className="text-slate-500">Trần mỗi giao dịch</dt>
                  <dd className="mt-0.5 font-mono font-semibold text-slate-800">
                    {formatAtomic(w.policy.max_value_per_call_atomic)} USDC
                  </dd>
                </div>
                <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                  <dt className="text-slate-500">Ngân sách / ngày</dt>
                  <dd className="mt-0.5 font-mono font-semibold text-slate-800">
                    {formatAtomic(w.policy.daily_budget_atomic)} USDC
                  </dd>
                </div>
              </dl>

              {editing && (
                <form
                  onSubmit={(e) => submitPolicy(e, w.policy)}
                  className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="cap" className="text-xs">
                        Trần / giao dịch (USDC)
                      </Label>
                      <Input
                        id="cap"
                        name="cap"
                        defaultValue={formatAtomic(w.policy.max_value_per_call_atomic)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="daily" className="text-xs">
                        Ngân sách / ngày (USDC)
                      </Label>
                      <Input
                        id="daily"
                        name="daily"
                        defaultValue={formatAtomic(w.policy.daily_budget_atomic)}
                      />
                    </div>
                  </div>
                  {policyError && <p className="text-destructive text-xs">{policyError}</p>}
                  <Button type="submit" size="sm" disabled={updatePolicy.isPending}>
                    {updatePolicy.isPending && <Loader2 className="animate-spin" />}
                    Lưu policy lên Turnkey
                  </Button>
                </form>
              )}
            </div>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}

export function IdentityRegistryCard({
  agentId,
  registrationQuery,
}: {
  agentId: string;
  registrationQuery: UseQueryResult<RegistrationStatus>;
}) {
  const queryClient = useQueryClient();
  const refreshUri = useMutation({
    mutationFn: () => api.agents.refreshUri(agentId),
    onSuccess: (status) => queryClient.setQueryData(["agents", agentId, "registration"], status),
  });

  return (
    <Card className="border-slate-200/90 shadow-sm">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base font-bold text-slate-900">
            Định danh On-Chain (ERC-8004)
          </CardTitle>
          <CardDescription className="text-xs">
            NFT định danh Agent trên Avalanche Identity Registry & siêu dữ liệu A2A.
          </CardDescription>
        </div>
        {registrationQuery.data?.erc8004_agent_id != null && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={refreshUri.isPending}
            onClick={() => refreshUri.mutate()}
            className="h-8 text-xs"
          >
            <RefreshCw className={refreshUri.isPending ? "size-3.5 animate-spin" : "size-3.5"} />
            <span>Đồng bộ URI</span>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <QueryState query={registrationQuery} feature="GET /agents/{id}/registration">
          {(r) => (
            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <dt className="text-slate-500 text-xs">Trạng thái đăng ký</dt>
                <dd className="font-semibold text-slate-900">
                  {r.state} {r.erc8004_agent_id != null && `· Token #${r.erc8004_agent_id}`}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-slate-500 text-xs">Agent Metadata URI</dt>
                <dd className="rounded-lg bg-slate-50 p-2 font-mono text-xs break-all text-slate-700 border border-slate-200/70">
                  {r.agent_uri ?? "—"}
                </dd>
              </div>
              {r.explorer_url && (
                <div className="pt-1">
                  <a
                    href={r.explorer_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#E84142] hover:underline"
                  >
                    Xem giao dịch mint trên Snowtrace <ExternalLink className="size-3" />
                  </a>
                </div>
              )}
            </dl>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}
