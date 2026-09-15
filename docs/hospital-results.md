# Hospital: checked routing comparison

For the subsequent all-seven-model HVAC, plumbing, electrical, sprinkler and fire-alarm assessment, see [whole-project installed services](hospital-installed-services.md). That run accounts for the existing hospital population; the checked routing comparison below remains a separate hypothetical two-terminal case.

On 2026-09-15, source build `06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949` completed generation, independent checking of both alternatives, selection, revision-2 acceptance and a fresh exported-IFC check. The complete campaign took **1,347.828 seconds (22.46 minutes)**.

This is a **two-terminal hypothetical pressure-pipe scenario against the complete Hospital architectural model**. Every architectural obstacle is included. The six other disciplines are outside this declared mission; this is not an installed-services redesign or a seven-discipline coordination result.

| Measured quantity | Selected alternative | Other feasible alternative |
|---|---:|---:|
| Unique routing length | 5.000000 m | 5.785398 m |
| Fittings | 1 | 5 |
| Physical components | 4 | 12 |
| Physical ports | 9 | 25 |
| Architectural obstacles | 14,409 | 14,409 |
| Component–obstacle comparisons | 57,636 | 172,908 |
| Distinct component-pair comparisons | 6 | 66 |
| Geometry, connectivity and declared service | PASS | PASS |
| Demand A irreversible pressure loss | 37.7105–37.7220 Pa | 51.6706–51.6859 Pa |
| Demand B irreversible pressure loss | 34.5239–34.5340 Pa | 34.5239–34.5340 Pa |

The selected alternative is **13.6% shorter**, uses **80% fewer fittings**, and reduces calculated Demand A irreversible loss by approximately **27%**. Demand B loss is unchanged. Both alternatives satisfy the same supplied simultaneous deliveries of 0.5 L/s per terminal, 100 Pa available static pressure difference and 2 m/s velocity limit. These are conditional results under the explicitly supplied ideal-bore, fixed-flow-control, Darcy-friction and fitting-loss assumptions; actual bore, terminal equipment and pump applicability are outside the model.

The optimizer minimizes unique length among the two checked alternatives in the predeclared finite catalogue. Fitting and pressure-loss reductions are additional measured outcomes, not separate optimized objectives. This does not establish an unrestricted global routing optimum or savings against an existing hospital installation.

The independent replay confirms strictly separated length bounds, with at least 0.785382 m improvement. Demand A loss decreases by 13.9487–13.9754 Pa. The deliveries are prescribed inputs to this fixed-flow check; an uncontrolled hydraulic operating point is not established.

The exported selected IFC passed a **separate completed managed execution**: four components, nine ports, all 57,636 source pairs, all six component pairs and the declared service checks. Original IFC bytes and records remain unchanged. Every mandatory check passes; no missing, failed or ambiguous clearance is treated as success.

## What changed

The follow-up [component-cost and structural-input audit](hospital-cost-and-structural-readiness.md) distinguishes centerline length from purchased straight pipe: both alternatives use 4.625 m of nominal straight stock and one tee; the selected alternative removes four elbows and eight modeled internal interfaces. No whole-hospital currency saving or structural safety approval follows from this benchmark. The seven source IFC4 files contain no embedded cost entities, and the structural files lack the load/support/analysis inputs needed for a buildability determination.

- The exact source enclosure checker captures immutable project identities once instead of repeatedly scanning all 1,346,650 source records. Identity-frame support avoids unnecessary directed-rounding matrix arithmetic while preserving enclosure results.
- The selected federation reference uses an exact identity transform after the existing datum prerequisites, avoiding numerical transform noise and unnecessary reference-model reconstruction.
- Every source product is still inventoried. Only obstacles whose independently reconstructed source enclosures prove sufficient separation avoid native conversion; near or unsupported objects retain the native checks and complete pair denominator.
- Tee CSG operands are authored near the fitting's local origin, with the correct building placement and relative owned ports. This corrects translation-sensitive native Boolean geometry. Dimensions, source geometry and the existing volume acceptance threshold remain unchanged.

A cold clearance probe completed in **305.41 seconds**, accounting for the same 14,409 represented obstacles and 232 grounded assemblies, with zero unresolved or failed geometry. The earlier hospital campaign exhausted its 1,800-second native-clearance budget. The cold probe alone was geometry evidence; the completed campaign additionally checks connectivity, service, acceptance and export.

## Evidence and recovery

- [Accepted campaign, both alternatives and actual exported IFC](../evidence/benchmarks/hospital-native-performance/accepted-4f0e44e4557a43528250e6884e8efd95/handoff.json).
- [Independent outcome and pressure-loss replay](../evidence/benchmarks/hospital-native-performance/outcome-independent-95ec195c23b0451faee62f3d27747e51/handoff.json).
- [Final 3,317-case original-native regression](../evidence/release/hospital-original-regression/final-06aa-1dc9d7691342/handoff.json): no failures, errors or skips; exact source and test identities retained.
- [Independent regression inventory verification](../evidence/release/hospital-original-regression/final-06aa-independent-verification-1dc9d7691342/handoff.json).
- [Cold full-inventory clearance](../evidence/benchmarks/hospital-native-performance/clearance-a7fcb8a295e249da85fdfe2493eaa3a2/handoff.json).
- [Tee controls and regression tests](../evidence/benchmarks/hospital-native-performance/local-tee-independent-a6d4e79524a442f288b3529e5b326387/handoff.json), including the failing prior build and corrected geometry.
- [Retained rejected fresh campaign](../evidence/benchmarks/hospital-native-performance/tee-volume-failure-426104a1bed4497ab1fe00902b92014d/handoff.json). Its failures remain historical failures.
- [Seven-model alignment and installed-service audit](../evidence/benchmarks/hospital-native-performance/alignment-and-installed-service/handoff.json). Approved discipline alignment and actual service contracts remain missing; they cannot be inferred from these routing results.

The original inputs, executed scripts, frozen application code, current IFC bytes, reports, execution receipts and lossless file mappings accompany the retained evidence. Existing portable releases remain separate immutable recovery checkpoints; this result does not create a new portable package. Full original OMA/ANANKE mathematics and complete production readiness remain unfinished.

The tested source is [running locally](../evidence/release/validated-backend-hospital-update/19be511c32ca447da2c213f0ce377940/handoff.json) at `http://127.0.0.1:8768`. The upgrade preserved all existing project data and interface assets. The Hospital campaign itself remains an isolated, retained benchmark Store, with its actual exported IFCs available in the campaign evidence.
