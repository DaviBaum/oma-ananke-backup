# Generated shared-tree backend

The backend can construct two- or three-sink branching networks from fixed terminals, placed tees and a bounded connector search. The request supplies requirements and individual fitting locations. The generator constructs the complete alternative networks, retaining shared trunks once in both the design and nominal cost.

This feature is available through the local backend API. The existing workbench interface is unchanged.

## API workflow

Import a source IFC into a project first. Submit this shape to `POST /api/projects/{project_id}/runs`:

```json
{
  "operation": "propose_network",
  "budget_seconds": 120,
  "idempotency_key": "unique-generation-request",
  "mission": {
    "schema": "oma.shared-tree-proposal-job/1",
    "requirements": {},
    "search": {},
    "max_results": 8
  }
}
```

The empty objects above show the envelope only. `requirements` contains the existing `SharedNetworkScenario` fields except `network_alternatives`. `search` contains exactly:

- `schema`: `oma.shared-tree-native-search/1`;
- `source_direction` and a complete `sink_directions` map of signed coordinate axes;
- `tee_instances`: IDs, centers, two perpendicular frame axes, and trunk/branch takeouts;
- `stub_lengths_m`: one to four positive proposed lengths;
- `detour_planes`: up to eight `{axis, value_m}` records.

The [three-sink pressure example](../examples/shared-tree-three-sink-request.json) is a complete synthetic request from the native regression fixture. Its coordinates and hydraulic assumptions were authored for that fixture. A building project needs its own terminals, zone, fitting locations and justified boundary data.

Poll `GET /api/runs/{run_id}` and read `GET /api/projects/{project_id}/events`. The `network_generation_complete` event supplies `payload.proposal_artifact_root`. Fetch it through `GET /api/artifacts/{root}`. If `result.status` is `PROPOSALS_READY`, submit `result.mission` unchanged in a new run with `operation: "optimize"` and a new idempotency key. That ordinary run materializes the alternatives and performs native geometry and service checks. Acceptance and export use the existing candidate APIs and current project revision.

Generation itself does not create candidates or change the project revision. Its immutable artifact binds the original request, source manifest, project state/revision, numerical policy and executable. Cancellation and deadlines use the existing supervised worker controls. An empty finite menu is reported as unresolved physical feasibility.

## What is proved

The independent catalogue checker reconstructs the admitted connector geometry, fabrication certificate, fitting identities, cap directions and rational-plus-pi nominal cost. A separate graph verifier enumerates every supported rooted assignment in that supplied catalogue and checks the full canonical assignment ledger and ranked prefix. Each tee and connector is charged once, including shared trunks.

The authored connector language is bounded. Membership is independently checked; completeness of every possible geometric template is not. Exact ranking covers the supplied nominal catalogue. It is not a lower bound on the native objective, an unrestricted topology optimum, or a proof that omitted physical alternatives are infeasible. `max_results` limits the returned prefix; a later alternative may be the first physically feasible one.

The geometry adapter currently requires exact binary64-representable coordinates for its nominal correspondence. Unsupported geometry, exhausted arithmetic/work budgets and unresolved comparisons remain explicit non-success states.

## Pressure-driven specialization

Fixed-flow and geometry-only requirements remain supported. The unequal-outlet `coupled_tree` profile requires exactly one fixed site per named tee loss identity, two or three sinks, and exactly sinks-minus-one tees. Each `b` and `branch` coefficient stays attached to its original tee and outlet. The complete source/sink pressure intervals, minimum deliveries, proof proposal box, fluid/loss assumptions and velocity limits remain unchanged through generation.

Each physical candidate still needs complete current native geometry and metric checks, independently reconstructed pressure equations, same-model local existence and global nonnegative uniqueness, and every delivery/port-velocity check. A pressure proof alone cannot override a geometry or service failure. Other generated pressure profiles remain unsupported.

The retained three-sink example passes native checks, acceptance at revision 2 and a fresh exported IFC check: 11 parts, 24 ports, 22 source pairs and 55 component pairs. Its reverse-pressure case remains unaccepted. An earlier proof box was too narrow to certify the full native uncertainty; the later fixture widens only that computational box, retaining all physical pressures, losses and delivery requirements. Both attempts and the independent exact diagnosis are preserved.

Mathematical contracts: [finite synthesis](math/shared-tree-synthesis.md), [catalogue provenance](math/shared-tree-catalogue-provenance.md), and [fixed-identity pressure provenance](math/shared-tree-coupled-provenance.md). Current validation and remaining work are recorded in [PROGRESS.md](PROGRESS.md). Full original mathematics and full production readiness remain incomplete.
