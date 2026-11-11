import { recoverTypedDataAddress } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { describe, expect, it } from "vitest";

import {
  buildAuthorization,
  chainIdOf,
  decodeReceipt,
  encodePayment,
  transferTypedData,
  type X402Accept,
} from "@/lib/x402";

// Throwaway key, used only to exercise signing in tests.
const payer = privateKeyToAccount(`0x${"11".repeat(32)}`);

const accept: X402Accept = {
  scheme: "exact",
  network: "eip155:43113",
  asset: "0x5425890298aed601595a70AB815c96711a31Bc65",
  payTo: "0x00000000000000000000000000000000000000a1",
  amount: "250000",
  maxTimeoutSeconds: 300,
  extra: { name: "USD Coin", version: "2" },
};

describe("x402", () => {
  it("authorizes exactly the quoted amount to the agent, valid around now", () => {
    const auth = buildAuthorization(accept, payer.address, 1_000_000);
    expect(auth.to).toBe(accept.payTo);
    expect(auth.value).toBe(250000n);
    expect(auth.validAfter).toBeLessThan(1_000_000n);
    expect(auth.validBefore).toBe(1_000_300n);
    expect(auth.nonce).toMatch(/^0x[0-9a-f]{64}$/);
    expect(buildAuthorization(accept, payer.address, 1).nonce).not.toBe(auth.nonce);
  });

  it("signs an EIP-3009 transfer on the challenge's chain and token", async () => {
    const auth = buildAuthorization(accept, payer.address, 1_000_000);
    const typed = transferTypedData(accept, auth);
    expect(typed.domain).toEqual({
      name: "USD Coin",
      version: "2",
      chainId: 43113,
      verifyingContract: accept.asset,
    });

    const signature = await payer.signTypedData(typed);
    expect(await recoverTypedDataAddress({ ...typed, signature })).toBe(payer.address);
  });

  it("encodes the X-PAYMENT envelope the gateway decodes", async () => {
    const auth = buildAuthorization(accept, payer.address, 1_000_000, `0x${"ab".repeat(32)}`);
    const header = encodePayment(accept, auth, "0xdead");
    expect(JSON.parse(atob(header))).toEqual({
      x402Version: 1,
      scheme: "exact",
      network: "eip155:43113",
      payload: {
        signature: "0xdead",
        authorization: {
          from: payer.address,
          to: accept.payTo,
          value: "250000",
          validAfter: "999940",
          validBefore: "1000300",
          nonce: `0x${"ab".repeat(32)}`,
        },
      },
    });
  });

  it("reads the CAIP-2 chain id and the settlement receipt", () => {
    expect(chainIdOf("eip155:43114")).toBe(43114);
    expect(() => chainIdOf("solana:mainnet")).toThrow();
    const receipt = { success: true, transaction: "0xabc", network: "eip155:43113", payer: "0x1" };
    expect(decodeReceipt(btoa(JSON.stringify(receipt)))).toEqual(receipt);
    expect(decodeReceipt("%%%")).toBeNull();
    expect(decodeReceipt(null)).toBeNull();
  });
});
