"""Enumerate source algorithm identities and conservative implementation gates.

This index is generated only after the separately recorded full-content review.
Lexical discovery here is an inventory aid, never the reading or proof evidence.
Matching an algorithm name to a bounded callable does not implement its full body.
"""
from collections import Counter, defaultdict
import hashlib
import importlib
import json
from pathlib import Path
import re

from corpus_audit import records_for

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"
CORE = {"F", "SEM", "MN", "DS", "AB", "ER", "PO", "RT", "CS", "RC", "ADV", "ASS", "SOV", "MAT", "PHY", "RTE", "SIR", "RTR", "JCD", "CMP", "GEO", "MEP", "STR", "INT"}
FAMILY_LIMITS = {
    "SIR": "Actual IFC state, source enclosure and finite report-menu components exist; general spatial cell complex, full rewrite/functor correspondence, complete physical fibers and complete PCSIR package are not implemented.",
    "RTR": "Finite master/pricing and independent native geometry checks exist; continuous inner/outer graph completeness, 3D homotopy presentation, topology-native branch-and-price and unrestricted fabrication/physics lifts are not implemented.",
    "JCD": "Finite materialized route/design alternatives are checked and selected; general architectural rewrite generation, universally valid Benders cuts, all strategic fibers and complete PCJCD release are not implemented.",
    "DYN": "Finite supplied histories, nonanticipative policies and exact finite risk are implemented; physical construction scheduling, continuous hybrid dynamics and universal adversarial closure are not implemented.",
    "CMP": "Internal immutable state, checks, dependencies, assurance and transaction gates exist; the complete source package and all operation-specific mathematical closures are not implemented. MCP-specific runtime clauses are excluded by the user.",
    "MN": "Complete finite typed tables and exact terminal profiles are supported; physical semantic extraction and unbounded context-language compilation need separate certified adapters.",
    "DS": "Finite explicit regional merge tables, exact context closure and original menu multiplicities are supported; automatic decomposition discovery and arbitrary physical separator sufficiency are not established.",
    "AB": "Finite table quotients and bounded Boolean-circuit symbolic refinement are implemented; arbitrary theorem/SMT interfaces, complete engineering CEGAR and physical context completeness are not established.",
    "ER": "Some exact interval checks and finite supplied outcomes exist; the full discrepancy, cover, adaptive enclosure and resource-rational refinement system is not implemented.",
    "PO": "Exact supplied rational linear port relations, a uniformly forward two-sink pressure relation and grounded positive-K signed quadratic graph enclosures are implemented with independent checks. The graph kernel covers its declared trees/loops, zero and reversed flow; native graph applicability is not established. Existing native two-sink and fixed-flow adapters retain loss and component-specific metric assumptions. General coupled nonlinear, dynamic, PDE and full physical applicability contracts remain open.",
    "CS": "Complete supplied finite nondeterministic relations admit a checked strong bisimulation; general causal physical transition discovery, evidence effects and full CSSP closure are not implemented.",
    "ASS": "Grounded finite positive assurance derivations, minimal support antichains, cuts and actual report foundations are implemented; no whole-project assurance closure is inferred from a local route report.",
    "SOV": "Frozen authorized candidate definitions and protected-state gates are present; complete menu-sensitive intent languages, global option preservation after every authorized amendment and general sovereign rewrite search are not implemented.",
    "INT": "Some internal proof packages and scoped adapters exist; the source's final conjunction requires all constituent domain closures and external assumptions, which are not implemented or established in full.",
    "LIFE": "The supplied original body starts with a continuation; earlier original definitions and proof steps are absent. The separate reconstructed canonical body does not repair original source availability. Full lifecycle operations are not implemented.",
}

