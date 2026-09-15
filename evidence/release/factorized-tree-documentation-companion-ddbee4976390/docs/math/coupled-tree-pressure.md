# Uniform positive-box certificates for unequal tree losses

This private component certifies **one root inside a supplied positive flow box for each admitted parameter tuple**. It supports row-specific quadratic losses referenced to subtree inlet flow, including different straight and branch coefficients at successive tees. It has no native adapter and does not establish global uniqueness or rule out equilibria outside the supplied box.

The common-outlet passive quotient remains unchanged. A common-head energy argument cannot silently replace the nonsymmetric equations considered here. A later native consumer must establish the declared equations and handle possible equilibria outside this box before transferring any physical conclusion.

## Source and implemented obligation

The unchanged original `math1/math1/1-10.pages` has SHA-256 `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`. Native paragraphs and the extracted-record hash are retained in `evidence/source-basis.json`.

| Original native paragraphs | Obligation used here |
| --- | --- |
| P5 P14530–14546 | Trusted-kernel sufficient evidence explicitly includes interval Newton/Krawczyk certificates. |
| P5 P14550–14566 | Checker conclusions remain relative to the admitted model and kernel. |
| P6 PO11 P16081–16114 | Nonlinear port inversion has invertibility and regime premises; local inversion does not supply a global conclusion. |
| P6 PO12 P16118–16135 | Selecting one equilibrium cannot replace the full admitted response relation. |
| P6 PO2 P17645–17681 | Certified solves require validated envelopes, domain/correlation discipline and an explicit locality-failure disposition. |

The implementation supplies one bounded sufficient certificate under these obligations. It does not implement all of PO2, all nonlinear physics, or the complete original algorithm bodies. Laminar set validation is a symbolic inventory check; it does not prove native tee geometry, physical component coverage, coefficient applicability, or a physical tree law.

## Exact model and public API

Module: `src/oma/optimization/coupled_tree_pressure.py`.

```python
compile_coupled_tree_pressure(model, flow_box, *,
    max_leaves=16, max_terms=128, max_matrix_entries=256,
    max_work=2_000_000, max_rational_bits=4096,
    max_input_bytes=1_048_576, max_certificate_bytes=16_777_216,
    checkpoint=None)

verify_coupled_tree_pressure(model, flow_box, certificate, *,
    # same budgets and checkpoint
)
```

The exact model fields are `schema`, `leaves`, `coefficients`, `terms`, `available_heads`, `context_root`, `physical_model_root`, and `assumptions`. The schema is `oma.coupled-tree-quadratic-pressure-model/1`; callers must supply the exact `MODEL_ASSUMPTIONS` constant. Context and physical-model identities are declared SHA-256 roots, not independently established physical authority.

Each coefficient and head is an object with exactly `lower` and `upper`, encoded as integers or exact rational/decimal strings. Floats, booleans, exponent strings, infinities, zero denominators and malformed bounds are rejected. Coefficients are nonnegative on their entire finite intervals. Heads may have either sign; unsupported root/existence situations remain UNKNOWN. Every box coordinate has `0 < lower < upper`.

Each term contains exactly:

```json
{
  "id": "tee2-branch",
  "coefficient_id": "k-tee2-branch",
  "descendant_leaves": ["B", "C"],
  "applies_to_leaves": ["C"]
}
```

The descendant set D is the sum of flows used by the term; A is the subset of leaf path equations containing that loss. Both are nonempty, A is a subset of D, and all declared D/A sets are laminar. Pipe terms normally have A=D. An outlet-specific tee term uses the full tee subtree D and its particular outlet subtree A. Every named coefficient is used, every leaf equation has at least one term, and duplicate identities or duplicate memberships are rejected. Reusing a coefficient ID retains a single parameter identity. Interval arithmetic may safely enlarge the result by discarding correlations; it never substitutes midpoint values for the uncertainty domain.

For each leaf i the equation and Jacobian are:

```text
F_i(q,theta) = sum_{t:i in A_t} a_t (sum_{j in D_t} q_j)^2 - P_i
J_ij(q,theta) = sum_{t:i in A_t,j in D_t} 2 a_t sum_{k in D_t} q_k
```

Available heads are total pressure plus gravitational potential differences in Pa; flows are in m³/s and coefficients in Pa·s²/m⁶. The kernel does not derive these quantities from native metrics, static-pressure inputs, or fluid laws.

## Certificate and proof

The producer chooses the rational box midpoint x0. It proposes an exact inverse R of the Jacobian at midpoint parameters only to obtain a useful preconditioner. The checker accepts any strictly interior rational center and rational R backed by the required exact inverse witness; it does not run midpoint inversion.

The certificate binds normalized model, parameter, topology, box, query and context roots. It includes the full leaf/coefficient/term/equation incidence, every term's center subtree sum and full-box derivative, F0, J, R, inverse witness, both inverse products, B, center image, K, each row norm and each strict inclusion margin. Matrix rows and columns use the sorted leaf order. No omitted matrix coordinate or equation is interpreted as zero.

The checker reconstructs F0 and J from the actual input model using a separate row/column traversal. It verifies both rational inverse products equal the identity and computes with signed interval multiplication:

```text
B = I - R J
K = x0 - R F0 + B (X - x0)
c = max_i sum_j max(abs(B_ij.lower), abs(B_ij.upper))
```

It requires `c < 1` and both inclusion margins positive in every coordinate, so K lies strictly inside X.

