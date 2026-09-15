# Factorized interval proof for coupled tree pressures

`oma.optimization.factorized_tree_pressure` proves existence and uniqueness inside a supplied strictly positive flow box for each admitted parameter tuple of the existing declared quadratic tree model. It preserves the original model schema and uses its own certificate schema, `oma.factorized-tree-positive-box-certificate/1`. It neither changes physical inputs nor treats a failed sufficient proof as physical infeasibility.

Source obligations remain those of the existing [coupled pressure contract](coupled-tree-pressure.md): original P5 paragraphs P14530–P14546 (validated nonlinear proof), P6 PO11/12 P16081–P16135 and PO2 P17645–P17681 (validated physical relation and correlated parameter identity). This is an additional sufficient test for that bounded model, not completion of all original nonlinear physics.

## Polynomial and parameter identity

For leaf flows q, each equation is

`F_i(q,a,h) = sum_t [i in A_t] a_(id(t)) (sum_(u in D_t) q_u)^2 - h_i`.

Here `D_t` is the declared descendant set, `A_t` is its applicable-equation set, and `id(t)` names an uncertain coefficient. Repeated uses of the same ID mean the same parameter value. Two distinct IDs with equal interval endpoints remain independent parameters.

Choose a rational matrix R, proposed as the inverse midpoint Jacobian. After exact expansion and collection,

`(RF)_i = sum_a a * sum_(u<=v) W_(i,a,u,v) q_u q_v - sum_j R_ij h_j`.

For every original term with coefficient ID a whose descendants contain u and v, add `sum_(j in A_t) R_ij` to W for a square and twice that value for a cross term. Weights may be negative. Collect all weights with the same complete `(row, coefficient ID, unordered variable pair)` key before interval evaluation. Exact cancellation therefore remains valid for every same parameter tuple.

The producer expands each term and collects weights. The independent checker enumerates every row, parameter and unordered leaf pair, rebuilding its weight from the complete original term/equation incidence. Its parameter indexes contain all and only original terms with that exact ID. Every nonzero weight is listed in the certificate; omission, duplication and changed signs or factors are rejected.

## Sufficient existence proof

For fixed admitted parameters, define `T(q)=q-RF(q)`. The certificate supplies a rational center strictly inside the original box, R and an inverse witness. Both exact rational inverse products must equal the identity, so a fixed point of T is a zero of F.

At the center, evaluate the collected polynomial exactly in q before multiplying by coefficient intervals. For each derivative, collect the rational linear coefficient of each flow under each named parameter; evaluate that linear expression over the original box, then multiply by the parameter interval. Signed interval products enclose the same RF and RJ for all admitted tuples. The independently computed derivative enclosure for T is `B=I-RJ`.

Require the maximum absolute row sum of B to be strictly below one. The mean-value enclosure `T(center)+B*(box-center)` must lie strictly inside every original box coordinate. The closed box is complete, T is a uniform contraction and maps it into itself. Banach's theorem yields one root in that box for each admitted tuple. It does not assert a common root for different parameter values or uniqueness outside the box.

The certificate also retains the complete original unpreconditioned term evidence, residual and Jacobian. The checker reconstructs these independently before checking the collected polynomial, both inverse products, derivative bounds, center image, root enclosure, strict margins and contraction norm. Exact rational, inventory, monomial, byte and cumulative work bounds apply to both paths.

## Native composition

The native adapter first tries the original local proof. Only a numerical sufficient-test failure (`STRICT_BOX_INCLUSION_NOT_ESTABLISHED` or `CONTRACTION_NOT_ESTABLISHED`) enables this stronger method. Invalid inputs, missing global premises, cancellation and exhausted budgets do not restart the proof budget. Both attempts use the identical derived model, original flow box and cumulative adapter allowance.

The producer assembles a proposed service report from the proposed enclosure. A mandatory complete independent consumer then reconstructs the native metric/section/path model, dispatches to the exact local certificate schema, checks the global nonnegative univalence certificate for the same model and parameter roots, and recomputes every delivery, port velocity, continuity identity and head path. A certificate or service proposal does not become authoritative before this final check passes. Removing a duplicate earlier invocation of the same local/global checks saves work without removing this mandatory independent check.

Native IFC semantics, full source/component geometry, permitted zone, numerical metric policy, mission/source/software bindings and fresh exported-IFC checks remain separate required gates. This module proves none of those by itself. Fixed loss laws and declared ideal-bore assumptions remain explicit physical applicability premises.

## Retained evidence

The original five-sink model did not satisfy strict inclusion under the older interval ordering. The new proof certifies exactly the original physical model and original ±1% flow box. An independent standard-library Fraction oracle rebuilt every weight and bound, including signed-preconditioner and shared-ID cases. The original five-sink native candidate was accepted and its fresh export rechecked; the physically obstructed alternative remains rejected.

The later index optimization preserves byte-identical complete certificates on exact five-, seven- and eight-sink models. After the complete late-packet guard, the seven/eight service producers use 1,268,666 and 1,882,615 work units, respectively, within the unchanged 2,000,000-unit adapter policy in the retained pure model probes. These figures alone are not new native acceptance claims. Native integration and exact software snapshots are identified separately by the current checkpoint.

The producer detaches the completed independent result before any subsequent caller callback. The consumer also returns the full packet hash it already verified; the producer checks that complete packet again after its last callback with callbacks disabled. Thus a retained producer alias cannot change a local/global certificate or proposed service after verification. The added bounded copy and packet guard consume the same adapter budget. A prior concrete mutation failure and its corrected rejection are retained separately.

Tests cover direct original-polynomial and Jacobian identities, parameter identity, exact old/new certificate equality, producer-disabled checking, coherent resealed proof/service forgeries, exact and one-below resource bounds, input mutation at final callbacks, and caller exception identity. Public peer evidence is under `evidence/math/factorized-tree-pressure-independent/`.
