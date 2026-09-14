# Private coupled-tree univalence specialization

New source: `src/oma/optimization/coupled_tree_univalence.py`.
The original local existence kernel is copied unchanged from the resource-hardened
`8144e76d...` checkpoint, and the shared exact/bounded helpers remain unchanged.
The two `__init__.py` files are only an isolated test-package scaffold.

The proof is in [docs/univalence-design.md](docs/univalence-design.md). It is a
new sufficient theorem for the declared polynomial law, not native engineering
approval or a claim of verbatim original-P6 coverage.

Public functions:

- `compile_coupled_tree_univalence(model, **budgets)` returns a
  `CERTIFIED_UNIVALENCE` certificate, `UNKNOWN` when the positive singleton
  premise or a resource bound is unavailable, or `INVALID_INPUT` for a malformed
  declared model.
- `verify_coupled_tree_univalence(model, certificate, **budgets)` independently
  returns `PASS` only for the exact complete current model/parameter box and
  hierarchy. It invokes no producer. Failed checks never prove infeasibility.
- `verify_coupled_tree_nonnegative_family(model, flow_box, local_certificate,
  univalence_certificate, **budgets)` is an optional composition. It reruns both
  independent verifiers, binds their same normalized model and full parameter
  box, and only then proves one positive solution in the supplied box and no
  other nonnegative solution for each admitted parameter tuple.

Common keywords are `max_leaves` (default16, maximum32), `max_terms` (default128,
maximum512), `max_work`, `max_rational_bits`, `max_input_bytes`,
`max_certificate_bytes`, and `checkpoint`. Composition's total work count covers
both inner replays and final guards. Caller exceptions propagate by identity.
No external callbacks run after the final input-integrity sweep starts.

The model and parameter roots use the existing local kernel's normalization.
A physical adapter must separately establish the current complete native model,
retain coefficient identities and derivation, and bind the exact same model to
both proof verifiers. A univalence certificate alone does not establish existence
of a solution or infeasibility.

Current frozen source bundle:
`ba979df65757aa9f4baa9c757a92a918c9df6f3183663adcf5c63a499d2e9dc1`.
The exact 57-test receipt is
`validation/ec046df972ea419fae005a792eca64cd/result.json`.
It includes independent Fraction polarization/determinant/inverse-row oracles,
coherently rerooted proof attacks, typed-JSON substitutions, shared parameter
binding, producer-disabled replay, work limits and final mutation/cancellation.

Run a new isolated frozen validation with the workspace virtual environment:
`python .oma/development/coupled-tree-univalence/validate.py`.
No production files, original mathematics, source IFCs, live stores or packages
are changed by this private validation.

The independent root audit is retained under
`evidence/root-independent-review/da3b179138e24f2bb979d07a27ca0471/`:
24 separately constructed 1–8-leaf models, 24 composed positive families and
240 resealed attacks. Its 28 local box proposals include four honest UNKNOWN
outcomes. The earlier overconstrained box-proposal audit and zero-case wrapper
import error remain alongside it; neither is rewritten as a successful run.

The final source/evidence inventory and exact merge contract are in
`handoff.json`. Merge only the new univalence module and its new test file into
the corresponding application paths. The local kernel, shared helpers and
private package scaffolds are dependencies to verify, not replacement files.
