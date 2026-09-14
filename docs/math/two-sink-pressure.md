# Two-sink pressure operating-point model and native adapter

This implementation proves a bounded nonlinear port relation for one directed
source, one tee and two forward-flow outlets. It is integrated into the working
backend at `bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac`.
Its full backend regression is tracked separately from the earlier sealed
43d9 package and live API, which retain their validated executable snapshots.
The independent checker establishes a unique operating point for every parameter
tuple in the supplied rational interval box, together with conservative rational
flow enclosures. It does not certify the truth of the caller's pressure, loss,
geometry or material assumptions.

## Source basis and the implemented refinement

The original sources remain unchanged. References below are native paragraph
identities, not reconstructed chapter labels or PDF line wrapping.

| Original source | SHA-256 | Relevant native source |
|---|---|---|
| `math1/math1/1-10.pages` | `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970` | Original Prompt 6, nonlinear port relations |
| `math1/math1/the 5 things that combine ceiling router with ananke.docx` | `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129` | RTR physical fiber and checking obligations |

Original P6 §16, paragraphs 16069–16077 and attached table 1736791, distinguishes
strong monotonicity and unique equilibria from arbitrary nonlinear relations
with absent or multiple equilibria. THM-PO11, paragraphs 16081–16114, requires a
fixed regime and invertible internal derivative for implicit sensitivity;
THM-PO12, paragraphs 16118–16135, preserves the set-valued relation when multiple
equilibria exist. This kernel supplies an explicit strict-monotonicity proof in
a declared forward regime. It neither assumes a general nonlinear solver is
complete nor follows one numerical root as evidence of global uniqueness.

Original P6 §40.1, paragraphs 16836–16853, gives the quadratic signed loss law,
adds two series coefficients, and derives its sign-preserving square-root
inverse. Its example has aggregate coefficient 5 and pressure interval [20,45],
giving flow [2,3]. The same passage warns that the derivative is unbounded at
zero and that a check-valve direction regime cannot be smoothed away. The new
kernel keeps strict positive pressure and branch resistance, and explicitly
requires the unique split to lie inside (0,1).

DEF-PO11 and THM-PO7/8, paragraphs 16139–16203, require a port envelope's domain,
validity, evidence and composition conditions. THM-PO14, paragraphs 16360–16397,
requires stability to turn residuals into errors. ALG-PO7, paragraphs 17130–17158,
checks units, wiring, regimes, parameter domains, correlations, conservation,
enclosure validity and dependency identity. ALG-PO1/2, paragraphs 17615–17681,
require certified nonlinear membership and envelopes, with refinement or
UNKNOWN when a certificate cannot be established. The current checker checks
exact inequalities directly; a floating residual is never its authority.

The integration DOCX's DEF-RTR56, native `word/document.xml::p[4592]` through
`p[4609]`, defines the hydronic area, velocity and Darcy/fitting loss fiber.
ALG-RTR19/20, `p[5530]` through `p[5533]`, separates compilation and untrusted
solving from independently checked physical evidence. The one-tee equations
below are an explicit bounded implementation refinement of these obligations;
the sources do not themselves provide this complete interval algorithm. This
does not close all of ALG-PO1/2/7 or RTR19/20.

Native text can be audited in `evidence/math/pages/1-10/body-records.jsonl` and
`evidence/math/extracted/oma-integration.jsonl`. Table 1736791's decoded model
1736794 has SHA-256
`e1ab94b17ca4244a44eb955cb6d38df09ada4df1126c6cc776780177ddcdaafb`.

## Model and proof

The input contains exact rational intervals for P1, P2, beta, A1, A2, B1 and B2.
P1, P2, beta, B1 and B2 are strictly positive throughout their intervals; A1 and
A2 are nonnegative. The domain is the complete Cartesian product. A correlated
physical model may be contained by this box, but no midpoint substitution or
independence claim about actual measurements is made.

For total flow Q and split t, the declared equations are

