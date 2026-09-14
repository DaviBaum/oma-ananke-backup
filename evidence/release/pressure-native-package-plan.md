# Pressure checkpoint: prepared native/package validation commands

Status: **prepared, not executed**. Start only after the corrected root regression
suite passes and its final test files are frozen. Keep every earlier package and
attempt unchanged.

The current application checkpoint is
`bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac` (97 Python
source files). The existing six `ui/dist` files were rehashed and match the sealed
`43d9e1f20085-0334c44cd3ba` package. Recheck that equality before building. The
recorded custom native wheel, standalone Python archive and 59 runtime wheels
remain unchanged; no native compilation is required by this source-only delta.

## New full test and executable snapshot

The native validator copies all current test files and the required supporting
scripts before collection. This must include the corrected `test_store.py` and
`test_project_dependencies.py`, new `test_physical_report_admission.py` and
`test_native_pressure_model_validation.py`, and the final native validation
helper SHA `bb9bf2d92d6d52580e93685cf09b99fccf6a255f86094d9cace53679afd4b5e3`.
Its complete node manifest is the authority for subsequent bundled tests; do not
reuse the old 1,490-node manifest or claim the previous partial snapshot includes
new tests.

```powershell
$build = 'bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac'
.venv/Scripts/python.exe scripts/native_validate_checkpoint.py --source-checkpoint $build
```

After its receipt reports `CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS`, assign
`$checkpointResult` to that newly created **absolute** evidence `result.json`
path. Require exact source equality, the recorded native extension/wheel, no
failed or skipped custom-native tests, and unchanged test-source hashes.

## New portable candidate and exact bundled tests

```powershell
.venv/Scripts/python.exe scripts/native_portable_candidate.py --checkpoint-validation $checkpointResult
```

Assign `$portableResult` to the new absolute portable evidence `result.json`
path. This creates a separate candidate, captures its validated payload before
testing, and performs the offline workflow. Do not point it at an existing
package. Then run:

```powershell
.venv/Scripts/python.exe scripts/native_portable_full_suite.py --result $portableResult
.venv/Scripts/python.exe scripts/native_portable_guard_probe.py --result $portableResult
```

Require exact copied test-source and node manifests, standalone Python 3.12.14,
the actual package native/source identity, and external local test tools only.
The only permitted skips are the three exact direct-interpreter bridge cases
already encoded in `verify_suite_xml`. Absolute receipt paths avoid the older
retained XML-location orchestration failure. Both distinct network-denial modes
must pass. These are Python socket audit probes, not an OS firewall claim.

## Real saved IFC regression under both runtimes

Repeat each command first with `--checkpoint-validation $checkpointResult` and
then with `--portable-validation $portableResult`, using separate new evidence
directories in `$b2Output` and `$pressureOutput`:

```powershell
.venv/Scripts/python.exe scripts/native_real_model_validation.py --source-checkpoint $build --candidate-id 4e4ae2ec320c4e038f09cae18bd386bf --expected-export-sha256 c9bb6d41e8fd3ae6adea5dc3fd132b23e606d89e0c6988f695a3f7dd12ac1a5d --prior-checker-version oma-independent-checker/2:e3fde02b5d3ef2eeeb59cbcdf780f1ea6361c42e3e35e22cd5a2d220d7a1b78d --checkpoint-validation $checkpointResult --output-directory $b2Output

.venv/Scripts/python.exe scripts/native_real_model_validation.py --source-checkpoint $build --candidate-id cde5e507fca2488d9a957364f6d5a763 --original-store .oma/development/two-sink-pressure/bench-stores/b44b3123cdb641709b2aa32ae5bd526c --expected-export-sha256 c116e3cf909e97719a613888043ca2b214aba538575e17f79dd3639bb5a12e58 --prior-checker-version oma-independent-checker/2:b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895 --checkpoint-validation $checkpointResult --output-directory $pressureOutput
```

Keep original Stores read-only and use the saved IFC bytes. Require completed
managed checks, exact prior/current identities, unchanged source/candidate/run/
head, unchanged objectives and obligation dispositions. Independently account
for B2's 4,818 source pairs, five cross-route pairs and two new elbows; pressure
Office's 3,212 source pairs, six unique component pairs, nine port velocities and
two deliveries. Retain full rational operating enclosures and their numerical
and hypothetical-input limitations.

## Seal prerequisite still to implement

Keep B2 as the existing canonical `real-office-validation.json`. The next sealer
needs a bounded additional guard/copy for
`real-office-pressure-validation.json`, bound to the same package/current
checker and validated payload, with complete native/pressure evidence. Merely
running the second check without retaining and validating its receipt in the
sealed provenance is insufficient. This sealer delta has **not** been made yet.

After that change and every required check passes:

```powershell
.venv/Scripts/python.exe scripts/native_seal_portable.py --result $portableResult
```

Rehash the final classified payload/index, exact source/native identities and
all receipt roots, then perform an independent read-only package audit. Preserve
all failed attempts. The result remains a separately validated local candidate;
public redistribution, whole-building adequacy and unrestricted optimization
claims are not established by these workflows.