Fix any one admitted parameter tuple theta. The polynomial is continuously differentiable on the convex box X. The integral of J along the segment from x0 to q remains in its coordinate interval enclosure. Therefore `T_theta(q) = q - R F(q,theta)` lies in K for every q in X. The **same theta** is used at the center, along the segment and at q; separate interval expressions merely enclose that same tuple. Thus T is a self-map of the complete closed box X. The derivative bound c gives a contraction in the infinity norm. Banach's theorem supplies exactly one fixed point in X. The checked inverse of R makes its fixed points exactly the roots of F. Every such root lies in K and has positive leaf coordinates.

This proves a family of solutions, one per tuple, not one numerical solution common to all tuples. It does not imply uniqueness outside X, tightness of K, physical service feasibility, or the absence of other operating regimes. No target-accuracy claim is made; the rational output widths are explicit.

## Dispositions and operational bounds

The producer returns a complete `CERTIFIED_BOX` certificate or an explicit non-proof disposition. A singular proposed midpoint inverse, noncontraction, failure of strict inclusion, or supported resource exhaustion returns `UNKNOWN`. Malformed or unsupported model input returns `INVALID_INPUT`. The verifier returns `PASS` only after the complete independent proof; false or malformed proof returns `FAIL`, and exhausted resources return `UNKNOWN`. These dispositions confer no native acceptance or physical infeasibility authority.

Maximum supported limits are 32 leaves, 512 terms, 1,024 entries per matrix, 10 million counted work operations and 4,096 rational bits. Input/certificate byte limits and strict bounded JSON structure are enforced before rational decoding; declared matrix limits cover R, inverse, J, B and both inverse products. Model and certificate shapes are checked again on frozen copies after callbacks. Counts are upper bounds, not promises that the largest model will finish under default work limits.

Callbacks may interrupt parsing, arithmetic and verification; their exception identity is preserved. After the final producer/verifier completion callback, no caller code runs again. The kernel rehashes the original model, box and supplied certificate without callbacks before returning. A late mutation fails closed. These are synchronous caller-binding guards, not a hostile-memory isolation or atomic external-filesystem claim.

## Validation and retained evidence

The first immutable implementation `a6ac45709a8ae32ac117acb48f011bf74340b8393cb07e7700432965d83bb0e6` passed 105 focused tests without failures or skips. Resource-only hardening then extended shape checks to inverse-product matrices and coordinate maps. Final build `8144e76ddff8f1b4cb146aad47592a1ced7ba12dc2d21853c0f087c386cc2a70` passed 124 focused tests in 0.896 seconds, with source and captured test bytes unchanged. Receipts are under `validation/7da216bb14a647829d41f1444c03c1ca` and `validation/45cd7242b8f24d2297ab6522a778f7b0`.

The manufactured two-tee/three-sink fixture has q=(1,2,3), available heads (14.9,23.2,30.85), unequal tee coefficients (0.2,0.3) and (0.25,0.4), and the nonsymmetric Jacobian:

```text
[ 5.8   4.8   4.8 ]
[ 3.6  10.0   7.6 ]
[ 3.6   9.1  13.3 ]
```

Tests cover exact and interval versions, shared coefficient identity, zero terms/singular inversion, invalid tree inventories, signed interval products including zero, all major resealed proof fields, transpose/common-outlet substitutions, box/domain mismatches, parser and byte/work/matrix budgets, early and final caller exceptions, mutable-input enlargement and final mutation guards. Disabling producer polynomial/inversion helpers still leaves independent verification passing.

An independent script constructs a rational adjugate inverse and tensor Bernstein bounds for each component of R·F on every box face. All 54 coefficient ranges have strict Poincaré–Miranda face signs over the whole parameter box, providing an independent existence proof. Separate rational J/R calculations confirm contraction. All 4,096 parameter-corner solves at 80 decimal digits lie in the certified enclosure; those finite numerical checks alone are not the universal proof. Initial and final script/source/results are preserved under `evidence/independent-rational-oracle/`.

The independent peer audit on final build 8144 passed 24 manufactured hierarchies with one to eight leaves, including 21 nonsymmetric models and 96 distinct exact parameter/root instances. Separate Fraction code rebuilt F, J, both inverse products, B, the norm and K. It rejected 293 resealed or final-callback attacks, checked six budget exhaustions and two oversized proof inventories, and verified a certificate with producer helpers disabled. No concrete soundness defect was found. The retained result is `evidence/independent-kernel-review/68137ae750cb4760b0b50448d29748be/result.json`, SHA-256 `21292058d6118c8fdabd03a7d85579316b1e9927a5b0f319f1a72c8cd350cc95`.

The implementation shares rational/interval arithmetic and the fixed-point-map checking utility between producer and checker; these are part of the trusted arithmetic/model kernel. The independent oracle and peer replay challenge that common code separately. These kernel tests and numerical oracles do not establish actual IFC/native service or managed acceptance. The private handoff left production files, previous kernels, mission schemas and capability registers unchanged.

## Integrated checkpoint

The exact module and its 124-case test file are now integrated on application source `8f6f5c18b77bb9ef45e7cd3b2c24987a13c822cca706178f0a8d173fc03c1206`. All 427 combined coupled/residual/passive/native-tree/control compatibility cases pass in 31.51 s. The 104 application files, 121 exact test/support inputs, full case identities, proof/oracle evidence and integration script are retained at `evidence/math/coupled-tree-pressure/latest.json`.

The native cases in this compatibility suite still concern the previously implemented common-outlet model. They do not make this unequal-loss kernel a native adapter. Its own scope remains uniqueness inside the supplied positive box. A separate stronger uniqueness certificate or a future native consumer must satisfy its own complete premises.
