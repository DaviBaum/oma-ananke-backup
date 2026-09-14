"""Build the source-to-callable traceability register without claiming release."""
from __future__ import annotations
import hashlib
import importlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    sources = json.loads((ROOT / "evidence/math/source_inventory.json").read_text(encoding="utf-8"))["sources"]
    identities = {s["document_id"]: s["sha256"] for s in sources}
    entries = [
        ("UNIFORM_POSITIVE_BOX_COUPLED_TREE_PRESSURE_CERTIFICATE", "1-10", [14530, 14546, 16081, 16114, 16118, 16135, 17645, 17681], ["THM-PO11", "THM-PO12", "ALG-PO2"],
         ["oma.optimization.coupled_tree_pressure.compile_coupled_tree_pressure"], ["oma.optimization.coupled_tree_pressure.verify_coupled_tree_pressure"], "tests/test_coupled_tree_pressure.py",
         "The declared complete polynomial system has one leaf-flow variable per outlet, named nonnegative coefficient intervals and laminar descendant/applicability sets. Every term contributes a coefficient times its full descendant-flow sum squared to every applicable leaf equation. Unequal tee outlet losses therefore need not give a symmetric Jacobian. For each same parameter tuple the independently reconstructed center residual and full interval Jacobian define T(q)=q-R*F(q), with an exact inverse witness proving R invertible. Full signed interval matrix arithmetic proves strict inclusion of the mean-value image inside the supplied positive box and an induced infinity-norm contraction below one. Banach then proves exactly one positive root inside that box for every admitted tuple. Complete term/equation/matrix/parameter/box inventories and final guards prevent incomplete or stale proof authority.",
         [], "Uniqueness is only inside the supplied nondegenerate positive box. This module does not exclude other equilibria outside it, certify the native tree/component correspondence, justify physical loss or boundary data, or grant service/acceptance authority. Failure to invert, contract or strictly include is UNKNOWN, never infeasibility. Shared parameter identities may be conservatively over-enclosed; no common root for every parameter tuple or tight hull is asserted. Variable/term/matrix/work/bit/input/certificate limits are explicit. Full original source algorithm completion remains false."),
        ("GROUNDED_PASSIVE_RESIDUAL_TO_SOLUTION_ERROR_BOUND", "1-10", [13753, 13781, 16360, 16397, 16836, 16853, 17130, 17158], ["THM-ER22", "THM-PO14", "ALG-PO7"],
         ["oma.optimization.passive_residual.compile_passive_residual"], ["oma.optimization.passive_residual.verify_passive_residual"], "tests/test_passive_residual.py",
         "On a complete grounded positive-K graph, the supplied exact internal head vector lies in each component's boundary hull and uses the same actual Dirichlet parameter tuple as the equilibrium. Every positive-span edge has a checked positive conductance satisfying 4*c*c*K.upper*span<=1; complete simple grounding paths and weighted Cauchy-Schwarz give sigma=sum_internal(sum_path(1/c)). Independent signed-root incidence and norm bounds prove uniform pressure L2 error at most sigma*R. Constant-span and boundary-only cases have explicit zero-error branches. The parameterized reference-flow family is widened by independently checked sqrt(2*endpoint_error/K.lower), including the essential zero-crossing factor two, then intersected with direct pressure-box images. Full model/query/term/node/path/radical inventories and final mutation guards are independently checked.",
         [], "A bounded-domain stability specialization, not a global unbounded strong-monotonicity constant. Parameter variation is included and is not labeled pure numerical solver error. Reference flows depend on actual boundary/resistance parameters and need not conserve internal flow. Coarse valid bounds may miss the requested target. No native model applicability, physical discrepancy, delivery, acceptance, best approximation, tight hull or full original algorithm completion; count/path/work/bit/byte exhaustion remains UNKNOWN."),
        ("NATIVE_COMMON_OUTLET_PASSIVE_TREE_MODEL_AND_SERVICE_ENVELOPE", "oma-integration", [4592, 4609, 5530, 5531, 5532, 5533, 5534, 5535, 5536, 5537], ["DEF-RTR56", "ALG-RTR19", "ALG-RTR20", "ALG-RTR21", "ALG-RTR22"],
         ["oma.routing.passive_tree_pressure.derive_passive_tree_model", "oma.routing.passive_tree_pressure.evaluate_passive_tree"], ["oma.routing.passive_tree_pressure.verify_passive_tree_envelope", "oma.routing.network_checker.verify_network_candidate"], "tests/test_passive_tree_pressure.py",
         "A new exact boundary contract explicitly assigns every tee one positive inlet-flow-referenced total loss common to its two outlets. Fresh native component lengths, radius enclosures and every transformed physical cap position determine a complete grounded graph quotient. Independent adjacency reconstruction and direct dimensional extrema replay each port group and per-component resistance. Independently verified passive pressure bounds induce every physical port flow, total pressure, velocity, exact minimum delivery and complete continuity identity. Native geometry and operating proof are separate mandatory checks; acceptance and fresh exported-byte checks bind current candidate, mission, rules, source, geometry and executable roots. Exact rational minima remain authoritative while legacy Demand floats are descriptive projections only.",
         [], "Explicit ideal-bore fixed-loss pressure-pipe trees only. Actual inner bore, wall thickness, catalog applicability and supplied boundary controls remain external. Unequal-outlet tee laws, zero resistance, duplicate boundary quotient nodes and a complete arbitrary physical fiber are not supported. A valid signed operating envelope may still fail required forward flow or service; unknown signs, nonpositive native bore or budget exhaustion cannot pass. Small admitted section differences do not prove additional transition losses absent. Hot arithmetic uses bounded ordinary-Run polling with forced start/end controls; no control cache has publication authority. No global topology optimum or complete original source algorithm is claimed."),
        ("GROUNDED_PASSIVE_QUADRATIC_NETWORK_COMPARISON_ENVELOPES", "1-10", [16069, 16077, 16118, 16135, 16139, 16203, 16360, 16397, 16836, 16853, 17130, 17158, 17615, 17681], ["ALG-PO1", "ALG-PO2", "ALG-PO7", "THM-PO7", "THM-PO8", "THM-PO12"],
         ["oma.optimization.passive_pressure.compile_passive_pressure"], ["oma.optimization.passive_pressure.verify_passive_pressure"], "tests/test_passive_pressure.py",
         "Explicit bounded signed quadratic edge model on any finite graph whose every component contains a Dirichlet boundary. Strict positive resistance boxes, full boundary-head boxes and exact zero internal injection define the admitted relation. Grounded strict-convex/coercive pressure energy proves unique existence for each parameter tuple, including loops, reversal and zero flow. Independently checked rational sub/supersolution barriers, signed resistance extrema, square-root inequalities and complete incidence sums enclose all pressures, edge flows and boundary injections. The producer may refine barriers but the verifier never invokes its search or radical producer. Model/query/domain/topology/assumption roots, every edge and node denominator, width claims and final callback mutation guards are independently checked.",
         [], "Conditional scalar-junction/per-edge law only; it does not establish native IFC applicability, catalogue loss truth, individual sink delivery, physical velocity requirements, continuous routing optimality, tight interval hulls or full source algorithm completion. Existing unequal outlet-specific tee losses referenced to total inlet flow cannot be transferred to the separable law. Zero resistance and ungrounded components are unsupported. Whole-parameter-box enclosures may be coarse; attained width is explicit. Count/work/rational/input/certificate limits return UNKNOWN without partial authority. No residual-norm error certificate or native graph adapter is implemented by this module."),
        ("RESIDUAL_WHOLE_WORD_FABRICATION_FRONTIER_AND_JOINT_PROPOSALS", "oma-integration", [4472, 4484, 5522, 5523, 5536, 5537, 5544, 5545, 5546, 5547], ["ALG-RTR15", "ALG-RTR22", "ALG-RTR26", "ALG-RTR27"],
         ["oma.optimization.fabrication_alternatives.compile_fabrication_alternatives", "oma.routing.fabrication_residual.residual_proposals", "oma.routing.certified_fabrication.build_certified_fabrication_proposals", "oma.routing.proposals.project_proposals"], ["oma.optimization.fabrication_alternatives.verify_fabrication_alternatives", "oma.optimization.fabrication.verify_orthogonal_fabrication", "oma.routing.joint_checker.verify_joint_candidate"], "tests/test_optimization_fabrication_alternatives.py",
         "Bounded new specialization of the fabrication lift and represented pricing domain. A compact prefix trie excludes only complete independently checked seven-coordinate graph-state words already generated as proposals; all prefixes, shared edges and successors of excluded goal states remain available. Grounded full reachable-product closure, independently reconstructed geometry/count/trie transitions, nonnegative rational potentials, terminal debt and a realizing path certify each exact count in the residual finite language. The pi coefficient remains fixed at wL*R*k/2. One optional source-bound residual round binds its original checked frontier, exact excluded words and generation ledger, then freshly checks binary64 bodies. The real joint consumer enables the round only under an explicit fitting budget before freezing the finite menu.",
         [], "Residual exact-count nominal optimum only, not original-language closure, full K-shortest ordering, all ties, simple paths, native cost lower bounds, physical uniqueness or continuous completeness. Excluded words are not declared physically infeasible; a native collision with another route cannot induce an unconditional edge or path cut. K<=32 and full joint budget B<=1024 remain distinct. Word/step/state/work/input/certificate/time budgets preserve UNKNOWN without partial closure. Binary64 duplicate or unresolved paths consume bounded attempts. Current source/frame/support authenticity and full native geometry, actual fitting count, selection, managed acceptance and fresh exported-file checking remain separate. Final callback input/certificate mutation guards prevent relabeling a different same-invocation problem; no atomic concurrent-memory or filesystem claim."),
        ("UNIFORM_TWO_SINK_PRESSURE_PORT_ENVELOPE_AND_NATIVE_ADAPTER", "1-10", [16069, 16077, 16118, 16135, 16139, 16203, 16836, 16853, 17130, 17158, 17615, 17681], ["ALG-PO1", "ALG-PO2", "ALG-PO7", "THM-PO7", "THM-PO8", "THM-PO12"],
         ["oma.optimization.two_sink_pressure.compile_two_sink_pressure", "oma.routing.network_pressure.partition_two_sink_tree", "oma.routing.network_pressure.derive_two_sink_pressure_model", "oma.routing.network_pressure.evaluate_pressure_network"], ["oma.optimization.two_sink_pressure.verify_two_sink_pressure", "oma.routing.network_checker.verify_network_candidate"], "tests/test_two_sink_pressure.py",
         "Bounded nonlinear port relation for exactly one tee and two forward outlets. Every parameter tuple in the complete rational Cartesian box has one unique interior split when independently checked adverse endpoint signs and a strict derivative lower bound hold. Independently reconstructed squared-flow, square-root and conserved-branch bounds enclose every such operating point; actual widths are reported. The native adapter independently reparses the full component/path partition, derives coefficient and elevation intervals from current native metric inputs, binds total-pressure boundary assumptions, and checks both minimum deliveries plus all physical port velocities. Tee total loss is referenced to inlet flow and its skeleton receives no additional Darcy charge.",
         [], "Fixed steady incompressible quadratic loss model only. P1/P2/beta/B1/B2 are positive throughout; A1/A2 are nonnegative. Caller-declared boundary control, loss/catalog applicability and conservative native metric enclosure premises remain external. The coefficient box may enclose correlated inputs without claiming physical independence. No general nonlinear/cyclic/multi-tee/reverse-flow solution, physical infeasibility, global route optimum or kernel acceptance authority. Coarse complete envelopes report unmet target width; hard work/bit/byte budgets or absent uniform regime yield UNKNOWN. Native geometry, source identity, managed acceptance and exported-file checks remain separate and mandatory."),
        ("EXACT_COUNT_FABRICATION_FRONTIER_AND_SOURCE_PROPOSALS", "oma-integration", [5522, 5523, 5536, 5537, 5544, 5545, 5548, 5549, 5568, 5569], ["ALG-RTR15", "ALG-RTR22", "ALG-RTR26", "ALG-RTR28", "ALG-RTR38"],
         ["oma.optimization.fabrication_frontier.compile_fabrication_frontier", "oma.routing.certified_fabrication.build_certified_fabrication_proposals", "oma.routing.proposals.project_proposals"], ["oma.optimization.fabrication_frontier.verify_fabrication_frontier", "oma.optimization.fabrication.verify_orthogonal_fabrication", "oma.routing.fitting_budget.check_joint_fitting_budget"], "tests/test_optimization_fabrication_frontier.py",
         "Bounded specialization of the source fabrication lift, column-cost and pricing-closure obligations. Product states add exact quarter-turn count k; each fixed k has constant pi coefficient wL*R*k/2, so nonnegative rational deferred costs admit exact Dijkstra. Independent grounded predecessor reachability, full outgoing closure, all rational edge/terminal inequalities and one realizing path certify every count 0..K. K is at most 32; graph walks may repeat vertices or visit the goal before returning. Actual source consumer binds full immutable joint budget B and cap min(B,32), authenticated source/frame coverage, objective and executable, then independently checks each binary64 fixed-fabrication path before proposing it.",
         [], "Exact nominal fixed-count optima only. No all-tie, simple-path, nonadjacent self-interference, continuous/native objective, full physical universe or acceptance claim. State/work/byte/time exhaustion remains UNKNOWN; default adapter limits are 24000 product states, 1000000 work units, 3 seconds or half the remaining time, and 8 output paths. Counts above 32 and output-limit alternatives remain unexamined. Fallback routes are not declared resource-feasible. Separate current IFC counting and finite checked-candidate master enforce the optional newly authored independent-elbow budget; no shared-tree/corridor resource is inferred."),
        ("SOURCE_AWARE_BOUNDED_GRID_ENRICHMENT", "oma-integration", [5522, 5523, 5524, 5525, 5546, 5547], ["ALG-RTR15", "ALG-RTR16", "ALG-RTR27"],
         ["oma.routing.fabrication_grid.enrich_fabrication_grid"], ["oma.routing.fabrication_grid.verify_fabrication_grid_enrichment"], "tests/test_fabrication_grid.py",
         "A bounded heuristic coordinate specialization, not source-prescribed CEGAR: retain every baseline coordinate; propose exact complete source-box face offsets and terminal first/two-trim thresholds; account every plane and budget omission. Independent equations, unique addition witnesses and baseline/product checks establish grid provenance only. Generic axis-balanced allocation has default cap10; application cap8 gives at most10775 structural states including pricing sink.",
         [], "No free-space, feasibility, ranking optimality, physical infeasibility or native acceptance claim. Source/frame/support authenticity is external, and positive search/body guards are not certified numerical error bounds. Every route still needs graph, binary64 fabrication and native checks. Actual Office evidence is historical-model-derived proposal generation with fresh complete native checks, not accepted project revision or continuous optimality."),
        ("FINITE_FABRICATION_GRAPH_COST_PRICING", "oma-integration", [5536, 5537, 5544, 5545, 5548, 5549, 5568, 5569], ["ALG-RTR22", "ALG-RTR26", "ALG-RTR28", "ALG-RTR38"],
         ["oma.optimization.fabrication_pricing.compile_fabrication_pricing"], ["oma.optimization.fabrication_pricing.verify_fabrication_pricing"], "tests/test_optimization_fabrication_pricing.py",
         "Fixed nonnegative exact length and per-quarter-bend objective on the complete declared finite fabrication graph. Deferred straight/arc charges and an explicit terminal sink make every edge nonnegative. Rational coefficient pairs a+b*pi use independently reconstructed alternating-series pi enclosures. A realizing path and total sparse capped potential independently prove finite graph optimality; every explicit state's outgoing edge is checked, and default-state edges are discharged by the nonnegative-cost theorem.",
         [], "A bounded pricing and CPU dual-edge component only, not full source node-dual/resource/branch-automaton/all-net closure. No continuous or native numeric objective lower bound, no physical infeasibility or acceptance transfer, no all-tie option preservation. State/work/arithmetic/precision exhaustion remains UNKNOWN. Source/frame/outer-support applicability is external. Actual IFC wall correspondence and five native pairs remain a separate numerical check."),
        ("BOUNDED_FABRICATION_LIFTED_GRID_SEARCH", "oma-integration", [4472, 4473, 4474, 4475, 4476, 4484, 5522, 5523, 1289, 1290], ["DEF-RTR39", "DEF-RTR40", "DEF-RTR41", "ALG-RTR15", "THM-SIR25"],
         ["oma.optimization.fabrication_search.compile_fabrication_search"], ["oma.optimization.fabrication_search.verify_fabrication_search"], "tests/test_optimization_fabrication_search.py",
         "Exact finite Cartesian route search carries incoming direction, straight-run origin and previous bend trim debt. Admitted straight continuations and quarter turns satisfy exact remaining-straight, full primitive envelope, allowed-box and complete outer-box separation predicates. Independent transition reconstruction checks a source-to-goal state path or a source-containing goal-free successor-closed finite set; producer geometry bound construction is not reused.",
         [], "Fixed round size and a declared conservative grid only; closed-set proof means no path in that graph, never physical universe infeasibility. No manufacturer/support/slope/service/homotopy closure, nonadjacent self-interference or length optimum claim. Source cover/frame authenticity belongs to the physical adapter. Work/state/callback budgets stop with UNKNOWN or propagated interruption. Actual native metre/millimetre wall tests remain separate from exact nominal proofs and candidate acceptance."),
        ("EXACT_ORTHOGONAL_FABRICATION_TRANSITIONS", "oma-integration", [4472, 4473, 4474, 4475, 4476, 4484, 5522, 5523, 1289, 1290], ["DEF-RTR39", "DEF-RTR40", "DEF-RTR41", "ALG-RTR15", "THM-SIR25"],
         ["oma.optimization.fabrication.compile_orthogonal_fabrication"], ["oma.optimization.fabrication.verify_orthogonal_fabrication"], "tests/test_optimization_fabrication.py",
         "Exact fixed axis-aligned constant-round polyline realization with tangent quarter bends, both-end straight trim debts, strict positive remaining-straight requirements, fixed size identities and full insulated body bounds. Independent attained support extrema and tangent identities check the complete component/transition denominator; exact outer-box separation is sufficient and inconclusive overlap remains UNKNOWN.",
         [], "A bounded component of the source fabrication-size lift only: no complete graph/homotopy, manufacturer catalog, support/slope/service or self-interference closure. Oversized input is an uninspected count/context-bound UNKNOWN, not a geometry-root claim. Exact model rejection is not automatic pruning authority over the numerical IFC writer. Retained native correspondence and actual strict-threshold counterexample are explicitly numerical and do not grant acceptance."),
        ("SOURCE_BOUND_IFC_OUTER_CELL_PROPOSALS", "oma-integration", [4293, 4367, 5502, 5504, 5508], ["DEF-RTR12", "DEF-RTR24", "ALG-RTR5", "ALG-RTR6", "ALG-RTR8"],
         ["oma.routing.certified_cells.build_certified_cell_proposals"], ["oma.routing.certified_cells.verify_cell_coverage", "oma.optimization.route_cells.verify_route_cells"], "tests/test_certified_cells.py",
         "Fresh immutable source hashes, complete physical-element/assembly denominator, audited common frames and complete native or exact-source outer support. Independent affine corner containment, exact out-of-zone separating planes and grouped-cover checks feed a bounded cell certificate; each final binary64 capsule proposal is independently rechecked.",
         [], "Native outer bounds and local BRep cache retain explicit numerical/provenance assumptions. Inner occupancy is empty, edited-host scenarios are not applicable, no physical infeasibility or fabricated-elbow coverage is transferred, and every route still needs full independent materialized checks. Separate adapter test artifact and actual IFC benchmark retain exact execution scope."),
        ("CERTIFIED_TRANSLATIONAL_INNER_OUTER_ROUTE_CELLS", "oma-integration", [4293, 4367, 4369, 4432], ["DEF-RTR12", "DEF-RTR24", "ALG-RTR5", "ALG-RTR6", "ALG-RTR7", "ALG-RTR8", "ALG-RTR9", "ALG-RTR10"],
         ["oma.optimization.route_cells.compile_route_cells"], ["oma.optimization.route_cells.verify_route_cells", "oma.optimization.route_cells.verify_route_cell_refinement"], "tests/test_optimization_route_cells.py",
         "Exact finite Cartesian cover of the full allowed-box domain eroded by a translating ball. Complete obstacle outer boxes prove free cells by checked separating planes; occupied inner boxes prove blocked cells by convex corner coverage. All MIXED cells remain outer. Independent cell denominator, 26-neighbour path/cut, full capsule embedding, length interval and fixed-model refinement checks establish bounded-model inner/outer inclusions.",
         [], "Continuous-path conclusion only for the declared translating-ball geometry under authenticated obstacle sandwich and frame assumptions supplied by an adapter. No fabricated-pipe impossibility without a necessary body model, no native IFC equality, orientation/fitting/service physics or continuous optimum. Synthetic 125-cell slab example proves no path before an exact model opening and a three-metre path afterward; fifty tests include thirty analytic random wall oracles."),
        ("EXACT_RECTILINEAR_AUTHORIZED_OPENING_SUPPORT", "oma-integration", [1647, 1653], ["ALG-SIR26", "DEF-SIR25", "DEF-SIR34"],
         ["oma.optimization.rectilinear_opening.compile_rectilinear_opening"], ["oma.optimization.rectilinear_opening.verify_rectilinear_opening"], "tests/test_optimization_rectilinear_opening.py",
         "Corrected explicitly bounded materialization model: one rational local host box and one strictly interior transverse footprint extending beyond both thickness faces. Four closed cells exactly represent the regularized difference. Independent endpoint-arrangement checker verifies complete set coverage including boundaries, disjoint interiors and exact volumes, with context/source/host/frame/authorization roots bound.",
         [], "Exact supplied local rational geometry only. Declared identities are not authenticated authority, frame validity, source geometry truth, native exported IFC equality, structural or fire approval. Native adapter and actual real-host benchmark remain separate. Forty-eight focused tests include shifted equal-volume attacks and fifty randomized independent voxel ground truths."),
        ("ACTUAL_FROZEN_PHYSICAL_MENU_PROJECTION", "1-10", [6005, 6031, 8179, 8841, 19214, 20012], ["ALG-MN0", "ALG-MN1", "ALG-DS1", "ALG-DS3", "ALG-CS1", "ALG-CS6"],
         ["oma.optimization.physical_menu.compile_physical_menu"], ["oma.optimization.physical_menu.verify_physical_menu"], "tests/test_optimization_physical_menu.py",
         "Complete finite ordered menu with immutable choice definitions, context and named report projection. Every assignment is retained; unexamined assignments are UNKNOWN. Exact prefix separator and full assignment replacement-action bisimulation preserve all higher-order interactions, original labels and report references. Caller authenticates physical report applicability.",
         [], "Projection equivalence only, with no acceptance authority or native PASS reuse. Historical actual Office reports produce one FAIL and one PASS assignment; withholding the PASS yields FAIL plus UNKNOWN. Different historical checker builds remain explicit in that benchmark projection. Current-build application assembly is separately implemented in routing/physical_archive.py and checked by root-owned integration tests; this kernel does not authenticate arbitrary supplied roots."),
        ("ORIGINAL_FINITE_CAUSAL_BISIMULATION", "1-10", [18648, 18747, 19214, 19264, 19974, 20012], ["DEF-CS5", "LEM-CS3", "THM-CS3", "ALG-CS1", "THM-CS21", "ALG-CS6"],
         ["oma.optimization.bisimulation.compile_bisimulation"], ["oma.optimization.bisimulation.verify_bisimulation"], "tests/test_optimization_bisimulation.py",
         "Complete finite typed state/action relations and direct observations under immutable context. Exact successor-block-set refinement gives the coarsest strong bisimulation; missing rows are invalid while explicit empty rows mean disabled actions. Independent verifier checks every relation row and typed acyclic modal characteristic formulas without repeating refinement.",
         [], "Exact supplied finite relation model only; no physical transition discovery, probability, weak bisimulation or general CSSP release. Modal witnesses retain branching distinctions invisible to linear traces. Eighty random systems match an independent greatest-pair-relation oracle. Full source ports, rewrite, evidence, action footprints and physical applicability remain separate adapter obligations."),
        ("ORIGINAL_EXACT_LINEAR_PORTS", "1-10", [15903, 16117], ["THM-PO6", "THM-PO14", "THM-PO31", "ALG-PO1", "ALG-PO7"],
         ["oma.optimization.ports.compile_linear_port", "oma.optimization.ports.compile_kron_network", "oma.optimization.ports.reconstruct_linear_port", "oma.optimization.ports.certify_linear_residual"], ["oma.optimization.ports.verify_linear_port", "oma.optimization.ports.verify_kron_network"], "tests/test_optimization_ports.py",
         "Explicit finite rational linear model, ordered boundary/interior coordinates, fixed interior loads, model/unit/regime/domain/source bindings. Exact Schur elimination when invertible; certified invertible row operations retain a full projected affine relation when singular. Independent checker uses matrix identities and original edge-incidence energy identity, not repeated elimination.",
         [], "Exact supplied linear mathematical network only. Synthetic thirteen-motif chain reduces forty coordinates to two boundary coordinates with stiffness 2/65, matching an independent series-compliance oracle. Residual bounds use checked inverse norms and component products; no conditioning-free or physical discrepancy claim. Nonlinear flow, dynamic/hybrid physics, general PDE envelopes and model applicability remain separate."),
        ("ORIGINAL_BOOLEAN_SYMBOLIC_QUOTIENT", "1-10", [10006, 12808], ["ALG-AB1", "ALG-AB4", "THM-AB10", "THM-AB22", "DEF-AB35"],
         ["oma.optimization.symbolic.compile_symbolic"], ["oma.optimization.symbolic.verify_symbolic"], "tests/test_optimization_symbolic.py",
         "Explicit Boolean circuit DAG, 1 to 128 named variables, exact domain, complete disjoint terminal fibers and simultaneous total context maps under an immutable root. A reduced ordered Boolean diagram kernel supplies exact set operations and preimages; context closure and final partition are checked without carrier enumeration.",
         ["OMA-MATH-A030", "OMA-MATH-A031"], "Corrected synthetic 40-module XOR/cardinality model represents 2**40 assignments in five exact blocks, three accepted splits and ten replayed distinguishing contexts. Actual full diagram contains 31,569 nodes. Independent checker verifies diagram structure, all universal set obligations, exact block counts, representatives and concrete context replay. No real-building symbolic completeness, unrestricted SAT/SMT efficiency or physical append semantics are claimed."),
        ("ORIGINAL_FINITE_SEPARATOR_DP", "1-10", [7423, 10166], ["ALG-DS1", "ALG-DS3", "THM-DS19.1", "THM-DS20.1", "THM-DS13A"],
         ["oma.optimization.separator.compile_separator", "oma.optimization.separator.reconstruct_separator_choices", "oma.optimization.separator.substitute_labeled_menu"], ["oma.optimization.separator.verify_separator"], "tests/test_optimization_separator.py",
         "Supplied tree, complete finite regional carriers and local choice merge tables, full terminal profiles, explicit immutable model/theory scope. FDQA generates all parent/sibling contexts. Counted quotient recurrence retains every labeled source choice and independently replays original-table witnesses.",
         ["OMA-MATH-A025", "OMA-MATH-A026", "OMA-MATH-A027"], "Synthetic projected hotel floor: 1,358,954,496 labeled assignments, 650 root messages and 1,224 stored messages including root, independently checked complete recurrence and small exhaustive ground truth. All unknown/failure states remain represented. Root memory and exact label multiplicity are explicit. Does not infer missing interactions, discover an optimal decomposition, prove nonempty physical fibers or eliminate provisional table construction."),
        ("ORIGINAL_TYPED_FDQA_COMPILER", "1-10", [4767, 7422], ["ALG-MN0", "ALG-MN1", "THM-MN14", "DEF-MN21", "DEF-MN22"],
         ["oma.optimization.fdqa.compile_fdqa", "oma.optimization.fdqa.evaluate_compiled_term"], ["oma.optimization.fdqa.verify_fdqa"], "tests/test_optimization_fdqa.py",
         "Complete explicit typed operation tables and canonically serialized complete terminal reports under an immutable experiment/model/scenario/evidence/intent scope. Generate every primitive argument context, compute the stable coarsest congruence, ground source representatives and produce distinct-block context witnesses.",
         [], "Independent checker verifies original-table congruence, primitive coverage, grounded representative DAG, uniform outputs and every distinguishing context. Original synthetic hotel table reproduces 768 typed states to 294 blocks in two strict rounds with 14,259 verified distinguishers. No model-adequacy or large-building compression claim. General source-language extraction and physical application adapter remain separate."),
        ("FINITE_CONTEXTUAL_QUOTIENT", "ananke-canonical", [17949, 18192], ["ALG-AB5", "DEF-AB7"],
         ["oma.optimization.finite.contextual_quotient"], ["oma.optimization.finite.verify_contextual_quotient"], "tests/test_optimization_finite.py",
         "Complete explicit finite state-by-experiment table, typed observations, immutable context. Partition by equality under every experiment; independently replay all state pairs and separating observations.",
         ["OMA-MATH-A006"], "Finite table equivalence only; replacing the active experiment family invalidates the quotient. Does not infer applicability of unmodeled physical experiments."),
        ("FINITE_ARCHIVE_WITH_UNKNOWNS", "ananke-canonical", [18178, 18185], ["THM-DS21.1"],
         ["oma.optimization.finite.finite_archive_optimum"], [], "tests/test_optimization_finite.py",
         "Complete declared candidate list plus PASS/FAIL/UNKNOWN outcomes, exact accepted costs and supplied valid objective floors. Every unresolved potentially improving candidate blocks optimum.",
         ["OMA-MATH-A007"], "Finite table conclusion relative to supplied domain outcomes and lower-bound evidence; no physical proof follows from an evidence-root string. Accepted-subset and complete-domain claims are distinct."),
        ("FINITE_CHANCE_AND_RISK", "oma-integration", [19531, 19686], ["ALG-DYN16", "ALG-DYN17", "ALG-DYN18", "ALG-DYN19"],
         ["oma.optimization.finite.finite_chance_constraint", "oma.optimization.finite.finite_risk"], [], "tests/test_optimization_finite.py",
         "Exact finite joint probability law, nonnegative probabilities summing to one, explicit event truth including UNKNOWN, rational losses and confidence alpha in [0,1). Bound violation probability and enumerate all CVaR breakpoints.",
         [], "Expectation, worst listed scenario and finite-law CVaR only. Samples do not certify universal uncertainty coverage, independence, or applicability of supplied probability law."),
        ("FINITE_QUANTITY_TRANSPORT", "oma-integration", [3816, 3825], ["ADD-SIR2.2"],
         ["oma.optimization.finite.check_quantity_transport"], [], "tests/test_optimization_finite.py",
         "Explicit source/target quantities and nonnegative finite allocation edges, equal units, complete identities. Exact outgoing and incoming marginal equalities establish conservative split/merge quantity transport.",
         [], "Quantity conservation only. No nonlinear physics, geometry, identity/functorial transport, or inherited certificate is established by these marginals."),
        ("FINITE_NONANTICIPATIVE_POLICY", "oma-integration", [19531, 19686], ["ALG-DYN8-19", "ALG-DYN60"],
         ["oma.optimization.policy.solve_finite_policy", "oma.optimization.finite.check_nonanticipativity"], ["oma.optimization.policy.verify_finite_policy_result"], "tests/test_optimization_policy.py",
         "Finite same-horizon scenarios, explicit pre-action histories, one action domain per history node, complete or UNKNOWN leaf outcomes. Enumerate common-history decisions and independently replay exact expected or worst-listed cost.",
         ["OMA-MATH-A007"], "Finite policy class and supplied leaf outcomes only; domain checkers must establish dynamic transitions and physical feasibility. Missing leaves, checker budgets and omitted uncertainty sets remain explicit."),
        ("FINITE_CANDIDATE_ROOTED_CODESIGN", "oma-integration", [14815, 14948], ["ALG-JCD9", "ALG-JCD17", "ALG-JCD18", "ALG-JCD39", "ALG-JCD43", "ALG-JCD44", "ADD-RTR3.2"],
         ["oma.optimization.codesign.solve_finite_codesign"], ["oma.optimization.codesign.verify_finite_codesign_result"], "tests/test_optimization_codesign.py",
         "Finite explicit strategic domains and materialized cases; fixed protected assignment tokens; each route master bound to its own design root; shared resource and hyperedge constraints; compatible capital/routing objective units supplied by adapter.",
         ["OMA-MATH-A002", "OMA-MATH-A007"], "Optimum only over complete declared finite assignments/materializations/routes with disposed or nonimproving unresolved alternatives. BIM sovereignty/materialization and physical route validity require upstream independent checks. No universal Benders cut or continuous design completeness theorem."),
        ("SOURCE_PLANAR_IFC_ENCLOSURE", "oma-integration", [797, 853], ["DEF-SIR25", "DEF-SIR34", "DEF-SIR36", "THM-RTR6", "THM-RTR18"],
         ["oma.ifc.enclosure.ExactIfcEncloser.enclose_product"], [], "tests/test_ifc_enclosure.py",
         "Complete selected Body item traversal from immutable raw STEP rationals; supported planar faces, validated positive linear extrusions, and bounded regularized Booleans have closed outer enclosures. Unit and placement/mapping transforms use outward rational interval arithmetic.",
         [], "Enclosure relation only for declared supported IFC subset and local engineering frame; no solid validity or route verdict. Explicit opt-in extends claim to all vertex-hull completions of source faces while retaining nonplanarity evidence. Unknown siblings, map origins and unsupported classes block. Full architectural DigitalHub probe: 705 represented elements checked, eight records without representations UNKNOWN."),
        ("FINITE_MASTER", "oma-integration", [4688, 4880], ["DEF-RTR62", "DEF-RTR68", "THM-RTR67-86"],
         ["oma.optimization.master.solve_master"], ["oma.optimization.checker.verify_master_result"], "tests/test_optimization_master.py",
         "Finite serialized route columns, one per required net; rational costs, nonnegative rational resource usage, explicit higher-order conflict semantics. Geometry and physical validity are separate obligations.",
         ["OMA-MATH-A002", "OMA-MATH-A007"], "Exhaustive finite optimum or finite infeasibility; budget stops retain incumbent and UNKNOWN. No unrestricted continuous/global building optimality. Upstream unresolved physical candidates cannot be dropped to claim optimum over a larger domain."),
        ("FINITE_PRICING", "oma-integration", [4728, 4802], ["DEF-RTR70-75", "THM-RTR69-76"],
         ["oma.optimization.master.generate_columns", "oma.optimization.master.price_columns"], ["oma.optimization.checker.verify_dual"], "tests/test_optimization_master.py",
         "HiGHS proposes restricted LP multipliers; exact rational pricing covers every serialized column and repairs selection duals. Every row sign and conflict RHS is independently replayed.",
         ["OMA-MATH-A002"], "Checked weak-duality bound over explicit column universe only. Numeric LP status is not a certificate; missing continuous route universe remains unproved."),
        ("EXACT_PRIMITIVES", "oma-integration", [4369, 4408], ["DEF-RTR25-26", "THM-RTR17-25"],
         ["oma.exact.orient2d", "oma.exact.orient3d", "oma.exact.segment_triangle_intersection", "oma.exact.segment_box_distance_squared", "oma.exact.capsule_box_clearance"], [], "tests/test_exact.py",
         "Finite 2D/3D rational coordinates; exact arbitrary-precision determinants, degenerate/coplanar predicates and globally minimized piecewise quadratic capsule/AABB distance.",
         [], "Exact predicates for represented primitives, independently analytically tested. Does not certify IFC approximation error, general BRep validity or missing geometry."),
        ("ALLOWED_REGION", "oma-integration", [954, 1002], ["DEF-SIR60-70"],
         ["oma.exact.capsule_within_box"], [], "tests/test_exact.py",
         "Entire capsule must fit allowed AABB, including its outer radius. Axis margins implement erosion of allowed domain by physical body.",
         ["OMA-MATH-A004"], "Exact capsule/AABB containment; general allowed polyhedra and rectangular rotating duct envelopes need additional implementations."),
        ("FLUID_FIBERS", "oma-integration", [4558, 4609], ["DEF-RTR52-56", "THM-RTR53-66"],
         ["oma.optimization.physical.evaluate_fluid_path", "oma.optimization.physical.select_fluid_catalog"], [], "tests/test_optimization_physical.py",
         "SI fixed-section constant-flow path with supplied Darcy friction enclosure, density, fitting losses, head, velocity and efficiency. Rational interval calculation; finite catalog plus separate envelope callback.",
         [], "Partial fixed-path physical evaluation. Branch pressure networks, friction applicability, fittings/supports/access and missing inputs remain separate. Analytic tests are not an independent whole-building simulator."),
        ("ELECTRICAL_FIBER", "oma-integration", [4611, 4629], ["DEF-RTR57", "THM-RTR63"],
         ["oma.optimization.physical.evaluate_electrical_path"], [], "tests/test_optimization_physical.py",
         "Balanced three-phase supplied resistance/reactance, current, power factor, ampacity, tray fill and voltage-drop limit. SI with exact rational square-root enclosure.",
         [], "Partial declared electrical approximation; no fault/harmonic/protection or code-compliance claim."),
        ("CONSERVATION_AND_TRUNKS", "oma-integration", [3786, 3826], ["ADD-SIR2.1", "ADD-SIR2.2", "DEF-RTR45"],
         ["oma.optimization.physical.aggregate_tree_flows", "oma.optimization.physical.check_conservation"], [], "tests/test_optimization_physical.py",
         "Finite directed arborescence with exact terminal demands; aggregate branch demands upstream. Incidence head +1, tail -1; Bf=storage+loss-injection-conversion.",
         ["OMA-MATH-A003"], "Exact conservation and arborescence topology. No geometric fitting correctness inferred from graph connectivity."),
        ("GRAVITY_FIBER", "oma-integration", [4631, 4646], ["DEF-RTR58", "THM-RTR64"],
         ["oma.optimization.physical.solve_gravity_elevations"], ["oma.optimization.physical.verify_gravity_result"], "tests/test_optimization_physical.py",
         "Finite fixed directed topology, rational positive horizontal lengths, slope intervals and complete node elevation bounds. Exact Bellman-Ford difference constraints.",
         [], "Feasible rational elevations or checked negative-cycle certificate tied to original constraints; vertical drops, fittings, cleanouts and physical body require separate checks."),
        ("INCREMENTAL_DEPENDENCIES", "oma-integration", [23806, 23861], ["DEF-CMP218-243", "THM-CMP79-85"],
         ["oma.dependencies.invalidation_closure", "oma.dependencies.DependencyEngine.build", "oma.dependencies.DependencyEngine.compare_with_cold"], [], "tests/test_dependencies.py",
         "Complete declared graph, deterministic versioned functions, guarded declared reads, fully typed source values and cache context including objective/theory/experiment/checker/environment/tool/scope.",
         ["OMA-MATH-A005"], "Conservative graph-relative reuse and equality to cold computation. Undeclared reads through interface fail. Arbitrary hidden Python globals require explicit versioned dependencies."),
        ("FINITE_CYCLE_CLOSURE", "oma-integration", [24199, 24204], ["THM-CMP31-33", "DEF-CMP110-116"],
         ["oma.dependencies.DependencyEngine.build"], ["oma.dependencies.verify_closure_certificate"], "tests/test_dependencies.py",
         "Each SCC has explicit finite chain domains. Enumerate full product-state operator, check every covering monotonicity relation, iterate from bottom. Budget and nonmonotone cases remain UNKNOWN.",
         [], "Least fixed point of serialized finite operator table only. No general nonlinear contraction solver or proof for arbitrary infinite cycles."),
        ("CORE_MINIMALITY", "oma-integration", [4882, 4891], ["DEF-RTR82", "THM-RTR96"],
         ["oma.optimization.certificates.classify_core_minimality"], [], "tests/test_optimization_certificates.py",
         "Finite checked-infeasible constraint core; each deletion must carry independently checked feasible evidence. UNKNOWN deletion is not proof of minimality.",
         ["OMA-MATH-A001"], "Logical evidence classification only; underlying deletion certificates checked by relevant solver/geometry checker."),
        ("FARKAS_ARITHMETIC", "oma-integration", [4833, 4852], ["DEF-RTR78-79", "THM-RTR89-92"],
         ["oma.optimization.certificates.verify_farkas"], [], "tests/test_optimization_certificates.py",
         "Exact rational finite matrix Ax>=b,x>=0 and ray y>=0. Check A^Ty<=0 and b^Ty>0 with strict exact comparisons.",
         [], "Infeasibility of supplied finite linear system only; full routing use additionally needs complete domain and Farkas pricing closure."),
    ]
    register = []
    for identifier, document, locations, objects, implementations, checkers, tests, interpretation, amendments, limitation in entries:
        callables = []
        for path in implementations + checkers:
            chunks = path.split(".")
            resolved = None
            for split in range(len(chunks) - 1, 0, -1):
                try:
                    resolved = importlib.import_module(".".join(chunks[:split]))
                except ModuleNotFoundError:
                    continue
                for attribute in chunks[split:]:
                    resolved = getattr(resolved, attribute)
                break
            callables.append({"path": path, "callable": callable(resolved)})
        register.append({"obligation": identifier, "source": {"document": document, "sha256": identities[document],
                         "paragraphs": locations, "objects": objects}, "interpretation_and_assumptions": interpretation,
                         "implementations": implementations, "independent_checkers": checkers,
                         "callable_probe": callables, "automated_tests": [tests],
                         "real_model_benchmark": {"status": "NOT_RUN_BY_MATH_AGENT", "evidence": None},
                         "status": "IMPLEMENTED_SCOPED_UNIT_TESTED", "amendments": amendments,
                         "certificate_and_limitations": limitation,
                         "cache_invalidation": ["source-state", "geometry", "envelope", "net-obligations", "catalog", "rules", "objective", "scenarios", "theory", "checker", "solver-version"]})
    pending = [
        "Retain original P7 and initial P26 source-body availability gaps; complete supplied-content review does not recover missing text or prove reconstructed-body equivalence",
        "General 3D solid/mesh uncertainty and complete obstacle-accounting closure",
        "Certified inner graph with continuous fitting/body transitions",
        "Complete outer abstraction and adaptive CEGAR geometry proofs",
        "Complete 3D homotopy presentations and fabrication/size lifts",
        "Multi-terminal topology pricing with physical fitting/junction validity",
        "General physical pressure/flow and coupled junction applicability beyond the declared positive-K passive graph and two-sink models, supports, penetrations and access fibers",
        "Full finite route universe closure or a continuous-completeness theorem",
        "Nested topology-native branch-and-price proof tree",
        "Universally scoped JCD Benders cuts and joint strategic rewrite search",
        "Continuous/nonlinear dynamic models and universal adversarial closure beyond implemented finite nonanticipative policy kernel",
        "Package composition and final release premise closure across complete corpus",
    ]
    test_path = ROOT / "evidence/math/implemented-obligation-tests.xml"
    suite = ET.parse(test_path).getroot().find("testsuite") if test_path.exists() else None
    coverage = json.loads((ROOT / "evidence/math/combined_review_coverage.json").read_text(encoding="utf-8"))
    for row in register:
        if row["obligation"] == "UNIFORM_POSITIVE_BOX_COUPLED_TREE_PRESSURE_CERTIFICATE":
            row["documentation"] = "docs/math/coupled-tree-pressure.md"
            row["evidence"] = "evidence/math/coupled-tree-pressure/latest.json"
            row["full_source_algorithms_implemented"] = False
            row["real_model_benchmark"] = {"status": "DECLARED_POLYNOMIAL_MODEL_AND_INDEPENDENT_MATRIX_AUDIT_PASS",
                "evidence": "evidence/math/coupled-tree-pressure/evidence/independent-kernel-review/68137ae750cb4760b0b50448d29748be/result.json",
                "scope": "124 kernel tests, an independent exact manufactured-box proof and 4096 supplementary numerical parameter corners, 24 independently reconstructed models/96 exact parameter-root instances and 293 rejected attacks. Combined 427-case compatibility passes. No actual native unequal-tree adapter or service decision is claimed by this module."}
            row["consumer_scope"] = {"native_adapter": False, "global_equilibrium_exclusion": False,
                "unique_root_inside_supplied_box_for_each_parameter_tuple": True,
                "default_leaves": 16, "default_terms": 128, "default_matrix_entries": 256}
        if row["obligation"] == "GROUNDED_PASSIVE_RESIDUAL_TO_SOLUTION_ERROR_BOUND":
            row["documentation"] = "docs/math/passive-residual-bound.md"
            row["evidence"] = "evidence/math/passive-residual-bound/latest.json"
            row["full_source_algorithms_implemented"] = False
            row["real_model_benchmark"] = {"status": "EXACT_DECLARED_MODEL_AND_INDEPENDENT_IMPLEMENTATION_REVIEW_PASS",
                "evidence": "evidence/math/passive-residual-bound/independent-implementation-review/e7ac3e79600843fdb8a4ba3fbc7debf8/result.json",
                "scope": "86 focused residual cases, 24 independently manufactured exact graph cases, 243 rejected attacks and four budget cases. All 303 combined residual/passive/native-tree/control compatibility tests pass. This kernel does not establish native applicability or add physical acceptance authority."}
            row["consumer_scope"] = {"native_geometry_adapter": False, "physical_discrepancy_bound": False,
                "same_actual_boundary_tuple_required": True, "reference_flow_is_parameterized": True,
                "default_nodes": 64, "default_edges": 128, "default_path_steps": 4096}
        if row["obligation"] == "NATIVE_COMMON_OUTLET_PASSIVE_TREE_MODEL_AND_SERVICE_ENVELOPE":
            row["related_sources"] = [{"document": "1-10", "sha256": identities["1-10"],
                "paragraphs": [16069, 16077, 16836, 16853], "objects": ["ALG-PO1", "ALG-PO2", "ALG-PO7"]}]
            row["automated_tests"].extend(["tests/test_passive_tree_integration.py", "tests/test_three_sink_native_geometry.py", "tests/test_worker_control_polling.py"])
            row["documentation"] = "docs/math/passive-native-tree.md"
            row["evidence"] = "evidence/math/passive-native-tree/latest.json"
            row["full_source_algorithms_implemented"] = False
            row["real_model_benchmark"] = {"status": "NATIVE_THREE_SINK_ACCEPT_AND_FRESH_EXPORT_CHECK_PASS",
                "evidence": "evidence/math/passive-native-tree/native-workflows/",
                "scope": "Seven actual components, two tees, sixteen ports, twenty-one unique component pairs, all three exact minimum deliveries and seventeen continuity identities. Complete service is independently checked; physical model applicability remains declared."}
            row["real_model_benchmark"]["office_campaign"] = {
                "status": "ONE_DECLARED_COMMON_TEE_MISSION_ACCEPTED_AND_FRESH_EXPORT_RECHECKED",
                "evidence": "evidence/benchmarks/passive-pressure/office/f64e250b57bb480f9dfe352892b61b3f/README.md",
                "source_checkpoint": "4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef",
                "scope": "58.5-second workflow covers all 5621 component/obstacle pairs, 21 unique component pairs, 16 ports, three deliveries and 17 continuity identities. Canonical parsed original entities are preserved; raw STEP formatting is not byte-identical. One hypothetical service model and one alternative; no improvement or unrestricted topology claim."}
        if row["obligation"] == "GROUNDED_PASSIVE_QUADRATIC_NETWORK_COMPARISON_ENVELOPES":
            row["related_sources"] = [{"document": "oma-integration", "sha256": identities["oma-integration"],
                "paragraphs": [4592, 4609, 5530, 5531, 5532, 5533], "objects": ["DEF-RTR56", "ALG-RTR19", "ALG-RTR20"]}]
            row["full_source_algorithms_implemented"] = False
            row["documentation"] = "docs/math/passive-pressure.md"
            row["evidence"] = "evidence/math/passive-pressure/latest.json"
            row["real_model_benchmark"] = {"status": "SEPARATE_EXPLICIT_COMMON_TEE_NATIVE_ADAPTER_AVAILABLE",
                "evidence": "evidence/math/passive-pressure/independent-implementation-review/result.json",
                "scope": "119 exact declared kernel cases, 32 independently manufactured rational equilibria, 210 coherent/inventory/callback attacks and five budget cases. Retained finite parameter references supplement the exact comparison proof; they do not establish physical model applicability."}
            row["consumer_scope"] = {"native_graph_adapter": False, "existing_native_tee_missions_reinterpreted": False,
                "kernel_proof_grants_physical_acceptance": False, "default_nodes": 64, "default_edges": 128,
                "signed_zero_and_reversed_flow": True, "positive_K_required_throughout_parameter_box": True,
                "every_connected_component_grounded": True, "individual_boundary_directions_assumed": False}
        if row["obligation"] == "RESIDUAL_WHOLE_WORD_FABRICATION_FRONTIER_AND_JOINT_PROPOSALS":
            row["automated_tests"].extend(["tests/test_certified_fabrication_residual.py", "tests/test_joint_residual_fabrication.py"])
            row["full_source_algorithms_implemented"] = False
            row["documentation"] = "docs/math/fabrication-residual-frontier.md"
            row["real_model_benchmark"] = {"status": "ANALYTIC_IFC_JOINT_SELECTION_ACCEPTANCE_EXPORT_RECHECK_PASS",
                "evidence": "evidence/math/fabrication-residual/latest.json",
                "scope": "Frozen synthetic wall plus separately declared competing route, with no solver/checker stubs. Cheaper original exact-count option has actual positive native common volume; a costlier residual option of the same two-fitting count is selected, accepted at revision 2, exported as actual IFC and independently rechecked. Both complete checks cover 5+1 source pairs and 5 cross-route pairs. This is analytic IFC integration, not a real Office benchmark or whole-building release."}
            row["real_model_benchmark"]["office_campaign"] = {"status": "UNCHANGED_MISSION_RESIDUAL_TIE_ACCEPTED_AND_EXPORT_RECHECKED",
                "evidence": "evidence/benchmarks/residual-fitting/office/310e9ac661714f8e91fcf67d91409415/README.md",
                "source_checkpoint": "1abe9a077844a184ec17e1c8a0a390aa4bf33d05dd302a6eefff7d770a0ff719",
                "scope": "Seven attempted candidates across frozen B2/B0 cases. B2 normally selects a distinct residual route tied with the original frontier at 3.2964797960769348 m and two fittings, accepts and freshly checks export against 4818 source, ten self and five cross-route pairs. B0 has no checked incumbent; no length improvement, physical infeasibility, continuous optimum or hydraulic adequacy claim."}
            row["consumer_scope"] = {"mission_field": "JointRoutingScenario.max_new_fittings", "absent_budget_activates_residual": False,
                "residual_rounds": 1, "default_phase_seconds": 3, "default_maximum_outputs": 8,
                "represented_count_maximum": 32, "declared_joint_budget_maximum": 1024,
                "excluded_word_semantics": "ALREADY_GENERATED_COMPLETE_GRAPH_WORDS_ONLY",
                "independent_source_frame_coverage_and_binary64_checks": True,
                "native_rejection_promoted_to_unconditional_infeasibility": False,
                "kernel_proof_grants_physical_acceptance": False,
                "physical_complete_cartesian_or_continuous_universe": False}
        if row["obligation"] == "UNIFORM_TWO_SINK_PRESSURE_PORT_ENVELOPE_AND_NATIVE_ADAPTER":
            row["related_sources"] = [{"document": "oma-integration", "sha256": identities["oma-integration"],
                "paragraphs": [4592, 4609, 5530, 5531, 5532, 5533], "objects": ["DEF-RTR56", "ALG-RTR19", "ALG-RTR20"]}]
            row["automated_tests"].extend(["tests/test_network_pressure.py", "tests/test_network_pressure_integration.py", "tests/test_network_pressure_native_section.py", "tests/test_physical_report_admission.py"])
            row["full_source_algorithms_implemented"] = False
            row["documentation"] = "docs/math/two-sink-pressure.md"
            row["real_model_benchmark"] = {"status": "STAGED_ANALYTIC_NATIVE_MANAGED_ACCEPTANCE_AND_EXPORT; REAL_OFFICE_NOT_RUN",
                "evidence": "evidence/math/two-sink-pressure/latest.json",
                "scope": "Kernel, native component-area correction and report-admission checkpoints are separately identified. Real Office pressure mission b44b3123cdb641709b2aa32ae5bd526c selects and accepts the direct tee layout, then checks the exported IFC against all 3212 component/source pairs. The offset layout passes all6424 native pairs but fails minimum branch delivery. Boundaries are frozen hypothetical inputs, not actual building operating data; no general topology or whole-building claim.",
                "office_evidence": "evidence/benchmarks/pressure-driven/office/b44b3123cdb641709b2aa32ae5bd526c/result.json"}
            row["independent_review"] = "evidence/math/two-sink-pressure/independent-review/corrected-result.json"
            row["native_dimensional_applicability_review"] = "CORRECTED_SCOPED_ADAPTER: independently parsed per-component outer-radius intervals, with explicit native numerical uncertainty, minus declared insulation define ideal bore intervals. Dimensionless reference-to-component diameter fourth-power factors and each component's area are used. Native wall/bore measurement, arbitrary reducers and catalog applicability remain unproved external premises. The original nominal-area false PASS and corrected UNKNOWN replay are retained in the portable evidence index."
            row["consumer_scope"] = {"mission_field": "SharedNetworkScenario.pressure_driven", "default": None,
                "pressure_convention": "TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION",
                "network_domain": "ONE_TEE_TWO_FORWARD_OUTLETS_COMPLETE_COMPONENT_PARTITION",
                "existing_fixed_flow_request_hashes_preserved": True,
                "static_budget_or_fixed_flow_contract_coexistence": False,
                "native_metric_enclosure_truth": "EXPLICIT_NUMERICAL_APPLICABILITY_PREMISE",
                "kernel_proof_grants_physical_acceptance": False,
                "required_independent_check": "network-pressure-operating-point",
                "real_office_benchmark": "FROZEN_HYPOTHETICAL_PRESSURE_MISSION_NATIVE_ACCEPT_EXPORT_RECHECK_PASS",
                "ideal_bore_interpretation": "NATIVE_OUTER_ENVELOPE_MINUS_DECLARED_INSULATION_NOT_MEASURED_WALL_GEOMETRY",
                "per_component_native_section_uncertainty": True,
                "complete_report_inventory_required_at_publication_and_acceptance": True}
        if row["obligation"] == "EXACT_COUNT_FABRICATION_FRONTIER_AND_SOURCE_PROPOSALS":
            row["automated_tests"].extend(["tests/test_certified_fabrication_frontier.py", "tests/test_joint_fitting_budget.py", "tests/test_joint_fitting_budget_adversarial.py"])
            row["real_model_benchmark"] = {"status": "ACTUAL_ANALYTIC_SOURCE_ADAPTER_AND_SEPARATE_NATIVE_WALL_CORRESPONDENCE",
                "evidence": "evidence/math/fabrication-frontier/latest.json",
                "scope": "Complete actual analytic wall source/frame/outer-support accounting; independently closed exact counts 0 through 2, checked binary64 k=2 path, five actual native parts/two elbows, full obstacle/self/zone/semantics checks. This retained attempt does not accept a project or check an aggregate joint budget."}
            row["independent_review"] = "evidence/release/fabrication-frontier-independent-review.json"
            row["consumer_scope"] = {"mission_field":"JointRoutingScenario.max_new_fittings", "default":None,
                "declared_budget_maximum":1024,"represented_per_route_count_maximum":32,
                "native_resource":"NEW_INDEPENDENT_ROUND_90_DEGREE_ELBOWS", "prior_routes":"EXCLUDED_PROTECTED_BASELINE",
                "nominal_bounds_are_native_or_continuous_bounds":False,
                "complete_cartesian_physical_route_universe":False}
        if row["obligation"] == "SOURCE_AWARE_BOUNDED_GRID_ENRICHMENT":
            row["real_model_benchmark"] = {"status": "SOURCE_DERIVED_REAL_OFFICE_PROPOSAL_AND_FRESH_COMPLETE_NATIVE_CHECK",
                "evidence": "evidence/math/fabrication-grid/latest.json", "scope": "100-micrometre guarded finite model, independent plane/grid and nominal pricing certificates; fresh4015 native pairs against803 obstacles, native zone and primitive correspondence. No candidate acceptance or continuous optimum."}
        if row["obligation"] == "FINITE_FABRICATION_GRAPH_COST_PRICING":
            row["real_model_benchmark"] = {"status": "FINITE_GRAPH_OPTIMUM_AND_SEPARATE_SYNTHETIC_ACTUAL_IFC_WALL_CHECK",
                "evidence": "evidence/math/fabrication-pricing/latest.json", "scope": "Exact finite nominal cost optimum, independent dual/path proof, actual native five-part IFC4 wall coordination; no native objective bound, candidate acceptance or continuous closure"}
        if row["obligation"] == "BOUNDED_FABRICATION_LIFTED_GRID_SEARCH":
            row["real_model_benchmark"] = {"status": "SYNTHETIC_ACTUAL_IFC_WALL_DETOUR_AND_FINITE_GRAPH_CUT",
                "evidence": "evidence/math/fabrication-search/latest.json", "scope": "Exact finite graph, separate fixed-polyline proof and actual native five-part IFC4 wall coordination in metres/millimetres; no accepted candidate or continuous closure"}
        if row["obligation"] == "EXACT_ORTHOGONAL_FABRICATION_TRANSITIONS":
            row["real_model_benchmark"] = {"status": "SYNTHETIC_ACTUAL_IFC_PRIMITIVE_CORRESPONDENCE_AND_BOUNDARY_TESTS",
                "evidence": "evidence/math/fabrication/latest.json", "scope": "Actual IFC4 and IFC2X3 round primitives; separate numerical CAD correspondence and exact model proofs, no whole-route or acceptance claim"}
        if row["obligation"] == "SOURCE_BOUND_IFC_OUTER_CELL_PROPOSALS":
            row["real_model_benchmark"] = {"status": "SEE_RETAINED_SOURCE_BOUND_MODEL_AND_SEPARATE_NATIVE_CHECKS",
                "evidence": "evidence/math/certified-cells/latest.json", "scope": "Pinned analytic IFC detour and immutable Office model proposal evidence; see exact dependency hashes and attempt summary, no acceptance authority"}
        if row["obligation"] == "ACTUAL_FROZEN_PHYSICAL_MENU_PROJECTION":
            row["real_model_benchmark"] = {"status": "HISTORICAL_IMMUTABLE_REAL_REPORT_PROJECTIONS_CHECKED",
                "evidence": "evidence/math/physical-menu-office.benchmark.json",
                "scope": "Historical report observations only; no current native recertification"}
    proof = {"schema": "oma.math.traceability/2", "source_review_complete": coverage["whole_corpus_fully_read"],
             "source_review_coverage": "evidence/math/combined_review_coverage.json", "source_bodies_available_in_full": False,
             "full_engine_mathematics_implemented": False,
             "obligations": register, "pending_source_mechanisms": pending,
             "unit_test_run": {"path": str(test_path.relative_to(ROOT)), "tests": int(suite.get("tests")) if suite is not None else None,
                               "failures": int(suite.get("failures")) if suite is not None else None},
             "additional_adapter_test_runs": ["evidence/math/certified-cells-adapter-tests.xml", "evidence/math/opening-inverse-regression.xml", "evidence/math/fabrication-tests.xml", "evidence/math/fabrication-search-tests.xml", "evidence/math/fabrication-pricing-tests.xml", "evidence/release/fabrication-pricing-adversarial.xml", "evidence/math/fabrication-grid-tests.xml", "evidence/release/fabrication-grid-native-zone-adversarial.xml", "evidence/release/certified-fabrication-frontier.xml", "evidence/math/route-metadata-tests.xml", "evidence/math/two-sink-pressure/kernel/kernel-corrected.xml", "evidence/math/two-sink-pressure/native-initial/tests.xml"],
             "command": ".venv\\Scripts\\python.exe -m pytest tests/test_exact.py tests/test_dependencies.py tests/test_optimization_master.py tests/test_optimization_physical.py tests/test_optimization_certificates.py tests/test_ifc_enclosure.py tests/test_optimization_finite.py tests/test_optimization_policy.py tests/test_optimization_codesign.py tests/test_optimization_fdqa.py tests/test_optimization_separator.py tests/test_optimization_symbolic.py tests/test_optimization_ports.py tests/test_optimization_bisimulation.py tests/test_optimization_physical_menu.py tests/test_optimization_rectilinear_opening.py tests/test_optimization_route_cells.py -q --junitxml=evidence/math/implemented-obligation-tests.xml"}
    destination = ROOT / "evidence/math/traceability_register.json"
    destination.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"registered_obligations": len(register), "callables_resolved": all(c["callable"] for r in register for c in r["callable_probe"]),
                      "supplied_content_review_complete": proof["source_review_complete"],
                      "full_engine_gate": "INCOMPLETE", "unit_tests": proof["unit_test_run"]}))


if __name__ == "__main__":
    main()
