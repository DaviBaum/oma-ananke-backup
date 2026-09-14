# Finite executable causal macro contract

The original Pages source `1-10` defines typed action relations and equality of
successor equivalence-class sets in DEF-CS5 (`P18648–P18655`). LEM-CS3 and
THM-CS3 (`P18708–P18747`) prove coarseness for finite carriers. ALG-CS1 and
THM-CS21 (`P19214–P19264`) give the explicit refinement algorithm and request
recursive distinguishing certificates. These native passages were read in
hash-bound review chunks 46–47. The source SHA-256 is
`0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`.

`oma.optimization.bisimulation.compile_bisimulation` implements that finite
relation algorithm. Inputs are nonempty typed carriers, all direct observation
values, and complete rows for every declared action and every source state.
An empty row explicitly means a disabled action. A missing row is rejected.
Relations preserve sets of outcomes, without assigning probabilities or counting
duplicate transitions. The immutable context root must bind the source model,
experiment family, action semantics, evidence, intent and applicable domain.
All actual table contents also contribute to the certificate root.

The compiler begins with observation classes and repeatedly splits by every
action's exact successor-class set. A strict round increases the block count,
so at most the initial state count minus initial block count rounds occur.
All supplied states are represented. Here “reachable macro” means each macro
has a concrete representative; no initial physical state or operational
reachability from an initial state is inferred.

`verify_bisimulation` independently checks carrier coverage, typed observation
uniformity and each original relation row against the quotient. Equality of
successor-class sets provides both directions required for strong bisimulation.
The checker does not repeat partition refinement. It evaluates a typed acyclic
modal formula DAG directly on the original transition relation. The grammar is
observation equality, conjunction, negation and existential action modality.
Each block must have a formula true on exactly its members within its sort.
Induction on these formulas shows they are invariant under every
observation-preserving strong bisimulation; their exact truth sets therefore
prove that no two reported blocks can be merged. One characteristic formula
per block witnesses all same-sort block pairs.

This certificate construction is an explicit implementation of the source's
recursive distinguishing obligation. Single action traces would be insufficient:
the test suite includes early versus late nondeterministic choice with identical
linear trace outcomes but different executable macrostates. It also checks 80
random small systems against an independent greatest-pair-relation elimination
oracle, and rejects stable but unnecessarily split partitions, cyclic modal
proofs, missing action rows and altered model roots. Compiler and verifier work
budgets return `UNKNOWN` upon exhaustion. Refinement telemetry is diagnostic;
the checker certifies the final semantic quotient and modal witnesses.

This is a supplied finite-model kernel. It supplies only the exact relation and
observation subset of ALG-CS6 (`P19974–P20012`). It does not establish omitted
physical actions, source-to-physics applicability, port or rewrite compatibility,
action footprints, approximate simulations, optimal causal separators, or
whole CSSP release. The original P7 body is unavailable in the supplied Pages
corpus; this implementation does not invent it. A physical adapter must include
every mandatory observable and supply independently justified transitions before
using a quotient to execute a physical change.
