# Original Prompt 6: exact linear port contract

The kernel in `src/oma/optimization/ports.py` implements an exact rational
specialization of original Pages Prompt 6, THM-PO6/PO31 and ALG-PO1/PO7. The
entire original chapter was read at native `1-10:P15438–18291`, including all
algorithm bodies, registry tables and its explicit unresolved assumptions.
These historical IDs are separate from reconstructed canonical namespaces.

`LinearPortModel` contains a square rational matrix, ordered boundary indices,
one load per remaining interior coordinate, and explicit model bindings. The
bindings name the model, units, regime, parameter domain, scenario domain and
source root. They identify a supplied mathematical contract; the kernel does
not prove that contract is an adequate description of a real physical system.
Integers, rational strings and `Fraction` values are accepted. Binary floats
must first receive an explicit interpretation outside this kernel.

`compile_linear_port` returns a Schur boundary response when the interior block
is invertible. It includes the inverse, exact boundary load offset and interior
reconstruction map. `verify_linear_port` checks two-sided inverse identities
and replays the original matrix equations for every coefficient. It does not
run the producer's inverse construction or elimination algorithm.

For a singular interior, the producer eliminates the interior columns from
all original equations using invertible row operations. The certificate
contains the transformation and its inverse, identity pivot columns, zero
interior rows, and the remaining exact affine constraints on boundary
displacements and forces. The checker validates those identities directly.
This retains incompatible loads, nonunique responses and free interior modes.
No numerical grounding, arbitrary pseudoinverse or equilibrium branch is added.

`reconstruct_linear_port` first verifies the certificate. A Schur response
requires boundary displacements and optionally checks supplied forces. A
singular relation requires both displacements and forces; compatible external
values yield one checked full interior witness by setting free coordinates to
zero. This selects a witness without claiming the whole fiber is a singleton.
Incompatible external values return `NO_REALIZATION` for that exact pair.

`compile_kron_network` builds a positive undirected conductance network;
parallel conductances add. `verify_kron_network` independently validates the
original edge-incidence energy identity and then the port certificate. The
identity establishes symmetry, positive semidefiniteness and zero row sums
for the supplied graph. Floating internal components remain singular affine
relations. The adapter is appropriate for declared linear springs, resistors
or resistance models; it does not replace nonlinear Darcy physics.

`certify_linear_residual` requires a checked Schur certificate. It calculates
the exact residual and bounds the interior error by both
`abs(Kii_inverse) * abs(residual)` componentwise and
`norm_inf(Kii_inverse) * norm_inf(residual)`. It propagates those component
bounds to boundary force through `abs(Kbi)`. The inverse norm supplies a
positive stability lower bound for a nonempty interior. The result bounds
algebraic solve or reduction error only. Singular interiors return `UNKNOWN`
because a different stability theorem is required; physical model discrepancy
is never inferred from a residual.

The default domain is at most 64 coordinates under an explicit conservative
matrix-work budget. Exhausting the budget returns `UNKNOWN`. Context, input
matrix, ordering, loads or model bindings changing invalidates the certificate.

The 29 dedicated tests include the exact native three-spring example, affine
loads, singular compatibility, free modes, empty fibers, 16 corruption cases,
a checker that cannot call the producer, and thirty random systems with 750
boundary queries checked by an independent all-minors rank oracle. The
ill-conditioned example has residual one millionth and actual error one,
demonstrating why conditioning cannot be omitted.

`scripts/corpus_ports_benchmark.py` measures a declared synthetic chain of 13
original spring motifs. The 40-coordinate full network and a composition of
13 condensed motifs have the same exact two-port stiffness, `2/65`. Its full
state witness is compared against an independently derived cumulative series
compliance formula. Certificates and measured timings are retained under
`evidence/math/original-linear-port-chain-*`. This is mathematical network
validation, not a full-building physical benchmark or general speedup claim.

Unimplemented general P6 mechanisms remain explicit: nonlinear multiequilibrium
port membership, PDE/FEM/CFD certificates, adaptive basis enrichment, continuous
parameter-domain certification, dynamic/hybrid ports, acoustic phase relations,
global-mode completeness and physical model discrepancy. The original chapter
itself calls many practical instances research-level or unproved. Source
amendment A034 also repairs its general set-valued error-composition limit.
