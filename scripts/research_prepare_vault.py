"""Prepare linked Obsidian views and a planned roster; never launch or impersonate workers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "research/OMA-ANANKE"
EVIDENCE = ROOT / "evidence/research/preflight-20261029"
SEED = ROOT / "evidence/math/occurrence-review-20261029"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, text: str) -> None:
    """Create an owned note atomically; preserve every existing unrelated edit."""
    raw = text.encode("utf-8")
    if path.exists():
        if path.read_bytes() == raw:
            return
        raise FileExistsError(f"Existing content differs; explicit reconciliation required: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    # Windows rename fails if destination appeared concurrently.
    temporary.rename(path)


def note(name: str, body: str, identifier: str) -> None:
    write_new(VAULT / (name + ".md"), f"---\nid: {identifier}\nstatus: preparation\nowner: coordinator\n---\n\n# {name}\n\n{body.rstrip()}\n")


def main() -> None:
    directive = (ROOT / "docs/RESEARCH_DIRECTIVE_20261029.md").read_text(encoding="utf-8-sig")
    groups = re.findall(r"^(\d{3})–(\d{3}): (.+)$", directive, re.MULTILINE)
    if len(groups) != 20:
        raise ValueError("Expected exactly twenty five-worker groups from the user's directive")
    seed = json.loads((SEED / "status.json").read_text(encoding="utf-8"))
    if seed["direct_read_occurrences"] != 0 or seed["complete_corpus_ledger"] is not False:
        raise ValueError("This preparation view must not overwrite a campaign with review progress")
    role_names = ["source analysis", "implementation", "independent reference method", "adversarial review", "integration and performance"]
    role_deliverables = [
        "Derive a source-bound mathematical contract, assumptions, dependency list and proof gaps. Attach precise native locators and counterexamples where needed.",
        "Implement the agreed contract in an exclusively assigned worktree after the source and interface reviews. Supply callable behavior, failure semantics and meaningful tests.",
        "Develop an independently reasoned small-instance reference method and reproducible oracle cases; identify common dependencies with the production implementation.",
        "Attempt to falsify the group's assumptions, bounds, geometry and certificates using independent calculations, adversarial inputs and malformed evidence.",
        "Integrate the agreed interfaces and measure end-to-end behavior, cancellation, replay and resources on the predeclared benchmark scope.",
    ]
    workers = []
    for first, last, responsibility in groups:
        for number in range(int(first), int(last) + 1):
            slot = f"{number:03}"
            role = (number - 1) % 5
            review_slot = f"{(number + 49) % 100 + 1:03}"
            reads = seed["planned_primary_assignments"][slot]
            reviews = seed["planned_primary_assignments"][review_slot]
            worker = {
                "worker_id": slot, "state": "NOT_STARTED_CAPACITY_BLOCKED",
                "actual_agent_id": None, "requested_model": "gpt-6.1-sol", "confirmed_model": None,
                "requested_reasoning_effort": "max", "confirmed_reasoning_effort": None,
                "group_responsibility": responsibility, "role": role_names[role],
                "deliverable": role_deliverables[role], "primary_ranges": reads, "independent_review_ranges": reviews,
                "external_reviewer_slot": review_slot, "actual_worktree": None,
                "owned_code_files": [], "code_edit_permission": "UNASSIGNED_UNTIL_CONTRACT_AND_FILE_OWNERSHIP_REVIEW",
                "owned_notes_directory": f"research/OMA-ANANKE/Workers/{slot}",
                "started_utc": None, "heartbeat_utc": None, "finished_utc": None,
                "completion_evidence": [], "blockers": ["Current conversation permits three workers; exactly 100 simultaneous workers required."],
            }
            workers.append(worker)
            lines = [f"**Not started.** This is a reserved assignment, not a running agent.",
                     f"Requested: `gpt-6.1-sol`, reasoning `max`. Actual agent ID, confirmed model and effort: **unavailable until launch**.",
                     f"Responsibility: {responsibility}", f"Role: {role_names[role]}. {role_deliverables[role]}",
                     "Read the full user directive and AGENTS.md first. All sources in math1 and acquired IFCs are read-only. Read both Ceiling Router and ANANKE/integration dependencies necessary for this task; assigned census ranges are only the initial coverage allocation.",
                     "Primary reading ranges (inclusive):"]
            lines.extend(f"- `{r['document_id']}`: {r['first_ordinal']}–{r['last_ordinal']} ({r['count']} primary locations)." for r in reads)
            lines.append("\nIndependent review ranges (inclusive):")
            lines.extend(f"- `{r['document_id']}`: {r['first_ordinal']}–{r['last_ordinal']} ({r['count']} primary locations)." for r in reviews)
            lines.extend([f"\nExternal reviewer of your primary ranges: [[Workers/{review_slot}/Assignment|slot {review_slot}]].",
                          "Every attached equation, table, native object and visual ambiguity must also be examined. These ranges do not cover all pending child units. Record only actual direct reads; do not inherit historical correspondence credit.",
                          f"Your contribution area is `research/OMA-ANANKE/Workers/{slot}/`. Only the coordinator writes shared indexes. Application file ownership and a separate worktree must be assigned before edits.",
                          "All accepted results must bind persisted state, input bytes, mission, rules, numerical model and software. Timeout, missing inputs, unsupported geometry and restricted search cannot establish feasibility or global optimality.",
                          "Return exact source locators, changed files, independent checks, reproducible commands, current blockers and the next executable step. Do not work on UI polish or marketing.",
                          "[[Mission]] · [[Reading ledger]] · [[Implementation contracts]] · [[Verification]] · [[Open problems]] · [[Worker roster]]"])
            note(f"Workers/{slot}/Assignment", "\n\n".join(lines), f"OMA-PLAN-WORKER-{slot}")
    roster = {
        "schema": "oma.research.planned-roster/1", "created_utc": seed["created_utc"],
        "requested_coordinator_model": "gpt-6-astra", "coordinator_model_attestation": None,
        "required_simultaneous_workers": 100, "actual_implementation_workers_launched": 0,
        "requested_pool_running": False, "source_seed_status_sha256": sha(SEED / "status.json"),
        "capability_authority": "docs/capabilities.json", "workers": workers,
        "preflight_helper": {"task_id": "/root/preflight_source_ledger", "requested_model": "gpt-6.1-sol", "requested_effort": "max",
                             "state": "COMPLETED", "effective_model_attestation": "NOT_RETURNED_BY_TOOL", "part_of_requested_pool": False},
    }
    write_new(EVIDENCE / "planned-roster.json", json.dumps(roster, ensure_ascii=False, indent=2) + "\n")
    table = "| Reserved slot | Role | State |\n|---|---|---|\n" + "\n".join(
        f"| [[Workers/{w['worker_id']}/Assignment|{w['worker_id']}]] | {w['role']} | Not started |" for w in workers)
    note("Worker roster", f"**0 of the requested 100 implementation workers launched.** The separate preflight helper completed a bounded inventory audit; it is not the implementation pool.\n\nMachine authority: `evidence/research/preflight-20261029/planned-roster.json`. Every session ID, start time and model confirmation stays null until observed.\n\n{table}\n\n[[Mission]] · [[Reading ledger]]", "OMA-ROSTER")
    note("Mission", "Implement the complete applicable Ceiling Router + ANANKE/OMA approach and all five integration families for entire buildings, improving the approach where independent evidence supports it. Exceptional results must preserve engineering requirements and survive independent checking.\n\nUser directive: `docs/RESEARCH_DIRECTIVE_20261029.md`. Original production directive: `docs/PRODUCTION_DIRECTIVE.md`. Repository instructions: `AGENTS.md`.\n\nExactly 100 real Sol workers at max reasoning under Astra are required simultaneously. Current session capacity is insufficient; no smaller implementation pool has been substituted.\n\nAcceptance has eight separate axes: corpus inventory, actual reading/review, mathematical validation, implementation, integration, independent verification, complete-building coverage and release readiness. No combined reassuring completion percentage.\n\n[[Home]] · [[Worker roster]] · [[Source inventory]] · [[Reading ledger]] · [[Release readiness]]", "OMA-MISSION")
    inventory = json.loads((EVIDENCE / "recursive-inventory-v3.json").read_text(encoding="utf-8"))
    source_table = "| Source path relative to math1 | SHA-256 |\n|---|---|\n" + "\n".join(f"| `{s['path']}` | `{s['sha256']}` |" for s in inventory["files"])
    note("Source inventory", f"24 files, 37,604,331 bytes and 8,018 archive file members inventoried. Hidden/ignored metadata is included. This is byte accounting, not reading.\n\nAuthority: `evidence/research/preflight-20261029/recursive-inventory-v3.json`. Tree hash: `{inventory['source_tree_sha256']}` (paths relative to math1). Replay with `python scripts/research_source_inventory.py --check evidence/research/preflight-20261029/recursive-inventory-v3.json`.\n\n{source_table}\n\n[[Reading ledger]] · [[Open problems]] · [[Mission]]", "OMA-SOURCES")
    note("Reading ledger", "242,141 primary extracted locations are seeded UNREAD in ten compressed JSONL shards. Direct reads credited in this new campaign: **0**. Independent mathematical reviews credited: **0**.\n\nAuthority: `evidence/math/occurrence-review-20261029/status.json`. Independent structural replay: `evidence/research/preflight-20261029/occurrence-seed-review.json`. All occurrences retain distinct IDs, hashes and native locators. Planned primary/reviewer slots differ. No actual worker IDs are assigned.\n\nThe final zero-omission denominator is **not frozen**. Remaining structural/visual units include 1,616 DOCX equations, 750 DOCX table contexts, 264 Pages tables and 16,811 cells, ancillary parts, auxiliary text stores, 791 PDF pages, graphical/native objects and metadata dispositions. These categories overlap primary locations and must not be added into a misleading completion percentage.\n\nHistorical substitutions/correspondence remain contextual evidence. They do not satisfy this campaign's direct-reading requirement.\n\n[[Source inventory]] · [[Worker roster]] · [[Open problems]] · [[Verification]]", "OMA-READING")
    topics = {
        "Definitions and assumptions": "Maintain source-version-qualified symbols, physical units, coordinate frames, assumptions and applicability domains. Resolve conflicting definitions before implementation. No new mathematical definitions are asserted by this preparation note.",
        "Equations and proofs": "Each substantive equation, quantifier, proof step and exception needs a source locator, preserved native structure, a primary reader and an independent reviewer. Proof validation is separate from executable tests and extraction completeness.",
        "Ceiling Router": "Read `math1/math1/CEILING_ROUTER_COMPLETE_MATHEMATICAL_TECHNICAL_ANALYSIS.md` completely, including physical routes, homotopy, inner/outer approximations, sizing/fabrication lifts and independent checks. Derive executable contracts from the source; a family-name summary is not the implementation.",
        "ANANKE OMA": "Read originals, reconstructed canonical material, repairs and integration source independently. Preserve version namespaces and repeated occurrences. Existing bounded obligations do not establish implementation of the complete original algorithms.",
        "Integration families": "Reconcile all five families: SIR (typed spatial state and ports), RTR (multisystem physical routing), JCD (authorized architectural/routing co-design), DYN (robust scenarios and recourse), CMP (persistent state and certificate composition). The complete integration DOCX is authoritative source material; this index is not a substitute for reading it.",
        "Dependencies": "Bind each source occurrence to definitions, assumptions, proof obligations, implementation callables, independent checkers and benchmarks. Reconcile with `evidence/math/traceability_register.json` and `docs/capabilities.json`; do not create a second capability authority.",
        "Amendments": "Recheck existing amendments in `docs/math/implementation-contract.md`. A replacement needs the original statement, proof gap or counterexample, corrected formulation, changed assumptions, preserved capabilities, independent checks and benchmark evidence. Do not invent missing original P7/P26 text.",
        "Design decisions": "Compare approaches under identical missions and declared budgets. Record rejected alternatives and unfavorable results. A replacement may improve the method, but universal optimality or superiority requires a valid proof and a stated domain.",
        "Implementation contracts": "Capability authority remains `docs/capabilities.json`; engine priorities and prior coverage are in `docs/math/required-engine-priorities.md` and `docs/math/source-capabilities.md`. Define types, units, invariants, failure states and certificate bindings before shared-module edits. Each source-to-code link must name a production callable and an independent check.",
        "Verification": "Check persisted output independently of optimizer flags and caches. Bind original bytes, canonical root, mission, rules, numerical model, checker/software versions and search universe. Preserve missing-input, unsupported, ambiguous, timeout, cancellation, infeasibility and bounded-optimality outcomes separately. Preflight tests and ledger replay are not building-engine validation.",
        "Building benchmarks": "Use immutable acquired IFC-Bench provenance. Required buildings: West Riverside Hospital, Digital Hub, Sixty5, WBDG Office, Dental Clinic and Duplex, with compatibility checks on the remaining corpus. Separate IFC2x3 and IFC4 alternative federations. Account for all systems, floors, objects and unresolved inputs. Compare actual installed geometry and performance; report gross material savings, net installed costs and total construction budgets separately.",
        "Open problems": "Execution blocker: current conversation supports three workers, while the user retains exactly 100 simultaneous workers. A fresh effective configuration accepts100, but account/host concurrency is unproven. Source gaps: original P7 body, original P26 opening and proof steps1–13, a damaged Pages table formula cell, and missing canonical archive provenance. Full visual/native-object coverage and full mathematical proof review remain open. Hospital materials, duties, jurisdiction and design criteria remain missing; no construction approval follows from inventory.",
        "Release readiness": "Full mathematics and full production readiness remain incomplete. No backend optimization was added by this preflight. Next installed-model work from `docs/PROGRESS.md`: generic circular-profile trimmed-circle IfcSurfaceCurveSweptAreaSolid fitting reconstruction, native port correspondence, fixed-boundary installed-subgraph replacement, checked removal/reconnection and fresh IFC export/recheck. Keep functional/unsupported components fixed. The entire-building algorithm still needs the broader source-derived mechanisms and independent gates.",
        "Reproducibility": "Use `.venv/Scripts/python.exe` (Python 3.12). Workstation detected: Ryzen 7900X3D, RTX 3090 with 24 GiB VRAM, approximately 128 GB system memory. The delivered engine must run locally without a mandatory hosted model or Obsidian. Keep native/GPU campaigns resource-limited even when 100 reasoning workers are active. Source hashes, commands and preflight results live under `evidence/research/preflight-20261029/`.",
    }
    for title, body in topics.items():
        note(title, body + "\n\n[[Home]] · [[Mission]] · [[Source inventory]] · [[Reading ledger]] · [[Worker roster]]", "OMA-" + title.upper().replace(" ", "-"))
    links = ["Mission", "Source inventory", "Reading ledger", "Worker roster", *topics]
    note("Home", "Research preparation is complete enough to resume safely; the requested 100-worker implementation run is **not started**. This vault is registered in Obsidian and file write/read plus app display were verified.\n\n" + "\n".join(f"- [[{title}]]" for title in links) + "\n\nRepository authority: `docs/capabilities.json`. Source ledgers and evidence remain machine-readable repository records. Shared notes are coordinator-owned; workers have separate contribution directories.\n\n[[Connection check]]", "OMA-HOME")
    print(json.dumps({"vault": str(VAULT), "reserved_assignments": len(workers), "actual_implementation_workers_launched": 0,
                      "primary_occurrences_unread": seed["primary_occurrences"], "new_reading_credit": 0}))


if __name__ == "__main__":
    main()
