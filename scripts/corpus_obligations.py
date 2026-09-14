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
        "General pressure/flow networks, supports, penetrations and access fibers",
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
             "additional_adapter_test_runs": ["evidence/math/certified-cells-adapter-tests.xml", "evidence/math/opening-inverse-regression.xml", "evidence/math/fabrication-tests.xml"],
             "command": ".venv\\Scripts\\python.exe -m pytest tests/test_exact.py tests/test_dependencies.py tests/test_optimization_master.py tests/test_optimization_physical.py tests/test_optimization_certificates.py tests/test_ifc_enclosure.py tests/test_optimization_finite.py tests/test_optimization_policy.py tests/test_optimization_codesign.py tests/test_optimization_fdqa.py tests/test_optimization_separator.py tests/test_optimization_symbolic.py tests/test_optimization_ports.py tests/test_optimization_bisimulation.py tests/test_optimization_physical_menu.py tests/test_optimization_rectilinear_opening.py tests/test_optimization_route_cells.py -q --junitxml=evidence/math/implemented-obligation-tests.xml"}
    destination = ROOT / "evidence/math/traceability_register.json"
    destination.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"registered_obligations": len(register), "callables_resolved": all(c["callable"] for r in register for c in r["callable_probe"]),
                      "supplied_content_review_complete": proof["source_review_complete"],
                      "full_engine_gate": "INCOMPLETE", "unit_tests": proof["unit_test_run"]}))


if __name__ == "__main__":
    main()
