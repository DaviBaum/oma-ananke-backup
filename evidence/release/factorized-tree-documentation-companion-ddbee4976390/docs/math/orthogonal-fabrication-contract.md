# Exact orthogonal fabrication transitions

`optimization/fabrication.py` checks a fixed, axis-aligned polyline realized with constant round section, flat-cap straight cylinders and tangent circular quarter bends. It proves the stated local construction and full-body bounds. It does not implement a complete fabrication graph or accept a route.

## Source and supported correction

The supplied integration source, SHA `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`, defines fabrication state in DEF-RTR39 (native paragraphs 4472–4473), size state in DEF-RTR40 (4474–4475), and the fabrication-size graph transition requirements in DEF-RTR41 (4476–4484). ALG-RTR15 (5522–5523) calls for an exact finite or bounded lifted state. THM-SIR25 (1289–1290) gives the concrete failure of two half-metre legs with a one-metre bend radius.

This implementation specializes those obligations to an existing declared constructor: a constant section and fixed bend radius on one explicit orthogonal polyline. It carries incoming/outgoing signed direction, trim debt, remaining incoming straight and a fixed size root at every corner. Support phase and slope state are explicitly unmodelled. It does not infer a manufacturer catalogue, authorize size changes, discover topology classes or prove label dominance. Nonorthogonal segments and gravity-drainage slope cases return UNKNOWN.

## Exact local mathematics

Input finite floats mean their exact binary values. Derived diameter/2 plus insulation is an exact rational sum. Clearance is a separate separation requirement and is not silently added to the physical body radius.

At a right-angle corner P with incoming signed coordinate unit vector u, outgoing orthogonal signed unit vector v, and bend radius R, the tangent endpoints are A=P−Ru and B=P+Rv. The bend centre is C=P−Ru+Rv and normal is n=u×v. Both adjacent legs pay a trim of R. An interior straight between two bends pays both trims. Every remaining straight must be strictly greater than `max(minimum_straight_m, binary64(1e-9))`, matching the declared writer's strict construction convention. Rejection applies to this fixed segmented polyline; simplification or a different route may change the result.

With complete insulated radius r and R>r, the quarter-torus body is

`C + (R+s)(u sin(theta) − v cos(theta)) + t n`, with `0 ≤ theta ≤ pi/2` and `s²+t² ≤ r²`.

The sign of R+s stays positive. In the signed coordinate basis, its extrema are u in [0,R+r], v in [−R−r,0], and n in [−r,r] relative to C. The constructor uses those signed ranges. The independent checker obtains the tight box from attained cap-disk support points A±rv, A±rn, B±ru and B±rn. This finite endpoint characterization is valid for the supported coordinate-aligned frame; arbitrary rotated world frames need a different support calculation.

A straight cylinder has flat caps. Its axial bounds end at its tangent endpoints, while each transverse coordinate extends by r. The checker uses independently attained disk support extrema rather than trusting the constructor's bounds. Full-component containment in the allowed axis-aligned box is therefore exact for these primitives. A component outside that box is a verified local FAIL.

The quarter angle is retained symbolically as pi/2, and arc length as the rational coefficient R/2 times pi. The kernel does not substitute an unproved floating approximation for this exact identity.

When a complete authenticated outer obstacle family is supplied, each component AABB must have exact squared distance greater than clearance² from every outer obstacle box. This is a sufficient separation condition. Overlap or contact between outer boxes yields UNKNOWN, since it does not establish collision of their actual contents. Source authenticity and frame correspondence of the supplied outer boxes remain adapter premises. Nonadjacent component self-interference and actual fitting joints still require the independent physical checker.

## API and interpretation

`compile_orthogonal_fabrication(scenario, points_m, context_root=..., outer_obstacles=None, outer_model_root=None, max_points=256)` returns a rooted certificate with `status` PASS, FAIL or UNKNOWN, exact components, transition states and a disposition witness. Malformed typed input raises `ValueError`. Optional obstacle records are `{id,bounds}` with `[min3,max3]` bounds and a mandatory nonempty outer-model root.

