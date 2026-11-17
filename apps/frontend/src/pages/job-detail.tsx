import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Check, ExternalLink, Loader2, X } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { MarkdownViewer } from "@/components/markdown-viewer";
import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useNetwork } from "@/hooks/use-network";
import { api } from "@/lib/api";
import {
  ACTIVE_JOB_STATUSES,
  EVENT_LABELS,
  jobSteps,
  requestText,
  type StepState,
} from "@/lib/job-log";
import { assetLabel, formatAtomic, shortAddress } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Job, JobEvent } from "@/lib/types";

/** How often the job log refreshes while the job is still moving. */
export const JOB_POLL_MS = 2000;

export function JobDetailPage({ pollIntervalMs = JOB_POLL_MS }: { pollIntervalMs?: number }) {
  const { id = "" } = useParams();
  const live = (status?: string) => (status && ACTIVE_JOB_STATUSES.has(status) ? pollIntervalMs : false);

  const job = useQuery({
    queryKey: ["jobs", id],
    queryFn: () => api.jobs.get(id),
    refetchInterval: (q) => live(q.state.data?.status),
  });
  const events = useQuery({
    queryKey: ["jobs", id, "events"],
    queryFn: () => api.jobs.events(id),
    refetchInterval: () => live(job.data?.status),
  });

  return (
    <>
      <PageHeader
        title="Job"
        description={id}
        actions={
          <Link to="/jobs" className="text-muted-foreground inline-flex items-center gap-1 text-sm hover:underline">
            <ArrowLeft className="size-4" /> Log job
          </Link>
        }
      />
      <QueryState query={job} feature="GET /jobs/{id}">
        {(j) => (
          <>
            <Summary job={j} live={ACTIVE_JOB_STATUSES.has(j.status)} />
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Timeline</CardTitle>
                  <CardDescription>Sự kiện từ gateway và worker, cũ nhất ở trên.</CardDescription>
                </CardHeader>
                <CardContent>
                  <QueryState query={events} feature="GET /jobs/{id}/events">
                    {(rows) => <Timeline events={rows} />}
                  </QueryState>
                </CardContent>
              </Card>
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Yêu cầu</CardTitle>
                    <CardDescription>Input client gửi qua A2A.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <pre className="bg-muted max-h-64 overflow-auto rounded-md p-3 text-sm whitespace-pre-wrap">
                      {requestText(j.request)}
                    </pre>
                  </CardContent>
                </Card>
                <Deliverable job={j} />
              </div>
            </div>
          </>
        )}
      </QueryState>
    </>
  );
}

function Summary({ job, live }: { job: Job; live: boolean }) {
  const { data: net } = useNetwork();
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>
            {formatAtomic(job.amount_atomic)} {assetLabel(job.asset, net)} · {job.settlement_mode}
          </CardTitle>
          <StatusBadge status={job.status} />
          {live && (
            <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
              <Loader2 className="size-3 animate-spin" /> đang cập nhật
            </span>
          )}
        </div>
        <CardDescription>
          {new Date(job.created_at).toLocaleString()} · client{" "}
          <span className="font-mono">{shortAddress(job.client_address)}</span> · agent{" "}
          <Link to={`/agents/${job.agent_id}`} className="hover:underline">
            {job.agent_id.slice(0, 8)}
          </Link>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Steps job={job} />
        {job.error && (
          <p className="text-destructive rounded-md border border-destructive/30 p-3 text-sm">{job.error}</p>
        )}
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
          <TxItem label="Thanh toán" hash={job.payment_tx_hash} />
          <TxItem label="Submit" hash={job.submit_tx_hash} />
          <TxItem label="Settle" hash={job.settle_tx_hash} />
        </dl>
      </CardContent>
    </Card>
  );
}

const STEP_STYLE: Record<StepState, string> = {
  done: "bg-primary text-primary-foreground border-primary",
  current: "border-primary text-primary",
  failed: "bg-destructive text-white border-destructive",
  todo: "text-muted-foreground",
};

