import { describe, it, expect } from "vitest";
import { currentPassingCheck } from "./checkApplicability";
import type { Candidate } from "./types";
const candidate: Candidate = {
  id: "c",
  state_root: "root",
  status: "CHECKED",
  check: { status: "PASS", applicability: "CURRENT" },
  objective: {},
  changed_ids: [],
  routes: [],
};
describe("current release evidence", () => {
  it("blocks a known defect even with a current passing report", () => {
    expect(
      currentPassingCheck({
        ...candidate,
        validation_advisories: [
          {
            id: "IFC-PORT-001",
            status: "REGENERATION_AND_FRESH_CHECK_REQUIRED",
            route_ids: ["route"],
            claim: "Port semantics superseded",
            reason: "Known native axis defect",
            source: "https://standards.buildingsmart.org/",
            scope: "Authored ports",
            resolution_contract: "Regenerate and independently verify",
          },
        ],
      }),
    ).toBe(false);
  });
  it("does not treat a historical passing verdict as current approval", () => {
    expect(currentPassingCheck(candidate)).toBe(true);
    for (const applicability of ["STALE_EXECUTABLE", "WRONG_ROOT", undefined])
      expect(
        currentPassingCheck({
          ...candidate,
          check: { status: "PASS", applicability },
        }),
      ).toBe(false);
  });
  it("does not grant release for a current rejection or absent candidate", () => {
    expect(currentPassingCheck({ ...candidate, status: "REJECTED" })).toBe(
      false,
    );
    expect(
      currentPassingCheck({
        ...candidate,
        check: { status: "FAIL", applicability: "CURRENT" },
      }),
    ).toBe(false);
    expect(currentPassingCheck(null)).toBe(false);
  });
});
