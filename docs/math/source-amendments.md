# Source amendment register

Sources are immutable. Corrections below govern scoped implementation and are
never represented as edits to the supplied mathematics. Paragraphs refer to
native extraction, not PDF pages. Historical references include the archive
name. Reading, counterexample reproduction and proof verification are distinct.

`scripts/corpus_math_checks.py` writes 35 successful audit probes to
`evidence/math/counterexample_results.json`. These include exact finite
counterexamples, two explicit analytic examples, and assumption-necessity
examples. They do not prove implementation completeness. A001–A007 are detailed
in `implementation-contract.md`; A005 is a namespace reconciliation requirement
rather than a numerical counterexample.

| Amendment | Native source and finding | Required correction |
|---|---|---|
| A008 | Canonical THM-LIFE23, 36025–36033: an observation tuple is compared to TRUE, and one obsolete part is used to exclude the repair fiber. | Define a typed obsolescence predicate; exclude every compatible repair including qualified substitutes before declaring the fiber empty. |
| A009 | Ceiling Router 5584–5597: variable spacing delta(s) is admitted but its derivative is omitted from offset length. | For arc-length centerline, integrate `sqrt((1-/+delta*kappa/2)^2+(delta'/2)^2)`. The original simplification requires constant spacing and its sign/regularity assumptions. |
| A010 | Ceiling Router 5615–5621: earliest feasible chain positions are called an ADMM projection. | Solve the specified quadratic projection. Earliest DAG positions establish feasibility, not nearest-point optimality. |
| A011 | Ceiling Router 2554–2560, with extra hypothesis acknowledged at 6455: the convergence proof uses a local spanner property beyond sample density. | State and verify transition coverage/local connectivity or the required spanner hypothesis. This is a proof-premise gap, not a rejection of every graph refinement construction. |
| A012 | Ceiling Router 7276–7288: a limited proposed order family is followed by an all-orders infeasibility claim. | Close all admitted orders/layers or supply a universal obstruction. Limited search failure stays UNKNOWN. |
| A013 | ALG-SIR19, integration 1596–1609: a rejected route witness can be confused with an empty route fiber. | Return witness invalidity; fiber emptiness needs a complete impossibility certificate. |
| A014 | SIR44, integration 1349–1354: existential local compatibility is confused with selected-witness agreement. | Glue fixed witnesses that agree on all overlaps; every global factor must be covered by a bag or a valid decomposition theorem, as ADD-SIR2.3 requires. |
| A015 | JCD97, integration 16901–16911: minimum OPEN-node lower bound omits closed incumbent regions. | Maintain a complete region cover. With exact incumbent U and sound closed-region dispositions use `min(U,min OPEN bounds)`; with interval accepted cost retain the relevant closed-region lower endpoints. |
| A016 | JCD99, integration 16931–16944: covering all excluded states by archive dominators does not ensure internal nondominance. | Check both internal nondominance and excluded-state coverage. Define objective ties separately from contextual state equivalence. |
| A017 | DEF-JCD106 at 14185–14193 and PRO-JCD1 at 14451–14453: both universal truth tests are vacuous on an empty concretization. | Require nonempty concretization or introduce EMPTY before the three-valued rule. |
| A018 | DEF-CMP205 at 23775–23777 orders tokens by reverse entailment, but DEF-CMP208/209, THM-CMP77, ALG-CMP41/42 and table 26213 reverse lattice operations. | Under this order meet is disjunction, the strongest common consequence; join is conjunction, the weakest common strengthening. Operate only in a compatible licensed context. |
| A019 | RTR Lean sketch 7020–7025 and CMP127 at 24404–24405: deterministic checking is used to infer equal verdicts for potentially different producer artifacts. | Require the same artifact and checked context, or proved observational equivalence. CMP53's same-artifact formulation is the applicable rule. |
| A020 | CMP18 at 24170–24171: failure of syntactic read/write independence is treated as semantic noncommutativity. | Independence is sufficient, not necessary. Conservative serialization remains sound; do not assert the converse theorem. |
| A021 | DYN60 at 19339–19340: the phrases invariant terminal set and disturbances covered leave the shift argument underspecified. | Bind the actual robust feedback/tube policy, disturbance consistency and robust terminal invariance. The executable example demonstrates why a merely nominal interpretation is insufficient, not a counterexample to a fully specified robust theorem. |
| A022 | CMP table 26213: probability-to-robust conversion cites a support theorem without enough applicability conditions. | Probability one need not mean every support point. Supply continuity/closed-predicate conditions or a separate universal proof. |
| A023 | JCD19 at 14543–14546: the zero-slope example at zero for x squared is actually a subgradient. | Move the example to x=1, where the constant zero lower bound is not tight and its slope is not a subgradient. |
| A024 | CMP108 at 24364–24365: a multiplicative unit formula is too broad. | Apply `x*scale+offset` for affine units; keep the source formula restricted to linear unit families. |

