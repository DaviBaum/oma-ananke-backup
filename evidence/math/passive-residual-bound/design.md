# Certified residual-to-error bounds for grounded passive graphs

This specialization accepts the complete positive-resistance signed quadratic graph of `oma.optimization.passive_pressure` and an untrusted rational approximation `x` at every internal node. It proves a quantitative error bound uniformly over the exact model's full resistance and Dirichlet parameter box. It does not identify a raw residual with pressure error and does not bound physical-model discrepancy.

Original P6 THM-PO14, Pages P16360–16397, requires coercivity, inf-sup or another stability certificate. Its nonlinear clause explicitly invokes P5 THM-ER22, P13753–13781. That theorem derives error from strong monotonicity and warns that an arbitrarily small residual can coexist with large error when the stability constant is small. P6 ALG-PO7, P17130–17158, requires residual, stability, complete parameter-domain and outer-inclusion checks. Signed quadratic inversion and zero-flow sensitivity appear at P16836–16853. The original Pages SHA is `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`; exact reread paragraphs are retained in `evidence/source-basis.json`.

## Bounded-domain stability proof

Every connected component has prescribed boundary pressures. Its global interval `[L,U]` is the minimum/maximum over all boundary intervals; let `M=U-L`. The grounded positive-K model has one unique equilibrium for each admitted parameter tuple and every equilibrium head lies in `[L,U]`. Require each rational internal approximation coordinate to lie in that same interval.

For the comparison vector, boundary coordinates are **the same actual Dirichlet tuple** as the equilibrium being compared, not boundary midpoints. Thus boundary error is zero, while the internal vector is the fixed input `x`.

When `M>0`, choose a positive rational conductance lower bound `c_e` satisfying

```text
4*c_e^2*K_e.upper*M <= 1.
```

For any two drops in `[-M,M]`, the inverse law `psi_K(d)=sign(d)*sqrt(abs(d)/K)` satisfies

```text
(psi_K(a)-psi_K(b))*(a-b) >= c_e*(a-b)^2.
```

For equal signs this follows by rationalizing the square roots and bounding their sum by `2*sqrt(M)`; across zero the same lower bound holds. No bounded inverse derivative at zero is required. This is monotonicity on the validated pressure hull, not a global constant on an unbounded pressure space.

For every internal node choose a simple actual graph path to any prescribed boundary. Put `R_i=sum_path(1/c_e)` and `sigma=sum_i R_i`. Weighted path Cauchy–Schwarz gives

```text
||delta h||_2^2 <= sigma * sum_e c_e*(delta h_u-delta h_v)^2.
```

Complete signed incidence cancellation and the preceding edge inequalities yield

```text
(1/sigma)*||delta h||_2^2 <= <F(x),delta h> <= ||F(x)||_2*||delta h||_2.
```

The residual `F(x)` is evaluated at the fixed internal vector and actual boundary tuple. Every edge's inverse law is enclosed over the entire resistance/boundary box, then all incident signed terms are summed. If the resulting node intervals have absolute bounds `rho_i`, a rational `R>=sqrt(sum_i rho_i^2)` establishes `||delta h||_2<=E=sigma*R`. A zero error requires no division by the error norm.

Components with `M=0` have every boundary and admitted internal approximation equal to the same exact head. Their exact internal pressure and every flow are known, so their error is zero and no conductance/path division is used. A boundary-only component has no internal error. If no active internal nodes remain, `E=0` directly.

Units are consistent: `c` is flow/head, `sigma` is head/flow, `R` is flow and `E` is head (Pa). Explicit paths and their full resistance sums supply the stability constant; a producer's claimed matrix eigenvalue is not trusted.

## Flow error and absolute enclosures

The approximate flow is the **parameterized family** `qhat_e(K,hB)=psi_K(x_u-x_v)`, with actual boundary coordinates when an endpoint is a boundary. It is not one numerical flow vector. Its complete interval is independently computed over the same parameter box.

Each internal coordinate error is at most `E`, and every boundary coordinate error is zero. Let `D_e` be the sum of its two endpoint error bounds. The global signed-square-root inequality gives

```text
|q_e-qhat_e(K,hB)| <= sqrt(2*D_e/K_e.lower).
```

The factor two is essential across zero. A finite Lipschitz constant at zero would be false. Rational square-root enclosures certify the reported flow-error bound. Absolute flow boxes are obtained by widening the full qhat-family interval; they may be intersected with direct signed-root images of the certified pressure boxes. Boundary-to-boundary edges have zero approximation error despite potentially wide parameter-dependent flow ranges.

The pressure/error bounds mix variation of the equilibrium across admitted parameters with deviation from fixed internal x. They are not a separately identified numerical solver error or a discrepancy bound. Output fields must preserve that distinction.

## Planned API and independent certificate

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

`internal_heads` exactly covers the declared internal nodes with rational encodings. The certificate binds complete model, topology, domain, context, approximation and target identities; every edge conductance, every node/path, all inverse-law radical evidence, the complete signed residual sums, residual norm enclosure, stability sum, pressure error and flow-family error. The verifier reconstructs all path and inequality obligations and does not run the producer.

Resource counts and bytes must be bounded before expensive rational traversal, with snapshot shape checks repeated after caller callbacks. Caller exception identity is preserved. Final model/approximation/certificate binding is checked after the final completion callback with no further callbacks. Hard exhaustion returns UNKNOWN without partial error authority. A certified coarse bound remains valid with `target_accuracy_met=false`.

Independent tests will cover manufactured rational equilibria, nonzero/zero/reversed loop flows, uncertain parameter corners, a small-residual/large-error scaling example, missing or forged stability paths/conductances, wrong signed-root resistance extrema, missing edges/nodes/residuals, deliberately absent factor two, boundary-family versus midpoint confusion, malformed rational/byte/work budgets and final mutations. Native applicability and application admission are outside this new module.
