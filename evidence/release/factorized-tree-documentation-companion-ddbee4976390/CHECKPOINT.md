# f73 checkpoint guide

Read this companion for the current compact/factorized backend and its API examples. The sealed package's `docs` directory is the historical EDF documentation captured before f73 documentation promotion. It is preserved exactly as tested. This companion is separately indexed; it changes no executable, test result, UI asset, Store, or package seal.

Start with [the shared-tree API guide](docs/shared-tree-generation.md), then the complete [five-sink](examples/shared-tree-5-sink-compact-request.json) and [eight-sink](examples/shared-tree-8-sink-compact-request.json) requests. Those coordinates and physical assumptions describe analytic fixtures. Supply a building project's own justified terminals, zones, fittings and boundary data; these examples do not certify a building mission.

The [compact top-K contract](docs/math/shared-tree-topk.md) describes exact finite-catalogue counts/ranking. The [factorized pressure contract](docs/math/factorized-tree-pressure.md) describes the strengthened bounded local proof. Each physical candidate still requires current native geometry, metrics, same-model local/global pressure verification, delivery and velocity checks, acceptance, and fresh export verification. The original mathematics and whole-building routing are not complete; retained Hospital attempts remain unresolved.

## Validated package

- Source checkpoint: `f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21`; 114 application files.
- Bundled checker: `oma-independent-checker/2:3492e0f42f803ff71dea9c70558bdd276c4b5469a3d17c00ae7c37b59dda7541`; standalone Python 3.12.14.
- Original and custom native suites: 3,275 passed each, zero failures/skips.
- Exact same 305-input bundled suite: 3,272 passed and three named direct-interpreter bridge cases not applicable. Those three passed in the two other environments.
- Offline import/collision/route/accept/export workflow, both Python network-denial modes, and three saved Office IFC rechecks passed. The Office records retain B2 fitting use, two-sink pressure and unequal three-sink pressure scopes separately.
- Package index: `de03e716e647f7ec8902f8ad793dc64f2355c2c763d849b8653b5f929030e01c`. The separately retained seven/eight-sink native fixtures and all new 4–8-sink regression cases do not establish Hospital or unrestricted building success.

Default generation remains FULL_LEDGER with 2,000,000 work units. Compact generation is explicit; the eight-sink example uses the bounded 48,000,000 work/32 MiB policy. Exhaustion is not a proof of feasibility, impossibility or optimality. Pressure, loss and native bore assumptions remain declared modeling assumptions.

## Launch and restore

1. Check the release ZIP SHA256 in its archive manifest, then extract into a new directory. Keep earlier packages separate.
2. Open the extracted package folder and run `OMA.cmd`, or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-OMA.ps1`. This package launcher defaults to port **8765**, so its default URL is **http://127.0.0.1:8765**. `Start-OMA.ps1 -Port <port>` explicitly selects another port; follow that invocation's actual URL.
3. The separately owned validated workspace service used **8768** at this handoff. That service and its Store are distinct from the extracted package; do not assume its URL opens the new copy.
4. Data is a separate backup. Preserve the original Store/source archives and follow their backup/restore instructions to restore into a new location. This runtime ZIP contains no Hospital/IFC-Bench source dataset and does not replace the data backup.

All documentation/example bytes below come from published commit `633a6cdbcd75a24b0146f4d8228edef1bc0c4046`; the guide above adds actual final package counts and restoration details. `docs/PROGRESS.md` is captured workspace history and may describe packaging as pending at its earlier capture; use this CHECKPOINT.md and the final package receipts for completion status. Links from copied contracts to external evidence refer to the separately retained repository/backup evidence, not additional files implicitly certified by this companion. Use the [immutable documentation/source commit](https://github.com/DaviBaum/oma-ananke-backup/tree/633a6cdbcd75a24b0146f4d8228edef1bc0c4046) and its [mathematical evidence directory](https://github.com/DaviBaum/oma-ananke-backup/tree/633a6cdbcd75a24b0146f4d8228edef1bc0c4046/evidence/math) for those references; access requires permission to the private backup repository.
