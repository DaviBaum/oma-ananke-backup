# Native-metric common-outlet passive trees

This adapter specializes the independently checked passive quadratic network kernel to a complete directed `NetworkDesign` tree under a new, explicit loss convention. Each tee has one strictly positive coefficient shared by its straight and branch outlets, referenced to its total inlet flow. Different tees may have different coefficients. Existing fixed-flow and two-sink missions, including their unequal tee coefficients, are not reinterpreted.

The optional `SharedNetworkScenario.passive_tree` contract is now integrated into current native checking, report admission, acceptance, assurance and fresh exported-byte checking. Exact boundary minima are the sole service authority; the existing `Demand` float field is only a descriptive projection. The full exact boundary belongs to the rule hash, including changes too small to alter that float projection. Old mission serialization omits the absent new field.

The integrated 267-case native/control regression passes, including actual three-sink selection, acceptance, fresh IFC export, three failed-service cases and cancellation at the final forced control boundary. The real Office mission also passes all 5,621 source pairs and twenty-one unique component pairs in both selected and exported checks. Native IFC preservation is canonical parsed-entity equality, not raw decimal-token equality. Full source/test snapshots and original polling-timeout failures are retained in `evidence/math/passive-native-tree/`; separate real-building evidence is in `evidence/benchmarks/passive-pressure/office/f64e250b57bb480f9dfe352892b61b3f/`. Complete regression and portable release remain separately gated.

The adapter consumes a complete set of native component length/radius intervals and every actual cap position. These metrics and their native correspondence must have been authenticated by the current independent geometric checker. The adapter binds their identities and checks their mathematical use; it does not establish their authenticity or rerun CAD. A pressure certificate never supplies geometric acceptance.

## Supplied source and bounded model

Original P6, native Pages P16069–16077, defines nonlinear port relations and explicitly distinguishes applicable theorem classes. P16836–16853 gives the signed quadratic relation and warns that a direction regime may not be smoothed away. The original Pages SHA is `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`.