function Steps({ job }: { job: Job }) {
  const steps = jobSteps(job);
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm" aria-label="Tiến trình job">
      {steps.map((s, i) => (
        <li
          key={s.key}
          className="flex items-center gap-2"
          data-state={s.state}
          aria-current={s.state === "current" ? "step" : undefined}
        >
          <span
            className={cn(
              "flex size-6 items-center justify-center rounded-full border text-xs font-medium",
              STEP_STYLE[s.state],
            )}
          >
            {s.state === "done" ? (
              <Check className="size-3.5" />
            ) : s.state === "failed" ? (
              <X className="size-3.5" />
            ) : s.state === "current" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              i + 1
            )}
          </span>
          <span className={cn(s.state === "todo" && "text-muted-foreground", s.state !== "todo" && "font-medium")}>
            {s.label}
          </span>
          {i < steps.length - 1 && <span className="bg-border mx-1 hidden h-px w-8 sm:block" />}
        </li>
      ))}
    </ol>
  );
}

function TxLink({ hash }: { hash: string }) {
  const { data: net } = useNetwork();
  if (!net) return <span className="font-mono text-xs">{shortAddress(hash)}</span>;
  return (
    <a
      href={`${net.explorer_url}/tx/${hash}`}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 font-mono text-xs hover:underline"
    >
      {shortAddress(hash)} <ExternalLink className="size-3" />
    </a>
  );
}

function TxItem({ label, hash }: { label: string; hash: string | null }) {
  return (
    <div className="flex justify-between gap-4 border-b py-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{hash ? <TxLink hash={hash} /> : <span className="text-muted-foreground">—</span>}</dd>
    </div>
  );
}

function Timeline({ events }: { events: JobEvent[] }) {
  if (events.length === 0) {
    return <p className="text-muted-foreground text-sm">Chưa có sự kiện nào.</p>;
  }
  return (
    <ol aria-label="Timeline" className="relative space-y-4 border-l pl-5">
      {events.map((e) => {
        const txHash = typeof e.data.tx_hash === "string" ? e.data.tx_hash : null;
        const uri = typeof e.data.uri === "string" ? e.data.uri : null;
        return (
          <li key={e.id} className="relative">
            <span
              className={cn(
                "bg-primary absolute top-1.5 -left-[25px] size-2.5 rounded-full ring-4 ring-[var(--card)]",
                e.type === "failed" && "bg-destructive",
              )}
            />
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="text-sm font-medium">{EVENT_LABELS[e.type] ?? e.type}</span>
              <time className="text-muted-foreground text-xs" dateTime={e.created_at}>
                {new Date(e.created_at).toLocaleTimeString()}
              </time>
            </div>
            {e.message && <p className="text-muted-foreground mt-0.5 text-sm break-words">{e.message}</p>}
            {txHash && (
              <p className="mt-0.5">
                <TxLink hash={txHash} />
              </p>
            )}
            {uri && <p className="text-muted-foreground mt-0.5 font-mono text-xs break-all">{uri}</p>}
          </li>
        );
      })}
    </ol>
  );
}

function Deliverable({ job }: { job: Job }) {
  const ready = job.deliverable_uri != null;
  const deliverable = useQuery({
    queryKey: ["jobs", job.id, "deliverable"],
    queryFn: () => api.jobs.deliverable(job.id),
    enabled: ready,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Deliverable</CardTitle>
        <CardDescription>Kết quả agent đã lưu (hash được ký kèm khi submit).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {!ready ? (
          <p className="text-muted-foreground text-sm">Chưa có deliverable. Job đang chạy hoặc đã thất bại.</p>
        ) : (
          <QueryState query={deliverable} feature="GET /jobs/{id}/deliverable">
            {(d) => {
              const output = d.content.output;
              return (
                <>
                  <MarkdownViewer
                    content={typeof output === "string" ? output : JSON.stringify(d.content, null, 2)}
                  />
                  <dl className="text-muted-foreground space-y-1 text-xs">
                    <div className="flex gap-2">
                      <dt>URI</dt>
                      <dd className="font-mono break-all">{d.uri}</dd>
                    </div>
                    {d.hash && (
                      <div className="flex gap-2">
                        <dt>Hash</dt>
                        <dd className="font-mono break-all">{d.hash}</dd>
                      </div>
                    )}
                  </dl>
                </>
              );
            }}
          </QueryState>
        )}
      </CardContent>
    </Card>
  );
}