The A-prefix above expands to `OMA-MATH-A`. Additional source findings awaiting
their own executable implementations or proof closures remain explicit:

| Source | Finding and disposition |
|---|---|
| SIR29, 1298–1301 | A four-neighbor grid cannot traverse the diagonal channel, but the proof's no-interior-sample assertion is false. Grid edges leave the channel; use that obstruction. |
| SIR38, 1325–1326 | Removing a radial slice from a central obstacle does not automatically make the surrounding free annulus simply connected. Specify an actual topology-changing geometry and prove it. |
| RTR example 67, 6177–6191 | Sum of current per-net route minima is not a full lower bound with incomplete pricing. Require independent globally valid floors or complete route pricing. |
| JCD70, 14720–14722 | Distinguish weak componentwise order from the strict dominance relation named elsewhere. |
| JCD materialization semantics | Multiple materializations do not automatically prevent exact route value if all checked realizations have a proved common value. Otherwise retain set-valued/minimized semantics with explicit coverage. |
| DYN124, 19490–19491 | The progressive-hedging argument invokes saddle-point existence not implied merely by existence of a primal optimum. State constraint qualification/dual attainment and the algorithm's applicability. |
| DYN141, 21562–21585 | Whole-construction release must include history/nonanticipativity and terminal commissioning-entry predicates, either directly or within the checked constituent obligations. |
| DYN regression 20541 | Independent confirmatory testing does not by itself establish a deterministic fault diagnosis. Retain test error, model and diagnostic logic. |
| DYN example 20016/20052 | The table already lists D as a predecessor of H/U, contradicting prose claiming precedence-only scheduling omits D. Retaining D still exposes the crane conflict. |
| CMP synthetic example 25465–25467 | UNKNOWN firestop feasibility cannot automatically become bounded feasible release. Explicit conditional authority may restrict use but cannot change the underlying truth status. |
| CMP transaction regression 25526 | Equal engineering state after commuting actions does not require equal lineage/event roots. Compare the engineering projection or define canonical history equivalence. |
| CMP project catalog and 23393 | Multiple operations return committed roots although prose says only transaction.commit does. Route all through a shared trusted commit primitive or correct the catalog claim. Protocol-specific runtime clauses are NOT_APPLICABLE_TO_STANDALONE_RUNTIME under the user's directive. |
| RTR table 6282, DYN table 19535, JCD table 17010 | Several original cells lose delimiters or shift scope/dependency columns. Literal cells are preserved and flagged. Complete prose governs only when its meaning is independently unambiguous. |
| Historical 1–10:P24 and P639 | P24's informal until-counterexample phrase cannot justify exact pruning. Later P639 explicitly supplies the correct proposal-only fallback; use that stronger source condition. |
| Historical 11–20:P408–P420, THM-ASS3 | Omitting a named root does not imply it is unprovable: `{P}` entails omitted `P or Q` without an exhaustive manifest theorem. State lack of a general guarantee for independent omitted obligations, or add explicit non-entailment. |

