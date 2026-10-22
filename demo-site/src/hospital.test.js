import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { hospital, comparison } from "./hospital.js";

const reportFile = path => new URL(`../../${path}`, import.meta.url);
const fraction = value => {
  const [numerator, denominator = "1"] = String(value).split("/");
  return Number(numerator) / Number(denominator);
};
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-7, `${actual} != ${expected}`);

test("public figures bind to both immutable reports and their selected plans", () => {
  for (const scenario of Object.values(hospital.scenarios)) {
    const bytes = readFileSync(reportFile(scenario.provenance.reportPath));
    assert.equal(createHash("sha256").update(bytes).digest("hex"), scenario.provenance.reportSha256);
    const report = JSON.parse(bytes);
    assert.equal(scenario.provenance.planRoot, report.purchasing_plan_root);
    assert.equal(scenario.provenance.requestRoot, report.request_root);
    assert.equal(hospital.provenance.checkerVersion, report.checker_version);
    for (const [demoKey, retainedKey] of [["perNetwork", "per_batch_scenario"], ["pooled", "baseline"], ["selected", "selected"]]) {
      for (const source of [{ plans: scenario.plans }, ...scenario.sources]) {
        const expected = source.sourceHash ? report.per_source_comparisons[source.sourceHash][retainedKey] : report.comparisons[retainedKey];
        const actual = source.plans[demoKey];
        close(actual.costUsd, fraction(expected.priced_material_subtotal.central));
        close(actual.purchasedM, fraction(expected.purchased_length_m));
        close(actual.requiredM, fraction(expected.required_length_m));
        close(actual.wasteM, fraction(expected.total_waste_m));
        assert.equal(actual.stockCount, expected.stock_count);
        assert.equal(actual.pieceCount, expected.piece_count);
      }
    }
  }
});

test("source and trade totals reconcile; no small-trade-only claim is presented as the entire hospital", () => {
  for (const scenario of Object.values(hospital.scenarios)) {
    assert.equal(scenario.sources.length, 7);
    assert.equal(scenario.trades.length, 4);
    assert.equal(scenario.sources.reduce((n, s) => n + s.productCount, 0), 149822);
    assert.equal(scenario.sources.reduce((n, s) => n + s.measuredCount, 0), 18559);
    assert.equal(scenario.sources.reduce((n, s) => n + s.unresolvedCount, 0), 793);
    assert.equal(scenario.sources.reduce((n, s) => n + s.plannedCount, 0), scenario.plannedCount);
    assert.equal(scenario.sources.reduce((n, s) => n + s.excludedCount, 0), scenario.excludedCount);
    assert.equal(scenario.sources.reduce((n, s) => n + s.additionalJoints, 0), scenario.additionalJoints);
    for (const key of ["perNetwork", "pooled", "selected"]) {
      for (const field of ["costUsd", "purchasedM", "requiredM", "wasteM", "stockCount", "pieceCount"]) {
        close(scenario.trades.reduce((n, s) => n + s.plans[key][field], 0), scenario.plans[key][field]);
      }
    }
  }
});

test("baseline toggles retain demand and show the correct, very different savings", () => {
  const broad = comparison();
  assert.equal(Math.round(broad.savings.costUsd), 35064);
  assert.equal(Math.round(comparison("broad", "pooled").savings.costUsd), 292);
  assert.equal(Math.round(comparison("noSplice").savings.costUsd), 29405);
  assert.equal(Math.round(comparison("noSplice", "pooled").savings.costUsd), 761);
  for (const sid of Object.keys(hospital.scenarios)) {
    for (const baseline of hospital.baselines) {
      const all = comparison(sid, baseline.id);
      assert.equal(all.before.requiredM, all.after.requiredM);
      assert.equal(all.before.pieceCount, all.after.pieceCount);
      close(all.savings.wasteM, all.savings.purchasedM);
      close(hospital.scenarios[sid].trades.reduce((n, s) => n + comparison(sid, baseline.id, s.id).savings.costUsd, 0), all.savings.costUsd);
    }
  }
  assert.equal(comparison("broad", "perNetwork", "fire").savings.costUsd, 0);
  assert.equal(comparison("broad", "perNetwork", "fire").savings.costPercent, null);
  assert.throws(() => comparison("unknown"), RangeError);
  assert.throws(() => comparison("broad", "unknown"), RangeError);
  assert.throws(() => comparison("broad", "pooled", "unknown"), RangeError);
});

test("review and procurement remain explicitly unapproved for construction", () => {
  const bytes = readFileSync(reportFile(hospital.review.reportPath));
  assert.equal(createHash("sha256").update(bytes).digest("hex"), hospital.review.reportSha256);
  const review = JSON.parse(bytes);
  assert.equal(hospital.review.constructionApproved, review.construction_approval);
  assert.equal(hospital.review.constructionApproved, false);
  assert.equal(hospital.review.geometryChanged, false);
  assert.equal(hospital.review.wholeBuildingRedesigned, false);
  assert.equal(hospital.scenarios.broad.additionalJoints, 3457);
  assert.equal(hospital.scenarios.noSplice.additionalJoints, 0);
  assert.equal(hospital.scenarios.noSplice.excludedCount, 2113);
  assert.equal(hospital.review.smallTailCount, 149);
  assert.equal(hospital.review.smallestTailMm, 3);
  assert.match(hospital.priceNote, /gross straight-material/);
  assert.match(hospital.scenarioNote, /cannot be added/);
});
