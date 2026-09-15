"""Retain and stage the independently completed 5e8 local package checkpoint."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    return json.loads(p.read_text(encoding="utf-8"))
def checked(record):
    p = Path(record["path"])
    assert p.is_relative_to(ROOT), p
    assert sha(p) == record["sha256"], p
    return p
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")

handoff_path = ROOT / "evidence/release/coupled-portable-completed-82d3a00a6ff4/handoff.json"
assert sha(handoff_path) == "01420647200ca9f093d24ad2e7ee39cc6157bfbb17bab9bf4a47ea19c3503f68"
h = read(handoff_path)
assert h["status"] == "SEALED_LOCAL_5E8_PACKAGE_AND_INDEPENDENT_AUDIT_PASS"
assert (h["file_count"], h["logical_bytes"], h["bundled_passed"], h["bundled_not_applicable"]) == (14450,1980048071,2464,3)
assert (h["declared_exact_nodes"],h["declared_frozen_inputs"],h["app_source_files"],h["required_command_count"]) == (2467,131,107,50)
pointers = ["sealed_handoff","independent_final_audit","original_full","custom_full","bundled_full","preparation","initial_resealed_summary_failures"]
for key in pointers:
    checked(h[key])
sources = [checked(v) for v in h["changed_sources"].values()]
assert len(sources) == 7
for rec in h["focused_packaging_tests"].values():
    checked(rec)
original = read(Path(h["original_full"]["path"]))
actual = {p.relative_to(ROOT / "src/oma").as_posix(): sha(p) for p in (ROOT / "src/oma").rglob("*.py")}
assert actual == original["source_files"]
live = ROOT / "evidence/release/validated-backend-pressure-update/1665a25f0e4341a1b3cc76d1b1041769/result.json"
assert sha(live) == "4a1c01b1ec398278970e71fbfc56b76b90b5cee362e8b8d55c62784253d0858c"
sealed = read(Path(h["sealed_handoff"]["path"]))
closure_path = Path(h["package"]) / "provenance/command-closure.json"
assert sha(closure_path) == sealed["command_closure_sha256"]
commands = read(closure_path)["commands"]
assert len(commands) == 50
command_files = []
for name, rec in commands.items():
    folder = Path(rec["source"])
    assert folder.is_relative_to(ROOT / "evidence/dependencies/native-build/commands")
    for filename, digest in rec["files"].items():
        p = folder / filename
        assert p.is_relative_to(folder) and sha(p) == digest, (name, p)
        command_files.append(p)

doc = '''# Validated native and portable candidate

The current sealed local package is `.release/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4/`. Run `OMA.cmd` or `Start-OMA.ps1` inside that directory. It contains the validated unequal-outlet pressure-tree backend, the existing workbench build, Python 3.12.14, the pinned offline runtime wheelhouse, and native build/source/notice provenance. Its complete index accounts for **14,450 files and 1,980,048,071 logical bytes**, SHA-256 `672444ca71c94e3970e60243a341b4d30d2c5070d39b179dc8d28c72ea75b997`.

All three executions bind the same 107 application files, source identity `5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c`, 131 frozen test/support inputs and 2,467 exact test identities:

| Execution | Checker identity | Completed validation |
|---|---|---|
| Original Python 3.12.10/native runtime | `5e8fe965...` | 2,467 PASS, zero failures/skips; pytest 758.46 s |
| Python 3.12.10 with the separately built native wheel | `66ea494f...` | 2,467 PASS, zero failures/skips; command 770.460 s |
| Bundled Python 3.12.14 with that wheel | `b63f99b5...` | 2,464 PASS and three exactly identified virtual-environment bridge tests not applicable to its direct interpreter; 912.26 s |

The package's fresh managed rechecks cover three saved real Office exports: a two-route fitting-budget case (4,818 source pairs and five cross-route pairs), a two-outlet pressure network (3,212 source pairs, six component pairs, nine ports and two deliveries), and an unequal-outlet pressure tree (5,621 source pairs, 21 component pairs, 16 ports and three deliveries). The last also independently replays the complete bound local/global operating proof, 17 continuity identities, 19 head identities and all-port service. These remain explicit hypothetical engineering models, with supported forward-flow assumptions.

The offline analytic import/check/accept/export workflow passes. Separate probes establish Python audit-hook socket denial in the main and frozen checker interpreters; this is not an operating-system or native-library firewall. All six compiled interface assets are unchanged. Fifty required command records, exact input/source inventories, raw earlier failures, completed XML and a fresh independent rehash of every indexed payload file are retained.

The custom IfcOpenShell extension has SHA-256 `398b43db6952d07645d4fbea2c23c73cb83696369871e22880b85a8c35bfd875`. It was built from pinned commit `1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2`, OCCT 7.8.1, Boost 1.86, Eigen 3.3.9 and SWIG 4.2.1, with CGAL disabled and the retained minimal SWIG coordinate-template patch. The original environment and previous portable packages remain separate.

The same validated application source is running at `http://127.0.0.1:8768` against the existing local Store. The recorded upgrade confirms unchanged source IFCs, project/revision/run/candidate inventories and served interface assets. It uses a frozen source copy with recovery disabled. The new generated-tree work remains a later development checkpoint and is not included in this package.

This is a validated local package checkpoint. Full directive coverage, all original mathematics, full production completion and public redistribution clearance remain incomplete.

Evidence: [completed package handoff](../evidence/release/coupled-portable-completed-82d3a00a6ff4/handoff.json), [sealed receipt](../evidence/dependencies/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4/sealed-handoff.json), [independent complete-package audit](../evidence/dependencies/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4/independent-seal/aee0cb2e283e45a9a9ca182c1ce1b9b4/result.json), and [validated local backend update](../evidence/release/validated-backend-pressure-update/1665a25f0e4341a1b3cc76d1b1041769/result.json). Earlier [52bd package](../evidence/dependencies/native-build/portable-candidates/52bd5d292171-2563efa50156/sealed-handoff.json), [43d9 validation](../evidence/dependencies/native-build/portable-candidates/43d9e1f20085-0334c44cd3ba/validation-summary.json), and [initial native build](../evidence/dependencies/native-build/handoff.json) remain historical evidence.
'''
(ROOT / "docs/native-portable-candidate.md").write_text(doc, encoding="utf-8", newline="\n")
caps_path = ROOT / "docs/capabilities.json"
caps = read(caps_path)
entry = next(x for x in caps["capabilities"] if x["id"] == "offline_installation_packaging")
links = [handoff_path.relative_to(ROOT).as_posix(), Path(h["sealed_handoff"]["path"]).relative_to(ROOT).as_posix(), Path(h["independent_final_audit"]["path"]).relative_to(ROOT).as_posix(), live.relative_to(ROOT).as_posix()]
entry["evidence"] = list(dict.fromkeys(entry["evidence"] + links))
entry["scope"] = "The local5e8 portable candidate is sealed with bundled Python3.12.14, custom native wheel, offline wheelhouse and six unchanged interface assets. All2467 frozen cases pass in both native environments; bundled2464 PASS plus three exactly named direct-interpreter bridge N/A. Offline workflow, two Python socket-denial probes and fresh real Office B2, two-outlet pressure and unequal-outlet pressure-tree rechecks pass. Independent final rehash accounts all14450 files/1980048071 bytes. Exact source/test/50-command provenance, earlier failures and corrected independent full-envelope replay are retained. The same5e8 source is live on8768 against unchanged Store/source inventories. Later generated-tree development is not included. Full directive and redistribution gates remain incomplete."
assert entry["status"] == "IN_PROGRESS" and len(caps["capabilities"]) == 15
caps["updated_at"] = "2026-09-15"
write(caps_path, caps)
progress_path = ROOT / "docs/PROGRESS.md"
progress = progress_path.read_text(encoding="utf-8").replace("Updated 2026-09-14.", "Updated 2026-09-15.", 1)
marker = "The global univalence specialization was committed"
paragraph = "The **5e8 unequal-outlet pressure backend package is sealed**, with all2,467 original/custom native cases passing and bundled2,464 PASS plus three exact direct-interpreter bridge N/A. Independent complete rehash confirms14,450 files/1,980,048,071 bytes; all three saved Office export rechecks and the offline analytic workflow pass. Exact50-command closure and corrected independent proof-summary replay are retained. The same frozen5e8 source is now live at **http://127.0.0.1:8768**, with all existing project/revision/run/candidate inventories, original source IFCs and six served interface assets preserved. Evidence: `evidence/release/coupled-portable-completed-82d3a00a6ff4/handoff.json` and `evidence/release/validated-backend-pressure-update/1665a25f0e4341a1b3cc76d1b1041769/result.json`. Later generated-tree development is under separate full validation and is not included in this sealed package.\n\n"
assert marker in progress
progress = progress.replace(marker, paragraph + marker, 1)
progress = progress.replace("The previously validated **52bd5d** backend is live at", "Historical launch: the previously validated **52bd5d** backend was restored at", 1)
progress_path.write_text(progress, encoding="utf-8", newline="\n")

directories = [handoff_path.parent, Path(h["sealed_handoff"]["path"]).parent, Path(h["preparation"]["path"]).parent, live.parent]
stage = set(sources + command_files + [ROOT / "docs/native-portable-candidate.md", caps_path, progress_path])
for directory in directories:
    stage.update(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"})
review_dir = ROOT / "evidence/release/coupled-portable-parent-review"
review_dir.mkdir(exist_ok=True)
copy = review_dir / "retain_pressure_package.py"
copy.write_bytes(Path(__file__).read_bytes())
result_path = review_dir / "result.json"
write(result_path, {"status":"PASS", "scope":"Parent verifies completed package handoff bindings and immutable live-update evidence; independent final audit supplies complete payload rehash", "handoff_sha256":sha(handoff_path), "current_application_source_files":len(actual), "required_command_records":len(commands), "command_file_count":len(command_files), "live_update_sha256":sha(live), "historical_failed_commands_retained":True, "public_redistribution_cleared":False, "full_production_complete":False, "retainer_sha256":sha(copy)})
stage.update([copy, result_path])
assert not subprocess.check_output(["git","diff","--cached","--name-only"],cwd=ROOT), "Index not empty"
paths = sorted(p.relative_to(ROOT).as_posix() for p in stage)
assert all(not p.startswith(("ui/", ".oma/", ".release/")) for p in paths)
pathspec = Path(__file__).with_suffix(".pathspec")
pathspec.write_bytes(b"\0".join((":(literal)" + p).encode("utf-8") for p in paths) + b"\0")
print(json.dumps({"status":"READY_TO_STAGE", "pathspec":str(pathspec), "files":len(paths), "retained_bytes":sum(p.stat().st_size for p in stage), "changed_sources":len(sources), "command_records":len(commands)},indent=2))
