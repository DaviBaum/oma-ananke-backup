# A bounded, authorized physical opening

The first contract is one rectangular through-opening in one explicitly selected, valid rectilinear slab or wall. The exact local support kernel is implemented and independently checked; the native IFC adapter and real-host benchmark remain separate application work. The opening is a physical architectural choice, with its own immutable authorization and candidate identity. It is not an inferred permission from a route clash.

The kernel API is `compile_rectilinear_opening(host_bounds_local, opening_bounds_local, *, through_axis, context_root, source_roots)` and `verify_rectilinear_opening(host_bounds_local, opening_bounds_local, certificate, *, through_axis, context_root, source_roots)` in `oma.optimization.rectilinear_opening`. Bounds are `[min3,max3]`; the axis is integer 0, 1 or 2; roots require `source`, `host`, `frame` and `authorization` identities. Decimal strings and fractions preserve exact decimal/rational values. Finite float inputs mean their exact binary values, not an assumed source decimal. Unsupported inputs raise `ValueError`; a malformed or false certificate returns FAIL. The verifier checks a complete exact arrangement of coordinate endpoints and interval interiors without rerunning the four-strip constructor.

The 48 focused tests cover every through axis, exact fractional coordinates, shaft boundary faces, identity/scope tampering, same-volume shifted support, overlap, missing cells, blind recesses, invalid numbers and fifty seeded random exact boxes against an independent voxel oracle. This establishes the kernel's stated represented-geometry scope, not native geometry or engineering approval.

## Immutable request and authority

The request binds the complete original source hashes and federation transforms, host source/STEP/GUID identity, the exact supported host representation and placement, an explicitly editable host, the allowed opening zone, opening dimensions and transform, geometric tolerance policy, and the authority/evidence roots approving that precise change. A user-supplied engineering assumption can define a deliberately scoped experiment; it must remain labeled as supplied and cannot become an independently established structural or fire approval.

Support only finite positive dimensions, an orthogonal rectangular section, and a through direction normal to the host faces in the first implementation. The cut must intersect the host, pass through both declared faces, remain within the approved footprint and leave the host in the supported nondegenerate topology class. Reject unknown units, ambiguous host identity, unsupported mapped/deformed host geometry, host or opening Boolean failure, uncertain datum, existing unexplained voids, overlapping new edits, and missing authority. Later support for nonrectilinear or multiple interacting openings requires its own checked contract.

## Exact geometric meaning and its numerical realization

Let `H` be the original effective occupied host support, `V` the authorized opening solid, and `O_other` every other occupied obstacle. The intended edited support is

```
H_new = regularized_difference(H, V)
O_new = O_other union H_new
```

For an axis-aligned or rigidly placed rational rectangular host and rational rectangular through-cut, derive the expected remaining host as a finite disjoint-interior union of rectangular cells. Check their complete union against the declared subtraction using exact interval endpoints in the host frame. This gives a source-independent expected support model for the first bounded case. A convenient implementation restricts the opening footprint strictly inside the host footprint, so four remaining strips cover the exact difference without disconnected or zero-width remnants.

The exported IFC must contain exactly the approved new `IfcOpeningElement`, its checked placement and swept representation, and exactly one appropriate `IfcRelVoidsElement` binding it to this host. Preserve every original STEP record, including the host's uncut representation, as required by the edit contract. The new relationship changes the host's effective geometry despite those original bytes being preserved. Check all new records and allowed relationship effects; appending an unauthorized second void is a material edit even if every original record is unchanged.

Reopen the actual exported IFC. Independently reconstruct the opening geometry and relation from its records, independently reconstruct the expected host difference, and inspect the native effective host returned by the IFC geometry conversion. The numerical CAD checker must establish compatible complete support, closed valid solids and agreement with the expected result under its declared numerical contract. Matching volume alone is insufficient: an opening at another location can remove the same volume. Exact source cell comparison is stronger for the restricted rectilinear case. Native Boolean symmetric differences and distances may supply additional independent numerical checks, but zero numerical volume must not be described as a formal exact equality proof.

## Complete application and invalidation

Bind the candidate's effective obstacle inventory to the edited source. Replace exactly the selected original host by its independently checked edited support. Retain every other original obstacle, including all separate federation files, and account for the opening as subtractive geometry rather than a second occupied solid. Preserve the original host identity while recording its new semantic geometry root and the authorizing edit. Do not simultaneously include the old uncut host as another physical obstacle or silently omit the host entirely.

The route and all fittings, insulation and clearance envelopes must fit through the actual opening and remain separated from the residual host and every other protected obstacle. New route geometry, opening geometry, allowed region and endpoint conditions are separately checked. Any intentionally permitted interface requires a local geometric certificate; there is no whole-pair contact exemption.

Invalidate every geometry, route-clearance, access, structural, fire, quantity, dependency and approval obligation that reads the changed effective host or its opening relations. Unimplemented affected disciplines remain explicit UNKNOWN or external supplied assumptions within the permitted scoped experiment. Original-byte preservation is neither a proof of unchanged structure nor a permission to retain stale obstacle-pair results. The export recheck rebuilds the new effective host and all pair denominators from actual IFC bytes.

## Required first ground truth and adversarial cases

Use a synthetic rational rectangular host with an interior rectangular through-cut. Check the independent exact remaining-cell union and exact removed volume, plus actual native IFC reopening and route clearance. Compare an uncut baseline failure with a cut candidate that passes only the approved local geometric scope. Then use an explicitly authorized opening in an eligible real IFC host; unsupported real host forms remain blocked.

Negative cases include absent or wrong-host void relation, shifted opening with equal volume, a blind recess that does not pass through, wrong units or placement, an extra unauthorized opening, a route colliding with the remaining edge, changed noneditable source records, stale host geometry cache, hidden body siblings, and changed approval or allowed-opening zone. Every expected rejection must use the actual exported file, not only the request object.

Source trace: integration SIR rewrite correspondences and occupied-support compilation; JCD architectural edit domains, authorization and materialization fibers; RTR physical fitting/clearance and complete obstacle accounting; CMP dependency and commit applicability. Original SOV protected-intent and trace-sensitive authority applies to the opening authorization. No general architectural synthesis, structural design, firestop selection or new-building generation is introduced.
