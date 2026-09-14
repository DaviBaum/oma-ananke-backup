# Execution checkpoint

Updated 2026-09-14. Implementation remains in progress. No full-production or full-ANANKE release claim is made. The complete user directive is preserved in PRODUCTION_DIRECTIVE.md; capabilities.json is the release-gate register.

## Working implementation

- Windows local Python service, isolated parser/checker workers, React/Three.js workbench, durable SSE, immutable content roots, SQLite revision/outbox transactions, guarded accept/revert, historical and candidate inspection.
- All 50 IFC-Bench files acquired at pinned repository commit, all 33 mandatory files represented in the audit campaign. Final retry dispositions are recorded in evidence/ifc/campaign.json; failed attempts remain evidence.
- Real IFC geometry and properties, explicit source coverage failures, separate local-datum and global-georeferencing claims. Digital Hub loads 13,677 products and renders 5,152 meshes / 2,534,364 triangles.
- Explicit bounded routing scenarios produce real extruded/revolved IFC solids with ports, insulation envelope and physical fittings. Independent fresh-process checks cover input identities, protected content, actual solids, port/body attachment, terminal connectivity, clearance, self-contact and declared service requirements.
- Analytic building repair: obstructed route rejected, detour checked, accepted at revision 2, exported as replacement IFC and freshly rechecked, then reverted at revision 3. Adversarial moved bodies and weakened requirements are rejected.
- Exact rational finite master and certificate checks, bounded physical fibers, exact geometric predicates, dependency/context/fixed-point primitives. These are scoped components; they do not establish full continuous global optimality or complete ANANKE implementation.
- RTX 3090 real-corpus broad-phase measurements: 57,293 boxes by 4,096 queries; CPU/GPU result hashes agree. Evidence includes setup/transfer/synchronization. Digital Hub real camera navigation measured about 59.87 FPS at the recorded viewport, with separate CPU-submission timing.
- Portable backup includes source, geometry, candidate and export bytes, immutable roots and event history. Relocation is separate from proof provenance. Restore verifies file hashes and SQLite integrity; process ownership is not inherited.
- Launcher and pinned installer exist. Full offline distribution and clean-machine installation are still pending.

## Active ownership

- Root: orchestration, proof applicability, transactional state, portable recovery, integration, releases.
- math_audit: complete tracked source review, mathematical dispositions and bounded exact optimization/dependency implementations.
- ifc_pipeline: all-file campaign, geometry/enclosure policies, independent CAD checks, frozen real repair scenarios, export.
- workbench_ui: actual browser QA, navigation/control/reconnect measurements, larger-model workbench validation.

## Required work still open

1. Finish actual source review and disposition every canonical/integration obligation. Source templates contain underspecified claims and errors; record amendments rather than treating headings as proofs.
2. Complete frozen real-model repair/optimization campaign, including large federations and failed/ineligible denominators.
3. Joint multiple-demand routing, shared trunks, source/topology co-design and scenario-conditioned engineering analysis; integrate the validated mathematical primitives into real state transitions.
4. Complete source-port normalization and real incremental/cold-equivalence checks.
5. Expand interruption, pause, resource exhaustion, crash/restart and relocated real-project verification.
6. Finish large-model UI benchmarks, offline wheelhouse/distribution, complete third-party notices and clean-install tests.
7. Independently evaluate every directive release gate. scripts/release_check.py must continue failing while required capabilities remain incomplete.

Original mathematical sources and benchmark IFC inputs remain read-only. Use .venv/Scripts/python.exe -m pytest and npm --prefix ui test -- --run for the scoped suites. Live server and data are local; no runtime model/MCP/cloud dependency is required.
