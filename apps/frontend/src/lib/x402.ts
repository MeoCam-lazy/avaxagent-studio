/**
 * x402 "exact" scheme on EVM: the payer signs an EIP-3009
 * `TransferWithAuthorization` for the asset, and the gateway relays it.
 * Mirrors `apps/backend/app/data_plane/gateway/x402.py` (`verify_payment`).
 */

/** One entry of a 402 challenge's `accepts[]`. */
export interface X402Accept {
  scheme: string;
  network: string; // CAIP-2, e.g. "eip155:43113"
  asset: `0x${string}`;
  payTo: `0x${string}`;
  amount: string; // atomic units
  maxTimeoutSeconds: number;
  extra: { name?: string; version?: string };
}

export interface X402Challenge {
  x402Version: number;
  error: string;
  accepts: X402Accept[];
}

export interface Authorization {
  from: `0x${string}`;
  to: `0x${string}`;
  value: bigint;
  validAfter: bigint;
  validBefore: bigint;
  nonce: `0x${string}`;
}

/** Settlement receipt from the `X-PAYMENT-RESPONSE` header. */
export interface PaymentReceipt {
  success: boolean;
  transaction: string;
  network: string;
  payer: string;
}

/** Seconds of clock skew tolerated between the browser and the gateway. */
const CLOCK_SKEW_S = 60n;

export function chainIdOf(network: string): number {
  const id = Number(network.split(":").pop());
  if (!Number.isInteger(id) || id <= 0) throw new Error(`unsupported network ${network}`);
  return id;
}

export function randomNonce(): `0x${string}` {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return `0x${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

export function buildAuthorization(
  accept: X402Accept,
  from: `0x${string}`,
  nowSeconds: number,
  nonce: `0x${string}` = randomNonce(),
): Authorization {
  const now = BigInt(Math.floor(nowSeconds));
  return {
    from,
    to: accept.payTo,
    value: BigInt(accept.amount),
    validAfter: now - CLOCK_SKEW_S,
    validBefore: now + BigInt(accept.maxTimeoutSeconds),
    nonce,
  };
}

/** EIP-712 payload for `signTypedData` (wagmi / viem shape). */
export function transferTypedData(accept: X402Accept, auth: Authorization) {
  return {
    domain: {
      name: accept.extra.name ?? "USD Coin",
      version: accept.extra.version ?? "2",
      chainId: chainIdOf(accept.network),
      verifyingContract: accept.asset,
    },
    types: {
      TransferWithAuthorization: [
        { name: "from", type: "address" },
        { name: "to", type: "address" },
        { name: "value", type: "uint256" },
        { name: "validAfter", type: "uint256" },
        { name: "validBefore", type: "uint256" },
        { name: "nonce", type: "bytes32" },
      ],
    },
    primaryType: "TransferWithAuthorization",
    message: auth,
  } as const;
}

/** Base64 `X-PAYMENT` header value for a signed authorization. */
export function encodePayment(
  accept: X402Accept,
  auth: Authorization,
  signature: `0x${string}`,
): string {
  const payload = {
    x402Version: 1,
    scheme: accept.scheme,
    network: accept.network,
    payload: {
      signature,
      authorization: {
        from: auth.from,
        to: auth.to,
        value: auth.value.toString(),
        validAfter: auth.validAfter.toString(),
        validBefore: auth.validBefore.toString(),
        nonce: auth.nonce,
      },
    },
  };
  return btoa(JSON.stringify(payload));
}

export function decodeReceipt(header: string | null): PaymentReceipt | null {
  if (!header) return null;
  try {
    return JSON.parse(atob(header)) as PaymentReceipt;
  } catch {
    return null;
  }
}