ADAPTERS = {
    "ALG-RTR15": (["oma.optimization.fabrication_search.compile_fabrication_search", "oma.optimization.fabrication_alternatives.compile_fabrication_alternatives", "oma.optimization.fabrication_alternatives.verify_fabrication_alternatives"], "Bounded fixed-size fabrication/count graph and checked whole-word exclusion trie; no general fitting, size, support or homotopy lift closure", ["tests/test_optimization_fabrication_search.py", "tests/test_optimization_fabrication_alternatives.py"]),
    "ALG-RTR4": (["oma.routing.scenario.RoutingScenario.model_validate"], "Typed explicit route request; no discovery of missing physical inputs", ["tests/test_routing_integration.py"]),
    "ALG-RTR11": (["oma.exact.orient2d", "oma.exact.orient3d", "oma.exact.segment_triangle_intersection"], "Exact represented rational primitive predicates; general CAD arithmetic remains numerical", ["tests/test_exact.py"]),
    "ALG-RTR16": (["oma.routing.engine.route_project_run"], "Finite generated physical routes with independent checking; not a complete certified continuous route graph", ["tests/test_routing_integration.py"]),
    "ALG-RTR17": (["oma.routing.network_engine.network_project_run"], "Explicit bounded shared-tree component candidates; no complete multi-terminal topology pricing", ["tests/test_network_integration.py"]),
    "ALG-RTR18": (["oma.ifc.network_semantics.check_network_semantics"], "Independent actual native component/port connectivity and approved component geometry checks", ["tests/test_network_integration.py"]),
    "ALG-RTR19": (["oma.routing.network_flow.evaluate_network_flow", "oma.optimization.physical.evaluate_fluid_path", "oma.routing.network_pressure.partition_two_sink_tree", "oma.routing.network_pressure.derive_two_sink_pressure_model", "oma.routing.network_pressure.evaluate_pressure_network"], "Declared fixed-flow tree/path physics plus a separate total-pressure one-tee/two-outlet model. Complete component-specific native radius, length and position enclosures feed velocity and head calculations; fixed-flow nominal-diameter false PASS is corrected. Minimum delivery and each physical port velocity remain distinct service gates. No general nonlinear flow discovery or full physical fiber", ["tests/test_network_scenario.py", "tests/test_fixed_flow_native_section.py", "tests/test_optimization_physical.py", "tests/test_network_pressure.py", "tests/test_network_pressure_integration.py"]),
    "ALG-RTR20": (["oma.optimization.physical.solve_gravity_elevations", "oma.optimization.physical.verify_gravity_result", "oma.optimization.two_sink_pressure.compile_two_sink_pressure", "oma.optimization.two_sink_pressure.verify_two_sink_pressure", "oma.optimization.passive_pressure.compile_passive_pressure", "oma.optimization.passive_pressure.verify_passive_pressure", "oma.routing.network_checker.verify_network_candidate"], "Exact finite elevation constraints, uniformly forward two-sink quadratic relation and grounded positive-K signed quadratic graph enclosures with complete independent barrier/incidence checks. The latter covers its declared trees/loops, zero and reversed flow but has no native adapter or transfer to existing unequal tee losses. Actual native checks and declared external model premises remain mandatory; no general physical fiber solver or kernel acceptance authority", ["tests/test_optimization_physical.py", "tests/test_two_sink_pressure.py", "tests/test_network_pressure.py", "tests/test_network_pressure_integration.py", "tests/test_passive_pressure.py"]),
    "ALG-RTR22": (["oma.routing.checker.verify_route_candidate", "oma.routing.network_checker.verify_network_candidate"], "Actual candidate geometry/semantics/report checks; no unrestricted source column schema closure", ["tests/test_routing_integration.py", "tests/test_network_integration.py"]),
    "ALG-RTR23": (["oma.optimization.master.generate_columns"], "Generate from an explicit complete serialized finite pool only", ["tests/test_optimization_master.py"]),
    "ALG-RTR24": (["oma.optimization.master.solve_master"], "Exact finite route-column master with explicit conflicts and capacities", ["tests/test_optimization_master.py"]),
    "ALG-RTR25": (["oma.optimization.checker.verify_dual"], "Independent exact rational dual feasibility over every supplied column", ["tests/test_optimization_master.py"]),
    "ALG-RTR26": (["oma.optimization.master.price_columns", "oma.optimization.fabrication_pricing.compile_fabrication_pricing", "oma.optimization.fabrication_pricing.verify_fabrication_pricing", "oma.optimization.fabrication_frontier.compile_fabrication_frontier", "oma.optimization.fabrication_frontier.verify_fabrication_frontier", "oma.optimization.fabrication_alternatives.compile_fabrication_alternatives", "oma.optimization.fabrication_alternatives.verify_fabrication_alternatives"], "Exact supplied finite column pricing, independently certified nominal length/fitting optimum and exact-count frontier on a declared finite fabrication graph. Actual source-bound frontier proposals support optional native fitting budgets; a separate residual exact-count frontier excludes only complete generated graph words, preserving all prefixes and goal successors; general node-dual resource pricing, original-language and continuous closure remain open", ["tests/test_optimization_master.py", "tests/test_optimization_fabrication_pricing.py", "tests/test_optimization_fabrication_frontier.py", "tests/test_certified_fabrication_frontier.py", "tests/test_optimization_fabrication_alternatives.py", "tests/test_certified_fabrication_residual.py"]),
    "ALG-RTR27": (["oma.routing.generator.proposal_paths", "oma.routing.fabrication_grid.enrich_fabrication_grid", "oma.routing.fabrication_grid.verify_fabrication_grid_enrichment", "oma.routing.fabrication_residual.residual_proposals", "oma.routing.proposals.project_proposals"], "Bounded proposal enumeration and exact source-plane/terminal-trim grid-coordinate provenance; one explicitly bounded residual-word proposal round before the fitting-budget joint menu is frozen; no physical feasibility verdict, native rejection cut, certified CEGAR or global bound", ["tests/test_routing_integration.py", "tests/test_fabrication_grid.py", "tests/test_certified_fabrication_residual.py", "tests/test_joint_residual_fabrication.py"]),
    "ALG-RTR28": (["oma.optimization.checker.verify_dual", "oma.optimization.fabrication_frontier.verify_fabrication_frontier"], "Finite supplied-column dual closure and independently grounded complete reachable-state/count closure for a declared bounded fabrication graph; physical route, continuous and topology-complete pricing remain open", ["tests/test_optimization_master.py", "tests/test_optimization_fabrication_frontier.py"]),
    "ALG-RTR32": (["oma.optimization.certificates.verify_farkas"], "Exact supplied rational linear-system ray checker; routing use needs domain closure", ["tests/test_optimization_certificates.py"]),
    "ALG-RTR38": (["oma.optimization.fabrication_pricing.verify_fabrication_pricing", "oma.optimization.fabrication_frontier.verify_fabrication_frontier"], "CPU exact finite fabrication path cost and dual-potential checks; scalar costs use independently bounded pi comparisons, while exact-count frontier potentials are rational with independently fixed pi coefficient. No GPU producer or continuous/native objective bound", ["tests/test_optimization_fabrication_pricing.py", "tests/test_optimization_fabrication_frontier.py"]),
    "ALG-RTR33": (["oma.optimization.checker.verify_master_result"], "Independently checked finite supplied-master infeasibility; no full-building infeasibility", ["tests/test_optimization_master.py"]),
    "ALG-RTR43": (["oma.verification.recheck_candidate_run"], "Persisted actual-candidate current-build recertification; physical pair results are recomputed", ["tests/test_joint_routing.py"]),
    "ALG-RTR45": (["oma.routing.checker.verify_route_candidate", "oma.routing.joint_checker.verify_joint_candidate", "oma.routing.network_checker.verify_network_candidate"], "Actual scoped route/joint/network checks and report packages; no complete source PCROUTE release claim", ["tests/test_joint_routing.py", "tests/test_network_integration.py"]),
    "ALG-SIR5": (["oma.ifc.federation.audited_local_federation"], "Audited supported local IFC federation correspondence only", ["tests/test_ifc_pipeline.py"]),
    "ALG-SIR8": (["oma.ifc.enclosure.ExactIfcEncloser.enclose_product", "oma.exact.capsule_within_box"], "Supported complete source outer enclosures and exact capsule/AABB allowed regions", ["tests/test_ifc_enclosure.py", "tests/test_exact.py"]),
    "ALG-SIR10": (["oma.ifc.ports.ownership_ledger", "oma.ifc.ports.port_facts"], "Actual explicit IFC port ownership, direction and placement facts; no inferred connectivity authority", ["tests/test_ifc_ports.py"]),
    "ALG-SIR15": (["oma.ifc.cad.cad_check_routes"], "Native numerical CAD Boolean/distance checks with complete source accounting; not formal general exact BRep geometry", ["tests/test_ifc_cad.py"]),
    "ALG-SIR22": (["oma.routing.physical_archive.compile_route_archive", "oma.optimization.physical_menu.compile_physical_menu"], "Frozen actual report projections and complete finite menu actions; no native PASS reuse or continuous closure", ["tests/test_joint_routing.py", "tests/test_optimization_physical_menu.py"]),
    "ALG-SIR24": (["oma.optimization.physical_menu.verify_physical_menu"], "Independent exact frozen-table contextual/action quotient verification; physical root authenticity belongs to assembly", ["tests/test_optimization_physical_menu.py"]),
    "ALG-SIR26": (["oma.optimization.rectilinear_opening.verify_rectilinear_opening", "oma.ifc.openings.check_opening_semantics", "oma.routing.opening.opening_check_arguments"], "Exact rational host-box through-cut support identity plus one explicitly requested native IFC wall/slab opening; complete source/void/relationship accounting and numerical native agreement, geometry-only scope", ["tests/test_optimization_rectilinear_opening.py", "tests/test_ifc_openings.py", "tests/test_opening_inverse_effects.py"]),
    "ALG-SIR27": (["oma.dependencies.invalidation_closure"], "Complete declared graph invalidation only", ["tests/test_dependencies.py"]),
    "ALG-SIR28": (["oma.dependencies.DependencyEngine.compare_with_cold"], "Finite declared deterministic dependency semantics and cold equivalence", ["tests/test_dependencies.py"]),
    "ALG-JCD9": (["oma.routing.joint_materialize.materialize_route_set"], "Actual simultaneous finite route/design assignment materialization", ["tests/test_joint_routing.py"]),
    "ALG-JCD13": (["oma.optimization.physical_menu.compile_physical_menu"], "Frozen actual finite assignment report projection; complete interactions retained", ["tests/test_optimization_physical_menu.py"]),
    "ALG-JCD39": (["oma.routing.joint_checker.verify_joint_candidate", "oma.optimization.codesign.solve_finite_codesign"], "Actual simultaneous route assignment checks plus scoped finite co-design selection", ["tests/test_joint_routing.py", "tests/test_optimization_codesign.py"]),
    "ALG-CMP48": (["oma.dependencies.invalidation_closure"], "Complete declared dependency cone", ["tests/test_dependencies.py"]),
    "ALG-CMP53": (["oma.dependencies.DependencyEngine.compare_with_cold"], "Explicit finite graph and current metadata-input evaluator cold equality", ["tests/test_dependencies.py"]),
    "ALG-CMP75": (["oma.exporting.export_project"], "Actual edited IFC with independent reopened-file checks within stated local scope", ["tests/test_joint_routing.py"]),
}


