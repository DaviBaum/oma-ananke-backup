# Validated compact topology and pressure portable checkpoint

Download the [private f73 portable release](https://github.com/DaviBaum/oma-ananke-backup/releases/tag/validated-compact-pressure-2026-09-15), verify the ZIP hash in its archive manifest, and extract into a new directory. Read `f73-checkpoint-documentation/CHECKPOINT.md` first. Then run `OMA.cmd` inside `f73a8793ae0d-ddbee4976390`. The package defaults to **http://127.0.0.1:8765**; `Start-OMA.ps1 -Port <port>` selects another port. The separately running workspace service at port 8768 is a different instance.

The three release assets total **1,175,670,105 bytes**. The ZIP contains the sealed application package and a separately indexed current documentation companion. Its SHA-256 is `9d9ba8b2a6710d049ea58fe369703a1fbce992b96410413eb7f3e2a08cb5d035`. The package's original documentation remains its historical capture; the companion supplies the current generation API, complete five/eight-terminal examples and mathematical contracts without changing the tested payload.

The sealed package contains **14,625 indexed files and 1,993,462,494 logical bytes**, with index SHA-256 `de03e716e647f7ec8902f8ad793dc64f2355c2c763d849b8653b5f929030e01c`. Its 114 application files have source identity `f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21`.

| Runtime | Checker identity | Completed exact validation |
|---|---|---|
| Original Python/native environment | `f73a8793ae0d` | 3,275 passed; zero failures/skips |
| Separately built native environment | `a4aa129a2d19` | 3,275 passed; zero failures/skips |
| Bundled Python 3.12.14 | `3492e0f42f80` | 3,272 passed; three named direct-interpreter bridge cases not applicable |

All three executions retain the same 305 test/support inputs and 3,275 exact case identities. The three bridge cases passed in both other environments. The custom native extension has SHA-256 `398b43db6952d07645d4fbea2c23c73cb83696369871e22880b85a8c35bfd875`.

Generated four-through-eight-terminal analytic fixtures complete native checking, acceptance and fresh export. The bundled runtime also freshly checks three saved Office export roles: the two-route fitting-budget case (4,818 source pairs and five cross-route pairs), two-outlet pressure network (3,212 source pairs, six component pairs, nine ports), and unequal-outlet pressure tree (5,621 source pairs, 21 component pairs, 16 ports). Independent replay checks their bound model, source, native report and service evidence. These remain distinct declared engineering models.

The offline import/check/accept/export workflow and both Python network-denial probes pass. The latter are Python audit-hook checks, not an operating-system firewall. The six compiled interface assets remain unchanged.

Evidence: [completed package](../evidence/release/factorized-tree-portable-completed-ddbee4976390/handoff.json), [verified upload](../evidence/release/github-compact-portable/5f95cfb7b71341e88756c644711c81e0/completed-handoff.json), [current backend](PROGRESS.md), and [backup/restore instructions](GITHUB_BACKUP.md). Original mathematics, unrestricted physical routing, whole-hospital verification and full production readiness remain incomplete. Earlier [EDF recovery](https://github.com/DaviBaum/oma-ananke-backup/releases/tag/validated-general-tree-2026-09-15) and [5e8 checkpoint](checkpoint-portable-5e8.md) remain separate immutable versions.
