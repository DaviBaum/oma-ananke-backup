# Independent review of the authorized opening integration

The reviewed contract is one explicitly requested rectangular through-opening in an eligible original IFC wall or slab, followed by a locally checked physical route. It is a geometry-only edit. Permission is bound to the immutable scenario; its external authority and structural, fire, access and whole-building adequacy are not inferred.

The review covered `routing/opening.py`, the opening paths in `routing/engine.py`, `routing/checker.py`, `routing/scenario.py`, `routing/joint_scenario.py`, `ifc/cad.py`, `exporting.py`, `ifc/recheck.py`, and the native adapter `ifc/openings.py`. It also inspected the shared inverse-relationship guard and its ordinary-route and shared-network call sites after the findings below. This is a code and adversarial behavior review, not a formal proof of all application behavior.

## Two corrected preservation gaps

The candidate entity-preservation check initially compared only baseline dictionary entries. Additional or duplicate candidate entity records could satisfy that subset test. The checker now requires the entire imported entity sequence to equal the baseline sequence and requires unique baseline identities, while tracking the authorized host edit separately.

More materially, an added `IfcRelDefinesByProperties` could attach an unauthorized property set to an original `IfcSpace`. Original STEP text remained unchanged, the new physical-element count was unchanged, and the native opening checker returned PASS. An `IfcSpace` is not an `IfcElement`, so a guard limited to original elements missed this inverse relationship effect. The original actual IFC artifacts and passing report remain unchanged under `evidence/math/probes/opening-inverse-property-5b5460894e`.

The corrected route argument builder checks the targets of property, group, nesting, port ownership, connection and containment relationships. New route metadata may refer only to the intended new route objects. The native checker protects original `IfcObjectDefinition` targets, with narrowly checked exceptions for new-part spatial containment and explicitly requested original terminal attachments. The common `ifc/protected_semantics.py` guard also applies to ordinary routes and shared networks. Hash equality authenticates neither arbitrary added relationships nor their effects.

Focused regressions in `tests/test_opening_inverse_effects.py` exercise original-space properties, original property sets and groups, both nesting directions, original port/host ownership, mixed original/new spatial containment, unrequested terminals and original realizing elements. Positive cases retain actual route metadata and spatial containment. Ordinary-route and shared-network checks are exercised against actual exported IFC files as well.

All 14 focused tests passed in 1.38 seconds; the retained JUnit record is `evidence/math/opening-inverse-regression.xml`. Replaying the unchanged earlier attack file now returns REJECTED from the route argument guard and FAIL from the native opening checker, each specifically because of the unapproved inverse effect. `corrected-result.json` beside the original evidence binds the old report, actual IFC bytes and current checker source hashes. The earlier PASS remains preserved as historical evidence of the defect.

## Checked claim boundaries

The immutable request names the original source hash, host GUID and STEP identity, host geometry root, permitted local bounds and explicit geometry-only permission. The source host descriptor and its geometry are freshly reconstructed. The original records, one added opening, one added void relation and the complete appended record denominator are checked. A second void cannot hide inside the separately checked route-record allowance.

The clearance adapter replaces exactly one original obstacle having the authorized source identity, STEP identity and GUID. It then applies the same source-to-federation transform and retains the other source obstacles and pair denominator. The route must pass against the effective host and every other admitted obstacle. Exported IFC files are copied and freshly rechecked rather than inheriting candidate acceptance.

The rational four-cell checker proves an exact identity for its declared local host-box difference. The IFC adapter checks numerical native agreement using topology, volumes and bidirectional symmetric differences under an explicit error budget. That numerical correspondence does not turn the rational cells into unconditional exact occupied subsets of arbitrary native IFC geometry. Likewise, a valid geometry-only opening does not establish structural or fire approval.

The separate route-cell kernel can use those cells as exact inner support in the declared rational model. A real geometry adapter must establish its own source/frame/body correspondence before transferring an inner-path or outer-impossibility conclusion. In particular, an oversized conservative envelope of a physical route is sufficient for some safe-path checks but is not automatically a necessary body model for proving physical impossibility.
