# Optional integer fitting budget for independent joint routes

The joint request may specify `max_new_fittings = B`, a strict integer in
`[0, 1024]`. It bounds the number of newly authored independent round 90-degree
elbows across every demand in this increment. Straight components use zero.
Previously accepted protected routes retain their full physical obligations but
do not consume this increment's budget. Shared trees, tees, corridor resources,
arbitrary-angle fittings and catalog procurement are outside this contract.

Omitting the field preserves the historical serialized request and aggregate
rule hash. When present, the candidate contains
`derived_artifacts.joint_fitting_budget` with schema
`oma.joint-new-fitting-budget/1` and the exact requested integer. The aggregate
rule hash binds the ordered individual rule hashes, the versioned resource
definition and B. The individual route missions remain unchanged.

For newly authored routes N, independent verification establishes integer uses
`u_r` and checks `sum(u_r for r in N) <= B`. The denominator is the exact
difference between the complete current route set and the immutable baseline,
with each newly requested demand represented once. Each materialized component
has unique source/GUID ownership and a complete ordered part index. A prior
route cannot be relabeled or replaced to avoid counting.

`joint-new-fitting-budget` runs after every current per-route physical check.
It requires current materialization/directrix correspondence, native source and
self-interference evidence, complete native zone bodies and independent
objective recomputation. These checks are supplied by the same invocation;
their full content roots and native artifact roots are retained. The resource
checker does not rerun the native kernel or turn these local producer records
into externally authenticated attestations.

The checker streams each replacement IFC into a private digest-verified copy
and parses that copy. It independently reads the actual circular extrusion or
revolution for every owned component. A revolution must be a quarter turn
within the explicit `1e-7` radian classification tolerance; unsupported or
unresolved interpretations remain UNKNOWN. The actual unique elbow recount
must equal the strict integer count from current checked IFC semantics.
Actual directrix lengths and profile radii must also agree. Producer path
vertex counts, frontier labels and claimed fitting totals cannot substitute
for these current IFC facts.

Only a complete count sets `count_complete=true`, the integer `count`, and
`excess=max(0,count-B)`. Complete over-budget use fails. Missing prerequisites
remain NOT_RUN, unresolved geometry remains UNKNOWN, and inconsistent current
bindings fail; none becomes a zero count. Callbacks propagate cancellation
unchanged. Before returning, current source/replacement hashes and the original
request, state and baseline bindings are checked again.

The postchecked finite master uses each admitted route's exact integer use in
the `new-fabricated-elbows` capacity row. Its costs continue to come from the
declared objective applied to actual independently checked numerical IFC
measurements. A nominal exact-count frontier supplies candidate paths, but its
length or optimality does not replace native measurements or physical checks.
This budget proves a local resource constraint and confers no acceptance,
continuous global optimality, or nominal-to-native cost-bound authority.

Validation includes four actual two-route alternatives around an IFC obstacle:
each route can use a longer two-elbow detour or a shorter four-elbow detour.
B=6 admits either mixed assignment and rejects the physically valid eight-elbow
assignment. Other tests cover B=0, protected prior elbows, altered resource
requests, forged/omitted/permuted evidence, callback cancellation and the actual
joint engine's checked incumbent and retained capacity row.

The actual Office campaign on frozen `e3fde02b...` completed both budget cases
in 281.328 seconds. It preserves the original obstructed route mission and
adds a separate frozen straight service. With B=2, the selected two-elbow
frontier route and straight service total 3.2964797960769348 m, versus
3.661477796076949 m for the independently checked heuristic assignment. The
frontier's nominal graph certificate, binary64 correspondence and exact native
master capacity row are separately replayed. Acceptance and fresh IFC export
complete in 161.547 seconds. Both candidate and exported bytes pass all
4,015 + 803 route/source pairs against the 803 original obstacles, and all five
cross-route pairs. All nine export release bindings hold.

With B=0, two geometrically passing assignments each independently count two
actual elbows and fail the resource budget by two. The direct route fails
native geometry, and another attempt cannot be materialized because its
fittings consume the permitted straight segment. No checked incumbent is
published. The independently replayed 14-state zero-count graph contains no
admitted route, but neither that bounded graph result nor the examined menu
establishes physical impossibility. The original project's head and source
bytes are unchanged. Complete attempts, independent replays and actual exported
native denominators are retained under
`evidence/benchmarks/joint-fitting-budget/office/111d3376fd4d4537887a0e63d1f80894/`.

The campaign also exposed an inaccurate objective PASS on an already rejected
direct-route report: semantic fallback values were aggregated after independent
native objective recomputation was NOT_RUN. This did not authorize acceptance;
the initial report remains retained. The corrected aggregation requires complete same-invocation semantic and independent native objective PASS entries, valid nonnegative fields and finite totals for every exact route. Twenty-two native, authority and arithmetic regressions pass on `43d9e1f2...` in `evidence/release/joint-objective-authority-corrected.xml`. A separate cross-route failure still retains a fully checked objective; there is no blanket deletion of valid measurements on a rejected candidate.
