import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { NetworkInfo } from "@/lib/types";

export const defaultNetworkInfo: NetworkInfo = {
  network: "avalanche-fuji",
  chain_id: 43113,
  rpc_url: "https://api.avax-test.network/ext/bc/C/rpc",
  explorer_url: "https://testnet.snowtrace.io",
  identity_registry: "0x8004A818BFB912233c491871b3d84c89A494BD9e",
  payment_asset: "USDC",
  payment_asset_address: "0x5425890298aed601595a70AB815c96711a31Bc65",
  erc8183_enabled: false,
};

export const defaultHandlers = [
  http.get("*/api/v1/network", () => HttpResponse.json(defaultNetworkInfo)),
];

export const server = setupServer(...defaultHandlers);
