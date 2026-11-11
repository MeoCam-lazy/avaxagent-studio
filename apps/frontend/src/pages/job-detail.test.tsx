import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { Job, JobEvent, JobStatus } from "@/lib/types";
import { JobDetailPage } from "@/pages/job-detail";
import { JobsPage } from "@/pages/jobs";
import { renderWithProviders } from "@/test/render";
import { defaultNetworkInfo, server } from "@/test/server";

const JOB_ID = "44444444-4444-4444-8444-444444444444";
const PAY_TX = "0x" + "ab".repeat(32);

function job(status: JobStatus, extra: Partial<Job> = {}): Job {
  return {
    id: JOB_ID,
    agent_id: "11111111-1111-4111-8111-111111111111",
    settlement_mode: "x402",
    status,
    chain_id: 43113,
    chain_job_id: null,
    client_address: "0x00000000000000000000000000000000000000c1",
    amount_atomic: 250_000,
    asset: "0x5425890298aed601595a70AB815c96711a31Bc65",
    request: { message: "Summarize the AVAX roadmap" },
    deliverable_uri: null,
    deliverable_hash: null,
    payment_tx_hash: PAY_TX,
    submit_tx_hash: null,
    settle_tx_hash: null,
    error: null,
    created_at: "2026-11-11T10:00:00Z",
    updated_at: "2026-11-11T10:00:00Z",
    ...extra,
  };
}

function event(type: string, i: number, data: Record<string, unknown> = {}, message = ""): JobEvent {
  return {
    id: `00000000-0000-4000-8000-00000000000${i}`,
    type,
    message,
    data,
    created_at: `2026-11-11T10:00:0${i}Z`,
  };
}

const settledJob = job("settled", {
  deliverable_uri: "file:///data/job-1.json",
  deliverable_hash: "0x" + "cd".repeat(32),
});
const settledEvents = [
  event("funded", 1, { tx_hash: PAY_TX }),
  event("llm_started", 2),
  event("submitted", 3, { uri: "file:///data/job-1.json" }),
  event("settled", 4),
];

/** Serves the job through `stages` (one per poll), then stays on the last one. */
function stagedBackend(stages: { job: Job; events: JobEvent[] }[]) {
  const counts = { job: 0, events: 0 };
  server.use(
    http.get(`*/api/v1/jobs/${JOB_ID}`, () => {
      const stage = stages[Math.min(counts.job, stages.length - 1)];
      counts.job += 1;
      return HttpResponse.json(stage.job);
    }),
    http.get(`*/api/v1/jobs/${JOB_ID}/events`, () => {
      const stage = stages[Math.min(counts.events, stages.length - 1)];
      counts.events += 1;
      return HttpResponse.json(stage.events);
    }),
    http.get(`*/api/v1/jobs/${JOB_ID}/deliverable`, () =>
      HttpResponse.json({
        uri: "file:///data/job-1.json",
        hash: "0x" + "cd".repeat(32),
        content: { job_id: JOB_ID, agent: "demo", output: "AVAX roadmap: subnets, then L1s." },
      }),
    ),
  );
  return counts;
}

function renderDetail() {
  return renderWithProviders(
    <Routes>
      <Route path="/jobs/:id" element={<JobDetailPage pollIntervalMs={10} />} />
    </Routes>,
    { route: `/jobs/${JOB_ID}` },
  );
}

describe("JobDetailPage", () => {
  it("test timeline polls until settled", async () => {
    const counts = stagedBackend([
      { job: job("funded"), events: [settledEvents[0]] },
      { job: job("running"), events: settledEvents.slice(0, 2) },
      { job: settledJob, events: settledEvents },
    ]);
    renderDetail();

    expect(await screen.findByText("Đã quyết toán")).toBeInTheDocument();
    const timeline = screen.getByRole("list", { name: "Timeline" });
    expect(within(timeline).getAllByRole("listitem")).toHaveLength(4);

    // Settled is terminal: polling stops.
    const after = counts.job;
    await new Promise((r) => setTimeout(r, 100));
    expect(counts.job).toBe(after);
  });

  it("shows the step progression for a running job", async () => {
    stagedBackend([{ job: job("running"), events: settledEvents.slice(0, 2) }]);
    renderDetail();

    const steps = await screen.findByRole("list", { name: "Tiến trình job" });
    const current = await within(steps).findByText("Chạy LLM");
    expect(current.closest("li")).toHaveAttribute("aria-current", "step");
  });

  it("test explorer link uses network explorer_url", async () => {
    stagedBackend([{ job: settledJob, events: settledEvents }]);
    renderDetail();

    const links = await screen.findAllByRole("link", { name: /0xabab/ });
    expect(links[0]).toHaveAttribute("href", `${defaultNetworkInfo.explorer_url}/tx/${PAY_TX}`);
  });

  it("shows the task input and the deliverable output", async () => {
    stagedBackend([{ job: settledJob, events: settledEvents }]);
    renderDetail();

    expect(await screen.findByText("Summarize the AVAX roadmap")).toBeInTheDocument();
    expect(await screen.findByText("AVAX roadmap: subnets, then L1s.")).toBeInTheDocument();
  });

  it("does not ask for a deliverable before one exists", async () => {
    let asked = 0;
    stagedBackend([{ job: job("running"), events: settledEvents.slice(0, 2) }]);
    server.use(
      http.get(`*/api/v1/jobs/${JOB_ID}/deliverable`, () => {
        asked += 1;
        return HttpResponse.json({ error: "deliverable_not_ready" }, { status: 404 });
      }),
    );
    renderDetail();

    await screen.findByText("Đang chạy LLM");
    expect(screen.getByText(/Chưa có deliverable/)).toBeInTheDocument();
    expect(asked).toBe(0);
  });

  it("shows the failure reason and stops polling", async () => {
    const counts = stagedBackend([
      {
        job: job("failed", { error: "upstream down" }),
        events: [settledEvents[0], settledEvents[1], event("failed", 3, {}, "upstream down")],
      },
    ]);
    renderDetail();

    expect(await screen.findAllByText("upstream down")).not.toHaveLength(0);
    const steps = screen.getByRole("list", { name: "Tiến trình job" });
    expect(within(steps).getByText("Chạy LLM").closest("li")).toHaveAttribute(
      "data-state",
      "failed",
    );
    const after = counts.job;
    await new Promise((r) => setTimeout(r, 100));
    expect(counts.job).toBe(after);
  });
});

describe("JobsPage", () => {
  it("links each row to its job log", async () => {
    server.use(http.get("*/api/v1/jobs", () => HttpResponse.json([settledJob])));
    renderWithProviders(<JobsPage />);

    const link = await screen.findByRole("link", { name: /11\/11|2026/ });
    await waitFor(() => expect(link).toHaveAttribute("href", `/jobs/${JOB_ID}`));
  });
});
