# Validated native and portable candidate

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