```
q1 = t Q, q2 = (1-t) Q, Q = q1+q2, Q>0, 0<t<1
P1 = beta Q² (A1 + B1 t²)
P2 = beta Q² (A2 + B2 (1-t)²).
```

P_i is source total pressure minus outlet total pressure, minus gravitational
pressure rise. Total pressure here includes the kinetic-pressure term. It is
not silently substituted for a static-pressure budget. A_i accounts for the
common-trunk and outlet-specific tee losses referenced to total inlet flow;
B_i accounts for that outlet's exclusive branch losses. The staged native
adapter checks complete component partitioning and binds the supplied loss-law
and boundary declarations. Their physical applicability remains an explicit
external premise rather than a theorem inferred from IFC geometry.

Eliminating Q gives

```
g(t) = P2(A1+B1 t²) - P1(A2+B2(1-t)²).
g'(t) = 2[P2 B1 t + P1 B2(1-t)]
      >= 2 min(P2.lower B1.lower, P1.lower B2.lower) > 0.
```

At every fixed t in [0,1], exact extrema over the declared Cartesian box are

```
g_lower(t) = P2.lower(A1.lower+B1.lower t²)
             - P1.upper(A2.upper+B2.upper(1-t)²)
g_upper(t) = P2.upper(A1.upper+B1.upper t²)
             - P1.lower(A2.lower+B2.lower(1-t)²).
```

The checker requires `g_upper(0)<0` and `g_lower(1)>0`. These signs and strict
monotonicity prove, by continuity, one and only one forward root for every
admitted parameter tuple. A proposed common split enclosure [l,u] is checked by
`g_upper(l)<=0` and `g_lower(u)>=0`. Its extrema can be enclosed by bisection of
the two adverse-corner quadratics, but the checker does not invoke that search.

Given t's enclosure, interval division encloses Q² using either path with a
positive denominator. The proof also supplies a finite global bound, including
when a coarse split enclosure touches both endpoints and both A_i are zero:

```
Q² >= max_i Pi.lower / [beta.upper(Ai.upper+Bi.upper)]
Q² <= 2 sum_i Pi.upper / (beta.lower Bi.lower).
```

The upper bound follows from `qi² <= Pi/(beta Bi)` and
`(q1+q2)² <= 2(q1²+q2²)`. Branch-wise division tightens this envelope whenever
its lower denominator is positive. The denominator in each actual interior
solution is strictly positive even if a coarse marginal interval contains zero.

The producer constructs dyadic square-root bounds. The checker independently
tests `Q_lower² <= Q²_lower` and `Q_upper² >= Q²_upper`, with nonnegative lower
flow and positive upper flow. It then encloses `tQ` and `(1-t)Q`. Returned
marginal intervals need not have endpoints that sum exactly; the retained
parametric relation states conservation for every actual solution. Arbitrary
points chosen independently from these intervals are not asserted to solve the
network equations.

## Interface and certificate scope

`compile_two_sink_pressure(model, ...)` returns CERTIFIED, UNKNOWN or
INVALID_INPUT. `verify_two_sink_pressure(model, certificate, ...)` accepts the
certificate itself and returns PASS, FAIL or UNKNOWN. Both always set
`physical_acceptance_authority=false` and `infeasibility_claim=false`.

The public model schema is `oma.two-sink-pressure-model/1`. It requires two
distinct branch IDs, all seven parameter intervals, a context root, a physical
model root and the exact `MODEL_ASSUMPTIONS` declaration. These roots bind
identities; they do not authenticate the truth of the caller's derivation.
Integers, Fraction objects and explicit rational/decimal strings are admitted.
Binary floating-point inputs, nonfinite values and exponential notation are
rejected. The model root uses normalized rational strings.

The certificate schema is `oma.two-sink-pressure-certificate/1` and contains:

- `model_root`, `query_root` and both `branch_ids`;
- `regime_proof`, with endpoint extrema and positive derivative lower bound;
- `enclosures`, with split, squared total flow, total flow and both branch flows;
- `accuracy`, reporting achieved widths and whether the requested split width
  was met; no total-flow accuracy target is asserted;
