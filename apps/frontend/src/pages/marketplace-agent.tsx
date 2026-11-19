import { useState, type FormEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Check, ExternalLink, Loader2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { erc20Abi } from "viem";
import { useReadContract } from "wagmi";

import { MarkdownViewer } from "@/components/markdown-viewer";
import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useNetwork } from "@/hooks/use-network";
import { usePayAgent, type PayPhase } from "@/hooks/use-pay-agent";
import { getTask, TERMINAL_TASK_STATES } from "@/lib/a2a";
import { api } from "@/lib/api";
import { formatAtomic, shortAddress } from "@/lib/format";
import type { MarketplaceAgentProfile, NetworkInfo } from "@/lib/types";

/** How often a paid task is re-read until it completes or fails. */
export const TASK_POLL_MS = 2000;

export function MarketplaceAgentPage({ pollIntervalMs = TASK_POLL_MS }: { pollIntervalMs?: number }) {
  const { slug = "" } = useParams();
  const profile = useQuery({
    queryKey: ["marketplace", "agent", slug],
    queryFn: () => api.marketplaceAgent(slug),
  });

  return (
    <>
      <Link
        to="/marketplace"
        className="text-muted-foreground inline-flex items-center gap-1 text-sm hover:underline"
      >
        <ArrowLeft className="size-4" /> Marketplace
      </Link>
      <QueryState query={profile} feature="GET /marketplace/agents/{slug}">
        {(agent) => (
          <>
            <PageHeader title={agent.name} description={agent.description} />
            <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <Profile agent={agent} />
              <CallAgent agent={agent} pollIntervalMs={pollIntervalMs} />
            </div>
          </>
        )}
      </QueryState>
    </>
  );
}

