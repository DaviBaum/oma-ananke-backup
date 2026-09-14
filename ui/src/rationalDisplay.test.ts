import { describe, expect, it } from "vitest";
import { intervalDecimal, rationalDecimal } from "./rationalDisplay";
describe("read-only rational evidence display", () => {
  it("preserves outward enclosure for negative and positive endpoints", () => {
    expect(intervalDecimal({ lower: "-1/3", upper: "1/3" }, 3)).toBe(
      "−0.334 to 0.334",
    );
    expect(intervalDecimal({ lower: "-2/3", upper: "-1/3" }, 3)).toBe(
      "−0.667 to −0.333",
    );
  });
  it("does not overflow when native rational numerator and denominator exceed Float64", () => {
    const large = 10n ** 800n;
    expect(rationalDecimal(`${3n * large}/${1000n * large}`)).toBe("0.003");
  });
  it("keeps exact terminating flow values and fails closed for absent or invalid fields", () => {
    expect(rationalDecimal("1/500")).toBe("0.002");
    expect(rationalDecimal("2/-1000")).toBe("−0.002");
    expect(rationalDecimal("1/0")).toBe("Not reported");
    expect(rationalDecimal(undefined)).toBe("Not reported");
  });
});