| Amendment | Historical native source and finding | Required correction |
|---|---|---|
| A025 | `1-10:P8179`, `P8700–8708`, ALG-DS1 and THM-DS15: root class deduplication is claimed to preserve arbitrary admitted menus. | Contextual substitution preserves an existing label; deleting labels can change a menu-dependent choice rule. Preserve all labels and multiplicities when lifting quotient profiles, or explicitly require duplicate-invariant class-menu semantics. A rule selecting all alternatives exactly when at least three labels exist is a finite counterexample. |
| A026 | `1-10:P7955–7959`, THM-DS8: decision width excludes the root, while storage sums over all nodes. | Retain root output storage or add an explicit root-width/streaming premise. Two children with n states can generate n squared distinct root outputs; a three-node tree then exceeds a uniform O(n) storage estimate based solely on nonroot width. |
| A027 | `1-10:P9121–9150`: the repeated-hotel example retains all 192 feasible bay assignments while treating varying cost/schedule/facade observations as fixed by conditioning. | Explicitly approve an observation projection, or restrict the carrier to a genuine fixed stratum and recount. Original P2 table 1736215 contains assignments with equal projected aggregate signatures but different cost and schedule. The implemented benchmark uses a declared projection under THM-DS13A. |
| A028 | `11-20:P408–420`, THM-ASS3: a missing manifest root is asserted unprovable without exhaustiveness. | Add non-entailment or independence. A manifest containing P already entails an omitted P OR Q. An incomplete manifest gives no general guarantee for arbitrary omitted obligations. |
| A029 | `11-20:P1145–1172`, ASS14: SCC condensation and DAG induction are used without an intra-component solution contract. | Deterministic mutually dependent functions may have no fixed point or multiple fixed points. Specify grounded least-fixed-point semantics with checked finite monotonicity, or another justified component-level cold contract. |

| A030 | `1-10:P12168–12171`, repeated in table 1736487: two initial blocks and four accepted binary splits are followed by five final classes. | Five final classes require three accepted nontrivial splits. A redundant fourth probe does not increase the block count and is not an accepted split. |
| A031 | `1-10:P11968–12021` and `P12104–12116`: a fixed finite string carrier is combined with literal append contexts and B+1 nonempty classes without explicit reachability bounds. | Supply typed total context maps and sufficient reachable counts. Literal append changes length and needs compatible sorts. A fixed-width activation operation may reproduce saturated count transitions under its explicitly named corrected interpretation. |
| A032 | `1-10:P14639–14692`: a cost interval changes from B=[81.1,81.8] to B=[81.85,81.90] while being called refinement. | The disjoint interval is a model/input change, not nested refinement. A valid nested example A=[80.90,80.95], B=[81.77,81.80] still proves B outside the one-percent band since 1.01 times 80.95 is 81.7595. |
| A033 | `1-10:P13943–13961`, THM-ER16, repeated as proved in P6 table 1736775: local constancy of discrepancy plus nested enclosure intersection is used to claim convergence of the whole discrepancy image. | The discrepancy floor inclusion is sound; exact limiting equality needs the enclosures eventually inside the local-constancy neighborhood. Closed nested sets E_n={0} union [n,infinity) intersect to {0} but retain a distant discrepancy branch forever. Shrinking diameter or suitable compact nested closed enclosure assumptions repair the limit. |
| A034 | `1-10:P16208–16242`, THM-PO9: a nonattained directed-excess distance is approached with arbitrary slack, then a modulus is evaluated at the exact distance without a continuity premise. | Require attained nearest points or a right-continuous modulus, or use its right-limit bound. On Y={0} union {1+1/n}, the approximate A images approach distance 1 without attaining it. A downstream map 0 at zero and 1 elsewhere admits the jump modulus omega(t)=0 for t<=1 and 1 otherwise; the composite error is 1 despite omega(1)=0. |
| A035 | `11-20:P3792–3804`, independently read by the UI agent in chunk 73: C({A,B})={A,B} and C({A,B,C})={C} is offered as a non-rationalizable menu example. | Fixed utility u(A)=u(B)=0, u(C)=1 rationalizes both menus. This is a local explanatory defect: later P4046–4052 supplies the valid stronger example C({x,y})={y}, C({x,y,z})={x,z}. Use that source witness and preserve the general menu-sensitive choice semantics. |

Canonical and historical object IDs are separate namespaces. A reconstructed
identifier matching a historical spelling is not evidence that their statements,
assumptions, algorithms or dependencies are equal.
