# OMA + ANANKE project index

This is a local Windows engineering application. User directive is authoritative:
`docs/PRODUCTION_DIRECTIVE.md` (unaltered copy of the supplied attachment).
Original mathematics in `math1/` and acquired IFC inputs are read-only.

- Scope: IFC import/federation, OMA/ANANKE optimization, physical routing, independent verification, live workbench, edited IFC export/recheck.
- Excluded: MCP product architecture, required hosted models, architectural foundation-model training, unrelated AI infrastructure.
- Evidence: `evidence/math/`, `evidence/ifc/`, `evidence/benchmarks/`.
- Current work and next commands: `docs/PROGRESS.md`.
- Single capability register: `docs/capabilities.json`.
- Backend: Python 3.12, `src/oma/`; frontend: `ui/`.
- Environment: `.venv/Scripts/python.exe`; tests: `.venv/Scripts/python.exe -m pytest`.

Never turn missing geometry/inputs, timeout, unchecked state, or restricted search into a verification/optimality claim. Physical checker evidence must bind the persisted root, rules, mission, numerical model and software version. No original overwrites. Never use benchmark-specific exceptions. Keep agent file ownership explicit and integrate frequently.