function Profile({ agent }: { agent: MarketplaceAgentProfile }) {
  const { data: net } = useNetwork();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Thông tin</CardTitle>
        <CardDescription>Danh tính on-chain và giá mỗi lần gọi.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p>
          <span className="text-2xl font-semibold">
            {agent.price_atomic === 0 ? "Miễn phí" : formatAtomic(agent.price_atomic)}
          </span>{" "}
          {agent.price_atomic === 0 ? (
            <span className="text-muted-foreground">· demo</span>
          ) : (
            <>{net?.payment_asset ?? "USDC"} <span className="text-muted-foreground">/ lần gọi</span></>
          )}
        </p>
        {agent.skills.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {agent.skills.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>
        )}
        <dl className="divide-y">
          <Row label="Thanh toán">
            <Badge variant="outline">
              {agent.price_atomic === 0 ? "Free demo" : agent.settlement_mode}
            </Badge>
          </Row>
          <Row label="Job hoàn thành">{agent.jobs_completed}</Row>
          <Row label="ERC-8004">
            {agent.erc8004_agent_id != null ? `#${agent.erc8004_agent_id}` : "—"}
          </Row>
          <Row label="Tham gia">{new Date(agent.created_at).toLocaleDateString()}</Row>
          <Row label="Agent card">
            <a
              href={agent.agent_card_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 hover:underline"
            >
              agent-card.json <ExternalLink className="size-3" />
            </a>
          </Row>
        </dl>
        <div className="space-y-1">
          <p className="text-muted-foreground text-xs">A2A endpoint</p>
          <code className="bg-muted block rounded-md p-2 text-xs break-all">{agent.a2a_url}</code>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

const PHASE_LABELS: Partial<Record<PayPhase, string>> = {
  quoting: "Đang lấy báo giá từ gateway…",
  connecting: "Đang kết nối ví…",
  signing: "Ký uỷ quyền thanh toán trong ví…",
  paying: "Gateway đang quyết toán on-chain…",
};

function CallAgent({ agent, pollIntervalMs }: { agent: MarketplaceAgentProfile; pollIntervalMs: number }) {
  const { data: net } = useNetwork();
  const [text, setText] = useState("");
  const pay = usePayAgent(agent.a2a_url);
  const symbol = net?.payment_asset ?? "USDC";
  const price = `${formatAtomic(agent.price_atomic)} ${symbol}`;
  const freeDemo = agent.price_atomic === 0;

  if (agent.settlement_mode !== "x402") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Gọi agent</CardTitle>
          <CardDescription>
            Agent này dùng escrow ERC-8183, chưa gọi trực tiếp được từ trình duyệt. Dùng A2A endpoint
            với client hỗ trợ ERC-8183.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim() && !pay.busy) void pay.run(text.trim());
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Gọi agent</CardTitle>
        <CardDescription>
          {freeDemo
            ? "Demo không thu x402 từ người gọi; job vẫn dùng quota LLM phía máy chủ. Kế hoạch paper-trading chỉ mô phỏng, không đặt lệnh thật."
            : `Ký uỷ quyền chuyển ${price} (EIP-3009). Gateway trả phí gas và chuyển tiền on-chain, nên ví chỉ cần ${symbol}, không cần AVAX.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="agent-input">Yêu cầu</Label>
            <Textarea
              id="agent-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={`Gửi yêu cầu cho ${agent.name}…`}
              rows={4}
              disabled={pay.busy}
            />
          </div>
          {net && pay.address && <PayerBalance net={net} address={pay.address} price={agent.price_atomic} />}
          <Button type="submit" disabled={pay.busy || !text.trim()} className="w-full sm:w-auto">
            {pay.busy && <Loader2 className="animate-spin" />}
            {pay.busy ? "Đang xử lý…" : freeDemo ? "Gửi yêu cầu miễn phí" : `Trả ${price} và gửi`}
          </Button>
          {pay.busy && PHASE_LABELS[pay.phase] && (
            <p className="text-muted-foreground text-sm" role="status">
              {PHASE_LABELS[pay.phase]}
            </p>
          )}
          {pay.error && (
            <p role="alert" className="text-destructive rounded-md border border-destructive/30 p-3 text-sm">
              {pay.error}
            </p>
          )}
        </form>
        {pay.paid && (
          <TaskResult
            a2aUrl={agent.a2a_url}
            taskId={pay.paid.task.id}
            txHash={pay.paid.receipt?.transaction ?? null}
            explorerUrl={net?.explorer_url}
            pollIntervalMs={pollIntervalMs}
          />
        )}
      </CardContent>
    </Card>
  );
}

function PayerBalance({ net, address, price }: { net: NetworkInfo; address: string; price: number }) {
  const balance = useReadContract({
    address: net.payment_asset_address as `0x${string}`,
    abi: erc20Abi,
    functionName: "balanceOf",
    args: [address as `0x${string}`],
    chainId: net.chain_id,
  });
  const low = balance.data !== undefined && balance.data < BigInt(price);
  return (
    <p className={low ? "text-destructive text-sm" : "text-muted-foreground text-sm"}>
      Ví <span className="font-mono">{shortAddress(address)}</span>
      {balance.data !== undefined && (
        <>
          {" "}
          · số dư {formatAtomic(balance.data)} {net.payment_asset}
        </>
      )}
      {low && ". Không đủ để trả lần gọi này."}
    </p>
  );
}

function TaskResult({
  a2aUrl,
  taskId,
  txHash,
  explorerUrl,
  pollIntervalMs,
}: {
  a2aUrl: string;
  taskId: string;
  txHash: string | null;
  explorerUrl?: string;
  pollIntervalMs: number;
}) {
  const task = useQuery({
    queryKey: ["a2a-task", a2aUrl, taskId],
    queryFn: () => getTask(a2aUrl, taskId),
    refetchInterval: (q) =>
      q.state.data && TERMINAL_TASK_STATES.has(q.state.data.state) ? false : pollIntervalMs,
  });
  const state = task.data?.state;

  return (
    <section aria-label="Kết quả" className="space-y-3 border-t pt-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 font-medium">
          {state === "completed" ? (
            <>
              <Check className="text-primary size-4" /> Hoàn thành
            </>
          ) : state === "failed" ? (
            <span className="text-destructive">Thất bại</span>
          ) : (
            <>
              <Loader2 className="size-4 animate-spin" /> Agent đang xử lý…
            </>
          )}
        </span>
        {txHash && (
          <a
            href={explorerUrl ? `${explorerUrl}/tx/${txHash}` : undefined}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground inline-flex items-center gap-1 font-mono text-xs hover:underline"
          >
            Thanh toán {shortAddress(txHash)} <ExternalLink className="size-3" />
          </a>
        )}
      </div>
      {task.isError && (
        <p className="text-destructive">Không đọc được trạng thái task. Đang thử lại…</p>
      )}
      {state === "failed" && task.data?.error && <p className="text-destructive">{task.data.error}</p>}
      {state === "completed" &&
        (task.data?.text ? (
          <MarkdownViewer content={task.data.text} />
        ) : (
          <p className="text-muted-foreground break-all">
            Gateway không đọc được nội dung. Deliverable: {task.data?.uri ?? "—"}
          </p>
        ))}
      <p className="text-muted-foreground font-mono text-xs break-all">task {taskId}</p>
    </section>
  );
}
