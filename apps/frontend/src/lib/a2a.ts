/**
 * Minimal A2A (JSON-RPC 2.0) client for the studio gateway
 * (`apps/backend/app/data_plane/gateway/a2a.py`).
 */
import { decodeReceipt, type PaymentReceipt, type X402Challenge } from "@/lib/x402";

export type TaskState = "submitted" | "working" | "completed" | "failed" | (string & {});

export interface TaskView {
  id: string;
  state: TaskState;
  /** Agent output, from the deliverable artifact's text parts. */
  text: string | null;
  /** Deliverable URI, when the gateway could not inline the content. */
  uri: string | null;
  error: string | null;
}

export type SendResult =
  | { kind: "payment_required"; challenge: X402Challenge }
  | { kind: "task"; task: TaskView; receipt: PaymentReceipt | null };

/** Gateway error with its machine code (`payment_replayed`, `bad_signature`, ...). */
export class GatewayError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string) {
    super(`gateway ${status} ${code}`);
    this.status = status;
    this.code = code;
  }
}

export const TERMINAL_TASK_STATES = new Set<TaskState>(["completed", "failed"]);

function rpc(method: string, params: Record<string, unknown>) {
  return { jsonrpc: "2.0", id: crypto.randomUUID(), method, params };
}

/** A2A `Message` with one text part. */
export function textMessage(text: string) {
  return {
    message: {
      role: "user",
      messageId: crypto.randomUUID(),
      parts: [{ kind: "text", text }],
    },
  };
}

interface RawTask {
  id: string;
  status: { state: TaskState };
  artifacts?: { uri?: string; parts?: { kind: string; text?: string }[] }[];
  error?: string;
}

function toTaskView(raw: RawTask): TaskView {
  const artifact = raw.artifacts?.[0];
  const texts = (artifact?.parts ?? [])
    .filter((p) => p.kind === "text" && typeof p.text === "string")
    .map((p) => p.text as string);
  return {
    id: raw.id,
    state: raw.status.state,
    text: texts.length ? texts.join("\n") : null,
    uri: artifact?.uri ?? null,
    error: raw.error ?? null,
  };
}

async function call(
  url: string,
  body: unknown,
  payment?: string,
): Promise<{ res: Response; json: Record<string, unknown> | null }> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (payment) headers["X-PAYMENT"] = payment;
  const res = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
  const json = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  return { res, json };
}

function fail(res: Response, json: Record<string, unknown> | null): never {
  const rpcError = json?.error as { message?: string } | string | undefined;
  const code =
    typeof rpcError === "string" ? rpcError : (rpcError?.message ?? `http_${res.status}`);
  throw new GatewayError(res.status, code);
}

/**
 * `message/send`. Without `payment` a paid agent answers with its x402
 * challenge; with a valid one it settles and returns the new task.
 */
export async function sendMessage(url: string, text: string, payment?: string): Promise<SendResult> {
  const { res, json } = await call(url, rpc("message/send", textMessage(text)), payment);
  if (res.status === 402 && json && Array.isArray(json.accepts)) {
    return { kind: "payment_required", challenge: json as unknown as X402Challenge };
  }
  if (!res.ok || !json?.result) fail(res, json);
  return {
    kind: "task",
    task: toTaskView(json.result as RawTask),
    receipt: decodeReceipt(res.headers.get("X-PAYMENT-RESPONSE")),
  };
}

/** `tasks/get`: current state of a task, with the output once completed. */
export async function getTask(url: string, id: string): Promise<TaskView> {
  const { res, json } = await call(url, rpc("tasks/get", { id }));
  if (!res.ok || !json?.result) fail(res, json);
  return toTaskView(json.result as RawTask);
}
