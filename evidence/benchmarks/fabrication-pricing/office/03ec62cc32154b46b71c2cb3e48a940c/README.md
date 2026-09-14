# Frozen Office pricing attempt: native zone rejection retained

Build: `ebe15db28b384f99ffe9c19f8cfe9d16128d424b829250d75d5251372836e219`.
Project: `9c1387d3818f4cd59ffbbb4fff5030fd`; run: `f11ca7811cfc4a56bc3a20c17ea58ccc`.
The original source, original project and frozen mission were preserved. This is a hypothetical local added-service mission, not a whole-building approval.

The worker completed normally in 123.797 seconds; the strict campaign ended **INCOMPLETE** after 123.922 seconds because no priced candidate passed native checking. It did not time out. The campaign's `--require-pricing` assertion stopped acceptance and export. There is no newly released/rechecked export from this attempt. Materialized candidate IFC bytes and every rejection remain retained.

| Proposal | Native result | Actual directrix length (m) | Fittings |
| --- | --- | ---: | ---: |
| Original direct | REJECTED, original obstacle interference | 1.6539999999999964 | 0 |
| Priced finite graph | REJECTED, permitted-zone containment | 2.2564777960769336 | 2 |
| Feasible graph fallback | CHECKED | 2.8614777960769375 | 2 |
| Selected ordinary heuristic | CHECKED | 2.461477796076946 | 2 |
| Other ordinary heuristic | CHECKED | 2.836477796076946 | 2 |

The run attempted 14 proposals. Nine failed fitting/materialization; five became persisted candidates. Three passed full native checking. Selection retained heuristic candidate `355252b0485144efa5baf081ffcc86a8` without a continuous optimum claim. The completion event and both selection artifacts are retained separately from the failed campaign's `result.json`.

The source cell model accounted for all 805 physical records (803 obstacles and two assemblies) in 15.64 seconds, but its bounded inner graph returned UNKNOWN/no path. The full fabrication adapter took 1.64 seconds, including 0.672 seconds for cost pricing/replay. Five groups cover retained support and 798 obstacles have independently checked whole-body-region omission proofs.

The independently verified finite nominal optimum has exact cost

`189367357131674097/144115188075855872 + (5404319552844595/18014398509481984) * pi`

under length weight one and fitting weight zero. Its dual replay checked 115 explicit potentials and 215 reconstructed transitions. This finite nominal proof grants no native acceptance or numeric objective lower bound.

The priced candidate `dc1cdd0d98e14838897f60dc0e3796ff` passed the nominal binary64 fabrication proof and 13 mandatory native/semantic checks, but failed permitted-zone containment. Its materialized IFC SHA-256 is `028f43fd780c577dfb11d90827b63d255056b508c08ff07787272c9320d5955c`.

Fresh per-part diagnosis used the same frozen build and unchanged bytes. All five parts have a native kernel tolerance of `0.00001 m`; the checker requires zone gap strictly greater than `0.000011 m`. The middle straight's native bound exceeds the upper-X zone plane by about 10 micrometres. Both elbows' conservative native bounds exceed it by **0.030495114108219923 m**, so a 10-micrometre search inset alone cannot fix this bound. This diagnosis does not infer that the actual curved surface penetrates the zone; it reports the exact envelope criterion used by the authoritative checker.

Files: `result.json`, `events.json`, every candidate/report, source/fabrication model artifacts, `completion-*.json`, and `rejected-priced-route-zone-gaps.json`. `inspect_zone.py` records the reproducible read-only native envelope extraction.

## Independent optimal native bounds diagnosis

`inspect_optimal_bounds.py` reopens the same unchanged candidate bytes on the same frozen build, compares `BRepBndLib.Add_s(shape, box, False)` with `BRepBndLib.AddOptimal_s(shape, box, False, True)`, and retains `native-optimal-bounds-diagnosis.json`. It compares both algorithms with the independently checked exact nominal primitive bounds and samples actual trimmed native faces, native curves and vertices, including quarter-period parameters and six coordinate extrema. Sampling corroborates the bounds; it is not an enclosure proof.

For both elbows, AddOptimal removes the approximately 30.5 mm excess from Add_s. Every optimal bound is the nominal bound expanded by approximately 10 micrometres, matching the native shape tolerance within binary64 rounding. No sampled native point falls outside the optimal box. The three straight parts are unchanged by the bound algorithm.

The rejected priced candidate remains **FAIL** under the unchanged zone margin rule even with optimal bounds: its two elbows and middle straight still have upper-X gaps of approximately -10 micrometres. Using a tighter native enclosure does not remove the need for an interior proposal guard and a fresh full check of any newly materialized route. No production checker, original mission, candidate acceptance or active runtime was changed by this diagnosis.
