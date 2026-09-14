# Simultaneous route design contract

The local route/optimize API accepts either an ordinary routing scenario or a composite mission:

```json
{
  "route_demands": [
    {"id": "supply", "alternatives": ["complete RoutingScenario object"]},
    {"id": "return", "alternatives": ["complete RoutingScenario object"]}
  ],
  "max_joint_candidates": 32,
  "max_paths_per_alternative": 4
}
```

The strings above describe where complete scenario objects belong; they are not executable mission values. Every demand has a stable identifier and one or more explicit physical design options. Alternatives retain the same service, load/physics inputs, clearance, minimum slope, source interpretation and assurance modality. Authorized endpoints, source discipline, permitted zone and physical catalog sizes may vary between alternatives. No source building element is silently moved or removed.

Each examined complete assignment materializes real IFC solids. One complete replacement IFC contains all proposed routes for each edited discipline. Every route is checked against every original physical obstacle, and every pair of parts belonging to different routes is independently checked using the stricter of the two clearances. There is no blanket exemption for a crossing or shared location. Physical shared tees and trunks are not implemented by this independent-route representation.

When another demand is added to an accepted state, its prior route definitions and mission contracts remain protected. The checker reopens prior and proposed IFC files and compares every prior STEP record. Geometry artifact locations may change, while the actual protected geometry, ports and relationships remain unchanged. Original source files are never overwritten.

The finite co-design kernel receives independently checked complete assignments, with a root-bound route master for each assignment. It replays exact finite arithmetic independently. Unexamined continuous route families remain outside the finite domain; time limits, rejected materializations and unexamined choices never establish global infeasibility or a global optimality gap.

Export copies one complete replacement per source, separately rechecks every route's IFC geometry/ports/system membership, then runs the composite independent checker on the exported state. Acceptance requires a current root-matched passing report. Exported objective values must equal the checked input candidate values.

`tests/test_joint_routing.py` demonstrates a crossing assignment being rejected, an authorized separated alternative passing, acceptance/export, an added third demand preserving the prior physical state, a second complete export, and rejection of a missing-demand tamper. These are analytic physical IFC fixtures, not evidence of performance or complete engineering design on every real federation.
