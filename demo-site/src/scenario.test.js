import { test } from "node:test";
import assert from "node:assert/strict";
import { calculateScenario, sampleTypes, inspectIfcText } from "./scenario.js";

test("all sample stock options preserve every original piece and exact integer capacity", () => {
  for (const type of Object.keys(sampleTypes))
    for (const stockM of [3, 6, 12])
      for (const kerfMm of [0, 3, 5]) {
        const result = calculateScenario({ type, stockM, kerfMm, price: 23 });
        for (const bins of [result.before, result.after]) {
          const cuts = bins
            .flatMap((b) => b.cuts)
            .sort((a, b) => a.id.localeCompare(b.id));
          assert.deepEqual(
            cuts,
            [...result.pieces].sort((a, b) => a.id.localeCompare(b.id)),
          );
          for (const bin of bins)
            assert.ok(
              bin.cuts.reduce((sum, p) => sum + p.length + kerfMm, 0) <=
                stockM * 1000,
            );
        }
        assert.ok(result.selected.purchasedM <= result.baseline.purchasedM);
        assert.equal(result.savedCost, result.savedM * 23);
        for (const bin of result.before)
          assert.equal(new Set(bin.cuts.map((p) => p.batch)).size, 1);
      }
});
test("invalid scenario values are rejected", () => {
  for (const input of [
    { price: NaN },
    { price: -1 },
    { price: Infinity },
    { price: 1001 },
    { stockM: 0 },
    { stockM: 5 },
    { kerfMm: -1 },
    { type: "fake" },
  ])
    assert.throws(() => calculateScenario(input));
});
test("IFC inspector scans records but never implies semantic verification", () => {
  const result = inspectIfcText(
    "ISO-10303-21;\nHEADER;FILE_SCHEMA(('IFC4'));ENDSEC;\nDATA;\n#1=IFCWALL();\n#2=IFCWALL();\n#3=IFCPIPESEGMENT();\nENDSEC;END-ISO-10303-21;",
    "sample.ifc",
  );
  assert.equal(result.records, 3);
  assert.equal(result.schema, "IFC4");
  assert.deepEqual(result.classes[0], ["IFCWALL", 2]);
  assert.throws(() => inspectIfcText("<html/>", "bad.ifc"));
});
