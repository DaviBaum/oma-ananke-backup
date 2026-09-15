# Independent provenance of generated shared-tree catalogues

`oma.routing.shared_tree_catalogue_check.verify_generated_catalogue` checks a supplied generated catalogue against the current authored requirements, finite search declaration and context. It independently reconstructs tee and connector geometry, exact section/cap relationships, nominal costs and the complete supplied macro inventory. It does not invoke the generator, its template enumerator, component converter or cost helpers.

This is the bridge between a generator's declared macros and the existing finite topology kernel. The latter proves complete ranked enumeration over the **supplied catalogue**. This checker proves that each supplied macro comes from the declared input and template language. Neither proof establishes that every allowed geometric template was generated, or that any tree is physically feasible.

## Source obligation

The unchanged source is `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. Native OOXML paragraph identities are ADD-SIR2.1 P3787-P3806 (branched carriers, edge sweeps and actual junctions); DEF-RTR39-44 P4472-P4513 (fitting and section states, connected terminal skeletons and allowed placements); THM-RTR50 P5254-P5256 (physical junction compatibility); and ALG-RTR17-22 P5526-P5537 (multi-terminal proposals, independent skeleton checking, physical fibers and route columns).

The implementation supplies a bounded independent macro-provenance check used by the ALG-RTR17/18 proposal workflow. It does not complete those source algorithms or the later fiber/physics/route-column obligations. All full-algorithm implementation flags remain false.

## API and identities

```python
verify_generated_catalogue(requirements, search, generated, *, context,
    max_work=2_000_000, max_bytes=16_777_216,
    max_macros=1024, max_attempts=20000, checkpoint=None)
