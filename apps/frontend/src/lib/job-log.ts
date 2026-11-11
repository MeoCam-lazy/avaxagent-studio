import type { Job } from "@/lib/types";

/** Statuses that can still change on their own, so the job log keeps polling. */
export const ACTIVE_JOB_STATUSES = new Set<string>(["funded", "running", "submitted"]);

/** Human labels for `JobEvent.type` (written by the gateway and the worker). */
export const EVENT_LABELS: Record<string, string> = {
  funded: "Đã nhận thanh toán",
  llm_started: "Đang chạy LLM",
  submitted: "Đã lưu deliverable",
  settled: "Đã quyết toán",
  failed: "Thất bại",
  refunded: "Đã hoàn tiền",
};

export type StepState = "done" | "current" | "failed" | "todo";

const STEPS = [
  { key: "funded", label: "Thanh toán" },
  { key: "running", label: "Chạy LLM" },
  { key: "submitted", label: "Submit" },
  { key: "settled", label: "Quyết toán" },
] as const;

/** Milestones already reached for each non-failed status. */
const DONE_COUNT: Record<string, number> = {
  negotiating: 0,
  funded: 1,
  running: 1,
  submitted: 3,
  settled: 4,
};

/**
 * Step progression for the job header: reached milestones are done and the
 * next one is current. A failed job marks the step it was on as failed,
 * inferred from what it got as far as (payment, deliverable).
 */
export function jobSteps(job: Pick<Job, "status" | "deliverable_uri" | "payment_tx_hash">) {
  const failed = job.status === "failed" || job.status === "refunded";
  const done = failed
    ? job.deliverable_uri
      ? 3
      : job.payment_tx_hash
        ? 1
        : 0
    : (DONE_COUNT[job.status] ?? 0);
  return STEPS.map((s, i) => {
    const state: StepState =
      i < done ? "done" : i === done ? (failed ? "failed" : "current") : "todo";
    return { ...s, state };
  });
}

/**
 * The A2A task input as readable text, following the worker's own
 * `_extract_prompt`: a string message, text parts, or else the raw JSON.
 */
export function requestText(request: Record<string, unknown>): string {
  const text = textOf(request.message ?? request.prompt);
  if (text) return text;
  return Object.keys(request).length ? JSON.stringify(request, null, 2) : "—";
}

function textOf(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(textOf).filter(Boolean).join("\n");
  if (value && typeof value === "object") {
    const v = value as Record<string, unknown>;
    if (typeof v.text === "string") return v.text;
    return textOf(v.parts ?? v.content);
  }
  return "";
}
