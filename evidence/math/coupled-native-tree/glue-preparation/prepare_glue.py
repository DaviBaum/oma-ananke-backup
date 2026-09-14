"""Prepare isolated application glue for the explicit coupled-tree boundary."""
from pathlib import Path
import hashlib
import json

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
OWNED = ("routing/network_scenario.py", "routing/network_checker.py", "routing/selection.py", "routing/network_export.py", "project_assurance.py")


def replace(text, before, after, count=1):
    assert text.count(before) == count, (before, text.count(before))
    return text.replace(before, after)


def prepare(relative):
    source = ROOT / "src/oma" / relative
    text = source.read_text(encoding="utf8")
    if relative == "routing/network_scenario.py":
        text = replace(text, "from .passive_tree_scenario import PassiveTreeBoundary", "from .passive_tree_scenario import PassiveTreeBoundary\nfrom .coupled_tree_scenario import CoupledTreeBoundary")
        text = replace(text, "    passive_tree: PassiveTreeBoundary | None = None", "    passive_tree: PassiveTreeBoundary | None = None\n    coupled_tree: CoupledTreeBoundary | None = None")
        text = replace(text, '        if self.passive_tree is None:\n            raw.pop("passive_tree", None)', '        if self.passive_tree is None:\n            raw.pop("passive_tree", None)\n        if self.coupled_tree is None:\n            raw.pop("coupled_tree", None)')
        before = '        if self.passive_tree is not None:\n            if self.physics is not None or self.pressure_driven is not None:'
        new = '''        if self.coupled_tree is not None:
            if any(value is not None for value in (self.physics, self.pressure_driven, self.passive_tree)):
                raise ValueError("The explicit coupled tree boundary cannot coexist with other hydraulic models")
            if any(s.required_flow_m3_s is not None or s.available_static_pressure_pa is not None for s in self.sinks):
                raise ValueError("Coupled tree exact minimum deliveries belong only in the boundary contract")
            if self.system_type != "PRESSURE_PIPE" or self.target_modality != "ENGINEERING_SERVICE":
                raise ValueError("Coupled tree calculation requires a pressure-pipe engineering-service mission")
            if set(self.coupled_tree.sink_total_pressures_pa) != set(required):
                raise ValueError("Every coupled tree sink needs its pressure, minimum delivery and proof search box")
'''
        text = replace(text, before, new + before)
        before = '            if self.passive_tree is not None and set(self.passive_tree.tee_common_loss_coefficients)'
        new = '''            if self.coupled_tree is not None and set(self.coupled_tree.tee_outlet_loss_coefficients) != {c.id for c in components.values() if c.kind == "tee"}:
                raise ValueError("Every alternative must cover exactly the declared unequal-outlet tee identities")
'''
        text = replace(text, before, new + before)
        text = replace(text, 'kind="scenario", description=("Explicit hypothetical network terminals and exact passive-tree minimum deliveries"',
            'kind="scenario", description=("Explicit hypothetical network terminals and exact coupled-tree minimum deliveries"\n            if scenario.coupled_tree is not None else "Explicit hypothetical network terminals and exact passive-tree minimum deliveries"')
        text = replace(text, '''        if scenario.passive_tree is None:
            return sink.required_flow_m3_s
        projected = float(Fraction(scenario.passive_tree.minimum_sink_flows_m3_s[sink.id]))''', '''        boundary = scenario.coupled_tree if scenario.coupled_tree is not None else scenario.passive_tree
        if boundary is None:
            return sink.required_flow_m3_s
        projected = float(Fraction(boundary.minimum_sink_flows_m3_s[sink.id]))''')
        text = replace(text, '    if scenario.passive_tree is not None:\n        rule["passive_tree"] = raw["passive_tree"]',
            '    if scenario.passive_tree is not None:\n        rule["passive_tree"] = raw["passive_tree"]\n    if scenario.coupled_tree is not None:\n        rule["coupled_tree"] = raw["coupled_tree"]')
    elif relative == "routing/network_checker.py":
        text = replace(text, '("pressure_driven", "passive_tree")', '("pressure_driven", "passive_tree", "coupled_tree")')
        text = replace(text, 'if request.pressure_driven is not None or request.passive_tree is not None:',
            'if request.pressure_driven is not None or request.passive_tree is not None or request.coupled_tree is not None:')
        start = text.index('        if request.passive_tree is not None:\n            from .passive_tree_pressure')
        end = text.index('        elif request.pressure_driven is not None:', start)
        original = text[start:end]
        added = original.replace('passive_tree', 'coupled_tree').replace('network_passive_', 'network_coupled_')
        added = added.replace('checked.get("status") == "PASS"\n', 'checked.get("status") == "PASS"\n                and checked.get("local_check", {}).get("status") == "PASS" and checked.get("global_check", {}).get("status") == "PASS"\n')
        added = added.replace("Independent pressure envelope, complete native cap quotient and every component's dimensional resistance checked under the explicit common-outlet tee law",
            "Independent local pressure enclosure and global nonnegative uniqueness, complete native path terms and outlet-specific inlet-flow losses checked")
        added = added.replace("under the explicit passive tree model", "under the explicit coupled tree model")
        text = text[:start] + added + original.replace('        if request.passive_tree', '        elif request.passive_tree', 1) + text[end:]
    elif relative in ("routing/selection.py", "routing/network_export.py"):
        text = replace(text, '("pressure_driven", "passive_tree")', '("pressure_driven", "passive_tree", "coupled_tree")', 2 if relative.endswith("selection.py") else 1)
    else:
        before = '        if scenario.get("passive_tree") is not None:'
        added = '''        if scenario.get("coupled_tree") is not None:
            declared.append({"coupled_tree_network_boundary_inputs": scenario["coupled_tree"],
                "source_position_m": scenario["start_m"], "sinks": scenario["sinks"],
                "flow_interpretation": "Exact minima are authoritative; Demand floats are descriptive. Every physical port requires positive flow and bounded speed. The search box proposes an enclosure; separate positive-singleton hierarchical uniqueness must exclude other nonnegative equilibria",
                "boundary_interpretation": "Explicit intervals of total pressure exclude elevation; each actual cap elevation enters head separately. Each tee outlet has its own inlet-flow-referenced total loss; its skeleton has no extra Darcy charge",
                "section_interpretation": "Ideal bore from native outer-radius enclosures minus declared insulation; actual inner bore and wall are not measured",
                "model_interpretation": "Declared fixed steady incompressible loss and nonnegative-flow regime; physical catalog, controls and applicability remain external. Reverse-flow laws are not certified",
                "connection_interpretation": "Matching native connected caps add no declared loss; every physical component, port, source/sink path and continuity identity is accounted"})
'''
        text = replace(text, before, added + before)
    target = STAGE / "src/oma" / relative
    assert not target.exists(), target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf8")
    compile(text, str(target), "exec")
    return {"before": hashlib.sha256(source.read_bytes()).hexdigest(), "after": hashlib.sha256(target.read_bytes()).hexdigest()}


rows = {name: prepare(name) for name in OWNED}
(STAGE / "glue-manifest.json").write_text(json.dumps({"production_modified": False, "source_files": rows,
    "scope": "Prepared syntax-checked glue only; native adapter and integration tests pending"}, indent=2) + "\n", encoding="utf8")
print(json.dumps({"prepared_files": len(rows), "syntax_checked": True, "production_modified": False}))
