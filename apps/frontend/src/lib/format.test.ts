import { describe, expect, it } from "vitest";

import { assetLabel, formatAtomic, parseAtomic, shortAddress } from "@/lib/format";

describe("formatAtomic", () => {
  it("formats standard 6-decimal atomic values", () => {
    expect(formatAtomic(1_500_000)).toBe("1.5");
    expect(formatAtomic(0)).toBe("0");
  });

  it("keeps full precision for large bigint values", () => {
    // 2n ** 70n = 1180591620717411303424n
    expect(formatAtomic(2n ** 70n)).toBe("1180591620717411.303424");
  });
});

describe("shortAddress", () => {
  it("returns an em-dash for null or empty values", () => {
    expect(shortAddress(null)).toBe("—");
    expect(shortAddress(undefined)).toBe("—");
    expect(shortAddress("")).toBe("—");
  });

  it("shortens a full Ethereum address", () => {
    expect(shortAddress("0x5425890298aed601595a70AB815c96711a31Bc65")).toBe("0x5425…Bc65");
  });
});

describe("parseAtomic", () => {
  it("converts decimal strings without float drift", () => {
    expect(parseAtomic("0.1")).toBe(100000n);
    expect(parseAtomic("0.25")).toBe(250000n);
    expect(parseAtomic("1")).toBe(1000000n);
    expect(parseAtomic(" 12.5 ")).toBe(12500000n);
    expect(parseAtomic("0.000001")).toBe(1n);
    expect(parseAtomic("1.", 6)).toBe(1000000n);
    expect(parseAtomic("0.3", 18)).toBe(300000000000000000n);
  });

  it("rejects more decimals than the asset has", () => {
    expect(() => parseAtomic("1.0000001")).toThrow();
  });

  it("rejects empty, negative and non-numeric input", () => {
    for (const bad of ["", ".", "-1", "1e3", "abc", "1,5", "1.2.3"]) {
      expect(() => parseAtomic(bad), bad).toThrow();
    }
  });
});

describe("assetLabel", () => {
  const net = { payment_asset: "USDC", payment_asset_address: "0x5425890298aed601595a70AB815c96711a31Bc65" };

  it("names the network payment token regardless of address case", () => {
    expect(assetLabel("0x5425890298AED601595A70AB815C96711A31BC65", net)).toBe("USDC");
  });

  it("shortens unknown tokens and works before the network loads", () => {
    expect(assetLabel("0x00000000000000000000000000000000000000ee", net)).toBe("0x0000…00ee");
    expect(assetLabel("0x5425890298aed601595a70AB815c96711a31Bc65")).toBe("0x5425…Bc65");
  });
});
