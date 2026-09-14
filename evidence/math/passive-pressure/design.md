# Passive quadratic pressure networks: bounded certificate design

Status: design and evidence only. No production solver, physical adapter, source-register entry or mission schema is changed. This is a proposed next kernel for three-sink trees and networks with loops. Its proof uses pressure energy and comparison, rather than treating a Newton residual or a selected numerical root as a certificate.

## 1. Exact supported relation

Let a finite undirected multigraph have a declared orientation for each edge. Each component must contain at least one Dirichlet boundary vertex. Parallel edges are distinct physical edges and counted separately; the first API can reject self-loops to keep inventory simple. Vertex and edge identities are unique. Every vertex is explicitly either boundary or internal; the two sets partition the full graph.

For an oriented edge e=(u,v), declare

```
h_u - h_v = K_e q_e |q_e|,      0 < K_e < infinity,
q_e = psi_e(h_u-h_v),
psi_e(s) = sign(s) sqrt(|s|/K_e).
```

At each internal vertex, signed outgoing flows sum to zero. Boundary pressures are prescribed and their net injections are outputs. There are no prescribed internal injections in this first model. A nominal source or sink label does not constrain direction: a delivery claim must separately prove the sign and magnitude of its boundary withdrawal. Zero flow and flow reversal are permitted mathematical states.

Inputs are exact finite rational intervals for every K and boundary h. Their entire Cartesian product is the certified parameter domain, including simultaneous endpoint choices. A correlated physical parameter set can be enclosed by this box if an adapter separately establishes that inclusion. No statistical independence or exact hull claim follows from box input.

The head variable has pressure units, Pa. An intended constant-density incompressible interpretation is h=total pressure+rho*g*z, with total pressure including the declared kinetic-pressure convention. K has units Pa/(m³/s)². This is a declared edge law, not an inference from pipe centerlines. No pumps, valves, check-valve regimes, nonpassive elements, fluid storage, compressibility, flow-dependent resistance, unbounded coefficients or zero-resistance elements are admitted by this first theorem. Every K interval must have strictly positive lower endpoint.

## 2. Existence and uniqueness, including loops and zero flow

Fix any admitted coefficient/boundary tuple. On the free internal pressure variables define

```
E(h_I) = sum_e 2 |h_u-h_v|^(3/2) / (3 sqrt(K_e)).
```

Each scalar summand is continuously differentiable and strictly convex in its pressure difference, including at zero. Its derivative is the continuous signed square-root flux. The derivative of that flux is unbounded at zero; no finite inverse Jacobian or positive minimum flow is used.

If two internal pressure vectors differ, their difference is zero at all boundary vertices. Grounding provides a path from any changed internal vertex to a fixed boundary. At least one edge difference must change on that path. Strict convexity of its positive summand, together with convexity of all other summands, makes E strictly convex on the entire internal-pressure space.

E is coercive: if an internal pressure grows without bound while boundary values stay fixed, along a finite grounding path at least one edge difference grows without bound. The corresponding positive |difference|^(3/2) term tends to infinity. More explicitly, if the largest internal magnitude is M, a grounding path of at most |V|-1 edges contains a difference of at least (M-max_boundary_abs)/(|V|-1). Finite positive weights give a common lower growth bound. Thus a minimizer exists, and strict convexity makes it unique. Its first-order equations are exactly internal continuity. Edge flows then follow uniquely from the loss law.

Boundary-only edges add constant energy terms and have uniquely determined flows. An isolated boundary vertex has zero net flow. An isolated internal component is invalid because pressure can shift by a constant. This proof is unaffected by loops or a zero-flow bridge. It is a new explicit specialization of the source's convex/passive classes, not a claim that every nonlinear physical network belongs to them.

If there are no internal vertices, continuity is an empty, explicitly accounted obligation and every edge flow follows directly from its two boundary intervals. No residual coercivity constant is needed. Zero resistance is a different degeneracy: a grounded all-zero-resistance cycle admits arbitrary circulating flow at constant pressure. The positive-K contract excludes that nonuniqueness rather than assigning it a numerical regularization.

