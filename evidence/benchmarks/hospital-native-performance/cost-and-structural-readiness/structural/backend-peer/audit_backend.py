"""Read-only backend capability audit; writes only in this audit directory."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
assert OUT == ROOT / '.oma/development/hospital-structural-readiness/backend-peer'
REFERENCE = ROOT / 'evidence/release/hospital-original-regression/final-06aa-1dc9d7691342'
EXPECTED_BUILD = '06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source_paths = sorted((ROOT / 'src/oma').rglob('*.py'))
source_manifest = {p.relative_to(ROOT / 'src').as_posix(): sha(p) for p in source_paths}
expected = json.loads((REFERENCE / 'source.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(ROOT / 'src'))
from oma.build_identity import checker_version

version = checker_version()
assert source_manifest == expected, 'Backend source differs from audited checkpoint'
assert version == 'oma-independent-checker/2:' + EXPECTED_BUILD
patterns = {
    'structural_solver_terms': r'(?i)(structural|stiffness|stress|buckl|finite.element|\bfem\b|\bfea\b|load.combination|load.case|displacement|elastic.modulus|young|poisson|seismic|eurocode|ACI.?318|AISC|ABNT|NBR)',
    'linear_port_integration': r'LinearPortModel|compile_linear_port|compile_kron_network|verify_linear_port',
}
searches = {}
for key, pattern in patterns.items():
    searches[key] = {'pattern': pattern, 'scope': 'all 114 src/oma Python files', 'matches': []}
    compiled = re.compile(pattern)
    for p in source_paths:
        for number, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if compiled.search(line):
                searches[key]['matches'].append({'path': p.relative_to(ROOT).as_posix(), 'line': number, 'text': line.strip()})

definitions = {}
for p in source_paths:
    tree = ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    definitions[p.relative_to(ROOT).as_posix()] = [
        {'name': node.name, 'kind': type(node).__name__, 'line': node.lineno}
        for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]

references = {
    'entrypoints': [('src/oma/api.py', 43, 49), ('src/oma/worker.py', 243, 262), ('src/oma/verification.py', 125, 139)],
    'baseline': [('src/oma/ifc/check.py', 1, 7), ('src/oma/ifc/check.py', 69, 102), ('src/oma/verification.py', 66, 81)],
    'physical_route': [('src/oma/routing/checker.py', 598, 666)],
    'network_service': [('src/oma/routing/network_checker.py', 30, 42), ('src/oma/routing/network_checker.py', 180, 262), ('src/oma/routing/network_flow.py', 1, 7)],
    'admission': [('src/oma/routing/selection.py', 19, 77), ('src/oma/routing/selection.py', 85, 112), ('src/oma/routing/selection.py', 123, 172)],
    'structural_redesign_boundary': [('src/oma/routing/checker.py', 468, 487), ('src/oma/routing/opening_scenario.py', 1, 30), ('src/oma/routing/scenario.py', 53, 66), ('src/oma/routing/opening.py', 13, 41), ('src/oma/ifc/openings.py', 187, 201)],
    'abstract_mathematics': [('src/oma/optimization/ports.py', 1, 22), ('src/oma/optimization/ports.py', 129, 145), ('src/oma/optimization/codesign.py', 1, 6), ('src/oma/optimization/codesign.py', 123, 128), ('src/oma/optimization/finite.py', 197, 204)],
    'ifc_properties': [('src/oma/ifc/audit.py', 132, 145), ('src/oma/models.py', 174, 202)],
    'capability_register': [('docs/capabilities.json', 259, 303)],
}
excerpts = {}
for key, refs in references.items():
    excerpts[key] = []
    for path, first, last in refs:
        p = ROOT / path
        lines = p.read_text(encoding='utf-8').splitlines()
        excerpts[key].append({'path': path, 'sha256': sha(p), 'first_line': first, 'last_line': last,
                              'lines': [{'line': n, 'text': lines[n-1]} for n in range(first, min(last, len(lines))+1)]})

findings = [
    {'id': 'NO_BUILDING_STRUCTURAL_ANALYSIS_PATH', 'status': 'NOT_IMPLEMENTED_IN_AUDITED_BACKEND',
     'finding': 'No implemented IFC structural analytical-model extraction/assembly, building stiffness/displacement/stress solver, FEA, buckling, load-case/combination generator, code-design capacity check, or structurally checked member redesign path was found across the full 114-file backend. This is a bounded implementation inventory finding, not a judgment on original mathematical source claims.',
     'evidence_groups': ['entrypoints', 'admission', 'ifc_properties', 'structural_redesign_boundary'],
     'search_evidence': ['structural_solver_terms']},
    {'id': 'SUPPORTED_CHECKERS', 'status': 'IMPLEMENTED_WITH_DECLARED_SCOPE',
     'finding': 'Checker dispatch supports imported tessellated baseline geometry, one physical route, simultaneous physical routes, and one shared physical network. Physical checks include source/export identity, semantics, native obstacle/self/cross-route interference, clearance, port attachment, zone containment, objective recomputation and applicable gravity slope. Service checks cover declared fixed-flow paths/trees and supported pressure-driven tree models. These reports explicitly exclude whole-building adequacy.',
     'evidence_groups': ['entrypoints', 'baseline', 'physical_route', 'network_service']},
    {'id': 'PHYSICAL_ADMISSION_IS_NOT_STRUCTURAL_ADMISSION', 'status': 'SCOPE_ENFORCED',
     'finding': 'Publication/acceptance/selection reconstruct exact allowed route/network check IDs and statuses; bind persisted root, original request, mission, rules and executable; and require exact bounded report scope. No structural demand/check inventory exists at that admission boundary. A route/network PASS is therefore not evidence of Hospital STR strength or stability.',
     'evidence_groups': ['admission']},
    {'id': 'GEOMETRIC_OPENING_IS_NOT_STRUCTURAL_REDESIGN', 'status': 'STRUCTURAL_ADEQUACY_NOT_CHECKED',
     'finding': 'Ordinary candidate checks preserve baseline entities/source identities. The supported host edit is one explicitly permitted wall/slab opening with SCENARIO_GEOMETRY_ONLY permission and structural_adequacy NOT_CHECKED. The route scenario forbids this opening in ENGINEERING_SERVICE. No column/beam sizing, reinforcement design, foundation design or structural adequacy loop is implemented.',
     'evidence_groups': ['structural_redesign_boundary']},
    {'id': 'ABSTRACT_PORT_AND_CODESIGN_KERNELS', 'status': 'MATHEMATICAL_KERNELS_NOT_IFC_STRUCTURAL_SOLVER',
     'finding': 'LinearPortModel accepts a supplied matrix, boundary indices, internal loads and model bindings; exact Schur/Kron reduction labels physical_applicability_verified false. Backend references to the linear-port API remain in its own module. Finite co-design proves finite-table arithmetic over supplied physical/materialization evidence, and quantity transport explicitly does not preserve stiffness. These implementations do not assemble or verify a Hospital structural model.',
     'evidence_groups': ['abstract_mathematics'], 'search_evidence': ['linear_port_integration']},
    {'id': 'PROPERTY_PRESENCE_IS_NOT_STRUCTURAL_INPUT_ADMISSION', 'status': 'METADATA_ONLY',
     'finding': 'IFC audit preserves property sets, marks load/demand by property-name substrings, and records material names/STEP IDs. These generic presence counts do not establish structural load values, constitutive parameters, supports, connectivity, sections or load-combination applicability.',
     'evidence_groups': ['ifc_properties']},
]
result = {'schema': 'oma.hospital-structural-readiness.backend-peer/1',
          'created_at': datetime.now(timezone.utc).isoformat(),
          'audit_scope': 'Read-only local code/capability review. No original IFC was parsed by this peer. No source/Git/UI/store mutation, runtime engineering job or structural solver execution was performed.',
          'source_build': EXPECTED_BUILD, 'checker_version': version,
          'reference_source_manifest': str((REFERENCE / 'source.json').relative_to(ROOT)).replace('\\', '/'),
          'reference_source_manifest_sha256': sha(REFERENCE / 'source.json'),
          'application_file_count': len(source_manifest), 'all_source_files_match_reference': source_manifest == expected,
          'source_manifest': source_manifest, 'findings': findings, 'searches': searches, 'excerpts': excerpts,
          'ast_definition_inventory': definitions, 'audit_script_sha256': sha(Path(__file__))}
assert {p.relative_to(ROOT / 'src').as_posix(): sha(p) for p in source_paths} == source_manifest
(OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'result': str(OUT / 'result.json'), 'sha256': sha(OUT / 'result.json'),
                  'application_file_count': len(source_manifest), 'checker_version': version,
                  'all_source_files_match_reference': source_manifest == expected, 'finding_count': len(findings)}))
