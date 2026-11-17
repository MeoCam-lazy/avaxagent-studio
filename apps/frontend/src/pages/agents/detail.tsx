import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, ExternalLink, Loader2, Pause, Pencil, Play } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { needsSetup } from "@/lib/agent-setup";
import { api } from "@/lib/api";
import { formatAtomic, parseAtomic } from "@/lib/format";
import type { Agent, AgentUpdate } from "@/lib/types";
import { IdentityRegistryCard, WalletAndPolicyCard } from "@/pages/agents/detail-panels";

export function AgentDetailPage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const agent = useQuery({ queryKey: ["agents", id], queryFn: () => api.agents.get(id) });
  const wallet = useQuery({ queryKey: ["agents", id, "wallet"], queryFn: () => api.agents.wallet(id) });
  const registration = useQuery({
    queryKey: ["agents", id, "registration"],
    queryFn: () => api.agents.registration(id),
  });

  const updateAgent = useMutation({
    mutationFn: (body: AgentUpdate) => api.agents.update(id, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(["agents", id], updated);
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      setEditing(false);
      setFormError(null);
    },
    onError: (err) => setFormError(err instanceof Error ? err.message : String(err)),
  });

  function onSaveConfig(e: FormEvent<HTMLFormElement>, current: Agent) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const priceAtomic = parseAtomic(String(f.get("price") ?? "0"));
      setFormError(null);
      updateAgent.mutate({
        name: String(f.get("name") || current.name),
        description: String(f.get("description") ?? ""),
        price_atomic: Number(priceAtomic),
        is_public: f.get("is_public") === "on",
        skills: String(f.get("skills") ?? "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        llm_config: {
          ...current.llm_config,
          system_prompt: String(f.get("system_prompt") ?? ""),
        },
      });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    }
  }

  const data = agent.data;
  const canTogglePause =
    data != null &&
    data.erc8004_agent_id != null &&
    (data.status === "active" || data.status === "paused");

  return (
    <>
      <PageHeader
        title={data?.name ?? "Chi tiết Agent"}
        description={data ? `Slug: /agents/${data.slug}/a2a` : id}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {data?.is_public && data.status === "active" && (
              <Button asChild variant="outline" size="sm">
                <Link to={`/marketplace/${data.slug}`}>
                  Xem trên Marketplace <ExternalLink className="size-3.5" />
                </Link>
              </Button>
            )}
            {canTogglePause && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={updateAgent.isPending}
                onClick={() =>
                  updateAgent.mutate({ status: data.status === "active" ? "paused" : "active" })
                }
              >
                {data.status === "active" ? (
                  <>
                    <Pause className="size-3.5" /> Tạm dừng
                  </>
                ) : (
                  <>
                    <Play className="size-3.5" /> Kích hoạt lại
                  </>
                )}
              </Button>
            )}
            {data && needsSetup(data) && (
              <Button asChild className="bg-[#E84142] hover:bg-[#D33738] text-white">
                <Link to={`/agents/new?id=${id}`}>
                  Tiếp tục thiết lập <ArrowRight />
                </Link>
              </Button>
            )}
          </div>
        }
      />

      <Card className="border-slate-200/90 shadow-sm">
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle className="text-base font-bold text-slate-900">
              Cấu hình & Mô hình AI
            </CardTitle>
            <CardDescription className="text-xs">
              Thông số vận hành, mức phí mỗi lượt gọi A2A và chỉ dẫn hệ thống (System Prompt).
            </CardDescription>
          </div>
          {data && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setEditing((v) => !v)}
              className="h-8 text-xs"
            >
              <Pencil className="size-3.5" />
              <span>{editing ? "Hủy" : "Chỉnh sửa"}</span>
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <QueryState query={agent} feature="GET /agents/{id}">
            {(a) =>
              editing ? (
                <form onSubmit={(e) => onSaveConfig(e, a)} className="space-y-4 text-sm">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="edit-name">Tên Agent</Label>
                      <Input id="edit-name" name="name" defaultValue={a.name} required />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="edit-price">Giá mỗi job (USDC)</Label>
                      <Input
                        id="edit-price"
                        name="price"
                        defaultValue={formatAtomic(a.price_atomic)}
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-desc">Mô tả</Label>
                    <Textarea id="edit-desc" name="description" defaultValue={a.description} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-skills">Skills (phân cách bằng dấu phẩy)</Label>
                    <Input id="edit-skills" name="skills" defaultValue={a.skills.join(", ")} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-prompt">System Prompt</Label>
                    <Textarea
                      id="edit-prompt"
                      name="system_prompt"
                      rows={4}
                      defaultValue={a.llm_config.system_prompt}
                    />
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="is_public" defaultChecked={a.is_public} />
                    Hiển thị công khai trên Marketplace
                  </label>
                  {formError && <p className="text-destructive text-xs">{formError}</p>}
                  <Button
                    type="submit"
                    disabled={updateAgent.isPending}
                    className="bg-[#E84142] hover:bg-[#D33738] text-white"
                  >
                    {updateAgent.isPending && <Loader2 className="animate-spin" />}
                    Lưu thay đổi
                  </Button>
                </form>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-lg font-bold text-slate-900">{a.name}</span>
                    <StatusBadge status={a.status} />
                    <Badge variant="outline">{a.is_public ? "Public Marketplace" : "Private"}</Badge>
                  </div>
                  <p className="text-slate-600">{a.description || "Chưa có mô tả."}</p>
                  {a.skills.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {a.skills.map((s) => (
                        <Badge key={s} variant="secondary">
                          #{s}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <dl className="grid gap-3 pt-2 sm:grid-cols-3 text-xs">
                    <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
                      <dt className="text-slate-500">Phương thức thanh toán</dt>
                      <dd className="mt-0.5 font-mono font-semibold text-slate-900">
                        {a.settlement_mode}
                      </dd>
                    </div>
                    <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
                      <dt className="text-slate-500">Đơn giá mỗi lần gọi</dt>
                      <dd className="mt-0.5 font-mono font-semibold text-[#E84142]">
                        {formatAtomic(a.price_atomic)} USDC
                      </dd>
                    </div>
                    <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
                      <dt className="text-slate-500">Mô hình LLM</dt>
                      <dd className="mt-0.5 font-mono font-semibold text-slate-900">
                        {a.llm_config.model} (temp {a.llm_config.temperature})
                      </dd>
                    </div>
                  </dl>
                </div>
              )
            }
          </QueryState>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <WalletAndPolicyCard agentId={id} walletQuery={wallet} />
        <IdentityRegistryCard agentId={id} registrationQuery={registration} />
      </div>
    </>
  );
}
