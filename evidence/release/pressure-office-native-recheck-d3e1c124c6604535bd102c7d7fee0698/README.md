# Saved pressure-network export: current native recheck

**PASS**, 30.50 seconds including command supervision; 27.906 seconds in the
validation workflow. No geometry was regenerated. The existing Office export
was copied with its required immutable artifact and asset closure, then checked
by a fresh managed child under the frozen `bac10b7f20d4...` application.

The source Store was opened read-only:
`.oma/development/two-sink-pressure/bench-stores/b44b3123cdb641709b2aa32ae5bd526c`.
Its candidate `cde5e507fca2488d9a957364f6d5a763`, originating run, project head,
source IFC and exported IFC remained unchanged. The exported IFC SHA-256 is
`c116e3cf909e97719a613888043ca2b214aba538575e17f79dd3639bb5a12e58`.

The native checks account for four components, nine physical ports, all
**3,212 component/source-obstacle pairs (4 × 803)** and all **six component
pairs**. Every native disposition, both required deliveries and all nine
component-port velocity checks pass. The objective remains
`length_m=1.8000000000000025`, `fitting_count=1.0`.

The exact delivery intervals are unchanged from the genuine prior `b61a...`
report. Approximate values in litres per second are:

| Outlet | Lower | Upper |
|---|---:|---:|
| branch | 2.208882235 | 2.234355020 |
| straight | 1.330020577 | 1.355064848 |

The freshly derived pressure model has a different root because the current
checker identity is part of its context. The full rational intervals and
accuracy limitations are retained in `current-pressure.json`; the rounded table
does not replace those values.

`result.json` binds the original manifest, exact source/checker, script SHA,
command record, prior/current report roots and complete native evidence.
`driver.py` records the invocation; `native_real_model_validation.py` is the
exact tested harness copy. The three prior/current artifact pairs preserve the
native semantics, CAD accounting and pressure calculations. The separate
`native-pressure-harness-3f4abdcc883c461fb39f721333d9b6b3` evidence records seven
passing harness regressions, including the four prior route-set tests.

This validation uses the original installed native wheel with the new frozen
application. It is not the later custom-native or bundled-interpreter run. The
model still assumes the explicit hypothetical regulated pressures, fixed loss
coefficients, stationary incompressible flow and declared ideal circular bore;
it does not certify measured Office operating conditions, whole-building
adequacy or unrestricted topology optimality. No portable package was changed.