- `correlation`, retaining the conserved parameterization;
- the precise model scope and absence of physical acceptance authority.

The query root includes the target split width. A verifier may accept a wider
valid enclosure if all inequalities and its reported widths are correct. Its
proof is a bounded canonical snapshot: later mutation of the caller's proof
does not change the returned enclosure under the previously checked root.

Defaults are target split width 1/1,000,000; at most 64 refinement rounds;
64 dyadic square-root bits; 100,000 work units; 4,096 rational bits; 65,536
normalized input bytes; and 1,048,576 certificate bytes. Configurable maxima
are 512 refinement rounds, 512 square-root bits, 1,000,000 work units, 16,384
rational bits, 1 MiB input and 4 MiB certificate. JSON depth, node and container
limits also apply. The checker enforces the certificate byte bound before
decoding its rationals. Work and rational-bit limits remain active during
independent verification.

Refinement exhaustion alone may yield a complete, coarse CERTIFIED envelope.
If its actual width exceeds the target, `target_split_width_met` is false;
parameter uncertainty can make the target impossible without narrowing the
input model. Hard work or encoding exhaustion returns UNKNOWN without a
certificate. Missing uniform endpoint signs also returns UNKNOWN rather than
claiming physical infeasibility. External checkpoint exceptions propagate
unchanged, including cancellation, timeouts and caller ValueError exceptions.
After the final explicit checkpoint, the model is re-bound in a bounded tail
that retains all work/bit/encoding limits but does not call back into the caller.
This prevents a callback from changing model fields after their final copy.
It does not claim atomicity against arbitrary concurrent external writers.

## Independent evidence and remaining integration

The first private frozen checkpoint is
`ca7109da654653a4423db7d68f58a08fc99e488715080b1c7dceb99e088e9fcb`.
All 118 staged kernel cases passed in 0.34 s; the retained XML is
`evidence/kernel-initial.xml` relative to the staging directory. Tests include
manufactured rational solutions, the source's direct inverse example,
24 separately expanded quadratic-root references, all 128 corners and an
interior point of one uncertain model, coarse zero-common-resistance cases,
identity and proof forgeries, budget limits and cancellation. Sampling tests
are independent bug oracles; the exact checked inequalities provide the
universal interval statement. Later evidence will record any corrected
checkpoint separately.

The corrected private kernel checkpoint is
`bbb0f8c3ab4d142679e377e6539fab3a74d4075f321765ac5e9d1e6255d1d53f`.
All 123 kernel cases passed in 0.35 s, recorded in
`evidence/kernel-corrected.xml`. Kernel source SHA-256 is
`f8d739cc404db60c40aed2e386dd76c6820fc37a306c5fac354eb95b52486fd6`.
An independent reviewer found that the first checkpoint could invoke a callback
after copying the fields used by its final model hash. Their callback changed
the caller model without changing that already computed hash. The final
no-callback binding tail corrects this. Both original false-success results,
the old source, exact reproducer and corrected replay remain under
`evidence/math/two-sink-pressure-independent/c4590116cb7c4828b814c2b7587a2ad0/`
in the main workspace. The corrected replay confirms no callbacks occur after
the final checkpoint and the caller model remains bound.

That reviewer also independently solved the original path equations using
100-digit bisection for 12 random interval boxes, all 128 corners and 32 interior
points per box: 1,920 parameter cases. All checked split and flow bounds agreed.
The oracle evidence retains its original source hash; only the final callback
binding changed afterward. This is additional finite numerical consistency
evidence, not a replacement for the universal rational proof.

The staged application adapter is a separate proof layer. It reconstructs
the actual one-tee/two-branch physical topology and all component lengths, keep
native coordinate enclosure assumptions explicit, derive gravitational pressure
terms, preserve diameter/area and loss conventions, and bind every input to the
current mission and native artifacts. Delivery and velocity requirements use
the entire checked flow intervals. Native geometry, IFC identity, interference,
materialization, acceptance and exported-file verification remain mandatory.

