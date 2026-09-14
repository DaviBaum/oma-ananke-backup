import { describe, expect, it } from "vitest";
import { scopeEvidence } from "./evidenceScope";
import type { Candidate, CheckRecord } from "./types";

describe("immutable evidence scope", () => {
  const candidates = [
    { id: "baseline", state_root: "r1" },
    { id: "proposal", state_root: "r2" },
  ] as Candidate[];
  const checks = [
    { id: "a", candidate_id: "baseline" },
    { id: "b", candidate_id: "proposal" },
  ] as CheckRecord[];
  it("never shows later candidate results on revision zero", () => {
    expect(scopeEvidence(checks, candidates, "r0")).toEqual([]);
  });
  it("shows only the selected physical state evidence", () => {
    expect(scopeEvidence(checks, candidates, "r1").map((c) => c.id)).toEqual([
      "a",
    ]);
  });
  it("isolates an explicitly inspected alternative", () => {
    expect(
      scopeEvidence(checks, candidates, "r1", "proposal").map((c) => c.id),
    ).toEqual(["b"]);
  });
});
