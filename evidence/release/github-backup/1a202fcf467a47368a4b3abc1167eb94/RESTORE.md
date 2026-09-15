# Restoring this private backup

The Git repository retains committed application source, evidence, and history. Clone it normally. The current validated source checkpoint is 33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95. The runtime archive is the separately validated older 5e8 package; its original proofs remain unchanged and do not certify newer source automatically.

Download all ZIP parts for each desired label into a new directory. Verify each SHA256 against backup-assets-manifest.json before extraction. Each part is an independent ZIP: extract every part into the same EMPTY restore directory. Do not overwrite the original workspace. ZIP member identities were independently read and hashed after creation.

- original-mathematics: original math1 contents, preserved verbatim.
- hospital-original-models: all 14 original hospital IFC files (seven disciplines in each of IFC2x3 and IFC4), plus the original license and model card. No new hospital result is claimed by this backup.
- ui-working-state: raw two changed UI files, 11 QA files, and a binary diff against the pre-backup commit. Review before applying to any checkout; the Git backup may already include them.
- current-project-store: portable Store with immutable roots, report/source/materialization closure and database. With the checked-out source and dependencies available, call oma.backup.verify_backup(path). To create a NEW operational Store, use oma.backup.restore_store(path, new_destination); never restore over the live original. Restored runs do not inherit live process ownership. Existing reports may require fresh verification under a different checker or runtime.
- sealed-runtime-5e8: all files of the unchanged sealed Windows portable candidate. Extract all parts together, read its README.md and CANDIDATE-STATUS.txt, then use its launcher. Its public redistribution status remains NOT_CLEARED; this backup repository is private.

No active process, virtual environment, whole private development tree, duplicated benchmark caches, or every historical temporary Store is claimed to be included. The supported current Store closure, original math, hospital inputs, source/evidence/history, UI work and sealed runtime are explicitly covered.