Integration `DEF-RTR56`, DOCX P4592–4609, supplies area, velocity, Darcy/local loss, conservation, applicability and geometric prerequisites. `ALG-RTR19/20`, P5530–5533, distinguishes a trusted physical-model compiler from untrusted solving plus independent certificate checking. `ALG-RTR21/22`, P5534–5537, requires complete request, geometry, physics and version binding. The original DOCX SHA is `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. The unchanged source extract is retained in `evidence/source-basis.json`; this bounded specialization does not complete the original algorithms.

The new `PassiveTreeBoundary` has exact rational scalar encodings and one coefficient for every tee ID. It requires strictly positive density, Darcy friction, common tee coefficients, velocity limit and minimum sink delivery; gravity and elbow excess loss are nonnegative. Every native component length and inferred bore has a positive lower bound. This first implementation avoids zero-resistance edge contraction.

The new boundary specifies total pressure `p_total = p_static + kinetic pressure`, excluding elevation. The graph head is `h = p_total + rho*g*z`, in Pa. The adapter reports total head and total pressure at every physical cap. It does not report static pressure or infer a kinetic-energy correction coefficient.

## Complete quotient and physical equivalence

Start with every actual physical cap as a distinct slot. Union only the two slots of each separately checked physical connection and, under the explicit tee law, that tee's two outlet slots. No other cap, geometric proximity or name creates equality. The producer computes this quotient by disjoint-set union. The verifier independently computes connected components of the complete equality-pair graph.

Every physical component becomes exactly one directed graph edge from its inlet `a` to its outlet node `b`. A tee's `b` and `branch` already share that node. All components, all ports, all physical connections and the reason for every union appear in the derivation. The resulting quotient has one more node than edges and no collapsed component edge. Source and sink assignments are explicit and separately namespaced, including a sink whose ID is `source`.

For a pipe or elbow, both physical port flows equal the component edge flow. For a tee, its inlet flow is the tee edge flow; a connected outlet takes the downstream component edge flow. A terminal tee outlet takes the net graph withdrawal at that unique boundary node, so any other downstream branch is subtracted. The adapter never assigns total tee inlet flow to each outlet.

Each component, connection, source and sink receives an exact linear conservation identity. The verifier requires its difference to vanish algebraically or to equal the complete continuity equation of an internal quotient node. This proves correspondence for the unique graph equilibrium, without pretending separately rounded flow intervals sum exactly. In the reverse direction, any physical slot flows satisfying the stated component/connection laws collapse to a graph equilibrium. The uniqueness theorem therefore applies to the complete physical port assignment under these prerequisites.

Two distinct physical boundaries at one quotient node are unsupported. Even if their prescribed heads agree, two terminal tee outlets without distinguishing downstream resistance have an undetermined individual flow split. Intersecting boundary intervals or dividing the total flow equally would not resolve that defect. One terminal and one connected downstream branch at a tee outlet node is supported and independently tested.

SOURCE/SINK tags specify the desired orientation; they do not prove the solution's sign. The kernel solves the signed law. Every physical cap must have a strictly positive certified lower flow bound before service can pass. A nonpositive upper bound establishes failed forward service; a zero-crossing enclosure leaves that sign unresolved.

## Native sections and losses

For each component, the ideal hydraulic diameter is `D_c = 2*(R_c - I_c)`, where `R_c` is the supplied native radius enclosure and `I_c` is the exact decimal interpretation of declared insulation. The hydraulic area is `A_c = pi*D_c^2/4`; pi is enclosed by the existing rational Machin-series bound. This is an ideal circular bore interpretation, not a measurement of wall thickness or the actual inner bore.

Each pipe/elbow resistance is

```text
K_c = rho/(2*A_c^2) * (f*L_c/D_c + k_excess)
h_in - h_out = K_c*q_c*abs(q_c)
```

The elbow coefficient is excess local loss and its curved-pipe Darcy term is also charged. Straight pipes have zero excess coefficient. For a tee:

```text
K_tee = rho*k_common/(2*A_tee^2)
h_in - h_b = h_in - h_branch = K_tee*Q*abs(Q)
```

The tee coefficient already represents total irreversible loss: its skeleton length is accounted for but never charged Darcy friction. The identical outlet drop makes the common outlet-head quotient exact under this explicitly declared model. A tee with unequal outlet loss coefficients does not satisfy this reduction.

The producer uses interval composition. The verifier recomputes the extrema directly: loss decreases with positive diameter and area, and increases with length; the correct endpoint expression is checked for every component. Each actual physical port then uses its own component area for signed velocity and speed. The coefficient box is a conservative Cartesian enclosure of correlated geometry/pi quantities. Universal kernel results remain sound for the included correlated physical parameter instances; no tight solution hull or equality of arbitrary independently selected box coordinates is claimed.

Native connected-cap coordinate intervals must at least overlap in each coordinate; disjoint enclosures are rejected. Overlap alone is not a cap-match proof. The native check must still establish the actual connection, section/tolerance correspondence, complete body support, system/port ownership, source frames and absence of unmodeled adapters or local losses. The new model explicitly assumes no additional loss at those checked matching connections. Small tolerated native section differences do not authorize reducers or prove that a supplied catalog coefficient remains applicable.

## Public API and proof interpretation

The new files are `routing/passive_tree_scenario.py` and `routing/passive_tree_pressure.py`.

```python
derive_passive_tree_model(boundary, network, native_metrics, *, context,
    max_components=128, max_work=500_000, max_bytes=4_194_304,
    checkpoint=None) -> (model, derivation)

evaluate_passive_tree(boundary, network, native_metrics, *, context,
    pressure_width_target=None, max_components=128, max_work=2_000_000,
    max_bytes=16_777_216, max_refinement_passes=128,
    checkpoint=None)

verify_passive_tree_envelope(boundary, network, native_metrics, certificate, *,
    context, pressure_width_target=None, max_components=128,
    max_work=2_000_000, max_bytes=16_777_216, checkpoint=None)
```

The exact native metric schema is:

```text
schema: oma.passive-tree-native-metrics/1
network_root: canonical complete NetworkDesign digest
native_evidence_root: declared current native evidence digest
components:
  component_id:
    length_m: {lower, upper}
    outer_radius_m: {lower, upper}
    ports:
      slot: {position_m: [{lower, upper}, {lower, upper}, {lower, upper}]}
