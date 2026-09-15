# GitHub backup and recovery

The private backup repository is [DaviBaum/oma-ananke-backup](https://github.com/DaviBaum/oma-ananke-backup). It retains the application's full Git history, implementation, tests, source-math traceability and committed validation evidence. The local `origin` remote points to it.

The private [backup-2026-09-15 prerelease](https://github.com/DaviBaum/oma-ananke-backup/releases/tag/backup-2026-09-15) is complete: 13 assets totaling 4,152,478,214 bytes. Archive members were independently reread and hashed, and uploaded asset sizes and SHA-256 digests match GitHub's records. Download `BACKUP-COMPLETE.json` for the recovery index. The [completed handoff](../evidence/release/github-backup/1a202fcf467a47368a4b3abc1167eb94/completed-handoff.json) retains the verification evidence. This is a backup release, not a claim that the complete production directive is finished.

The recovery set includes the original mathematical source documents, hospital IFC source files with their attribution/license/card, the existing sealed portable runtime, a verified snapshot of the live project Store, and the uncommitted UI work preserved separately. Reproducible caches and installed development dependencies are not the project backup's source of truth.

## Restore code and evidence

Clone the private repository using an account with access. Application, test and script bytes are preserved by `.gitattributes`, because checker identities depend on exact file bytes. Read `docs/PROGRESS.md` and the checkpoint receipt it links before selecting a runtime or replaying an older report.

## Restore archived assets

Download the required completed release assets and their manifests. Verify their SHA-256 values before extracting them. Original `math1/` documents and IFCs must remain unchanged. Hospital input coordinates and discipline alignment remain separate engineering obligations; possessing the original files does not establish federation alignment.

For a portable Store backup, extract every numbered part into the same new directory, preserving relative paths. Use `oma.backup.verify_backup` on the extracted directory. `oma.backup.restore_store` creates a separate restored Store, checks every recorded asset and database root, and does not inherit live worker ownership. Choose a new destination; do not overwrite an existing project Store.

The sealed portable package contains source5e8. The generated-tree backend at this backup's initial Git checkpoint contains source33a. They are distinct validated versions. Restore the sealed package as its own directory and launch its `OMA.cmd`; do not replace its source files and continue calling it the original sealed package. The repository's current code and pinned development/runtime requirements provide the newer application checkpoint.

The saved UI working files are a backup of unfinished work. They are separate from the six compiled interface assets used during backend validation.

## Validated general-tree portable checkpoint

The newer [validated-general-tree-2026-09-15 prerelease](https://github.com/DaviBaum/oma-ananke-backup/releases/tag/validated-general-tree-2026-09-15) contains the sealed EDF portable ZIP, its manifest and restore instructions: three assets totaling 1,174,189,376 bytes. GitHub's SHA-256 digests and sizes match all local assets. The ZIP digest is `ba61710a0cd3f02a5be9f3021c55ac3c7aef10f632ec33fe4c032556e8292eb0`.

This package contains source `edf555760245` and bundled checker `b1f5ee819e5e`, with 14,578 sealed files. Its bundled suite passed 3,009 tests; three named direct-interpreter bridge tests do not apply to that runtime and pass in both other native environments. All three saved Office export roles passed fresh native rechecks. See the [verified release receipt](../evidence/release/github-edf-portable/completed-218ccb24ff4d4ba7824d1187b95f57e4/completed-handoff.json) and [independent package audit](../evidence/release/edf-portable-peer/sealed-2687db76a91942c9b137dacfcaa7b2fe/result.json).

Extract this package into a new directory and use its own `OMA.cmd`. The subsequent compact topology and factorized pressure implementation has a different source identity and is not included in this EDF ZIP. Existing recovery releases remain intact.

## Ongoing hospital and mathematics work

Hospital results and subsequent completed mathematical checkpoints are committed and pushed as they finish. Each report states its exact source model, coordinate assumptions, tested scope, failure/unknown outcomes, runtime identity and export verification. Incomplete runs are retained as incomplete evidence, never counted as successful validation.
