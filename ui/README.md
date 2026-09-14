# OMA + ANANKE local workbench

A standalone React, TypeScript, and Three.js interface for the local engine. It reads actual project snapshots, immutable IFC mesh artifacts, checks, candidates, and durable events. It does not generate demonstration models or simulated progress.

From the repository root:

```powershell
npm --prefix ui ci
npm --prefix ui run build
.venv\Scripts\python.exe -m oma.cli serve --port 8765
```

Open `http://127.0.0.1:8765/`. For frontend development, keep the engine running and execute `npm --prefix ui run dev`; Vite serves `http://127.0.0.1:5173/` and proxies `/api` to port 8765. The frontend does not need a cloud account or external asset service. Run `npm --prefix ui test` for the contract, engineering-input, evidence-scope, and geometry tests. A clean `npm ci` and production build were exercised on Node 20.15.1/npm 10.7.0. Exact package versions and integrity hashes are in `package-lock.json`; `dependency-register.json` records package license metadata.

The primary workflow is import absolute local IFC paths, inspect input audits and meshes, start an explicit scoped check or routing mission, inspect alternative candidates and their evidence, accept a qualifying candidate, and export a draft or checked release. The server enforces mutation and release predicates. A completed operation is not a global engineering certificate.

## Implemented interaction

- One shared world-coordinate origin preserves registration between files. Geometry must explicitly declare meters and world coordinates. Invalid mesh buffers stop rendering.
- Three.js meshes are batched by source discipline and candidate membership. A single-pixel GPU identity pass retains semantic entity selection without scanning tens of millions of triangles on the CPU. Multiple route fitting meshes retain one selectable route identity.
- Source visibility, IFC-type service filter, storey/system filtering, search, selection, isolate/hide, properties, and complete JSON records.
- Perspective, plan, section, horizontal clipping, an editable six-plane section box in world meters, x-ray, fit, focus, zoom, actual collision witness points, and candidate comparison. The envelope display is explicitly a parameterized straight-section guide, not a fitting-clearance certificate.
- Explicit routing inputs include service type, terminals or source/sink IFC port GUIDs, diameter, insulation, bend radius, minimum straight, clearance, and an allowed box. Additional engineering assumptions are entered as JSON. Missing dimensions remain missing; no loads or pressures are invented.
- SSE live events with durable cursor polling fallback. Project switches, out-of-order snapshots, duplicate events, obsolete geometry responses, and immutable root mismatches are guarded.
- Revision and candidate replay use dedicated snapshot and geometry queries. Historical views disable new runs and exports. Evidence is restricted to the selected immutable state or explicitly inspected candidate. Accept and revert use the current live revision plus stable retry idempotency keys.
- Every verdict exposes declared scope, reasons, participants, witnesses, and artifact links. Checks include pass, fail, unknown, blocked, and not-applicable statuses supplied by the engine.
- Hardware and capability diagnostics report observed backend data. API timing, control acknowledgement and observed state timing, and event-stream reconnect timing are accessible through **Diagnostics → Browser timing evidence**.

## Navigation measurement

The viewport's **Navigation benchmark** button fits the visible scene, disables interactive orbit controls, warms up for two seconds, then moves the camera around a fixed full orbit for ten seconds. Each sampled frame renders the real model. Results record immutable root, object/triangle counts, viewport size, pixel ratio, WebGL renderer, delivered frame intervals, CPU submission duration, and the mean 30 FPS gate. CPU submission duration does not include asynchronous GPU completion. Hidden tabs, changed scenes/settings, and explicit cancellation invalidate a run. A downloadable JSON record is retained in browser local storage.

Measurements describe the specific loaded scene and machine. They do not establish performance for an untested federation. See `qa/` for recorded browser observations and measurements.

## Current limits

The viewport incrementally reads immutable NDJSON mesh streams into typed arrays and then batches the complete mesh set in memory. The legacy JSON endpoint is used only for known small snapshots. Spatial LOD and view-dependent mesh streaming are not implemented. Candidate comparison hides/shows added route geometry and does not reconstruct an arbitrary removed baseline element. Explicit branching and element-lock editing require backend-supported UI flows beyond the present revision/candidate controls. The interface is designed for a desktop engineering workstation; very narrow screens hide the inspector.

The scope and completeness of physical verification, IFC round-trip preservation, graph optimization, or engineering-service capability are defined by backend evidence, not by frontend rendering.
