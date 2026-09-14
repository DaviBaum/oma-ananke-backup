# Unequal-outlet native tree pressure adapter

This private adapter derives the complete quadratic leaf-flow model for a supplied directed physical tree with different tee straight and branch loss coefficients. Every tee coefficient refers to the tee's **total inlet flow**. A service report requires independent local existence **and** independent global nonnegative uniqueness proofs on the same complete parameter model. The proposed flow box alone has no authority to exclude another equilibrium.

The adapter operates on supplied authenticated native metric enclosures. Native geometry, source/edited-file identity, cap matching, coordinate frames, coefficient applicability and managed publication remain obligations of the caller. This component does not change any old common-outlet, fixed-flow or two-sink pressure mission.

## Source and proof boundary

Original `math1/math1/1-10.pages`, SHA-256 `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`, is unchanged. P5 P14530–14546 explicitly permits interval Newton/Krawczyk sufficient certificates. P6 PO11 P16081–16114 retains local inversion/regime premises; PO12 P16118–16135 prohibits silently replacing a multivalued response by one selected equilibrium. PO2 P17645–17681 requires certified solves, validated domains and explicit locality failure. The complete original paragraph extraction used for the local kernel is retained with this handoff. Native path/section construction also specializes the existing RTR19/20 physical-model obligations; it does not implement the complete original solver algorithms.

The local kernel is unchanged SHA `ce5a264c7815b860b9ce0b8001e1b35cc3ecf7f4acacafc4925f7a6e37060c90` (8144). It proves a root inside the strictly positive supplied box for each same parameter tuple. The separate global kernel is unchanged SHA `f433e0c007912aa9501306b2bfc95f0809a135e46b5ad898421410eabe10e4df` (ba979). It checks laminar descendant sets, every term's row support and a strictly positive singleton coefficient sum at every leaf. Exact polarization and laminar rank-one induction then show that a positive root excludes any other nonnegative root for the same tuple. The global certificate alone supplies no existence. Both checks and their exact model/parameter roots are mandatory here.

## Explicit boundary and API

`CoupledTreeBoundary` in `routing/coupled_tree_scenario.py` uses schema `oma.coupled-tree-boundary/1`. Its numerical fields are exact rational strings or integers, normalized under a 512-bit contract limit:

- `source_total_pressure_pa: {lower, upper}` and `sink_total_pressures_pa: {sink_id: {lower, upper}}`. Point intervals are allowed.
- `minimum_sink_flows_m3_s: {sink_id: positive rational}`.
- `flow_search_box_m3_s: {sink_id: {lower, upper}}`, with strictly positive, distinct endpoints. These intervals are proof proposals.
- Exact positive `density_kg_m3`, `darcy_friction`, `maximum_velocity_m_s`; nonnegative `gravity_m_s2` and `elbow_loss_coefficient`.
- `tee_outlet_loss_coefficients: {tee_id: {b: positive rational, branch: positive rational}}`, covering every physical tee exactly.

The required assumptions name total pressure **p plus kinetic pressure, excluding elevation**, steady incompressible fixed coefficients, Darcy friction, elbow excess loss excluding curved-pipe friction, outlet-specific total tee loss at total inlet flow, and no extra loss at independently checked matching connected caps. The ideal hydraulic bore is inferred from the native outer envelope minus declared insulation. It is not a measurement of real pipe wall thickness or bore.

`routing/coupled_tree_pressure.py` exposes:

```python
derive_coupled_tree_model(boundary, network, native_metrics, *, context,
    max_components=128, max_work=500_000, max_bytes=4_194_304,
    checkpoint=None)  # -> model, flow_box, derivation

evaluate_coupled_tree(boundary, network, native_metrics, *, context,
    max_components=128, max_work=2_000_000, max_bytes=16_777_216,
    checkpoint=None)

verify_coupled_tree_envelope(boundary, network, native_metrics, certificate, *,
    context, max_components=128, max_work=2_000_000,
    max_bytes=16_777_216, checkpoint=None)
```

The metric schema is `oma.coupled-tree-native-metrics/1`, with exactly `schema`, `network_root`, `native_evidence_root`, and `components`. Each component supplies positive whole `length_m`, `outer_radius_m`, and every actual port's three `position_m` intervals in the audited common SI frame. The canonical network root must match. Missing or additional components/caps are rejected. Declared connected cap position boxes must overlap. Actual cap geometry/radius matching and native metric truth are still external prerequisites.

