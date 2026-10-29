# Research launch checkpoint

The requested 100-worker implementation run has **not started**. The user explicitly retained exactly 100 simultaneous `gpt-6.1-sol` workers at `max` under `gpt-6-astra`, and asked preparation to continue in this conversation. This conversation exposes four total slots, including the coordinator. A smaller implementation pool has not been substituted.

## Verified preparation

- Project-only [.codex/config.toml](../.codex/config.toml) requests Astra/Max coordination, 100 worker slots and Sol/Max defaults. A fresh read-only app-server `config/read` confirmed the effective settings. This did not create a model thread or change the current conversation's capacity. The account rate-limit API responded, but does not expose worker concurrency entitlement. See [effective configuration](../evidence/research/preflight-20261029/effective-config-final.json).
- Obsidian 1.14.5 was installed from its official signed Windows distribution. The dedicated vault is `C:\Users\Davi\Downloads\oma\research\OMA-ANANKE`, registered as `08b3f88e8d0388da`. A project note was written, read back byte-for-byte, and observed in the Obsidian app after opening its supported URI. Access uses filesystem plus URI; CLI is not enabled and cloud sync was not configured. See [access verification](../evidence/research/preflight-20261029/obsidian-verification.json) and [vault home](../research/OMA-ANANKE/Home.md).
- The recursive source census covers 24 files, 37,604,331 bytes and 8,018 ZIP file members, including hidden/ignored metadata and repeated member names. [V3 inventory](../evidence/research/preflight-20261029/recursive-inventory-v3.json) replay found no source changes. Its source-tree hash uses paths relative to `math1`; older inline inventory used paths relative to the repository, so their tree digests intentionally differ.
- The [primary occurrence seed](../evidence/math/occurrence-review-20261029/status.json) retains 242,141 distinct locations in ten compressed JSONL files, all `UNREAD`. Its [independent replay](../evidence/research/preflight-20261029/occurrence-seed-review.json) found no dropped/duplicated locations or binding errors. Each range has different planned primary/reviewer slots. **Direct reads credited: 0. Independent mathematical reviews credited: 0.** The final zero-omission denominator remains open; equations, table contexts/cells, ancillary/native graphical objects, metadata dispositions and PDF visual obligations still require explicit expansion and review.
- The [planned roster](../evidence/research/preflight-20261029/planned-roster.json) preserves all twenty requested five-worker groups. It reserves 100 owned note directories and initial reading ranges. Every actual agent ID, effective-model confirmation, start time and heartbeat remains null. A single separate Sol/Max-requested preflight helper performed bounded inventory and ledger checks; it is not the requested implementation pool.
- Fourteen focused preflight tests pass. They exercise immutable originals/prior evidence, duplicate archive names, invalid prior inventories, extraction/source mutation, duplicate occurrence identities and zero reading credit. These are tooling checks, not new backend regression or engineering approval. [Test evidence](../evidence/research/preflight-20261029/preflight-tests.xml).

## Commands

Run from `C:\Users\Davi\Downloads\oma` with the existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe scripts/research_source_inventory.py --check evidence/research/preflight-20261029/recursive-inventory-v3.json
.\.venv\Scripts\python.exe -m pytest tests/test_research_source_inventory.py tests/test_research_occurrence_seed.py -q
.\.venv\Scripts\python.exe scripts/research_runtime_preflight.py --output evidence/research/preflight-20261029/effective-config-next.json
.\.venv\Scripts\python.exe scripts/research_prepare_vault.py
```

The runtime command requires a fresh output filename and launches no agent/model turn. The vault generator permits exact idempotent replay but refuses to overwrite changed notes. The original seed is retained; recreating it requires a fresh destination:

```powershell
.\.venv\Scripts\python.exe scripts/research_occurrence_seed.py --audit evidence/math/occurrence-review-20261029/source-audit.json --output evidence/math/occurrence-review-next
```

Open `obsidian://open?vault=OMA-ANANKE&file=Home` to view the research record.

## Required next actions

1. In a session with the requested Astra coordinator, inspect the **actual** available worker capacity and effective model settings. Reading a file with `100` in it is insufficient. Current-conversation capacity remains three workers. Account/host access may impose an additional limit even after a new session loads the configuration. Do not bypass limits or change billing.
2. Only when the required capacity exists, launch exactly 100 genuine workers with explicit Sol/Max settings and fresh complete briefs. Update the reserved roster with observed IDs, confirmed settings, timestamps and actual states. Preserve one owner per shared file/module and outside-group independent review. The reserved assignment notes are not proof of running workers.
3. Expand the occurrence seed into complete structural/native/visual obligations. Preserve original P7/P26 source gaps, the damaged native table cell and missing canonical archive provenance. Then execute actual reading and mathematical review; summaries and extraction must not increase those counters.
4. Reconcile current engine code and evidence against the full sources. `docs/capabilities.json` remains the capability authority. The larger algorithm and full production readiness remain incomplete. No application algorithm changes were made by this preflight.
5. The concrete installed-model target from the existing checkpoint is generic circular-profile/trimmed-circle `IfcSurfaceCurveSweptAreaSolid` reconstruction, mapped endpoints/tangents/radius/section and owned-port correspondence. Continue to fixed-boundary installed-subgraph replacement, checked removal/reconnection, and fresh edited IFC reimport/geometry/service checks. This is one required increment, not completion of Ceiling Router + ANANKE or of the whole hospital.

## Ownership and preserved work

Coordinator owns the four new `scripts/research_*.py` tools, two new preflight test modules, project agent config, this checkpoint, the copied research directive, generated vault views, `evidence/research/preflight-20261029/` and `evidence/math/occurrence-review-20261029/`. The preflight helper owned only `source-ledger-audit.json` and `occurrence-seed-review.json` within that evidence directory. All requested implementation worker worktrees remain uncreated and code ownership unassigned until launch/contracts.

Original `math1` and acquired IFCs were not written. Existing live engine processes, customer deployment and unrelated UI/evidence changes were preserved. Installer binaries are locally retained and excluded from Git. `docs/PRODUCTION_DIRECTIVE.md` remains unaltered; [the new directive](RESEARCH_DIRECTIVE_20261029.md) is a byte-identical copy of the latest supplied attachment (SHA-256 `89f5adb002293898f5c3e16178e6403c1c51b6e85ada8273492a59bc9d605fa6`).

Configuration references: [official Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents), [effective configuration RPC](https://learn.chatgpt.com/docs/app-server), [Obsidian URI](https://help.obsidian.md/Extending+Obsidian/Obsidian+URI).
