import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { stepForAgent, type WizardStep } from "@/lib/agent-setup";
import { ConfigStep, RegisterStep, Stepper, WalletStep } from "@/pages/agents/wizard-steps";

/** How often step 3 polls `GET /registration` while the tx is pending. */
export const REGISTRATION_POLL_MS = 3000;

/**
 * Three-step agent creation: config -> wallet -> register -> done.
 * The agent id lives in `?id=` so a reload, or the "Tiếp tục thiết lập" link
 * on an unfinished agent, resumes at the right step.
 */
export function NewAgentPage({ pollIntervalMs = REGISTRATION_POLL_MS }: { pollIntervalMs?: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const agentId = params.get("id");
  const [step, setStep] = useState<WizardStep | null>(agentId ? null : "config");

  // Resume: derive the step from the saved agent once.
  const existing = useQuery({
    queryKey: ["agents", agentId],
    queryFn: () => api.agents.get(agentId!),
    enabled: agentId != null && step == null,
  });
  useEffect(() => {
    if (step == null && existing.data) setStep(stepForAgent(existing.data));
  }, [step, existing.data]);

  useEffect(() => {
    if (step === "done" && agentId) navigate(`/agents/${agentId}`, { replace: true });
  }, [step, agentId, navigate]);

  const onCreated = useCallback(
    (agent: Agent) => {
      queryClient.setQueryData(["agents", agent.id], agent);
      setParams({ id: agent.id }, { replace: true });
      setStep("wallet");
    },
    [queryClient, setParams],
  );
  const onRegistered = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["agents"] });
    setStep("done");
  }, [queryClient]);

  const index = { config: 1, wallet: 2, register: 3, done: 3 }[step ?? "config"];

  return (
    <>
      <PageHeader title="Tạo agent" description={`Bước ${index}/3 · config → ví Turnkey → đăng ký ERC-8004.`} />
      {step == null ? (
        <QueryState query={existing} feature="GET /agents/{id}">
          {() => null}
        </QueryState>
      ) : (
        <>
          <Stepper step={step} />
          {step === "config" && <ConfigStep onCreated={onCreated} />}
          {step === "wallet" && agentId && (
            <WalletStep agentId={agentId} onProvisioned={() => setStep("register")} />
          )}
          {step === "register" && agentId && (
            <RegisterStep agentId={agentId} pollIntervalMs={pollIntervalMs} onRegistered={onRegistered} />
          )}
        </>
      )}
    </>
  );
}
