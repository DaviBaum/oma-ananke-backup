# Execution checkpoint

Updated 2026-09-14. Implementation remains in progress. No full-production or full-ANANKE release claim is made. The complete user directive is preserved in PRODUCTION_DIRECTIVE.md; capabilities.json is the release-gate register.

## Working implementation

- Windows local Python service, isolated parser/checker workers, React/Three.js workbench, durable SSE, immutable content roots, SQLite revision/outbox transactions, guarded accept/revert, historical and candidate inspection.
- All 50 IFC-Bench files acquired at pinned repository commit, all 33 mandatory files represented in the audit campaign. Final retry dispositions are recorded in evidence/ifc/campaign.json; failed attempts remain evidence.
- Real IFC geometry and properties, explicit source coverage failures, separate local-datum and global-georeferencing claims. Digital Hub loads 13,677 products and renders 5,152 meshes / 2,534,364 triangles.
- Explicit bounded routing scenarios produce real extruded/revolved IFC solids with ports, insulation envelope and physical fittings. Independent fresh-process checks cover input identities, protected content, actual solids, port/body attachment, terminal connectivity, clearance, self-contact and declared service requirements. Composite scenarios now check simultaneous demands and explicitly authorized design choices, including all cross-route physical pairs, and use candidate-rooted finite co-design selection with independent replay.
- Analytic building repair: obstructed route rejected, detour checked, accepted at revision 2, exported as replacement IFC and freshly rechecked, then reverted at revision 3. Adversarial moved bodies and weakened requirements are rejected.
- Exact rational finite master/certificates, physical fibers, verified finite contextual quotient compiler, supplied-tree separator dynamic programming and Boolean symbolic quotient discovery now have executable source-derived benchmarks and independent checkers. Synthetic counts are explicitly labeled; these do not establish complete continuous ANANKE optimization on real buildings.
- Grounded assurance now binds actual checker reports, explicit assumptions and known validation advisories; independently replayed proof cores and external evidence cuts remain separate from physical PASS. Actual engineering revision publication cold-compares inventory, netlist, mission coverage and complete input invalidation. Full Sixty5 unchanged-state reconstruction covers 188,312 entities and all 7 sources in 7.70 seconds on the pinned benchmark. Native CAD verdicts are never reused across changed roots by this metadata layer.
- RTX 3090 real-corpus broad-phase measurements: 57,293 boxes by 4,096 queries; CPU/GPU result hashes agree. Evidence includes setup/transfer/synchronization. Digital Hub real camera navigation measured about 59.87 FPS at the recorded viewport, with separate CPU-submission timing.
- Digital Hub, Dental Clinic, Duplex and WBDG Office completed actual repair/check/accept/export cycles, and Office also completed a two-demand simultaneous route-set export. A subsequent standards review identified IFC-PORT-001: earlier authored port-semantic checks are superseded. Corrected export/check logic is being validated and all affected examples require regeneration. Physical clearance and whole-building scopes remain separate.
- Sixty5 renders all 78,173 meshes / 50,865,326 triangles. Recorded native viewport is 975 by 324 CSS pixels at DPR 2; actual GPU timer p95 is 6.3 ms and camera navigation about 59.87 FPS. Cooperative scene assembly supports cancellation without stale scene publication.
- Browser upload endpoint streams actual bytes with bounded disk/time/size usage, immutable hashes and durable retry receipts. Actual Duplex byte upload and subsequent UI import passed. Automated native file chooser selection is limited by browser extension permissions; that automation path is not claimed tested.
- Portable backup includes source, geometry, candidate and export bytes, native coordinate sidecars, immutable roots and event history. Relocation is separate from proof provenance. A full actual-IFC restore/recheck test passes with the old store unavailable. Asset copying no longer holds the live publication lock.
- Portable preview bundles Python 3.12.14 and all runtime wheels, launches without external Python/Node, and passes an offline analytic IFC import/repair/check/accept/export cycle. Native notices/source review is recorded, with explicit CGAL/IfcOpenShell corresponding-source and Microsoft redistribution gates. Final distribution and the remaining release gates are still pending.
- Canonical reconstructed and integration source content review is complete with explicitly distinguished reading modes. Historical Pages decoding revealed 101,153 native paragraphs and substantial original mechanisms absent from reconstruction; semantic reconciliation is ongoing and remains a release obligation.

## Active ownership

- Root: orchestration, proof applicability, transactional state, portable recovery, integration, releases.
- math_audit: complete tracked source review, mathematical dispositions and bounded exact optimization/dependency implementations.
- ifc_pipeline: all-file campaign, geometry/enclosure policies, independent CAD checks, frozen real repair scenarios, export.
- workbench_ui: actual browser QA, navigation/control/reconnect measurements, larger-model workbench validation.

## Required work still open

1. Finish actual source review and disposition every canonical/integration obligation. Source templates contain underspecified claims and errors; record amendments rather than treating headings as proofs.
2. Complete frozen real-model repair/optimization campaign, including large federations and failed/ineligible denominators.
3. Extend checked simultaneous independent routes to physical shared trunks, topology/architectural changes and scenario-conditioned engineering analysis. The current joint finite design-option implementation does not establish complete continuous OMA/ANANKE coverage.
4. Extend actual cold-compared metadata/input dependency integration into certified incremental physical/simulation artifact reuse. Complete corrected IFC flow-axis/owner-placement normalization and regenerate affected IFC-PORT-001 examples; unresolved frames and source gaps remain explicit.
5. Expand interruption, pause, resource exhaustion, crash/restart and relocated real-project verification.
6. Finish large-model UI benchmarks, offline wheelhouse/distribution, complete third-party notices and clean-install tests.
7. Independently evaluate every directive release gate. scripts/release_check.py must continue failing while required capabilities remain incomplete.

Original mathematical sources and benchmark IFC inputs remain read-only. Use .venv/Scripts/python.exe -m pytest and npm --prefix ui test -- --run for the scoped suites. Live server and data are local; no runtime model/MCP/cloud dependency is required.

Latest full test checkpoint: 205 tests passed at build 7268a9463fb3637807f845b1c7c05f3f5c5f3ea4398a6560121239f8ad567f9e, before the subsequent port-semantic correction. New scoped tests and current integration validation continue. Full live-store backup-v2 copied 1,184 files / 3,329,453,604 bytes and passed manifest validation; full restored-store checks are underway.