## 3. Global bounds and the comparison certificate

For each component, every equilibrium internal pressure lies between the minimum and maximum of its fixed boundary values. At a strict interior maximum above all boundaries, every outward pressure difference is nonnegative, so every outward flow is nonnegative. Continuity forces every neighboring pressure equal. The maximum plateau must propagate to a boundary, a contradiction. The same argument treats a minimum. It also proves equality cases: no arbitrary epsilon or strict residual sign is needed.

Across input boxes, componentwise global boundary extrema L and U are rational, finite uniform bounds. Setting every internal lower barrier to L and every upper barrier to U always supplies a valid comparison enclosure. If L=U, every pressure is exactly that number and every edge flow is zero, even with uncertain positive K.

A tighter certificate supplies rational internal vectors l<=u. For each admitted parameter tuple use its actual prescribed boundary pressures when forming F(l) and F(u), where F is the outgoing-flow residual vector. Independently checked universal inequalities

```
F_v(l; K, h_D) <= 0,
F_v(u; K, h_D) >= 0           for every internal v and every input tuple
```

prove l<=h*<=u. For the lower bound, suppose l-h* has a positive interior maximum. Every adjacent difference increases, so strict monotonicity of psi makes every corresponding outgoing-flow difference nonnegative. F(l)<=F(h*)=0 forces each difference to vanish. The maximum plateau propagates along every adjacent edge to a grounded boundary, where l and h* use the same prescribed value. Contradiction. The upper-bound proof reverses the comparison. This establishes uniqueness independently as well.

The producer need not make l and u solve continuity, nor find one simultaneously worst parameter corner. It must only supply values for which sound outward arithmetic establishes every required sign. Per-node or per-edge adversarial parameter choices may be mutually inconsistent; that loses tightness but preserves uniform soundness.

### Exact radical bounds

For a drop interval [a,b] and resistance [klo,khi], psi is increasing in the drop. Its minimum at drop a uses khi when a>=0 and klo when a<0. Its maximum at b uses klo when b>=0 and khi when b<0. Apply the appropriate sign to nonnegative rational square-root enclosures. To bound sqrt(x), the checker verifies rational 0<=slo<=shi and slo²<=x<=shi², with no floating tolerance.

The verifier reconstructs oriented drops, both endpoint radicands, square inequalities, every edge's orientation, and each node sum. It requires the upper end of each lower-barrier residual <=0, and the lower end of each upper-barrier residual >=0. For a negative square root the endpoints must be reversed. Omitting one edge or changing a boundary to an unknown internal variable invalidates the graph/domain root.

Equal irrational terms can defeat naive finite-width interval cancellation at a sharp barrier. Optional exact same-radicand collection can prove such zeros; otherwise the producer must move the barrier outward or return a coarser valid enclosure. It must not replace an unresolved sign with an epsilon test. The trivial global barriers remain available because their edge-flow signs are exact, including zero.

## 4. Flow, pressure error and optional residual certificate

After verifying pressure barriers, independently propagate [l_u,u_u]-[l_v,u_v] through the signed radical rule for each complete edge. This encloses its unique flow for every admitted tuple. Report pressure/flow intervals and their actual widths; midpoint plus half-width is an error enclosure. The interval vector is an outer set: not every arbitrary combination of its coordinates satisfies continuity. Retain the exact incidence/loss relation, boundary identifiers and conservation theorem alongside the box.

An optional certificate can turn a numerical pressure approximation into an independently bounded error without requiring positive flow. It is a useful secondary method, not necessary for the basic barrier checker. For H=U-L>0, choose rational gamma_e>0 such that

```
4 gamma_e² K_e.upper H <= 1.
```

For pressure differences s,t within [-H,H], the inverse-law secant slope is at least gamma_e. To see this without differentiating at zero, q values have magnitude <=sqrt(H/K), and the forward law K q|q| is Lipschitz on that finite interval with constant 2sqrt(KH). Strict monotonicity transfers that upper forward slope to a lower inverse slope.