```

The separate context binds the caller's current mission, candidate, source/export bytes, frames, native evidence and executable version. Those identities have to be authenticated by the invoking checker. Derivation/certificate hashes cannot authenticate an invented input by themselves.

`CERTIFIED_ENVELOPE` means the adapter and independent pressure proof are complete. Its separate `verdict` is `PASS`, `FAIL` or `UNKNOWN` for all forward signs, minimum deliveries and velocity maxima. The independent verifier can correctly return `status=PASS, verdict=FAIL`: it has established an accurate failed-service report. Admission requires service PASS as well as the independent native prerequisites. A complete but coarse envelope remains explicitly coarse and may leave service UNKNOWN. Numerical delivery requirements are taken only from the exact new contract; any legacy floating demand field is descriptive metadata.

The packet binds raw input, canonical graph, all native coefficients, quotient/port inventory, the complete kernel pressure certificate, all service computations and content root. Its verifier does not invoke the producer or trust producer service summaries. Minimum flow uses the lower bound; speed uses the upper bound. Endpoint head boxes derive from each terminal's own native elevation, without adding elevation or kinetic terms again to the edge loss.

Malformed/unsupported inputs return BLOCKED without a pressure claim. Exhausted parsing/work/byte/graph budgets return UNKNOWN. The standalone derivation helper raises on invalid inputs and does not itself certify equilibrium. Caller exceptions retain their identity throughout both producers and verifiers. Every public successful path has a final completion callback followed by bounded input guards with callbacks disabled; the verifier also guards the caller's original certificate. These guards are not an atomic guarantee against arbitrary concurrent memory or filesystem writers.

## Retained evidence

The native fixture has two tees, three sinks, seven solids, 16 ports and six physical connections. The separately supervised native checker passed seven source-obstacle pairs, 21 self pairs, six contact checks and seven allowed-zone checks. The original IFC, edited IFC, raw native semantics, metric bounds and an independent 85-digit closed-form reference are retained under `evidence/native-three-sink/5c0e4ad0641d4acab0aca886eb023bf0`.

The adapter's focused tests passed 65 cases, including all 16 independently referenced flows, complete quotient and conservation denominators, terminal-at-tee withdrawal, duplicate boundary rejection, elbow loss, per-component native area variation, reversal/zero flow, coarse uncertainty, scalar/metric/proof tampering, budgets, producer-free verification and final callback mutation. Fixture bytes are pinned in the test.

Initial failures are retained: a pytest source-path collection error; 60 PASS/1 incorrect expected UNKNOWN where the fixture actually proved underdelivery; and two malformed `1/0` values that escaped as `ZeroDivisionError` in the initial adapter/class. The expectation was corrected by using an explicitly smaller test minimum, and both parsers now reject zero denominators with a controlled failure. No earlier evidence was overwritten.

The independent native review of initial frozen build `2fb43437f5c6d45477e9a474204e0ccfb2236afb7762c4399c65dfce1d79c048` found no false PASS in graph/port/conservation/service or late-mutation checks. The corrected parser source is frozen as `f606e781935fa758da335c0519b84cc5df4461c8fc7a3a87154cf1d945469188`, with adapter SHA `cfe2edb0bd3d5557508fb01ac0e5d9dd7ca38aa07350d799c83a9e5654a7168b` and class SHA `345d5dd367d2785ac2b6bc9d230ccdc3841e42ffaf86b2226a75e53fd1bc73e5`. The root-owned application integration and its managed acceptance/export evidence are separate from this focused adapter result.

The corrected f606 source also passed the independent native replay, retaining its exact eight-node quotient, 16 reference flow memberships, 32 head/total-pressure memberships and 17 conservation identities. Its result is `evidence/independent-adapter-review/5c07525d40c943a0bce109673a59d13e/result.json`, SHA `8deb6a538aa197fb54ee25dbaed665eb2279d30dcc274161aaec4578f38edf9b`. Both zero-denominator attacks were independently replayed without an escaped exception. The final 65-test immutable snapshot is `validation/16676ce0975448758f745e61cbbe946c`; its receipt pins all source, test and fixture bytes and reports zero failures/skips.
