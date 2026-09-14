import { it, expect } from "vitest";
import { isServiceElement } from "./semantics";
it("uses imported IFC element type instead of assuming MEP file contents", () => {
  expect(
    isServiceElement({
      id: "wall",
      ifc_type: "IfcWall",
      source_file: "mep.ifc",
      discipline: "mechanical",
    }),
  ).toBe(false);
  expect(
    isServiceElement({
      id: "duct",
      ifc_type: "IfcDuctSegment",
      source_file: "arc.ifc",
      discipline: "arc",
    }),
  ).toBe(true);
  expect(
    isServiceElement({ id: "port", ifc_type: "IfcDistributionPort" }),
  ).toBe(false);
});
