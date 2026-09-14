# Mathematical implementation contract

The authoritative product scope is the supplied final production directive. The
mathematical sources constrain the engine's algorithms and claims; their older
AI, MCP and whole-building-compiler architecture does not expand that scope.

Source locations below are native XML paragraph numbers, including table cells.
Use `python scripts/corpus_audit.py read oma-integration START END`. They are not
PDF page numbers. SHA-256 identities and the exact extraction are in
`evidence/math/source_inventory.json`. The review ledger records what was read;
unrecorded ranges remain unread. Neither extraction nor a source author's audit
is independent proof of mathematical correctness or implementation coverage.

## Source state

The 12 supplied files were inventoried without modifying originals. The canonical
DOCX, companion PDF, CSV and repair audit match the canonical manifest's hashes.
The manifest's source ZIP is absent. All three historical `.pages` archives are
now present although the canonical reconstruction describes them as unavailable
in its earlier run. Their IWA bytes have been inventoried but not yet decoded or
reconciled with the reconstruction. The repaired canonical body remains the
declared active source; historical fidelity is unresolved.

The native canonical extraction contains 63,298 paragraphs, 638 tables and all
1,616 OMML equation nodes. Complete OMML XML is retained, so fractions and other
structures can be inspected without trusting concatenated tokens. The integration
DOCX contains 26,737 paragraphs, 107 tables and literal LaTeX equations. Its
Prompt 2 paragraphs 3585–8330 and 8331–13076 are exactly duplicated as paragraph
text; preserve both source occurrences and use the first as canonical locator.

Ceiling Router is a PCB autorouting research program. Its report explicitly
distinguishes specification, audit, formalization and proposal from available
implementation. PCB coordinate bounds, path-class completeness and performance
claims cannot be inherited as building-engine evidence.

## Engine interfaces

The SIR combines typed geometry, systems/netlists, constraints, proof evidence and
dependencies over common semantic IDs. Each relationship must agree on units,
frame, scope and version (integration §§9–27, p637–1043). Source IFC identity,
internal semantic identity and renderer identity have different purposes.

`RouterRequest` must bind a state root, fixed-design context, net obligations,
modes, scenario family, explicit objective policy, compute budget, target claim
modality and version vector (DEF-RTR9, p4285–4291). `RouterResult` must retain
route witnesses, physical states, resource use, objective vector, bounds with
scope, conflicts, repairs, proof references and unresolved obligations. Candidate
geometry is not a feasibility certificate. A user interface may expose shorter
labels but must preserve these distinctions in persisted evidence.

`JointDesignRequest` additionally binds baseline state, editable variable domains,
protected roots, permitted rewrite templates and authorization scope (DEF-JCD8,
p13808–13939). Materialize each assignment, check it, and rerun dependent routing.
The router cannot silently move a protected shaft or lower a demand. Authorized
equipment, service-zone and opening changes are legitimate strategic variables.

Every bound/cut/dual carries the design-rooted tuple from ADD-RTR3.2,
p13314–13346: candidate root, request, route universe, master rows, branch state,
resource semantics, objective, physical theory and checker versions. Geometry,
envelope, topology, capacity, objective or rule changes invalidate descendants.

## Required algorithm distinctions

