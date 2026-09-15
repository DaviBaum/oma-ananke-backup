# Frozen physical candidate menu

`oma.optimization.physical_menu.compile_physical_menu` connects the original
P2 FDQA, P3/P4 separator and P8 action quotient kernels to a table of actual
candidate report projections. `verify_physical_menu` independently checks both
certificates and the complete label/provenance binding. Neither compiler runs
inside the verifier.

The input is a JSON object:

```json
{
  "schema": "oma.physical-menu/1",
  "context_root": "immutable aggregate context digest",
  "projection_contract_root": "digest of the named report projection",
  "demands": [
    {"id": "service", "choices": [
      {"id": "route-label", "definition_root": "scenario and route-spec digest"}
    ]}
  ],
  "examined": [
    {"assignment": ["route-label"], "candidate_id": "candidate",
     "state_root": "materialized state digest", "report_root": "checked report digest",
     "verdict": "PASS", "projection": {"length_m": "12.0"}}
  ]
}
```

Demand and choice order is part of the original menu. Every assignment is a
choice vector in that demand order. Distinct labels can share a definition;
they remain distinct alternatives. Multiple materializations of one nominal
route need distinct choice labels. Duplicate examined assignment rows are
rejected. Missing assignments become explicit `UNEXAMINED` / `UNKNOWN` rows,
with no invented report or objective. An examined `UNKNOWN` report is kept
separate from an assignment with no report.

The application boundary must resolve and hash-check every report and design,
confirm their binding and applicability, and construct the context digest from
the base revision, authoritative sources, existing obligations, mission, rules,
catalog, evidence, interpretation policy and checker/build versions. The
projection contract names exactly which report fields are observations. A
root string inside this mathematical module does not authenticate its content.
If authority or human menu identity affects a requested report, it must appear
in that observation contract. Excluding it permits only a narrower projection
claim, never general contextual equivalence.

The regional model is a chain of assignment prefixes. Each local choice appends
one demand label; the terminal table contains every complete assignment's
projected outcome. Consequently every represented interaction, including
three-way conflicts, reaches the terminal observation. No pairwise independence
or spatial separation is inferred. FDQA produces exact suffix-context classes;
separator messages count every original labeled realization, including root
storage. The separate action model contains every replacement of one coordinate
by one frozen choice. Its checked strong bisimulation preserves the projected
reports after every such finite menu-edit sequence. These are edits of menu
assignments, not simulated IFC rewrites.

The returned `terminal_profile_groups` and `action_stable_groups` retain all
assignment IDs. Every full row retains its candidate, state and report root.
The certificate authorizes no deletion, substitution of a different physical
witness, acceptance or export. The existing independent physical checker and
publication boundary remain required for the selected candidate.

The implementation accepts at most 64 demand coordinates and, by default,
4,096 complete assignments, with a separate explicit work budget. Resource
exhaustion returns `UNKNOWN`, not a partial exact certificate. Complete coverage
of this finite frozen menu does not prove route-generation completeness,
continuous optimality or absence of other physical designs. The prefix input
construction itself can be exponential and is reported separately from the
smaller quotient messages.

Source correspondence: original `1–10` ALG-MN0/1, ALG-DS1/3 with
THM-DS19.1/20.1, and ALG-CS1/6. The original P7 body and the original P26 initial
body remain absent as recorded in `evidence/math/pages/source-gaps.json`.
No reconstruction equivalence or full-program release follows from this adapter.

The focused tests cover every original label, immutable report bindings,
unexamined alternatives, three-way conflicts, future-action distinctions,
typed certificate tampering, budget behavior and independent verification.