## Complete physical-to-polynomial derivation

The producer traverses the directed component tree from the source, collects each outlet's descendant leaves, and propagates loss prefixes to every physical slot. The verifier separately walks each actual sink backward through incoming connections, reconstructs every path, and accumulates the descendant and prefix inventories. Both must match the complete `NetworkDesign` demand paths and all physical slots. No tee outlet is identified with the other outlet as a common head.

For component c, its independently measured native radius interval R_c and exact declared insulation I_c imply:

```text
D_c = 2 (R_c - I_c) > 0
A_c = pi D_c^2 / 4
```

Each pipe or elbow gives one term with D=A equal to that component's descendant leaf set and coefficient:

```text
a_c = rho/(2 A_c^2) * (f L_c/D_c + K_excess)
```

The excess coefficient is zero for a straight pipe. Each tee gives two distinct terms, one per outlet. Both use the whole inlet descendant set D; their applicability sets A are the respective outlet subtrees:

```text
a_c,outlet = rho K_c,outlet/(2 A_c^2)
```

The tee skeleton receives **no Darcy charge** because its declared total coefficient includes the body's distributed loss. For each sink i, the complete available total head is:

```text
P_i = source_total_pressure - sink_total_pressure_i
      + rho g (z_source - z_sink_i)
```

Thus every physical path obeys the kernel equation `sum a_t (sum_{j in D_t} q_j)^2 - P_i = 0`, with each outlet loss assigned to its exact rows. Positive leaf flows imply positive flow through every nonempty component/outlet descendant set. Complete source, sink, connection and component conservation equations reduce to exact linear identities in those leaf flows.

The verifier uses direct dimensional lower/upper expressions, independently of the producer's interval composition. Exact Machin bounds enclose pi. All native length/radius/cap inputs and exact raw coefficient/head intervals remain in the hashed derivation.

To keep inverse arithmetic within the bounded rational kernel, the polynomial coefficient and available-head boxes are conservatively rounded outward onto the fixed `2^-40` dyadic grid in their stated units. The checker independently reconstructs the integer quotient/remainder bounds and verifies raw-to-rounded containment. Negative heads round correctly; a positive coefficient too small to retain a strictly positive rounded lower bound gives UNKNOWN. This is a parameter-domain enlargement, never a midpoint replacement or a numerical precision claim. The rule, units and grid are bound by the physical-model root.

The true correlated physical tuple maps into one tuple of the outer polynomial box. Repeated diameter, density, pi, source-pressure or coordinate dependencies may widen the box. They are not claimed independent in reality, and the resulting enclosure is not a tight hull.

## Every port and service requirement

Each physical port has an exact sum of leaf flows and a complete source-to-port loss prefix. Its total head is source total head minus the prefix's body/outlet losses; its total pressure subtracts `rho g z_port`. At physical boundary ports, the result is intersected with the independently supplied pressure/head boundary interval, justified by the complete leaf equation at the true physical parameter tuple. This is total pressure, not static pressure.

Every port's velocity uses **its own** native-inferred component area. The report checks strict forward flow, each sink's exact minimum delivery, and the speed upper bound at every physical port, including the aggregate source trunk. Unresolved comparisons remain UNKNOWN. A valid equilibrium certificate may therefore accompany a FAIL or UNKNOWN service verdict.

`evaluate_coupled_tree` returns `CERTIFIED_ENVELOPE` only after complete independent replay. It includes a separate `verdict`, `certificate`, `independent_check`, and `service`. `verify_coupled_tree_envelope` returns `PASS` for a correct complete report, with separate `verdict`, `local_check`, `global_check`, `service`, roots and complete counts. Missing global singleton support, missing proofs, failure of local inclusion, unsupported reversed regimes or exhausted budgets never receive partial service authority. Native geometry acceptance remains false in the scope metadata.

## Resource and current-input guards

Component, path, sink, metric and port inventories are bounded before parsing and again after the caller input snapshot. Exact contract, metric and derived/service arithmetic have explicit size limits. All certificate/model bytes pass strict bounded JSON snapshots. Caller exceptions retain identity.

Shared work accounting includes nested verifier work that occurs after callbacks are disabled. Successful mathematical producers omit a work scalar, so the adapter explicitly counts and charges their known final canonical snapshot tails; the accounting traversal itself is counted and interruptible. The exact reported overall budget passes, while one less returns UNKNOWN, for both producer and verifier in the focused regression.

