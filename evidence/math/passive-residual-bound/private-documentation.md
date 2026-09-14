# Checked passive-network residual error bounds

`oma.optimization.passive_residual` implements the bounded proof in the companion design. It accepts the existing grounded positive-K signed quadratic graph and an exact rational internal head vector. It independently certifies pressure error and flow-family error over every admitted resistance and Dirichlet parameter tuple.

The source basis is original P5 THM-ER22, native Pages P13753–13781, together with P6 THM-PO14 P16360–16397 and ALG-PO7 P17130–17158. These require a stability certificate before residuals become error bounds. The signed-square-root warning at zero is P16836–16853. The reread original Pages SHA is `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`. The retained source extract and design do not claim full original algorithm completion.

## What is certified

Each component's global boundary hull contains both the exact equilibrium and the supplied internal approximation. Boundary values in the comparison vector are the *same actual Dirichlet tuple* as the equilibrium. They are never replaced by midpoints.

For positive component span `M`, every edge has a checked rational conductance `c>0` satisfying `4*c*c*K.upper*M<=1`. Complete simple grounding paths give `sigma=sum_internal(sum_path(1/c))`. Exact outward signed-root intervals establish every internal residual, followed by a checked rational upper L2 norm `R`. The pressure bound is `E=sigma*R`, in Pa. This is a bounded-domain coercivity argument; no global constant over unbounded pressures or invertible derivative at zero is assumed.

Constant-span components have exact zero internal/flow error; boundary-only components have no internal error. They require no division by span or a nonexistent stability constant. The verifier still checks their complete graph inventory.

The reference flow is a parameterized family `qhat(K,hB)`, evaluated at the fixed internal approximation and actual boundary tuple. It need not conserve internal flow: that discrepancy is the residual being bounded. Pressure-form coercivity does not assume an already feasible approximate flow. For an edge, the sum `D` of its endpoint coordinate-error bounds gives `|q-qhat|<=sqrt(2*D/K.lower)`. The factor two handles crossing zero. Boundary endpoint error is zero. Separate outward intervals enclose the entire reference family; these are widened by the error and intersected with direct images of the certified pressure boxes.

A small residual may still imply a large error when `sigma` is large. A parameter-dependent equilibrium's deviation from fixed internal x also includes parameter variation; it is not labeled pure numerical solver error. Physical model discrepancy, native geometry, applicability, delivery or acceptance are not checked by this module.

## API and result

```python
compile_passive_residual(model, internal_heads, *, pressure_error_target=None,
    max_nodes=64, max_edges=128, max_path_steps=4096, max_work=2_000_000,
    sqrt_bits=96, max_rational_bits=4096, max_input_bytes=1_048_576,
    max_certificate_bytes=16_777_216, checkpoint=None)

verify_passive_residual(model, internal_heads, certificate, *,
    pressure_error_target=None, max_nodes=64, max_edges=128,
    max_path_steps=4096, max_work=2_000_000, max_rational_bits=4096,
    max_input_bytes=1_048_576, max_certificate_bytes=16_777_216,
    checkpoint=None)
```

The graph schema is unchanged. `internal_heads` is a complete node-to-rational map, using strict integers or integer/decimal/fraction strings, never floats or booleans. Every coordinate must lie within its component boundary hull. The optional nonnegative pressure-error target is part of the query identity.

The producer returns a `CERTIFIED_BOUND` certificate or `INVALID_INPUT`/`UNKNOWN` without a partial proof. Verification returns `PASS`, `FAIL` or `UNKNOWN`. `target_accuracy_met=false` is compatible with a sound coarse bound. There is no claim to choose a best approximation, tight hull, smallest stability sum or shortest grounding path.

Certificate fields bind model/topology/domain/context/approximation/target, every conductance, every grounding path, full approximate edge-flow radicals, every signed residual, squared residual norm, radical norm interval, stability sum, pressure error/boxes and every flow error/box. The checker uses the existing independently checked radical/incidence primitives, never producer square-root construction or path search. It recomputes direct path membership and every conductance, norm and error inequality. Producer-free replay is tested.

The model's positivity, exact partition, complete edge inventory and grounded components are normalized again by the shared model parser. Node/edge/path-step counts and certificate bytes are bounded before rational proof traversal; frozen shapes are checked after callbacks. Arithmetic bit/work limits apply independently to each invocation. Caller exception identity is preserved. After the final completion callback, model/approximation/target and supplied-certificate guards run with callbacks disabled. This is not atomic protection against arbitrary concurrent memory mutation or an altered checker implementation.

## Tested private checkpoint

The standalone module SHA is `553b92f34237b74018f3de7825c183149c3e5d0c07a271a26ca180592b6ee0fc`; its immutable private build is `123f1fe4133e0d988eed185303364e7c9ab05b43fd08e6f70011c9a4be0ddf7a`. The source base is unchanged combined checkpoint 52bd5 plus this new module, not a proposed replacement of the application tree.

The expanded focused suite passes 86 tests. It includes exact manufactured tree/loop/reversed equilibria with E=0, zero-flow and constant uncertain-K cases, a small-residual/large-error counterexample, an uncertain boundary-only family with zero approximation error but nonzero flow uncertainty, and all 144 independently computed coupled-loop parameter samples checked against both pressure and parameterized-flow errors. Adversarial cases cover omitted/duplicated denominators, false conductances and spans, wrong/ungrounded paths, false norms/errors, missing factor two, boolean/root/target changes, byte/work/rational limits, callback mutation and exact exception identity. A valid nonshortest path is accepted as a conservative proof.

Initial evidence is retained: 75 PASS/1 test expectation error, followed by 77 and then 86 PASS. The initial test wrongly demanded UNKNOWN from a small arithmetic budget that actually admitted a valid coarse proof. It was corrected by adding an actually oversized rational input and keeping the successful low-precision case as a positive test. These counts overlap and are not cumulative.

The same unchanged module passed independent implementation review: 24 rationally manufactured equilibrium networks, including 12 uncertain boxes and eight mixed disconnected constant/boundary-only extensions, satisfied the actual pressure L2 and parameterized-flow error bounds. There were 243 rejected resealed/final-mutation attacks and four supported budget exhaustions returning UNKNOWN. The verifier passed with producer/radical constructors disabled. Result SHA `1d7d980d40124f057ec47bdd38980b67afe7c020d14fb33e4660b173963140a1` is retained under `evidence/independent-implementation-review/e7ac3e79600843fdb8a4ba3fbc7debf8`. The peer's two initial oracle/test expectation errors are retained with their corrections; no module change was required and no concrete soundness defect was found.

The final immutable 86-test receipt is `validation/41db3d9308c2460eb404b45fff658ea8`, with source/test/fixture hashes unchanged and zero failures/skips. Application integration remains separate. The minimal module/test merge is three files: `src/oma/optimization/passive_residual.py`, `tests/test_passive_residual.py`, and the unchanged pinned `tests/fixtures/passive-residual/coupled-loop-result.json`.
