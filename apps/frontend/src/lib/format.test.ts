import { describe, expect, it } from "vitest";

import { formatAtomic, shortAddress } from "@/lib/format";

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
