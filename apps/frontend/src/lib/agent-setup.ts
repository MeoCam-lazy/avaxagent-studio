import type { Agent } from "@/lib/types";

export type WizardStep = "config" | "wallet" | "register" | "done";

export const WIZARD_STEPS: { key: Exclude<WizardStep, "done">; label: string }[] = [
  { key: "config", label: "Cấu hình" },
  { key: "wallet", label: "Ví Turnkey" },
  { key: "register", label: "Đăng ký ERC-8004" },
];

/** Where an existing agent resumes in the creation wizard. */
export function stepForAgent(agent: Agent): WizardStep {
  switch (agent.status) {
    case "draft":
      return "wallet";
    case "provisioning":
    case "registering":
    case "failed":
      return "register";
    default:
      return "done";
  }
}

/** True while an agent still has a wizard step left (anything not active or paused). */
export function needsSetup(agent: Agent): boolean {
  return stepForAgent(agent) !== "done";
}