def scope_for(document, family, name, title):
    if document == "oma-integration":
        if name in {"ALG-CMP59", "ALG-CMP60"}:
            return "EXPLICITLY_EXCLUDED_PRODUCT_SCOPE", "MCP registry/server/client architecture is excluded by directive section 1. Internal schema/capability/idempotence checks remain required in other rows."
        if name in {"ALG-JCD37", "ALG-JCD38", "ALG-CMP67", "ALG-CMP68", "ALG-CMP69", "ALG-CMP70"}:
            return "HISTORICAL_OR_NONREQUIRED_REFERENCE", "AI-generated proposal integration is optional source context, not a compulsory model/LLM runtime requirement; ordinary authorized proposal validation remains required."
        if family == "DYN":
            number = int(re.search(r"\d+$", name)[0])
            if number == 4 or 22 <= number <= 59 and number not in {27, 57}:
                return "HISTORICAL_OR_CONDITIONAL_DOMAIN_REFERENCE", "Construction execution, commissioning, live operational control, digital-twin observation, lifecycle maintenance or external-system operations are broader source context. Their relevant model-boundary predicates apply only when a declared standalone optimization mission invokes them; this is not a requirement to build those full products."
            return "REQUIRED_SUPPORTING_MATHEMATICS", "Use finite scenario, risk and nonanticipativity obligations when a declared optimization mission needs them. This does not require a live construction/BMS/operational controller or all continuous lifecycle physics."
        return "REQUIRED_ENGINE_MATHEMATICS", "Source mechanism concerns the standalone state, routing, authorized co-design, verification or local compiler workflow; implementation may still be partial or absent."
    if document == "ceiling-router":
        return "REQUIRED_SUPPORTING_MATHEMATICS", "Routing/optimization proof architecture is required supporting source; the historical PCB product, worktrees and benchmark claims are not this building engine's runtime."
    if document == "1-10" or family in {"F", "SEM", "MN", "DS", "AB", "ER", "PO", "RT", "CS", "RC", "ADV", "ASS", "SOV", "RTE"}:
        return "REQUIRED_SUPPORTING_MATHEMATICS", "Finite semantics, compression, routing, evidence or authorized-choice foundation; only the admitted engine model and its applicability contract are invoked, not every broad domain program."
    if family == "MAT":
        return "REQUIRED_SUPPORTING_MATHEMATICS", "Concrete materialization, witness identity and proof transport support actual IFC candidates. Construction sequencing and document-production operations are conditional source context, not automatically runtime requirements."
    if family in {"GEO", "MEP", "STR"}:
        return "REQUIRED_SUPPORTING_MATHEMATICS", "Represented geometry and supplied engineering-model boundaries support physical candidate checks. This does not imply complete structural analysis or all physical laws; unsupported affected requirements remain explicit UNKNOWN or declared external premises."
    if family == "INT":
        return "REQUIRED_SUPPORTING_MATHEMATICS", "Scope compatibility, shared identities, assumption closure and no stronger release than checked premises apply to the standalone engine. Full all-domain final release is not claimed."
    supporting = {"ALG-HUM12", "ALG-HUM13", "ALG-HUM18", "ALG-HUM19", "ALG-REG2", "ALG-REG6", "ALG-REG20",
                  "ALG-SEC2", "ALG-SEC4", "ALG-SEC6", "ALG-SEC7", "ALG-SEC10", "ALG-SEC11", "ALG-SEC12",
                  "ALG-ACC9", "ALG-ACC10", "ALG-ACC13", "ALG-ACC14", "ALG-ACC20", "ALG-ACC24"}
    if name in supporting:
        return "REQUIRED_SUPPORTING_MATHEMATICS", "Only the decision-interface, exact evidence/applicability, software provenance or invalidation principle supports this engine. No complete operational human, legal, security or commissioning program is required by this classification."
    return "HISTORICAL_OR_CONDITIONAL_DOMAIN_REFERENCE", "Broader domain program retained and reviewed as reference. A mission that explicitly asserts a result in this domain must supply its applicable checks/evidence; otherwise do not claim that result. This row does not make the full legal, commercial, social, human, environmental, lifecycle or live-control program mandatory runtime scope."


