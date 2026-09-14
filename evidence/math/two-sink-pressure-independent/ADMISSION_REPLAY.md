# Physical report admission: retained failure and corrected replay

This audit concerns the separately staged pressure backend. It does not alter the
sealed `43d9` portable package, the production Store, original building IFC files,
or the earlier validation evidence.

## Retained defect

`81a7d567cf424654ba3ea883af348d16/result.json` reproduces the defect on frozen
`b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895`.
A genuine managed native network check passed for four physical components, four
component/source pairs and the complete component self check. Removing only the
`network-pressure-operating-point` result from its passing report allowed both
an unmanaged `record_verification` call and a trusted managed
`finish_check_execution(COMPLETED)` call to publish `CHECKED`. Both candidates
were then accepted, advancing their separate private project copies from
revision 1 to revision 2.

`audit.json` confirms the original completed execution, the exact one-result
omission, and the fact that normal candidate selection already rejected the
omission. It also documents a correction to the initial diagnostic selection
call's objective weights. That diagnostic correction did not affect either
publication/acceptance reproduction.

This is an omission at a trusted report-producer/caller boundary. No ordinary API
exploit, forged native computation, or fabricated process-supervision receipt is
claimed. Original and narrowed reports, actual IFC files, native and pressure
artifacts, cloned Stores, fixture hashes and the reproduction scripts are
retained.

## Corrected native replay

`admission-replay-81f8e61208344be8af2f2a020abcf883/result.json` records **21 passing
cases in 9.705 seconds** on frozen
`bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac`.

Each of the following report cases was exercised through unmanaged publication,
managed publication, and acceptance of an explicit historical unmanaged
`CHECKED` row installed only in a private test Store:

- Intact native report: publication, selection and acceptance pass.
- Missing required pressure check: rejected.
- Duplicate required check: rejected.
- Required check changed to `NOT_APPLICABLE`: rejected.
- Narrowed overall scope: rejected.
- Wrong mission hash: rejected.
- Wrong rule hash: rejected.

Every invalid publication stayed out of `CHECKED`; every invalid acceptance left
the project head unchanged. The genuine native fixture's head, source IFC and
materialized IFC remained unchanged. Complete native reports, per-case report
variants, copied Stores, fixture hashes and results are retained under that
attempt directory.

The command was:

```powershell
.venv/Scripts/python.exe evidence/math/two-sink-pressure-independent/replay_admission.py --source .oma/development/two-sink-pressure/validation-runtimes/runtimes/bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac/src --checker-version oma-independent-checker/2:bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac
```

Each invocation creates a new evidence directory and preserves all older
attempts. The native fixture is synthetic; the separate real Office campaign
provides real-building evidence. These tests establish the exercised admission
boundaries, not unrestricted mathematical or physical correctness.
