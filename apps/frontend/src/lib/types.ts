// Re-exported from the generated OpenAPI schema (`src/lib/api-schema.d.ts`).
// Run `pnpm gen:api` to refresh `api-schema.d.ts` from the backend OpenAPI spec.

import type { components } from "@/lib/api-schema";

export type Schemas = components["schemas"];

export type SettlementMode = Schemas["SettlementMode"];
export type AgentStatus = Schemas["AgentStatus"];
export type JobStatus = Schemas["JobStatus"];
export type LedgerKind = Schemas["LedgerKind"];
export type PayoutStatus = Schemas["PayoutStatus"];

export type LLMConfig = Schemas["LLMConfig"];
export type Agent = Schemas["AgentRead"];
export type AgentRead = Schemas["AgentRead"];
export type AgentCreate = Schemas["AgentCreate"];
export type AgentUpdate = Schemas["AgentUpdate"];
export type MarketplaceAgent = Schemas["MarketplaceAgent"];

export type WalletPolicy = Schemas["WalletPolicy"];
export type Wallet = Schemas["WalletRead"];
export type WalletRead = Schemas["WalletRead"];
export type WalletBalances = Schemas["WalletBalances"];

export type RegistrationRequest = Schemas["RegistrationRequest"];
export type RegistrationStatus = Schemas["RegistrationStatus"];
export type NetworkInfo = Schemas["NetworkInfo"];

export type FeeSchedule = Schemas["FeeSchedule"];
export type EarningsSummary = Schemas["EarningsSummary"];
export type LedgerEntry = Schemas["LedgerEntryRead"];
export type LedgerEntryRead = Schemas["LedgerEntryRead"];
export type PayoutCreate = Schemas["PayoutCreate"];
export type Payout = Schemas["PayoutRead"];
export type PayoutRead = Schemas["PayoutRead"];

export type Job = Schemas["JobRead"];
export type JobRead = Schemas["JobRead"];
export type JobEvent = Schemas["JobEventRead"];
export type JobEventRead = Schemas["JobEventRead"];
export type JobDeliverable = Schemas["JobDeliverable"];

export type NonceResponse = Schemas["NonceResponse"];
export type VerifyRequest = Schemas["VerifyRequest"];
export type TokenResponse = Schemas["TokenResponse"];
export type User = Schemas["User"];