def resolve_callable(path):
    parts = path.split(".")
    for split in range(len(parts) - 1, 0, -1):
        try:
            value = importlib.import_module(".".join(parts[:split]))
        except ModuleNotFoundError:
            continue
        try:
            for field in parts[split:]:
                value = getattr(value, field)
            return callable(value)
        except AttributeError:
            return False
    return False


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def object_names(text):
    # Expand the few compact source-object ranges used by the relied-on register.
    match = re.fullmatch(r"ALG-([A-Z]+)(\d+)-(\d+)", text)
    if match:
        return [f"ALG-{match[1]}{i}" for i in range(int(match[2]), int(match[3]) + 1)]
    return [text]


def main():
    inventory = {s["document_id"]: s for s in read(OUT / "source_inventory.json")["sources"]}
    coverage = read(OUT / "combined_review_coverage.json")
    if not coverage["whole_corpus_fully_read"]:
        raise ValueError("Complete supplied-content review gate is not satisfied")
    register = read(OUT / "traceability_register.json")
    related = defaultdict(list)
    for obligation in register["obligations"]:
        # Explicit extra source identities may share a bounded implementation;
        # never resolve original/reconstructed names by spelling alone.
        for source_binding in [obligation["source"], *obligation.get("related_sources", [])]:
            if inventory[source_binding["document"]]["sha256"] != source_binding["sha256"]:
                raise ValueError("Related source binding differs from its inventory identity")
            for name in source_binding["objects"]:
                for expanded in object_names(name):
                    related[source_binding["document"], expanded].append(obligation)
    # These extra adapters were independently read, but their complete original
    # domain programs are not asserted by the existence of these exact callables.
    extras = {
        ("11-20", "ALG-ASS4"): ["oma.assurance.solve_assurance"],
        ("11-20", "ALG-ASS5"): ["oma.assurance.verify_assurance"],
        ("11-20", "ALG-ASS6"): ["oma.assurance.solve_assurance"],
        ("11-20", "ALG-ASS7"): ["oma.assurance.evidence_cuts"],
        ("11-20", "ALG-ASS1"): ["oma.dependencies.DependencyEngine.build"],
    }
    rows = []
    documents = ["ananke-canonical", "oma-integration", "1-10", "11-20", "21-30", "ceiling-router"]
    for document in documents:
        source = inventory[document]
        if hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Source bytes changed")
        if document in {"1-10", "11-20", "21-30"}:
            records = [json.loads(line) for line in (OUT / "pages" / document / "body-records.jsonl").read_text(encoding="utf-8").splitlines()]
            records = [{"location": r["paragraph"], "text": r["text"]} for r in records]
        else:
            records = records_for(OUT, document)
        headings, mentions = defaultdict(list), defaultdict(list)
        for record in records:
            text = record["text"]
            for name in set(re.findall(r"\bALG-[A-Z]+\d+(?:\.\d+)?\b", text)):
                mentions[name].append(record["location"])
            heading = re.match(r"^(ALG-[A-Z]+\d+(?:\.\d+)?)\s*\u2014\s*(.+)$", text)
            if document == "ceiling-router":
                heading = re.match(r"^\*\*Algorithm (C\.\d+[AB]?)\s*\u2014\s*(.+?)\*\*\s*$", text)
            if heading:
                headings[heading[1]].append({"paragraph": record["location"], "title": heading[2],
                    "heading_text_sha256": hashlib.sha256(text.encode()).hexdigest()})
        registry = {}
        if document == "ananke-canonical":
            registry = {o["id"]: o for o in read(OUT / "canonical_namespace.json")["objects"] if o["id"].startswith("ALG-")}
        for name in sorted(set(headings) | set(mentions) | set(registry)):
            family_match = re.match(r"ALG-([A-Z]+)", name)
            family = family_match[1] if family_match else "CEILING"
            matches = related[document, name]
            implementations = sorted(set(c for ob in matches for c in ob["implementations"] + ob["independent_checkers"]))
            implementations += extras.get((document, name), [])
            adapter = ADAPTERS.get(name) if document == "oma-integration" else None
            if adapter:
                implementations += adapter[0]
            variants = headings[name]
            body = bool(variants)
            title = variants[0]["title"] if body else registry.get(name, {}).get("title")
            disposition = "PARTIAL_BOUNDED_COMPONENT_AVAILABLE" if implementations else "FULL_SOURCE_MECHANISM_NOT_IMPLEMENTED"
            if not body:
                disposition = "REFERENCE_OR_REGISTRY_ONLY_NO_LOCAL_BODY_HEADING"
            scope, scope_reason = scope_for(document, family, name, title)
            if scope == "EXPLICITLY_EXCLUDED_PRODUCT_SCOPE":
                disposition = "NOT_APPLICABLE_TO_STANDALONE_RUNTIME"
            limitation = FAMILY_LIMITS.get(family, "No full domain algorithm is claimed. Explicit requirements must be checked by their admitted finite/model-specific procedure; missing technical or external evidence remains UNKNOWN. General domain operations do not arise solely from reading this chapter.")
            if family == "CEILING":
                limitation = "Historical PCB algorithm, retained as source architecture and proof obligations. Native building geometry and finite master components do not establish this full original PCB algorithm or its complete continuous/pricing universe."
            if document == "ananke-canonical":
                limitation += " Reconstructed canonical identifiers and templates remain separate from materially different original Pages bodies."
            rows.append({"qualified_id": f"{document}:{source['sha256'][:16]}:{name}", "document": document,
                "source_sha256": source["sha256"], "id": name, "family": family, "title": title,
                "body_headings": variants, "all_native_reference_paragraphs": mentions[name],
                "source_declared_registry": registry.get(name), "supplied_content_review_complete": True,
                "review_evidence": "evidence/math/combined_review_coverage.json", "scope_classification": scope, "scope_reason": scope_reason,
                "implementation_disposition": disposition, "full_algorithm_implemented": False,
                "bounded_related_callables": sorted(set(implementations)),
                "callable_probe": [{"path": path, "callable": resolve_callable(path)} for path in sorted(set(implementations))],
                "actual_adapter_contract": None if adapter is None else adapter[1],
                "relied_on_obligations": [ob["obligation"] for ob in matches],
                "automated_tests": sorted(set(t for ob in matches for t in ob["automated_tests"]) | set(adapter[2] if adapter else [])),
                "limitations_and_missing_requirements": limitation,
                "reference_only_note": None if body else "A cited identifier does not supply a local algorithm body; do not resolve it by matching spelling in another source."})
    missing_tests = sorted(set(t for r in rows for t in r["automated_tests"] if not (ROOT / t).is_file()))
    unresolved = sorted(set(p["path"] for r in rows for p in r["callable_probe"] if not p["callable"]))
    if missing_tests or unresolved:
        raise ValueError({"missing_test_paths": missing_tests, "unresolved_callables": unresolved})
    families = []
    for document, family in sorted(set((r["document"], r["family"]) for r in rows)):
        selected = [r for r in rows if r["document"] == document and r["family"] == family]
        bodies = [r for r in selected if r["body_headings"]]
        families.append({"document": document, "family": family, "local_algorithm_id_count": len(bodies),
            "body_heading_occurrences": sum(len(r["body_headings"]) for r in bodies),
            "reference_only_id_count": len(selected) - len(bodies),
            "bounded_related_components": sum(bool(r["bounded_related_callables"]) for r in bodies),
            "full_source_algorithms_implemented": 0})
    result = {"schema": "oma.source-algorithm-capabilities/1", "review_complete": True,
        "all_source_algorithms_implemented": False, "source_body_availability_gaps": read(OUT / "pages/source-gaps.json"),
        "inventory_method": "Every explicit ALG identifier in supplied native text, plus every canonical registry algorithm and Ceiling Router Appendix C algorithm heading. References and local body headings are separated; repeated body headings remain listed, not assumed semantically identical.",
        "scope_rule": "Conditional domain obligations cannot be silently dropped from an accepted mission. Unsupported affected requirements remain UNKNOWN. Only MCP-specific runtime architecture is explicitly excluded; underlying internal schema, authority, dependency and commit obligations still apply.",
        "notice": "This complete index is not another source-reading claim. The independent hash-bound review ledger is the reading evidence. Bounded component links are not claims that an entire matching source algorithm is implemented. Original and reconstructed IDs never resolve across namespaces by spelling alone.",
        "classification_counts": dict(Counter(r["scope_classification"] for r in rows)),
        "relied_on_traceability_register": "evidence/math/traceability_register.json", "families": families, "algorithms": rows}
    write(OUT / "source_algorithm_capabilities.json", result)
    summary = ["# Source algorithm capability gates", "", "All supplied content has completed its tracked review. The original P7 and initial P26 bodies remain absent. Full source implementation and whole-building release remain open; exact bounded components have their own checked contracts.", "", "The machine-readable index separates explicit local bodies from references, retains repeated headings, and binds each identity to its own document hash. A callable association is a partial component, not a full source-program completion claim.", "", "| Source | Family | Local algorithm IDs | Body occurrences | Bounded component links |", "|---|---:|---:|---:|---:|"]
    for family in families:
        if family["local_algorithm_id_count"]:
            summary.append(f"| {family['document']} | {family['family']} | {family['local_algorithm_id_count']} | {family['body_heading_occurrences']} | {family['bounded_related_components']} |")
    summary.extend(["", f"The {len(register['obligations'])} relied-on executable obligations and their actual callable/checker/test/benchmark bindings are in `evidence/math/traceability_register.json`. All remaining local body mechanisms have explicit open dispositions in `evidence/math/source_algorithm_capabilities.json`.", "", "The index distinguishes required engine mathematics, required supporting principles, historical or conditional domain reference, and explicitly excluded MCP runtime. Broader commercial, legal, human, lifecycle and operational programs are not automatically mandatory because they occur in the source. Their evidence or boundary obligations apply whenever a mission actually relies on such a claim.", "", "Core open mechanisms include certified continuous inner/outer geometry, complete homotopy and fabrication lifts, topology-native branch-and-price, general physical fibers, complete architectural rewrite/Benders closure, and the final conjunction of domain package premises. Finite models and actual local route checks do not close those general claims.", ""])
    (ROOT / "docs/math/source-capabilities.md").write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps({"algorithm_identities": len(rows), "local_body_identities": sum(bool(r["body_headings"]) for r in rows),
        "body_occurrences": sum(len(r["body_headings"]) for r in rows), "families": len(families),
        "dispositions": dict(Counter(r["implementation_disposition"] for r in rows))}))


if __name__ == "__main__":
    main()