```

`requirements` is the authored shared-network field declaration without `network_alternatives`. The shared `SharedTreeRequirements` Pydantic field parser preserves field types, defaults and constraints from `SharedNetworkScenario`; it is a declared parser dependency, not a replacement for downstream complete mission validation. The independent checker replays field normalization and compares `generated.normalized_requirements` exactly.

The raw input identity is the canonical JSON hash of `{"requirements": requirements, "search": search, "context": context}`. The catalogue separately binds raw requirements, normalized requirements, search, current context and the nominal cost policy. Hashes identify supplied data; authentication of source files, native geometry, policy or current execution belongs to the caller.

`search.schema` is `oma.shared-tree-native-search/1`. The supported declaration has one source direction, every sink direction, one to eight authored tee instances, one to four positive stub lengths and up to eight named coordinate planes. There are exactly two or three sinks. Tee frames and forward cap directions are signed coordinate axes. The current generator/checker contract supports fixed-flow requirements; pressure-specific generated tee contracts remain unsupported and are not reinterpreted.

## Independent reconstruction

Every authored tee must appear once, including unused tee alternatives. Its proper signed-axis frame, center, takeouts, nominal section, three physical port roles and exact caps are recomputed. The tee definition hash and its unchanged loss-contract hash are checked. Takeouts must exceed the full nominal outer radius. Source and sink identities, demand identities, locations and forward directions must match the normalized mission and authored search.

Each supplied connector must connect allowed directed caps: source to tee inlet, or tee outlet to a different tee inlet or sink. Its first and last nonzero directed runs must match the complete cap positions and forward directions. Coordinates, tangent points and physical geometric fields promised exact by this model must be exactly representable in binary64. The complete diameter and insulation fields must agree with the normalized section.

Template membership is checked independently. A supplied reduced orthogonal word must be either the direct option or a word obtainable from the declared lead/tail stubs and a Manhattan coordinate permutation, optionally through one declared plane. The checker combines equal consecutive directed runs using its own segment representation rather than calling the producer's point simplifier. Membership does not establish that all words in this language appear in the supplied catalogue.

For each connector, `verify_orthogonal_fabrication` replays the actual path against a freshly constructed current `RoutingScenario` and input root. Both its proof disposition and nominal fabrication status must pass. Producer witnesses and the stored independent-check result are compared to fresh replay, rather than trusted.

The checker separately derives every segment and quarter-turn elbow directly from the connector points. Each orthogonal elbow consumes bend radius R from the incoming and outgoing runs. Segment lengths are the remaining flat-cap axial distances; elbow arc length contributes `R*pi/2`. All segment endpoints, elbow center/normal/radius/angle, diameter/insulation, ordering and IDs are checked against the supplied physical component list. Components are not reconstructed from the producer's claimed component array. All physical IDs are unique across tees and all supplied macro alternatives.

With weights `wL,wF`, connector cost is the exact pair `(wL * sum(straight lengths) + wF * elbows, wL * R * elbows / 2)`, representing `a+b*pi`. Tee cost is `wL*(2*trunk_takeout+branch_takeout)+wF`. These are nominal accounting values, not measured native costs or physical lower bounds. The finite topology kernel later charges each selected tee and connector once; it does not sum shared-trunk costs once per demand path.

Connector IDs derive from current endpoints and the complete reduced word. Macro geometry hashes include the complete physical component list. Fabrication roots, section, caps and cost are checked separately. The connector row list, macro map and admitted-attempt list must have exactly the same unique IDs and definitions. Missing, duplicated or extra members in any one denominator fail.

Rejected/unsupported attempt definitions must reference current caps and template words and carry allowed diagnostic shapes. Their rejection payloads remain untrusted diagnostics. The result explicitly denies certified diagnostic rejections. Removing a macro coherently from the row, macro and admitted-attempt inventories yields a smaller supplied catalogue which may validly pass; it cannot establish full-template coverage or physical infeasibility.

## Dispositions and resource boundary

Success returns `status: PASS`, `proof_complete: true`, the input/generated/catalogue/normalized-requirements/context roots, complete counts and scope `SUPPLIED_CATALOGUE_CURRENT_INPUT_TEMPLATE_MEMBERSHIP_AND_NOMINAL_MACRO_PROVENANCE_ONLY`. It explicitly sets `native_acceptance_authority`, `all_templates_enumerated` and `diagnostic_rejections_certified` to false. Invalid or forged evidence gives `FAIL`; supported resource exhaustion gives `UNKNOWN`. Neither disposition carries a partial proof.

Strict integer budget types, bounded JSON shapes and canonical byte limits precede arithmetic. The default limits are ceilings, not a promise that the simultaneous maximum inventory fits the work/byte budget. Rational fields are bounded before `Fraction` conversion, including a scientific exponent check and a strict canonical rational precheck for fields passed to the older fabrication verifier. Derived rational coordinates and costs are also bounded. Each macro has at most 16 points, 32 claimed fabrication components and 16 transitions. The existing fabrication replay is a bounded synchronous subcall with checkpoints immediately before and after; work accounting charges its bounded inventory rather than claiming instruction-level or wall-time accounting.

Callbacks are cooperative and retain the exact caller exception object. The final callback precedes complete current-input/current-generated hashing with callbacks disabled. These final tails count toward work. Captured inventory shapes are rechecked after callbacks. This protects against callback mutation, not simultaneous hostile threads or an atomic filesystem transaction.

## Validation and retained evidence

The new module SHA256 is `688cb03a0c75f23ee07e3e4b668980ec7d94267337b6c0f9b7ac4e5309045f7b`. Snapshot `2db9a9cd13eea2fbd1633b4b9a02f44892a90d37f870d25d005c6a283c648ab4` binds the module, exact test bytes, four portable JSON fixtures and a 110-file dependency-source root. It is not a complete production executable identity.

Receipt `validation/6ee4dfcb1f67409baee0be07f8a986cd` records 94 collected and executed tests, zero skips/errors/failures, and unchanged new/dependency inputs. It includes producer-disabled verification; coherent cap/section/geometry/cost/proof/root attacks; a valid fabrication proof for an unauthored detour word; numeric exponent sentinels; full input/byte/work boundaries; callback exception identity and final mutation checks. The fixture contains two tees, three terminals, twenty connector macros, 106 physical catalogue components and ten non-authoritative rejection diagnostics. These are provenance tests; they do not rerun native acceptance.

The first immutable collection attempt failed because a Windows backslash path in the pytest override selected the wrong package path. Its receipt and source/test snapshots are retained at `validation/ea16b6f1110b4aaca0b85a1047dec11d`; the runner was corrected with an explicit dependency `PYTHONPATH` and forward-slash pytest path. No kernel failure was hidden or converted to success.

An unchanged replay of the earlier producer resource probes is retained at `evidence/corrected-producer-resource-review/9915534d5b6a4de49a89dc2ee3911a92`. The corrected producer observes callbacks when work jumps over a polling threshold, returns UNKNOWN for an exhausted nested budget, and binds a decimal-string dimension to the same normalized exact section used by fabrication. The original failed receipt remains unchanged. Pure synthesis module `0034130d` already rejects scientific notation before rational allocation; its separately retained sentinel replay required no source amendment.

Actual native materialization, complete source/self/contact/zone coverage, current service requirements, managed admission, acceptance and fresh exported-IFC verification remain downstream obligations. No native PASS is reused by this module. Its tests and proof cannot replace those checks or certify all feasible physical shared trees.
