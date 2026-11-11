/** Avalanche USDC / EURC use 6 decimals. */
export const PAYMENT_DECIMALS = 6;

export function formatAtomic(amount: number | bigint, decimals = PAYMENT_DECIMALS): string {
  const value = BigInt(amount);
  const base = 10n ** BigInt(decimals);
  const whole = value / base;
  const frac = (value % base).toString().padStart(decimals, "0").replace(/0+$/, "");
  return frac ? `${whole}.${frac}` : whole.toString();
}

/**
 * Parse a human decimal amount ("0.25") into atomic units (250000n) using
 * string arithmetic only, so there is no float drift. Throws on malformed
 * input or on more fractional digits than the asset supports.
 */
export function parseAtomic(input: string, decimals = PAYMENT_DECIMALS): bigint {
  const match = /^(\d*)(?:\.(\d*))?$/.exec(input.trim());
  if (!match || (!match[1] && !match[2])) {
    throw new Error(`Không phải số hợp lệ: "${input}".`);
  }
  const [, whole, frac = ""] = match;
  if (frac.length > decimals) {
    throw new Error(`Số tiền chỉ được tối đa ${decimals} chữ số thập phân.`);
  }
  return BigInt(whole || "0") * 10n ** BigInt(decimals) + BigInt(frac.padEnd(decimals, "0") || "0");
}

export function shortAddress(address: string | null | undefined): string {
  if (!address) return "—";
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

export const CHAIN_NAMES: Record<number, string> = {
  43113: "Avalanche Fuji",
  43114: "Avalanche C-Chain",
};