| Mechanism | Required finite computation and evidence | Native source |
|---|---|---|
| Configuration space | Classify complete position/orientation/section/fitting/support/slope cells using exact predicates or sound clearance enclosures. Keep unresolved cells UNKNOWN. | DEF-RTR12–17, p4293–4333 |
| Inner route graph | Each admitted edge contains a checked continuous full-body transition. Missing paths mean refinement or UNKNOWN. | DEF-RTR18–24, p4335–4367 |
| Outer abstraction | Only use graph disconnection to prove impossibility when every feasible continuous route maps to an outer walk. Coarseness is not completeness. | Same sections |
| Exact geometry | Arbitrary-precision integers/rationals or certified enclosure predicates; fixed-width paths require expression bounds. Degenerate contact follows an explicit rule. | p4369–4408 |
| Lifted route search | Search state includes incoming direction, bend, straight length, fitting, slope, support phase, size and insulation. Homotopy words are theorem-scoped and not automatically complete in 3D. | p4434–4484 |
| Multi-terminal routes | Embedded graph spanning all required terminals with permitted junctions and aggregate trunk demand. A bundle of distinct services differs from a shared trunk. | p4486–4556; ADD-SIR2.1 p3786–3806 |
| Physical fibers | Check catalog sizes, directed conservation, pressure/head/velocity or electrical ampacity/drop/fill, gravity slopes and communications constraints where applicable. Carry missing inputs as UNKNOWN. | p4558–4686 |
| Checked columns | Each route column binds physical witness, cost vector, exact or bounded resource incidence and dependencies. Quarantine heuristic-only columns from certified masters. | p4688–4712 |
| Column generation | Solve restricted master, independently validate primal/dual, price the full declared route universe, check proposed columns and repeat to pricing closure. Artificial phase-I columns never become routed incumbents. | p4728–4802 |
| Branch and price | Every branch is exhaustive and disjoint; branch predicates also constrain pricing. Keep unresolved nodes and budgets explicit. | p4804–4852 |
| Infeasibility | Accept only checked outer separators, full-domain Farkas closure, exact branch/enumeration proofs or a valid combinatorial obstruction. Search failure and floating solver status are insufficient. | p4833–4891 |
| Co-design cuts | Universal validity domain must be certified. Classical Benders needs a fixed dual-feasible region; heuristic congestion maps and local multipliers are not global cuts. | p14030–14184 |
| Incremental execution | Complete dependencies; invalidate columns, bounds, cuts and accepted claims transitively. A cyclic dependency needs fixed-point/termination semantics, not a one-pass topological walk. | p5022–5037; p22973–22987; p23806–23861 |
| Transaction and export | Stage immutable artifacts then atomically publish complete root, branch CAS and event. Import/export are translation-validated with explicit loss sets and root-bound round-trip checks. | p22851–22889; p23869–23981 |

The scalar master optimum over an incomplete route subset is not a full-problem
lower bound. A cost-10 restricted route with an omitted valid cost-1 route is a
counterexample. Exact enumeration can close a *declared finite model*; it cannot
prove unrestricted continuous routing optimality without a completeness theorem.

## Amendments required before relying on affected results

`python scripts/corpus_math_checks.py` reproduces the following defects and checks
the corrected finite rules. These probes establish the counterexamples and small
rules only, not application implementation or real-building performance.

| ID | Exact statement and defect | Corrected obligation |
|---|---|---|
| OMA-MATH-A001 | DEF-RTR82 p4891 and THM-RTR96 p5425–5427 allow deletion that is merely “noncertified” to establish inclusion-minimality. Core `{x>=1,x<=0,y>=0}` stays infeasible after deleting the irrelevant last premise even if its deletion solver returns UNKNOWN. | Require independently checked feasible witnesses for **every** single-premise deletion. UNKNOWN yields MINIMALITY_UNKNOWN; a checked infeasible deletion proves nonminimality. Propagate to ALG-RTR34 and all core-based explanations. |
| OMA-MATH-A002 | DEF-RTR49 p4535–4537 defines arbitrary jointly forbidden hyperedges, but DEF-RTR68 p4734 imposes `sum(H)<=1`. A triple-only conflict permits all pairs and violates this strengthening. | For a jointly forbidden set use `sum(H)<=|H|-1`. Use `<=1` only for a pairwise-incompatible clique with a checked clique witness. Recompute corresponding dual constants, master bounds and Farkas certificates. |
| OMA-MATH-A003 | ADD-SIR2.2 p3816 defines injection minus withdrawal while p3825 defines incidence as incoming minus outgoing; p3821 uses incompatible signs. | With incidence head `+1`, tail `-1`, define signed demand as withdrawal minus injection and use `Bf = demand + storage_rate + losses - conversion`. Alternatively reverse incidence consistently. Bind the convention in every physical-fiber certificate and test source-to-sink direction. |
| OMA-MATH-A004 | DEF-SIR64 p978 writes `W minus (O plus -B)` for translational free space. If W is the permitted occupied spatial region (DEF-SIR37), a center inside W may still place part of B outside it. | Use `(W eroded by B) minus (O plus -B)` or prove W already denotes admissible centers. Include fittings, insulation and relevant access envelope in boundary containment. |
| OMA-MATH-A005 | Integration p106 imports DEF-F4 as a contextual computation family, but canonical p15636 defines an independent checker. Integration p214/p220 import THM-RT15/17 as reuse/cold-equivalence; canonical p20569/p20589 are a second-order jet bound and approximate-reuse modality. | Resolve definitions by body semantics and source namespace. The actual reuse theorem is canonical THM-RT16 (p20579), and cold equivalence is THM-RT19 (p20605). Cyclic reuse additionally requires certified closure, as in integration THM-CMP85. Other imported IDs remain subject to semantic reconciliation. |

