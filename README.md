# OMA + ANANKE

A local IFC engineering workbench under active implementation. Runs on Windows 11,
Python 3.12 and the tested RTX 3090. No hosted model, paid solver, account or cloud
runtime is required. **The complete production directive is not yet fulfilled.**
The authoritative capability and coverage status is in [the capability register](docs/capabilities.json).
See [the current checkpoint](docs/PROGRESS.md) for the running validated backend,
completed native tests, hospital results and portable recovery downloads.
The [checked Hospital comparison](docs/hospital-results.md) now includes two feasible
architectural-model alternatives, 13.6% less routing and a freshly checked IFC export.

Double-click **OMA.cmd**, or run `./Start-OMA.ps1`. The service binds only to
`http://127.0.0.1:8765` by default. The existing validated session runs at
`http://127.0.0.1:8768`. Initial installation uses `./Install-OMA.ps1`; after
dependencies and desired IFC files are acquired, the core workflow runs offline.

The workbench imports actual IFC geometry, displays source identity and missing
inputs, streams durable worker events, inspects candidates and witnesses, compares
revisions, and restores history. Source files are copied into immutable local
storage and never overwritten. Local repair verification has an explicit scope;
it does not certify the whole building or pre-existing defects.

## Implemented commands

Use `.venv/Scripts/python.exe -m oma.cli` (or `.venv/Scripts/oma.exe`):

```powershell
oma doctor --save evidence/hardware/current.json
oma import path/to/arc.ifc path/to/mep.ifc --name "My federation"
oma projects
oma serve --port 8765
oma check PROJECT_ID --budget-seconds 300
oma route PROJECT_ID scenario.json --budget-seconds 300
oma optimize PROJECT_ID scenario.json --budget-seconds 300
oma verify CANDIDATE_ID
oma accept CANDIDATE_ID EXPECTED_REVISION
oma export PROJECT_ID --candidate-id CANDIDATE_ID --no-draft
oma replay PROJECT_ID
oma revert PROJECT_ID TARGET_REVISION EXPECTED_REVISION
oma backup C:/path/to/new-backup-directory
```

The route/optimize commands support explicit circular routes, simultaneous
route demands, shared trunk/tee networks, and scoped revisions preserving prior
requirements. Exact finite optimization selects independently checked physical
alternatives. Source-bound route-cell mathematics supplies additional checked
geometric proposals; fabricated fittings still require a fresh physical check.
Complete continuous routing, broader topology and all ANANKE theory remain open.

The [generation API](docs/shared-tree-generation.md) also builds two- through
eight-terminal branching alternatives from individual tee sites and connector
choices. Its optional compact proof verifies exact finite counts and nominal
top-K results. Generated candidates still require native geometry and pressure
service checks before acceptance and fresh exported-IFC verification. Complete
five- and eight-terminal request examples are linked from the API guide.

One explicitly permitted rectangular wall/slab opening can be authored with its
route, inspected as actual cut geometry, accepted, exported and rechecked. The
opening form requires native host inspection, a bounded allowed edit volume and
explicit permission. Structural and fire approval are outside this geometric
contract. Subsequent opening-preserving revisions remain unsupported.

An explicit scenario supplies start/end positions in meters, system family,
diameter, insulation, bend radius, minimum straight length, clearance, a permitted
occupied zone and either source/sink port GUIDs or `scenario_terminals: true`.
The workbench exposes these fields and an advanced scenario editor. Hydraulic
adequacy additionally needs explicit physical inputs; geometric verification
alone never implies it.

## Reproduction and evidence

```powershell
.venv/Scripts/python.exe -m pytest
cd ui
npm test
npm run build
```

The original user directive is in `docs/PRODUCTION_DIRECTIVE.md`. Source hashes,
native equation extraction and exact reviewed locations are in `evidence/math/`.
Real IFC acquisition, per-model audit and federation evidence are in
`evidence/ifc/`. Hardware and benchmark records are in `evidence/hardware/` and
`evidence/benchmarks/`. Reading of all supplied canonical, integration and
historical mathematics is accounted, including 228 historical chunks and 264
native tables. Missing original sections are recorded. Reading coverage is
separate from mathematical validation and implementation completeness.

IFC-Bench is pinned to immutable commit
`66c0737e7a48d7e0ce9303f213d88f670cb27855`. All 50 IFC files were acquired;
all 50 have recorded geometry/compatibility dispositions. Unknown geometry and
remaining real-model engineering campaigns are explicit. Dataset inputs are
downloaded separately and are not bundled with the application. Project-specific
licenses and model cards are retained alongside acquired data.

See `docs/PROGRESS.md` for the current checkpoint and remaining release gates.