Give each internal vertex a simple independently checked path to a boundary. Let

```
R_v = sum_(e in path_v) 1/gamma_e,
alpha = 1 / sum_(internal v) R_v > 0.
```

For an error vector z that is zero on the boundary, weighted Cauchy–Schwarz along each simple path gives z_v² <= R_v sum_e gamma_e (z_u-z_v)². Summation gives a grounded coercivity bound alpha ||z||₂². Repeated edges within a claimed path must be rejected; silently counting them once would invalidate this bound. A tighter rational grounded Laplacian certificate can be added later, but is not required.

The approximate internal pressures x must all lie in [L,U]; their boundary values are the actual admitted Dirichlet values. Use exact outward radical sums to bound each F_v(x) by an interval and let rho_v be its largest absolute endpoint. A supplied rational E>=0 satisfying

```
E² alpha² >= sum_v rho_v²
```

then proves ||h*-x||₂<=E uniformly, hence every component lies within x_v±E. This follows by pairing the monotonicity inequality with z=h*-x and applying Cauchy–Schwarz to the residual. Both vectors have identical boundary values, so their boundary error is zero. Intersect these bounds with the global and/or independently checked barrier enclosure. H=0 uses the exact constant solution; there is no division by zero.

For a graph with no internal vertices the residual section is empty and alpha/E are not divided or fabricated. For disconnected but individually grounded components, prove each bound with its own H and internal paths, or use a coarser common positive H after handling constant components explicitly.

This is a pressure residual certificate. A different flux-energy proof would require an approximation satisfying internal continuity exactly, or a certified feasible correction, before pressure terms cancel. A small unconstrained flux residual alone does not justify that cancellation.

## 5. Why useful bounds exist, and what precision cannot guarantee

Finite positive K boxes and grounded finite boundary intervals always give finite rational pressure and flow enclosures. Rational outward square-root bounds exist for every finite nonnegative radicand. Near zero, flow uncertainty is generally proportional to the square root of pressure uncertainty; a universal linear flow-error constant must not be assumed. For the one-edge law with K=1, pressure epsilon² produces flow epsilon. Dividing pressure residual by an invented fixed positive flow derivative would be wrong.

The global pressure envelope can be coarse. A simple proposal producer can start there and perform bounded coordinate bisection: raise a lower coordinate only after checking its own universal residual remains <=0; lowering an upper coordinate similarly requires >=0. Neighbor residuals move in the helpful direction because F decreases in neighboring pressure. Fresh complete verification remains mandatory after refinement. An untrusted solver may propose better barriers or centers, but success depends only on the independent inequalities.

For nonzero uncertainty a common rectangular barrier may remain much wider than the true correlated solution image. Increasing arithmetic precision cannot eliminate parameter uncertainty or interval dependency loss. Return `CERTIFIED_ENCLOSURE` with measured widths and `target_accuracy_met=false` when the proof is valid but coarse. A work/byte/cancellation limit that prevents full verification returns UNKNOWN with no partial network authority. No convergence rate or large-network runtime guarantee is claimed by this design.

## 6. Proposed bounded API and certificate fields

Planned module: `oma.optimization.passive_pressure`, not created by this design task.

```python
compile_passive_pressure(model, *, pressure_width_target=None,
    max_nodes=64, max_edges=128, max_work=2_000_000,
    max_refinement_passes=128, sqrt_bits=96,
    max_input_bytes=1_048_576, max_certificate_bytes=16_777_216,
    checkpoint=None)

verify_passive_pressure(model, certificate, *, independent_budgets,
    checkpoint=None)
```

The model declares schema, context/model-assumption identities, units, signed edge-law kind, full nodes/edges, orientation, boundary intervals and `internal_injection=EXACT_ZERO`. It explicitly declares `CARTESIAN_OUTER_PARAMETER_BOX`. All interval endpoints are finite rational encodings, with strict size/count bounds checked before Fraction construction and graph allocation. Reject missing coverage, duplicate identities, nonexistent endpoints, invalid boundary partitions, unsupported laws and components without a boundary. No input may silently default to a Dirichlet node or a zero-loss link.