This kernel does not solve arbitrary cyclic, multi-tee, flow-reversing,
compressible, transient, pump-controlled or state-dependent-loss networks. It
does not prove Reynolds-regime applicability, select loss coefficients, infer
missing boundary conditions or establish a global continuous routing optimum.

## Actual staged native consumer

`SharedNetworkScenario.pressure_driven` is an optional and separately versioned
boundary contract. With its default `None`, serialization omits the field and
the pre-existing fixed-flow request and rule hashes are preserved. The retained
regression checks scenario root
`325e42b8438567c3593814d0c8cc0684b86c994ff5e81b2030347dad2275d864`
and rule root
`1285d1b13298c90be97861a85d56c4d74fcadd8b0a036217eecc80046b0e9915`.
When the field is present, all boundary values and minimum deliveries enter the
authorized request/rule identities. It requires an engineering-service pressure
pipe mission with exactly two named outlets and one tee in every admitted
alternative. It rejects simultaneous fixed-flow physics or static-pressure
budgets. Existing fixed-flow calculations retain their explicit control
assumptions and do not acquire an operating-flow discovery claim.

The pressure boundary quantity is `p + kinetic pressure`, in Pa, excluding
gravitational potential. The model uses

```
Pi = source_total_pressure - sink_i_total_pressure
     - rho*g*(z_sink_i-z_source)
beta = rho/(2*A_ref²), A_ref = pi*D_ref²/4
D_c = 2*(R_outer_c - declared_insulation)
r_c = (D_ref/D_c)^4
Ai = sum_common[(f*L_c/D_c + K_elbow_c)*r_c]
     + tee_outlet_i_total_K*r_tee
Bi = sum_exclusive_branch_i[(f*L_c/D_c + K_elbow_c)*r_c].
```

Here `K_elbow_c` is zero on straight segments and the supplied excess local-loss
coefficient on elbows. The same mathematical pi cancels exactly in
`(A_ref/A_c)^2=(D_ref/D_c)^4`; reference area is a normalization, not a substitute
for each component's own model section.

The tee's supplied total coefficient is specific to the selected outlet and
referenced to tee inlet velocity, hence total Q. Its geometry skeleton length
is accounted for in the physical denominator and model identity, but is not
charged again as Darcy loss. Segment lengths and elbow centerline arc lengths
receive the stated Darcy term; elbow K is the declared additional local loss.
No pump, hidden pressure controller, extra kinetic correction or static/total
conversion is invented.

`routing.network_pressure.partition_two_sink_tree` reparses the complete typed
network. Both oriented paths traverse the unique tee exactly once, share the
same trunk prefix, use its distinct `b` and `branch` outlets, and then have
exclusive branch components. The trunk, tee and two branches account for every
physical component exactly once. Missing, duplicated, unrelated or incomplete
components cannot disappear from the modeled domain. The independent native
network semantics checks remain a prerequisite to using measured metrics.

`derive_two_sink_pressure_model` requires every component's current length and
outer-radius enclosures, plus all three-dimensional terminal position
enclosures. It records
the complete partition, geometry metrics, boundary contract, section area,
gravity terms, derived coefficients, source context and physical model root.
The native lengths, radii and terminal coordinates use the checker's explicit
metric radius `max(1e-6 m, native numerical-policy absolute tolerance)` around
the independently parsed value. Bore uncertainty is twice radius uncertainty:
`D_c` has endpoints `2*(R_outer_c.lower-insulation)` and
`2*(R_outer_c.upper-insulation)`. Every lower bore must be strictly positive;
the adapter never clamps a nonpositive bore to a nominal diameter or epsilon.
These remain conditional engineering enclosures, not formally proved general
CAD error bounds. The required
`IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION` declaration
states exactly how the represented envelope is interpreted. It is not a
measurement of pipe wall thickness or a proof of the actual physical lumen.
Loss-catalog validity and regulated boundary applicability must describe this
same model; a kernel proof cannot supply them. Each component's own area uses
its bore interval and a rational pi enclosure. Shared
length, area and elevation uncertainties may be correlated; taking a Cartesian
outer coefficient box is conservative and does not assert physical independence.

