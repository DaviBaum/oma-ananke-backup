# Validated native and portable candidate

The current isolated portable package is `.release/native-build/portable-candidates/f48d7c5261a7-ac832a6e2ba2/`. It contains the tested `f48d7c52...` application source, the existing workbench build, Python 3.12.14, 59 pinned local runtime wheels, installation/start scripts and source/patch/notice provenance. `OMA.cmd` and `Start-OMA.ps1` are its entry points. The complete package index contains 14,762 files and 1,981,288,526 logical bytes. Its index SHA-256 is `3771606992aa75e1ba8ec384e6c82bb5ff671a42674d61ffaee70b3a29ea5dcb`.

The custom IfcOpenShell wheel was built separately from pinned commit `1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2`, OCCT 7.8.1, Boost 1.86, Eigen 3.3.9 and SWIG 4.2.1, with CGAL disabled. A minimal declared SWIG patch makes the always-available generic coordinate templates available in this build variant. Original source archives, applied patches, compiler/configuration records and completed/failed build attempts are retained. The loaded extension SHA-256 is `398b43db6952d07645d4fbea2c23c73cb83696369871e22880b85a8c35bfd875`; its full hash is embedded in the distinct package version. The active original environment remains unchanged.

Source and interpreter identities are kept separate:

| Execution | Checker identity | Validation |
|---|---|---|
| Original Python/native runtime, current source | `f48d7c52...` | 1,100 full tests; 15 later native-zone safeguards separately checked; actual Office acceptance and exported-byte recheck |
| Python 3.12.10 with custom native wheel, identical current source | `5a1ebed5...` | All 1,115 frozen current tests pass in 301.94 s; same real Office export passes in 24.062 s |
| Bundled Python 3.12.14 with custom wheel and identical source | `c0e717e9...` | Offline analytic import, collision rejection, route acceptance and fresh exported IFC check; same real Office export passes in 20.640 s |

The real Office exported bytes are unchanged across those checks: SHA-256 `3f52326a2e81423751f72aebba58a843dc9e9f81b99c77baede1cc1ece61e49f`, 2.096479796076932 m directrix length and two fittings. Each native comparison preserves the original project head and source files. Eight separately tested IFC schema identifiers also pass STEP roundtrip, mesh conversion and serialized BRep volume inspection.

The portable smoke runs with a Python audit hook denying socket connections. Separate probes verify that denial in both the main and frozen checker interpreters. It therefore exercises the local analytic workflow without relying on downloaded runtime packages or a hosted service. The real Office comparison reads the explicitly retained local IFC inputs; it does not imply that the entire building corpus is embedded in this package.

The original portable preview and the earlier `94e74251...` native candidate remain separate. This package is a validated local candidate, not a declaration that all directive capabilities or final distribution gates are complete. The ongoing joint-counterexample work is later source and is not included.

The exact evidence is [current-source handoff](../evidence/dependencies/native-build/checkpoint-validation/f48d7c5261a7-c20682030837/promotion-validation-handoff.json), [sealed portable index receipt](../evidence/dependencies/native-build/portable-candidates/f48d7c5261a7-ac832a6e2ba2/sealed-handoff.json), and [initial native build handoff](../evidence/dependencies/native-build/handoff.json). The build and validation commands are implemented in the `scripts/native_*.py` files.
