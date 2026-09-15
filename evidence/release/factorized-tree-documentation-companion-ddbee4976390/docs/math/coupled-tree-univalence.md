# Separate sufficient univalence certificate for declared coupled tree losses

This is a new sufficient specialization proved here. It is not presented as a
verbatim theorem from original P6, and it does not alter the local coupled-tree
Banach kernel. The model is the exact named-coefficient polynomial model from
the frozen resource-hardened `8144e76d...` local kernel.

For a fixed admitted tuple of coefficients and heads, write

\[
F_i(q)=\sum_{t:i\in A_t}a_t(\sum_{j\in D_t}q_j)^2-h_i.
\]

Every coefficient interval is nonnegative, every nonempty applicability set
`A_t` is contained in its nonempty descendant set `D_t`, and the declared tree
sets are laminar. Coefficient identities are reused exactly; a repeated named
coefficient is the same parameter in every occurrence. The new sufficient
premise is that the sum of lower endpoints of all singleton-descendant terms
at each leaf is strictly positive. An absent singleton or zero lower sum means
this theorem is unavailable, not that a solution is infeasible or nonunique.

## Exact argument

Take `q > 0` and `r >= 0` componentwise, with the SAME fixed parameter tuple.
Exact difference-of-squares polarization gives

\[
F(q)-F(r)=M(q,r)(q-r),\qquad
M=\sum_t a_t(S_{D_t}(q)+S_{D_t}(r))1_{A_t}1_{D_t}^{T}.
\]

All scalar multipliers are nonnegative. Group terms with the same descendant
set into `u_D 1_D^T`, where `u_D >= 0` is supported within `D`. Every singleton
node has scalar block `(q_i+r_i) sum_{D_t={i}} a_t > 0` by the new premise.

Add all singleton sets and a full-leaf root to the distinct descendant sets.
Laminarity gives a unique minimal strict-superset parent for each nonroot node.
Its maximal proper children are disjoint and partition it. At an internal
node, all smaller-set terms form a block diagonal matrix `B` of child blocks.
The terms whose descendant set equals the node form `u 1^T`.

Inductively, `det(B)>0` and the row `w=1^T B^-1` is entrywise positive. Hence
`d=1+w u>0`. Exact rank-one determinant and inverse identities give

\[
\det(B+u1^T)=\det(B)d>0,\qquad
1^T(B+u1^T)^{-1}=w/d>0.
\]

The proof does NOT require an entrywise nonnegative inverse; nonsymmetric child
blocks can have negative inverse entries. The complete root block is therefore
invertible, and `F(q)=F(r)` implies `q=r`.

Consequently each admitted parameter tuple has at most one positive root, and
any positive root excludes every other nonnegative root. This certificate by
itself does not establish existence of a root or infeasibility. A separately
verified local Banach certificate
for the exact same normalized model and full coefficient/head parameter box
supplies a positive root for every tuple; only their conjunction supports a
unique nonnegative solution for each tuple. It is not one common solution for
all tuples.

## Certificate and independent verification contract

The univalence certificate carries exact normalized model, parameter, topology,
context and physical-model roots; all named coefficient intervals and complete
term incidence; singleton lower sums with term IDs; every distinct hierarchy
set including virtual/singleton nodes, exact parent and child identities, and
every term's unique descendant-node assignment. Each node records whether its
proof step is the positive scalar base or the laminar rank-one update. These
are symbolic structural witnesses, not a sampled numerical matrix proof.

The verifier parses and normalizes the caller's full model independently,
reconstructs the expected complete set/term hierarchy and positive leaf sums,
and checks exact inventories, identities, parent/child partitions, all roots,
coefficient reuse and schema/scope. It does not invoke or trust the producer.
The optional composed verifier reruns both independent certificate verifiers
with the same caller model and supplied positive flow box; it binds normalized
model/parameter identities and performs its own final raw-input guards.

Strict count, rational-bit, structural, byte and work bounds apply before large
clones or rational interpretation. Caller checkpoints run during traversal,
assembly and streamed encoding. After the last caller checkpoint, callbacks
are disabled and all original model/proof inputs are rehashed before returning
authority. Caller exceptions propagate by identity. Exhaustion is UNKNOWN.

## Explicit limits

No negative/reverse-flow uniqueness, uniform strong-monotonicity constant,
physical/native geometry or coefficient applicability, native acceptance,
delivery/velocity guarantee, complete original-source implementation, global
engineering approval, or infeasibility from failed proof is established.

The retained tests independently compare exact polarization and determinant/inverse-row
identities on nonsymmetric nested examples, replay with producer disabled, and
attack missing singleton positivity, nonlaminar incidence, incomplete or forged
term/hierarchy/parameter/root witnesses, budgets and late caller mutation.