`evaluate_pressure_network` invokes the producer and then the independent
verifier. A forged producer flow envelope is rejected. An independently
certified operating relation does not imply adequate service: each sink's
`required_flow_m3_s` is a minimum delivery in this mode. A minimum is PASS only
if the entire checked flow interval meets it, FAIL only if the entire interval
falls below it, and UNKNOWN for overlap. Every unique component inlet and
outlet velocity is similarly checked against the supplied maximum, including
the aggregate trunk and all three tee ports. A broad but correct enclosure may
therefore establish a unique operating point while leaving delivery or velocity
unresolved.

The native checker publishes separate `network-pressure-operating-point` and
`network-demand-conditioned-service` checks. Selection requires the former to
be PASS whenever this mode is requested, along with the existing native and
service gates. Geometry PASS alone is insufficient. Assurance records the
supplied pressure and loss assumptions and their conditional scope. Managed
acceptance uses the current independently checked report and current physical
inputs. Export reopens the actual resulting IFC, reconstructs its own component
and metric inputs, and independently rechecks a newly bound operating relation.
No earlier numerical operating-point PASS is imported as current authority.

## Portable evidence and promotion boundary

The export-ready relative evidence directory is
`evidence/math/two-sink-pressure/`. Its `latest.json` lists each retained file,
SHA-256 and portable relative path, with original locations kept only as
provenance. It distinguishes:

- `kernel/kernel-initial.xml`: 118 initial kernel cases at `ca7109...`;
- `native-initial/tests.xml`: 19 initial adapter/native cases at `ca7109...`;
- `kernel/kernel-corrected.xml`: 123 corrected kernel cases at `bbb0f8...`;
- `native-corrected/tests.xml`: 145 combined corrected cases at `bbb0f8...`,
  comprising the 123 kernel cases and 22 adapter/native cases;
- `independent-review/`: the unchanged old kernel, original callback failure,
  exact replay script, corrected result and 1,920-case independent oracle.

The corrected combined native run includes actual managed candidate selection,
acceptance and fresh exported-file checking for an analytic IFC network. Its
negative fixture has geometry PASS and operating-point existence PASS but
insufficient delivery, a rejected candidate and no acceptance. This does not
itself constitute the real Office pressure benchmark. That later campaign and
the independent diameter-applicability review have their own evidence below.

The dimensional review found a real defect in the `bbb0f8...` native adapter:
using nominal area ignored a small actual native radius difference allowed by
the geometric matching tolerance. A tiny-bore fixture was checked PASS although
its minimum delivery exceeded the separately computed inferred-bore flow.
That historical result remains in `native-radius-initial/`. It is not treated
as valid current pressure evidence. The corrected adapter uses the component
bore intervals and fourth-power normalization described above. The kernel API
and its interval proof are unchanged. The same fixture, with only the new
required ideal-bore declaration added to its mission, now yields UNKNOWN and
cannot authorize delivery or acceptance; see `native-radius-corrected/`.

The first component-section integration run is retained in
`native-sections-initial/`: 156 tests passed and one failed because the selection
gate still expected the old report-scope string. The candidate checks passed,
but no incumbent was selected. Updating that scope expectation produced the
staged checkpoint
`b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895`:
all 157 pressure/kernel/native integration tests passed. Its results and test
snapshots are in `native-sections-corrected/`. Neither failed run has been
replaced or erased.

An independent retained dimensional oracle is in
`dimensional-review/09a030c3d51147329266816ed92fd81a/`. It uses the immutable
`b61a7a...` source, its own 100-digit pi constant, and bisection of the original
per-component pressure equations rather than the adapter's normalized
coefficients to obtain reference flows. Two supplied metric boxes, one with a
common straight and one with a common elbow, each cover all 128 diameter/length
corners and 32 interior points. All 320 flow comparisons, 1,280 exact coefficient
comparisons and 2,880 component-port velocity comparisons agree with the
adapter's enclosures. Three additional exact rational cases change D_ref while
preserving the manufactured q1=1/100 and q2=3/200 solutions. These are bounded
algebraic consistency checks, not proof that arbitrary differing sections form
an approved native network.