The source itself repairs several earlier results: ADD-SIR2.1 uses embedded
graphs for multi-terminal services; ADD-SIR2.3 requires every complete factor
scope in a local-gluing bag; ADD-RTR3.1 permits equality of averaged loads only
for affine maps and otherwise uses Jensen bounds. Implement these active
addenda, not their earlier superseded forms.

Two additional canonical corrections are necessary. **OMA-MATH-A006**: native
paragraphs 18160–18177, equations P04-E0034/0035, copy an argmin formula into
global-dominance and contextual-equivalence theorems. PDF pages 155–156 confirm
the defect is present in the source. Use componentwise order over the complete
objective vector for THM-DS19.1, and equality of all active experiments through
the quotient for THM-DS20.1. Dominating one candidate does not establish argmin
membership; two interchangeable states need not be optimal.

**OMA-MATH-A007**: THM-DS21.1 at 18178–18185 states that complete finite generation
and a sound checker suffice for declared global optimality. A sound three-valued
checker may leave a feasible cost-1 candidate UNKNOWN while accepting cost 10.
Minimizing the accepted subset then misses the declared feasible optimum. Close
every candidate's feasibility, or prove a valid bound excludes improvement by
every unresolved candidate. Otherwise report an accepted-subset optimum with
unresolved candidates retained. `corpus_math_checks.py` reproduces both defects.

## Remaining review and claim limits

The current executable obligation register is
`evidence/math/traceability_register.json`, rebuilt by
`.venv\Scripts\python.exe scripts/corpus_obligations.py`. It resolves 19 scoped
obligations to actual callables and tests. The recorded focused run contains
72 passing tests, covering finite master selection and pricing, physical path
models, exact primitive predicates, conservation, gravity, guarded dependency
recomputation, finite cyclic closure, exact source IFC enclosures, contextual
quotients, finite nonanticipative policies, quantity transport and candidate-rooted
co-design. The adapter requirements are in `finite-kernel-integration.md`.
These tests do not close the real-model
benchmark, complete routing, or whole-program release requirements.

Full source review is incomplete. The precise read ledger is authoritative;
remaining canonical bodies, theorem proofs, tables, appendices and dependency
closures must still be reviewed before their claims are advertised. Registered
object dependency references all resolve in the manifest, but this does not
establish that those dependency lists are mathematically complete. Canonical PDF
pages 100, 155, 156, 209 and 210 were rendered and visually inspected to reconcile the
finite-search and rewrite-theorem equations. Remaining page review and
historical Pages reconciliation are pending.

The five-part document's MCP catalog and compulsory AI compiler concepts are
excluded by the newer directive. Dynamic/scenario mathematics may support the
engine's explicit simulation and robust-design capabilities; whole-lifecycle or
whole-building release theorems require additional evidence beyond an individual
route or finite optimization result.