Schema proposal: `oma.passive-quadratic-pressure-envelope/1`. Required proof fields are complete model/domain/topology/boundary/assumption roots; component and grounding coverage; each internal lower/upper pressure; each oriented lower/upper barrier edge radical enclosure; all node residual sums; every final pressure/flow interval; actual width/target disposition; complete denominators; and certificate content root. An optional residual section adds centers, positive rational gamma values, simple grounding paths, alpha, radical residual bounds and E. The checker reconstructs all structures and inequalities rather than invoking the producer or trusting its iteration/work metadata.

Producer dispositions: CERTIFIED_ENCLOSURE, INVALID_INPUT or UNKNOWN. Checker dispositions: PASS, FAIL or UNKNOWN. PASS proves the declared relation's uniform enclosure and pointwise unique existence for every parameter tuple; it does not prove one common flow works for all tuples, universal satisfaction of a physical delivery requirement, physical model applicability or native IFC acceptance. A separate decision layer uses flow lower bounds for minimum delivery and upper bounds for velocity/maximum-flow conditions; mixed intervals remain unresolved.

Cancellation must be called during parsing, graph inventory, every bounded radical batch, refinement, proof serialization and verification. Caller exception identity must survive internal error handling. After the final callback, bounded canonical input/certificate guards run with callbacks disabled. Do not publish partial component success as complete network proof. Default 64/128 limits are a proposed first workload, not a tested performance promise.

## 7. Current native tee model is not this edge law

The existing one-tee kernel and adapter use

```
P_i = beta [A_i Q² + B_i q_i²],       Q=q1+q2.
```

Each A_i includes an outlet-specific tee total-loss coefficient referenced to upstream total flow. A branch loss proportional to Q² is coupled to other branch flows. It is not an independent edge coefficient times q_i|q_i|. In particular, the two pressure-drop functions have cross derivatives 2 beta A1 Q and 2 beta A2 Q. When A1!=A2 they are not the gradient of the separable passive energy above. Positivity alone does not supply the missing reciprocal/separable structure.

If both outlet tee drops are identically the same declared function of Q, a common series loss can sometimes represent them. That requires a new explicit model derivation and complete component accounting; it is not permission to reinterpret existing missions. Dividing a Q² loss by q_i² to invent a branch K depends on the unknown flow split, may diverge at zero, and does not meet the fixed independent-edge theorem. A correlated parameter overapproximation would still require proof of inclusion and would not transfer pointwise-box uniqueness into uniqueness of that coupled physical law.

A future native adapter must explicitly opt into this new ideal-junction/per-edge law, independently account for every actual component and junction, derive units/metric/area/resistance intervals, verify complete wiring, head boundaries and the assumed single node potential. Reducers, tee outlet losses, kinetic-pressure differences and reverse-flow applicability must be handled by declared physical contracts. The current fixed-flow and two-sink pressure missions, request hashes and total/static-pressure conventions must remain unchanged. This design gives no native interface or fabricated fitting authority.

## 8. Source traceability and independent examples

The read-only original `math1/math1/1-10.pages` has SHA `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`. P6 §16 P16069–16077 and table 1736791 distinguish strictly convex energy, strongly monotone operators and general multiple-equilibrium relations. The table's native model 1736794 payload hash `e1ab94b17ca4244a44eb955cb6d38df09ada4df1126c6cc776780177ddcdaafb` was independently checked against its retained native payload.

