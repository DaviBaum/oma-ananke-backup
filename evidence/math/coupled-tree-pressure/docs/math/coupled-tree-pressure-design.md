# Positive-box certificates for unequal coupled tree losses

This new model addresses multiple tees whose two outlet losses have different coefficients, both referenced to the tee's total inlet flow. The existing common-outlet quotient and globally unique passive-edge model remain unchanged. Their energy argument does not automatically apply to this nonsymmetric coupled system.

Original P6 THM-PO11, native Pages P16081–16114, supplies only local implicit-function conclusions under invertibility and a fixed regime. THM-PO12 P16118–16135 warns that one selected equilibrium cannot replace all admitted responses. ALG-PO2 P17645–17681 requires certified solves, validity domains, conservation/correlation and explicit locality failure. Original P5 P14530–14546 explicitly lists interval Newton/Krawczyk certificates as trusted-kernel sufficient evidence. These paragraphs were reread from the unchanged original Pages SHA `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970` and retained in `evidence/source-basis.json`.

## Declared polynomial model

There is one positive flow variable per leaf. Every named loss term has a named nonnegative coefficient interval, a set D of descendant leaves whose total flow it uses, and a nonempty subset A of leaves whose equations include that loss. Pipe terms use A=D. An unequal tee outlet term uses the whole tee's descendant set D and that particular outlet subtree A. Shared coefficients retain one parameter identity even when used in several terms. All declared coefficients/terms/leaves must be used and accounted for.

The complete equation for each leaf i is

```text
F_i(q,theta) = sum_{t: i in A_t} a_t * (sum_{j in D_t} q_j)^2 - P_i.
```

The descendant/applicability subsets must be laminar, so they describe nested/disjoint tree groups. This is a symbolic model inventory, not proof that every actual IFC component was represented. Available head intervals P_i are supplied total-pressure-plus-elevation differences. Coefficients are finite and nonnegative throughout; zero coefficients are admitted, but may make certification impossible.

The Jacobian is

```text
J_ij(q,theta) = sum_{t: i in A_t and j in D_t} 2*a_t*(sum_{k in D_t} q_k).
```

Unequal tee coefficients generally give J_ij != J_ji. No symmetric energy or global strong-monotonicity theorem is assumed. The positive box is an explicit fixed flow-direction regime; no zero-flow/reversal branch is smoothed away.

## Uniform preconditioned fixed-point certificate

The caller supplies a nondegenerate rational flow box X with every lower bound strictly positive. The producer proposes its rational midpoint x0 and an exact rational inverse of the midpoint Jacobian. Midpoints are used only to choose a preconditioner, never as a replacement for uncertain coefficients or heads in the proof.

The certificate supplies a rational square matrix R and an inverse witness A. The independent checker verifies both R*A=I and A*R=I. It independently reconstructs a complete interval F0 containing F(x0,theta), and a complete interval J containing J(q,theta) for all q in X and all admitted coefficient/head tuples. Positive subtree sums allow exact monotone interval endpoints for each derivative term. Shared parameter dependencies may be conservatively forgotten during interval arithmetic; the same actual tuple is still included throughout.

Define

```text
B = I - R*J
K = x0 - R*F0 + B*(X-x0).
```

The checker requires every rational endpoint of K to lie strictly inside X and requires

```text
max_i sum_j max(abs(B_ij.lower), abs(B_ij.upper)) < 1.
```

For each fixed admitted parameter tuple theta, T_theta(q)=q-R*F(q,theta) maps X into itself. The mean-value integral along the segment from x0 to q gives T_theta(X) subset K. Its induced infinity-norm derivative bound is strictly less than one on the convex box. Banach's theorem gives one unique fixed point in X. Invertibility of R makes that fixed point exactly a zero of F. The strict positive box preserves the chosen physical direction regime. The root also lies in K, yielding a smaller uniform flow enclosure.

The result is **exactly one root inside X for each admitted tuple**. It does not prove global uniqueness elsewhere in the positive orthant, exclude other equilibrium branches outside X, or justify physical acceptance when those branches matter. It does not assert one common flow vector for every tuple. A failed midpoint inversion, interval contraction, strict inclusion or resource budget returns UNKNOWN; it is not an infeasibility certificate.

## Model, proof and API boundaries

The planned model schema contains `leaves`, named `coefficients`, complete `terms` with `descendant_leaves` and `applies_to_leaves`, one `available_heads` interval per leaf, context/model roots, fixed units and the explicit positive-flow quadratic regime. The proposed public API is `compile_coupled_tree_pressure(model, flow_box, *, budgets..., checkpoint)` and its independent `verify_coupled_tree_pressure(model, flow_box, certificate, *, budgets..., checkpoint)`.

The certificate binds complete model/parameter/tree-set/box roots and every variable, coefficient, term, equation, matrix entry and inverse witness. It carries center residual term evidence, Jacobian term evidence, all matrix products, row norm sums, K bounds and strict inclusion margins. The checker does not invoke midpoint inversion or trust producer scalar norms. Rational, node/term/matrix-entry, input/certificate byte and work budgets apply before allocation or expensive parsing; final no-callback input/certificate guards prevent a callback from relabeling stale results. Caller exceptions retain their identity.

Initial examples will use a two-tee/three-sink hierarchy with unequal outlet coefficients and a manufactured rational root. Independent exact coefficient boxes and interval checks will establish universal validity; numerical corner solves are supplementary consistency evidence only. Tests will cover nonsymmetric Jacobians, coefficient identity reuse, laminar/complete inventories, false inverse/matrix/contraction/inclusion proofs, positive regime guards, zero/singular coefficients, budgets and final mutations. There is no native adapter, new mission interpretation, geometry/velocity/delivery certification or global physical closure in this component.