After the last completion checkpoint, no caller code runs again. Original boundary, network, metrics, context and supplied certificate are rehashed without callbacks. Changes fail closed. This synchronous binding check does not itself prove atomic external files or native metric authenticity.

## Actual reference and validation

The independent reference is `.oma/development/coupled-native-tree-reference/evidence/d5b064b69b3f4cf19b7c5824cd439f63`, result SHA `7e10fc9764ca8cac2701bd1e0bd587a7eb1fdb043d432b64b989d786f9653f65`. It contains fresh actual IFC geometry with seven components, two tees, three sinks, 16 ports and six connections. The native checks cover seven source-obstacle pairs, 21 self-pairs, six connections and seven zone checks. The reference independently derives nine unequal quadratic terms, 16 port maps and 17 continuity identities.

Its nominal flows are `(3/1000, 3/2000, 1/1000)` m³/s. Tee coefficients are `(1/5,3/10)` and `(1/4,2/5)`. The source regulated total pressure is 200 Pa; sink pressures are predeclared rational intervals around manufactured nominal expressions. Every length/radius/cap coordinate retains the declared 1 μm native uncertainty policy. The initial uniform box of halfwidth `1/100000` failed strict interval inclusion and remains retained as UNKNOWN. The separately predeclared anisotropic halfwidths `(3,17,17)/1000000` certify with unchanged geometry, pressures, constants and metric assumptions.

Frozen adapter build `9d8bd53fe2ef49883228b7477f369e9640e62cb9b0dcf350c486d6920a19147e` passed 113 focused tests in 3.898 seconds, zero failures/skips. The test captures six portable JSON fixtures and all source/test hashes. It checks all 16 flows, velocities and 32 head/pressure values against the independent 85-digit nominal oracle; both kernel proofs, 17 continuity identities and 19 head-path identities pass. The nominal oracle is consistency evidence, while interval/local/global verification carries the mathematical claim.

Initial prototype history is retained: a Fraction/Interval division exception produced no certificate; exact unrounded coefficient inversion honestly exceeded its rational budget; uniform-box attempts remained UNKNOWN. The first test run had 108 passes and one ineffective test-mutation assertion (`sink-a` was replaced by itself); that test was corrected without a source change. The subsequent 113-test run passed.

This handoff contains only new adapter/schema/test/fixture files and their existing-kernel dependencies. Existing application glue, mission/rule hashes, report admission, native execution, acceptance and export integration are owned by the parent and are outside this component's standalone evidence.

The final independent peer audit against adapter SHA `bc1ce17fe8c0bc97287cb8d2ef3212de8fdddbfbf03456898635ff77eb6aecae` passed. It independently matched all nine terms, seven sections, 16 ports, 17 continuity and 19 head identities; confirmed raw-to-dyadic coefficient containment and all nominal reference memberships; rejected 18 resealed, five changed-input and four final-callback attacks; and retained producer-disabled verification plus exact shared-work exhaustion. Receipt `coupled-native-tree-reference/adapter-peer-audits/40cc39a20acb4ed2bc1016b6c722bc57/result.json` has SHA-256 `f12e72ab2f6b20c2a750d76c15687f47cfcb69c8fc946c315f45423beca705d9`. No concrete soundness defect was found. The exact tests and peer audit use frozen 9d8 source; subsequent documentation changes do not alter that source receipt.


## Application integration checkpoint

The exact adapter and schema are now integrated on source `5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c`, with five separately reviewed application glue changes. Old fixed-flow, two-sink and common-tee normalized missions and requirements retain their complete pre-change values. New missions require exact complete tee identities and exact authoritative minima; their search boxes and all boundary values bind mission/rule roots.

The actual analytic IFC workflow passes complete source/self/port/zone checks, both mathematical proofs, all16 physical-port service requirements, managed acceptance at revision2 and a fresh exported-IFC check. Delivery and velocity violations fail service despite operating proof PASS. Wrong proof boxes and reverse-pressure regimes remain UNKNOWN and cannot be accepted. Final completion cancellation prevents publishing a replacement report.20 corrected integration cases pass in23.734s; initial746 retains744PASS and two incorrect test expectations (UNKNOWN versus REJECTED), with no source change. Exact inputs, logs, native Stores, failed/corrected results and peer reviews are retained at `evidence/math/coupled-native-tree/latest.json`. Full2467-case regressions are running separately in both native environments; no full-suite completion is claimed here.