THM-PO12 P16118–16135 requires all admitted equilibrium branches unless an exact selection theory exists. DEF-PO11 and THM-PO7/8 P16139–16203 require validity-domain inclusion and sound composition. THM-PO14 P16360–16397 explicitly rejects residual-only error claims without stability. P6 §40.1 P16836–16853 gives the signed quadratic series law, square-root inverse and zero-pressure sensitivity warning. ALG-PO7 P17130–17158 requires units, wiring, parameter coverage, conservation, stability, inclusion and dependency checks. ALG-PO1/2 P17615–17681 permits exact implicit relations and certified envelopes with UNKNOWN/refinement.

The integration DOCX SHA is `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. Native `word/document.xml::p[4592]`–`p[4609]` (DEF-RTR56) includes conservation, areas/velocity, friction/fitting losses and geometry applicability. P5530–5533 (ALG-RTR19/20) separates physical model compilation from untrusted solving and trusted evidence. P5536–5537 (ALG-RTR22) requires complete request, geometry, physics and version binding. These clauses motivate the design; they do not provide this particular graph comparison algorithm or close their full bodies.

[source-basis.json](../evidence/source-basis.json) retains 247 reread Pages paragraphs, the complete native table, 26 directly re-extracted DOCX paragraphs and current code touchpoint hashes. Original flattened equation gaps are preserved rather than silently reconstructed.

[reference_examples.py](../scripts/reference_examples.py) is an evidence-only script, not a production solver. Its retained [results](../evidence/reference-results.json) check exact rational barrier signs, final radical enclosures and the optional grounded residual bound for three tiny models:

| Model | Exact nominal solution | Independent uncertainty evidence |
| --- | --- | --- |
| Three-sink tree S→J→T1,T2,T3, all K=1, hS=10 and hTi=0 | hJ=1, common flow 3, each branch 1 | K±1%, source±0.1 and sinks±0.01; barriers 0.95…1.05; 256 box corners and 16 interior tuples checked by independent 80-digit scalar continuity bisection |
| Triangle loop S→A→T plus S→T, KSA=3, KAT=KST=1, heads 4 and 0 | hA=1, series flow 1, direct flow 2 | K±1%, source±0.04, sink±0.01; barriers 0.95…1.05; 32 corners and 16 interior tuples checked against the independently eliminated series formula and direct edge inverse |
| Diamond S→A→T and S→B→T plus A→B, all K=1, heads 8 and 0 | hA=hB=4, four outer flows 2 and bridge flow 0 | K±1% and boundary±0.01; uniform barriers 3.9…4.1 checked by exact rational radical sums; nominal zero-flow solution checked exactly |

All 320 finite reference cases lie inside the proposed pressure, flow and residual-error bounds. Sampling is consistency evidence only; uniformity follows from the stated comparison/stability proof and exact inequalities. This task has not implemented or machine-proved a general certificate verifier, performed native materialization, or modified the production source/capability register.

An independent peer additionally checked a genuinely coupled diamond loop with nonzero cross-flow: hS=10, hA=6, hB=4, hT=0; oriented flows (SA,AT,SB,BT,BA)=(3,2,1,2,-1) and K=(4/9,3/2,6,1,2). Its 144 coefficient/boundary corner and interior tuples were solved by an independent 65-digit two-node continuity procedure and lie within rational barriers A∈[5.5,6.5], B∈[3.5,4.5]. The peer also checked 2,250 exact signed-root memberships, an exact constant uncertain-K plateau and the irrational-cancellation limitation. [The independent review](../evidence/independent-design-review/review.json) retains the exact reviewed draft/script hashes and the separate oracle; it found no concrete false bound. These results remain finite consistency and bounded proof review, not a machine-checked universal theorem.

[edge-case-obligations.json](../evidence/edge-case-obligations.json) also retains an exact three-sink binary tree with two internal junctions, all K=1: S14→J1=5→J2=1, outlets T1=4 and T2=T3=0. The five flows are respectively 3,1,2,1,1 and satisfy every edge law and both continuity equations exactly. It requires only degree-three junctions, but still grants no native tee-loss applicability. The same evidence records negative-flow endpoint selection, unresolved sharp radical cancellation versus valid outward slack, zero/empty internal cases and explicit ungrounded/zero-resistance counterexamples.