`verify_orthogonal_fabrication(scenario, points_m, certificate, same keyword arguments)` checks the complete component and transition denominator, tangent identities, exact support extrema, source/input/artifact roots and stated disposition. It does not call the producer or its body-bound constructor.

The point budget is checked before traversing or converting any coordinate. An oversized sequence returns UNKNOWN with only its count, budget and caller context root bound; scenario, coordinates and obstacles are explicitly uninspected. It cannot provide a geometry identity or pruning claim. Normal in-budget certificates bind the complete normalized inputs. The verifier also bounds and type-checks component/transition lists before copying the certificate. The point budget bounds combinatorial work, not the bit complexity of arbitrary caller-supplied rational numbers.

**Verifier `status: PASS` means the disposition certificate is valid. Inspect `fabrication_status` for the geometric outcome.** A valid negative witness therefore has verifier PASS and fabrication_status FAIL. An unsupported case has verifier PASS and fabrication_status UNKNOWN. Either remains distinct from a candidate's native acceptance. Typed scope and identity substitutions, including Boolean/integer substitutions, cannot preserve certificate validity.

The context root must bind the intended proposal, immutable scenario and coherent implementation. The compiler provides no authority to change source objects, fixed endpoints or permissions. A local PASS is suitable for proposing or prechecking materialization; every candidate still needs actual IFC geometry, source preservation, contacts, full obstacle and service checks. Numerical export rounding can still reject a theoretically admissible near-threshold construction.

The converse numerical mismatch was also reproduced in actual files: two orthogonal legs of 0.75 m with R=0.5 m and minimum straight 0.25 m fail the exact strict rule at equality, but the historical floating constructor used `tan(pi/4) < 1` and accepted a remaining length of 0.25000000000000006 m. Both IFC4 and IFC2X3 produced three valid native parts. The immutable counterexample is retained in `evidence/math/fabrication/attempts/92c8f7d0b95a456e89f4787bec2a3310`. Thus an exact FAIL is a rejection in the stated mathematical construction model, not automatic authority to prune the numerical writer's outcomes. An adapter must establish the exact branch's applicability or a sufficient numerical margin. In particular, global axis alignment does not imply exact source-local axis alignment after a federation transform; full body-zone and obstacle claims retain their geometry-correspondence premises.

## Native correspondence and tests

The IFC exporter uses an `IfcCircleProfileDef` revolved through a quarter turn at radius R for an elbow, and direct circular extrusion for a straight. The independent IFC agent checked that its profile frame and revolution axis map to the signed construction above. The tests reopen the actual files using the independent component reader, then compare tangent endpoints, centres, normals, radii and volumes. Separately constructed OpenCASCADE cylinders and torus sectors undergo bidirectional Boolean-difference and volume checks against the actual native bodies. These are numerical CAD correspondence checks, not formal native equality.

The corrected writer now uses `ifc/orthogonal_fillet.py` for exact source-axis paths of at most 1024 points. Its independent rational construction uses trim R, exact strict remaining-straight predicates and rational tangent coordinates before conversion to native floats. The numerical arbitrary-angle fallback remains distinct. Actual regression evidence rejects the original equality case and exports the next representable admissible case in both schemas; the old passing counterexample is retained unchanged. This correction establishes the supported nominal construction rule, not exact native solid equality or a bound on every coordinate rounding error. The kernel's `automatic_numerical_writer_pruning_authority` remains false.

The focused suite has 69 passing tests. It covers all 24 signed coordinate quarter turns with rational samples of the complete swept disk and independent writer tangent comparison, both-end trim consumption, strict-threshold equality and the next representable value, full insulated-body zone failure, flat caps, separate clearance, unsupported cases, forged component/transition/root/scope witnesses, invalid finite-dimension guards, and IFC4/IFC2X3 correspondence in three axis orientations. `scripts/corpus_fabrication_benchmark.py` retains standalone exact certificates, actual IFC and independent native comparison reports in immutable attempt directories.