The existing connected-section and approved fitting gates remain unchanged.
No reducer is authorized by the normalization. A real section transition can
introduce an additional irreversible loss; total-pressure bookkeeping does not
remove it. The supplied friction and fitting coefficients must apply over the
admitted bore and flow-ratio domain. These applicability conditions remain
explicit external assumptions even though their algebraic consequences are
independently checked.

Application integration includes `routing/network_scenario.py`,
`routing/network_pressure.py`, `routing/network_checker.py`,
`routing/network_export.py`, `routing/selection.py`, `store.py` and
`project_assurance.py`. Named immutable test checkpoints determine exactly
what each retained run validated.

The integrated traceability register has exactly 34 relied-on obligations. The new
`UNIFORM_TWO_SINK_PRESSURE_PORT_ENVELOPE_AND_NATIVE_ADAPTER` obligation binds the
original P6 source and an explicit related RTR source hash. It associates
ALG-PO1/PO2/PO7 and ALG-RTR19/20 with these bounded callables and tests while
retaining `full_algorithm_implemented=false` for every source algorithm.
Original supplied mathematics and failed evidence remain unchanged.

## Real Office workflow and physical report admission

The separate frozen pressure mission in
`evidence/benchmarks/pressure-driven/office/b44b3123cdb641709b2aa32ae5bd526c/`
completed in 79.504 seconds on `b61a7a...`. It preserves the earlier Office
geometry, two layout alternatives, loss coefficients and minimum deliveries.
The new hypothetical regulated total pressures are 200 Pa at the source,
170 Pa at the straight outlet and 65 Pa at the branch outlet. They were frozen
before computation, not inferred from actual Office equipment or operating data.
The older fixed-flow mission and its project head remain unchanged.

The offset layout passes all 6,424 native component/source pairs against 803
obstacles and establishes a valid operating point, but its branch delivery is
only 1.218 to 1.227 L/s against a required 2 L/s. It is rejected on service.
The direct layout passes all 3,212 pairs and both minimum deliveries: branch
2.209 to 2.234 L/s, straight 1.330 to 1.355 L/s. Its unique measured length is
1.8000000000000025 m with one fitting. The engine selects this layout, accepts
revision 1 in its separate project, and reopens and checks the actual exported
IFC against all 3,212 pairs again. The fresh state and operating model roots
differ; the independently checked delivery enclosures agree. This is finite
alternative selection, not an unrestricted topology or whole-building claim.

A subsequent audit found that trusted internal report publication could omit
`network-pressure-operating-point` from an otherwise genuine PASS report and
still allow acceptance. Both original managed and unmanaged reproductions are
retained in `evidence/math/two-sink-pressure-independent/81a7d567cf424654ba3ea883af348d16/`.
This was a trusted report-producer omission, not an ordinary API exploit.

The `bac10b7f...` correction shares exact report admission checks between
selection, report publication and acceptance. The pending report must bind its
original candidate/run/baseline, mission, rules, current executable, complete
unique required check inventory and exact overall/per-check scope. Legitimate
NOT_APPLICABLE states remain explicit. Joint fitting budgets also retain their
complete actual new-route count denominator. Imported or materialized physical
states cannot bypass this boundary by changing the candidate kind. Publication
and acceptance execute this validation inside their existing transactions;
process ownership, current input bytes and deadlines remain separate gates.

The corrected 157-case pressure suite passes in 15.15 seconds. An independent
21-case native replay confirms intact reports still publish, select and accept,
while omissions, duplicates and applicability/scope/mission/rule alterations
cannot publish CHECKED or advance a historical accepted head. A separate
71-case conditional-inventory suite passes on the same build. These executions
and the subsequent full backend regression remain separately identified.
