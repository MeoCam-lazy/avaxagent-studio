import { describe, expect, it } from "vitest";

import { jobSteps, requestText } from "@/lib/job-log";

const states = (job: Parameters<typeof jobSteps>[0]) => jobSteps(job).map((s) => s.state);

describe("jobSteps", () => {
  const base = { deliverable_uri: null, payment_tx_hash: "0x1" };

  it("marks reached milestones done and the next one current", () => {
    expect(states({ ...base, status: "funded" })).toEqual(["done", "current", "todo", "todo"]);
    expect(states({ ...base, status: "submitted" })).toEqual(["done", "done", "done", "current"]);
    expect(states({ ...base, status: "settled" })).toEqual(["done", "done", "done", "done"]);
  });

  it("marks the step a failed job was on", () => {
    expect(states({ ...base, status: "failed" })).toEqual(["done", "failed", "todo", "todo"]);
    expect(states({ status: "failed", deliverable_uri: null, payment_tx_hash: null })).toEqual([
      "failed",
      "todo",
      "todo",
      "todo",
    ]);
  });
});

describe("requestText", () => {
  it("reads A2A message shapes like the worker does", () => {
    expect(requestText({ message: "hi" })).toBe("hi");
    expect(requestText({ message: { parts: [{ kind: "text", text: "a" }, { text: "b" }] } })).toBe(
      "a\nb",
    );
    expect(requestText({ prompt: "p" })).toBe("p");
    expect(requestText({ other: 1 })).toBe('{\n  "other": 1\n}');
    expect(requestText({})).toBe("—");
  });
});
