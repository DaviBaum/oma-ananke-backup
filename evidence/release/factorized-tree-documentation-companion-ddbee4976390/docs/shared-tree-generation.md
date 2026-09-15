# Generated shared-tree backend

The backend can construct two- through eight-sink branching networks from fixed terminals, placed tees and a bounded connector search. The request supplies requirements and individual fitting locations. The generator constructs complete alternatives, counting shared trunks once. Dense larger catalogues can exhaust the full-ledger budget. The explicitly selected compact method supports the same finite domain; declared four-through-eight-sink fixtures have completed native acceptance and fresh export on the current live f73 version.

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

The [four-sink pressure example](../examples/shared-tree-four-sink-request.json) supplies the complete new request. Optional `generation_budget` contains exactly integer `max_work` and `max_partial_trees`. Defaults are 2,000,000 work units and 20,000 partial trees; hard limits are 10,000,000 and 200,000. The four-sink example explicitly uses the larger limits. These resource limits do not alter physical requirements or authorize incomplete proofs. The current f73 checkpoint also supports the explicitly selected compact method described below.

## Optional compact method

This method is available in the live f73 backend recorded in [PROGRESS](PROGRESS.md). Existing requests omit `proof_method` and retain `FULL_LEDGER`. The new explicit value `COMPACT_TOP_K` chooses the separate compact recurrence certificate; `max_results` is K, an integer from 1 through 32. Both methods prove the supplied finite nominal catalogue, not geometric feasibility.

For the measured dense eight-sink K=2 case, add these fields inside `mission`:

```json
{
  "proof_method": "COMPACT_TOP_K",
  "max_results": 2,
  "generation_budget": {"max_work": 48000000, "max_partial_trees": 200000},
  "compact_limits": {
    "max_transitions": 2000000,
    "max_label_pairs": 10000000,
    "max_bytes": 33554432
  }
}
```

`generation_budget` keeps its two-field schema. Default work is 2,000,000; the FULL_LEDGER ceiling remains 10,000,000 and only explicit COMPACT_TOP_K requests can use up to 48,000,000. `max_partial_trees` retains its 20,000 default and 200,000 ceiling; the compact recurrence instead uses its own transition/label limits. `compact_limits` is optional, requires all three integer fields when present and is valid only with COMPACT_TOP_K. Its defaults are 500,000 transitions, 2,000,000 label pairs and 16,777,216 bytes; ceilings are 2,000,000, 10,000,000 and 33,554,432 bytes. The minimum byte value is 256. These limits are not a promise that every supported catalogue closes.

Complete synthetic [five-sink](../examples/shared-tree-5-sink-compact-request.json) and [eight-sink](../examples/shared-tree-8-sink-compact-request.json) request files accompany the f73 checkpoint. Each binds its own declared physical assumptions; copying a request into a different building does not establish those assumptions.

Every nested phase receives the remaining shared work and its own stricter ceiling: the independent catalogue checker at most 10M and each compact kernel at most 20M. Input parsing, proof replay and final output/publication checks are charged to the same job grant. Source generation alone does not run CAD or operating/service checks. Budget exhaustion yields no authoritative partial prefix or count. The 32MiB option is a bounded complete compact proof/output allowance, not an increase to the separate authored-input 2MiB/40,000-item or generated-macro400,000-item limits.

The compact result has the same proposal/mission structure as full-ledger output. Its certificate schema is `oma.shared-tree-topk-certificate/1`; `counts.complete_assignments` is a canonical decimal string, and `returned_proposals` is an integer. The exact nominal cost order is followed by deterministic sorted connector-ID tie order. Different connector words can describe the same materialized geometry. A native-rejected returned prefix does not prove the unreturned physical alternatives infeasible.

Poll `GET /api/runs/{run_id}` and read `GET /api/projects/{project_id}/events`. The `network_generation_complete` event supplies `payload.proposal_artifact_root`. Fetch it through `GET /api/artifacts/{root}`. If `result.status` is `PROPOSALS_READY`, submit `result.mission` unchanged in a new run with `operation: "optimize"` and a new idempotency key. That ordinary run materializes the alternatives and performs native geometry and service checks. Acceptance and export use the existing candidate APIs and current project revision.

Generation itself does not create candidates or change the project revision. Its immutable artifact binds the original request, source manifest, project state/revision, numerical policy and executable. Cancellation and deadlines use the existing supervised worker controls. An empty finite menu is reported as unresolved physical feasibility.

## What is proved

The independent catalogue checker reconstructs the admitted connector geometry, fabrication certificate, fitting identities, cap directions and rational-plus-pi nominal cost. With FULL_LEDGER, a separate graph verifier enumerates every supported rooted assignment in that supplied catalogue and checks the full canonical ledger and ranked prefix. The optional COMPACT_TOP_K verifier instead checks a complete count/top-K recurrence over the finite rooted mask-state domain. Each tee and connector is charged once, including shared trunks.

The authored connector language is bounded. Membership is independently checked; completeness of every possible geometric template is not. Exact ranking covers the supplied nominal catalogue. It is not a lower bound on the native objective, an unrestricted topology optimum, or a proof that omitted physical alternatives are infeasible. `max_results` limits the returned prefix; a later alternative may be the first physically feasible one.

The geometry adapter currently requires exact binary64-representable coordinates for its nominal correspondence. Unsupported geometry, exhausted arithmetic/work budgets and unresolved comparisons remain explicit non-success states.

## Pressure-driven specialization

Fixed-flow and geometry-only requirements remain supported. The unequal-outlet `coupled_tree` profile requires exactly one fixed site per named tee loss identity, two through eight sinks, and exactly sinks-minus-one tees. Each `b` and `branch` coefficient stays attached to its original tee and outlet. The complete source/sink pressure intervals, minimum deliveries, proof proposal box, fluid/loss assumptions and velocity limits remain unchanged through generation.

Each physical candidate still needs complete current native geometry and metric checks, independently reconstructed pressure equations, same-model local existence and global nonnegative uniqueness, and every delivery/port-velocity check. A pressure proof alone cannot override a geometry or service failure. Other generated pressure profiles remain unsupported.

The retained three-sink example passes native checks, acceptance at revision 2 and a fresh exported IFC check: 11 parts, 24 ports, 22 source pairs and 55 component pairs. Its reverse-pressure case remains unaccepted. An earlier proof box was too narrow to certify the full native uncertainty; the later fixture widens only that computational box, retaining all physical pressures, losses and delivery requirements. Both attempts and the independent exact diagnosis are preserved.

The four-sink accepted candidate and fresh export each pass 14 components, 31 ports, 28 source pairs, 91 unique component pairs, four deliveries, 32 continuity identities and 35 head paths. Its pressure boundary was independently authored with rational arithmetic and a separate Machin-series pi evaluation. Obstructed and reversed-pressure alternatives remain unaccepted.

Mathematical contracts: [original synthesis](math/shared-tree-synthesis.md), [four-to-eight extension](math/general-shared-tree-synthesis.md), [catalogue provenance](math/shared-tree-catalogue-provenance.md), and [pressure provenance](math/shared-tree-coupled-provenance.md). Current validation and remaining work are recorded in [PROGRESS.md](PROGRESS.md). Full original mathematics and full production readiness remain incomplete.

The current compact/factorized checkpoint has native accepted and freshly rechecked analytic fixtures for 4, 5, 6, 7 and 8 sinks. The independent seven/eight replay covers all complete saved native/pressure/accept/export bindings without rerunning CAD. Its scope and immutable evidence are in [the compact contract](math/shared-tree-topk.md). No Hospital acceptance follows from those fixtures.
