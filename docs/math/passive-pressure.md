# Checked passive quadratic network envelopes

`oma.optimization.passive_pressure` implements a bounded exact model for grounded pressure networks with any admitted finite topology, including three-sink trees and loops. Each edge obeys `h_u-h_v=K*q*abs(q)` with strictly positive finite resistance; internal vertices conserve flow at one common pressure potential. All prescribed boundary heads and resistances range over their full rational parameter boxes.

The kernel proves one unique equilibrium for each admitted parameter tuple and encloses every corresponding pressure and flow. It does not prove that a physical IFC junction follows this law. In particular, the existing outlet-specific tee losses referenced to total inlet flow are a different, coupled model. They cannot be silently converted to the new independent-edge law. No native adapter, delivery decision or acceptance authority is introduced here.

## Source and proof

The retained [design](../../evidence/math/passive-pressure/design.md) supplies the full argument and source locators. Original P6 PO1/PO2/PO7, the nonlinear classes at native Pages P16069–16077 and table 1736791, the port-envelope obligations P16118–16203, stability requirement P16360–16397 and signed quadratic example P16836–16853 motivate this specialization. The Pages source SHA is `0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970`.

Integration DOCX DEF-RTR56 P4592–4609 and RTR19/20 P5530–5533 require hydronic conservation/applicability and separate solving from independently checked evidence. Its SHA is `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. [Pinned paragraphs and native table evidence](../../evidence/math/passive-pressure/source-basis.json) remain unchanged. This implementation does not close the full original algorithms or their wider physical models.

For fixed parameters, the pressure energy is `sum 2*abs(h_u-h_v)^(3/2)/(3*sqrt(K))`. Every component is grounded at a prescribed boundary; its incidence map on free internal pressures is injective. Positive weights make the energy coercive and strictly convex. Its continuously defined gradient gives continuity equations even at zero flow. Hence a unique minimizer/equilibrium exists. No positive minimum flow, invertible numerical Jacobian or local Newton theorem is assumed.

The equilibrium lies within its component's boundary minimum/maximum. Rational internal lower and upper barriers establish a tighter enclosure when every complete lower-barrier outgoing residual is nonpositive and every upper-barrier residual is nonnegative, uniformly over the parameter box. Weak equality is valid: a hypothetical positive comparison-error plateau propagates along strictly monotone edge laws to a grounded boundary, yielding a contradiction.

The verifier independently reconstructs sign-dependent resistance extrema, pressure drops, rational square-root enclosures and the complete incidence sums. For each nonnegative radicand `x`, it checks `0<=a<=b` and `a*a<=x<=b*b`. At a negative drop, square-root endpoints and resistance choices reverse appropriately. It then independently derives all final edge-flow and boundary-injection intervals. This is a universal comparison proof, not interior sampling or acceptance of a producer's residual summary.

## Public API and exact input

```python
compile_passive_pressure(model, *, pressure_width_target=None,
    max_nodes=64, max_edges=128, max_work=2_000_000,
    max_refinement_passes=128, sqrt_bits=96, max_rational_bits=4096,
    max_input_bytes=1_048_576, max_certificate_bytes=16_777_216,
    checkpoint=None)

verify_passive_pressure(model, certificate, *, pressure_width_target=None,
    max_nodes=64, max_edges=128, max_work=2_000_000,
    max_rational_bits=4096, max_input_bytes=1_048_576,
    max_certificate_bytes=16_777_216, checkpoint=None)
```

The target is part of the query identity and must be supplied identically to verification. `None` means no target requested; a nonnegative rational including zero is permitted. Arithmetic values use strict integers or explicit integer, decimal or fraction strings. Binary floating values, booleans as numbers, exponential strings, Fraction objects and arbitrary subclasses are not model encodings. Container schemas are exact; unknown fields are rejected.

The complete model has these fields:

```python
{
    "schema": MODEL_SCHEMA,  # oma.passive-quadratic-pressure-model/1
    "nodes": ["S", "J", "T"],
    "internal_nodes": ["J"],
    "boundary_heads": {
        "S": {"lower": "1", "upper": "1"},
        "T": {"lower": "0", "upper": "0"}
    },
    "edges": [
        {"id": "SJ", "source": "S", "target": "J",
         "resistance": {"lower": "1", "upper": "4"}},
        {"id": "JT", "source": "J", "target": "T",
         "resistance": {"lower": "1", "upper": "4"}}
    ],
    "context_root": "<64 lowercase hex characters>",
    "physical_model_root": "<64 lowercase hex characters>",
    "assumptions": deepcopy(MODEL_ASSUMPTIONS)
}
```

`MODEL_ASSUMPTIONS` explicitly binds Cartesian domain, signed bidirectional flow including zero, head in Pa, flow in m³/s, resistance in Pa·s²/m⁶, zero internal injection, ideal scalar-head junctions and caller-declared physical applicability. Context/model roots are declared identities; their physical authenticity is not established by this standalone kernel.

Nodes and edges have unique bounded string identities. Internal and boundary sets must exactly partition all nodes. Parallel edges are retained separately; self-loops are unsupported. Every connected component must contain a boundary. A boundary-only graph, isolated boundary, zero-flow edge and constant uncertain-resistance plateau are supported. Nonpositive resistance, missing graph records, missing assumptions, unknown endpoints and ungrounded components fail input validation.

## Certificate and result interpretation

The certificate schema is `oma.passive-quadratic-pressure-envelope/1`, with scope `UNIQUE_GROUNDED_PASSIVE_EQUILIBRIUM_ENCLOSURE_FOR_EVERY_PARAMETER_IN_DECLARED_BOX`. It binds model, query, topology, domain, context, declared physical model and content roots. Complete component/grounding inventories and node/edge/internal/boundary counts are reconstructed from the input.

The proof carries:

- One ordered pressure interval for every node; prescribed boundary intervals cannot be narrowed.
- Three complete ordered edge proofs: lower barrier, upper barrier and final pressure box. Each carries two nonnegative radical enclosures and its signed flow enclosure.
- Both independently summed barrier residuals for every internal node.
- Every boundary's net outgoing-flow interval using the entire incidence.
- Actual internal pressure widths and the independently recomputed target-accuracy disposition.
- Explicit non-authority limitations and untrusted producer diagnostics.

Producer outcomes are `CERTIFIED_ENCLOSURE`, `INVALID_INPUT` or `UNKNOWN`. Verifier outcomes are `PASS`, `FAIL` or `UNKNOWN`. A valid certificate can be coarse: `target_accuracy_met=false` never turns into a tightness claim. When no target was requested this field is null. PASS returns actual checked denominators, pressure/flow boxes, boundary injections and fresh verifier work. It never means that every arbitrary combination of box coordinates is a feasible equilibrium or that one common flow works for every parameter tuple.

To make later physical decisions, a separate caller must use lower bounds for minimum delivery and upper bounds for velocity or maximum flow, with uncertainty handled explicitly. The kernel neither names every boundary a forward sink nor silently clips negative flow. Required physical regime, geometry and complete source applicability remain outside this certificate.

## Producer bounds and independent replay

The producer begins with the always-valid rational global boundary extrema. It tries a simultaneous midpoint vector, accepting a lower/upper update only when all appropriate node signs are established. This permits exact symmetric zero-flow cases to converge without relying on an inverse derivative. It then performs bounded coordinate bisection with the corresponding sign check. Neighbor effects preserve the barrier inequality; a final complete producer pass and independent verifier still recheck the entire graph.

At most half the work remaining after normalization is available for refinement. Local refinement work exhaustion or rational-bit growth retains the latest safe barriers and attempts a complete certificate. If overall parsing, proof, output or final guard budgets cannot finish, the result is UNKNOWN without partial network authority. Pass limits, target satisfaction and small progress provide additional search stopping conditions. They do not claim optimal or smallest enclosures.

Default arithmetic precision and refinement do not guarantee a requested width. Equal irrational fluxes may make a sharp residual sign unresolved under separate finite outward intervals. The producer uses outward slack/coarser barriers rather than an epsilon acceptance test. A general exact radical-cancellation engine and the design's optional residual-norm certificate are not implemented.

Before normalization, generic bounded JSON snapshots bind exact input bytes. Container counts are rechecked on those snapshots, including after a caller callback changes an object. The verifier byte-checks and snapshots the full certificate before parsing its rational proof quantities. Rational-token size, integer bits, depth, container and total structure, node/edge counts, work and byte ceilings are explicit. Supported configurable maxima are 1,024 nodes, 2,048 edges, ten million work units, 1,024 refinement passes, 512 square-root bits, 4,096 rational bits, 8 MiB input and 32 MiB certificate.

Each invocation has an independent budget; producer work/precision metadata never suppresses verifier arithmetic. Caller exception identity is preserved, including exceptions with internal budget exception types. After the final public completion callback, bounded input and certificate guards run with callbacks disabled. No callback can mutate the model or proof after normalization and obtain a mislabeled success. This does not assert atomic safety against arbitrary concurrent memory or filesystem writers, or against changes to the checker implementation itself.

## Tested checkpoint and integration files

The kernel SHA is `10fd4677d37952d4e0b41a1bf90aeba9bbdef5506e7e5c33ec8773dd456ec51e`. The immutable private source checkpoint is `6792b9b6eefbe8ceb91392b86582c4a2a4dcf6e7e3d2e994c84f8e2b37896cca`, based on the unchanged 1abe application tree plus this new standalone module.

The final portable focused test snapshot passed **119 tests, zero failures and zero skips**. [Its receipt](../../evidence/math/passive-pressure/kernel-final-checkpoint.json) pins the test and both fixture hashes and verifies source/test immutability. Tests cover exact one/two-junction three-sink trees, nonzero and reversed loop flows, zero-flow bridges, uncertain plateaus, boundary-only and disconnected grounded graphs, complete parameter-box comparisons against all 320 initial and 144 independent coupled-loop reference tuples, coherent false barrier packets, omitted/duplicated inventory, radical and incidence forgeries, request/root/type changes, all resource guards, independent producer-free verification and early/final callback mutation.

Initial evidence remains separate: 110 PASS/2 test failures on checkpoint 00087c6e, then 112 PASS after the reference-key and checked whole-vector refinement corrections, then 119 expanded/portable PASS. No false enclosure was observed in those initial failures. Counts overlap and are not cumulative coverage totals.

An [independent implementation audit](../../evidence/math/passive-pressure/independent-implementation-review/result.json) tested the same final module hash. Its 32 rationally manufactured equilibrium networks include 16 uncertain parameter boxes. All exact reference states and flows lay inside the public API enclosures; 210 resealed inventory, coherent false-barrier and final-callback attacks failed verification, and five explicit budget cases returned UNKNOWN. The verifier also passed with producer/refinement/square-root construction helpers disabled. These are bounded implementation checks, separate from the universal comparison argument. No concrete false bound was found. An earlier suspected callback count bypass was independently rejected and its original result plus correcting disposition remain retained.

The minimal application merge consists of exactly these four new files:

```text
src/oma/optimization/passive_pressure.py
tests/test_passive_pressure.py
tests/fixtures/passive-pressure/reference-results.json
tests/fixtures/passive-pressure/coupled-loop-result.json
```

The two fixtures are copied unchanged and their exact hashes are asserted by the test with UTF-8 decoding. The rest of this private source tree is a testing base, not a requested application replacement. Design/source evidence and this document may be retained as support artifacts. Native physical integration, current tee-model replacement, general solver machinery and full-source algorithm completion remain unimplemented.
