# Checked outer obstacles for incomplete solid topology

For a selected, completely interpreted source representation, let its represented
occupied support be `O`, and let `E` be a checked closed outer box with `O ⊆ E`.
For a complete route envelope `R`, set-distance monotonicity gives
`distance(R, O) >= distance(R, E)`. Therefore `distance(R, E) > clearance` proves
the strictly separated route relation against that represented support. Closure,
orientation and interior validity of the source shell are unnecessary for this
one-sided implication. They remain unresolved questions about solid semantics.

An intersection with `E` establishes no actual clash with `O`. The box may be
occupied conservatively during candidate generation, but excluding all such
candidates proves neither actual clash nor routing infeasibility. Unknown source
items without a checked extent cannot become free space. Filling an open shell's
box is an explicit conservative search approximation; a physical completion that
could extend outside the box requires a larger proven bound or UNKNOWN.

Source trace: integration `DEF-SIR25`, native paragraphs 802–807; `DEF-SIR34` and
`DEF-SIR36`, 846–853; strict separation `THM-SIR13`, 1237–1246; certified FREE
cells `THM-RTR6`, 5091–5095; sound interval sign and unresolved overlap
`THM-RTR18`–`19`, 5132–5139. Source SHA-256 is
`72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`.

`ExactIfcEncloser` in `src/oma/ifc/enclosure.py` constructs an enclosure from raw
STEP decimal rationals for all items of every selected `Body` representation.
It traverses source references rather than asking whether a CAD result exists.
This prevents successful partial CAD conversion from hiding an omitted sibling
item. A source polygon is contained in its vertices' convex hull; affine maps
preserve convex combinations. Coordinatewise minima and maxima of outward
rational interval images of all vertices therefore enclose every supported face.
This proves the box relation directly, without converting the source to a solid.

Supported input is polygonal/triangulated face sets including indexed point maps,
faceted BReps, and shell/face-based collections of polygon loops. All source
polygons must be exactly planar; every referenced index must resolve. Placement
chains, 3D mapping operators, nonuniform scales and source length units are
included. Direction normalization uses rational square-root bounds, including
irrational rotations. Nonidentity representation-map origins and context frames
remain UNKNOWN until their convention is reconciled with the importer. Any
unsupported item blocks the entire selected Body enclosure.

There is a separate explicit mission policy, `vertex_hull_completion=True`, for
nonplanar source polygons. This policy defines an admissible family: each face
may be any affine triangulated interpolation/completion of its listed vertices,
or more conservatively any subset of that vertex convex hull. Every member of
this entire family lies inside the computed outer box even when the vertices are
not coplanar. The emitted claim is
`ALL_SOURCE_VERTEX_HULL_COMPLETIONS_SUBSET_OF_OUTER_BOX`; nonplanarity counts and
unestablished original face validity remain in the certificate. It does not
prove an unspecified CAD projection or a physical completion outside those hulls
is enclosed. The default exact-planar policy continues to reject nonplanarity.
The caller must select this broader represented-geometry interpretation in the
mission and bind it in every downstream certificate and cache key.

Every result binds the original source hash, product STEP identifier, arithmetic
contract, represented item coverage and the local engineering frame in metres.
The caller must establish that the selected Body representations are the intended
authoritative occupancy scope, and must transform route and obstacle bounds into
the same checked frame. Other representation identifiers are listed explicitly.
The result establishes neither whole-product solid validity nor unrepresented
physical extent. `ENCLOSURE_CHECKED` is an enclosure verdict; it is not route PASS.
The route checker must still dispose the full swept body, clearances, joint
geometry and every other in-scope obstacle.

Ordinary `BRepBndLib` output can supply a useful separate numerical CAD contract.
Its documented tolerances and triangulation deflections are not an independent
proof bounding every source conversion and floating-point rounding error. A
fixed added epsilon cannot silently promote that contract to exact geometry.
The [OpenCASCADE BRepBndLib documentation](https://dev.opencascade.org/doc/occt-7.5.0/refman/html/class_b_rep_bnd_lib.html)
describes the shape and triangulation tolerances used in CAD bounds;
[Bnd_Box](https://dev.opencascade.org/doc/occt-7.8.0/refman/html/classBnd__Box.html)
documents inclusion of the box gap when reading endpoints. These are distinct
from the raw-source rational enclosure implemented here.

The IFC interpretation follows buildingSMART's definitions of
[polygonal face sets and PnIndex](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcPolygonalFaceSet.htm),
[normalized placement axes](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcBuildAxes.htm)
and [mapping axes](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcBaseAxis.htm).
The finite tests in `tests/test_ifc_enclosure.py` cover raw decimal precision,
mutated in-memory numeric values, open surfaces, mapped nonuniform scaling,
units, irrational rotation, omitted/unsupported sibling support, invalid indices,
nonplanarity and unresolved map origins. Real-model coverage is measured
separately; tests do not imply all IFC geometry classes are supported.

## Exact extrusion and Boolean extension

The source checker also encloses positive-depth `IfcExtrudedAreaSolid` objects.
It reads rectangle dimensions, circle radii, simple closed 2D `IfcPolyline` or
straight `IfcIndexedPolyCurve` profiles as source rationals. Circular disks use
a containing square, so the witness corners are explicitly an enclosure rather
than a tessellation. Profiles with voids require simple closed nonintersecting
boundaries, all holes inside the outer boundary, and no nested holes. Profile
placement, solid placement, object placement, mapping and units are composed in
their declared order. A normalized extrusion vector multiplied by positive
depth gives the two endpoint copies whose convex hull contains the entire sweep.
This follows buildingSMART's [extrusion semantics](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2/HTML/schema/ifcgeometricmodelresource/lexical/ifcextrudedareasolid.htm),
[straight indexed curves](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcIndexedPolyCurve.htm)
and [profile void conditions](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcArbitraryProfileDefWithVoids.htm).

For supported bounded Boolean operands with boxes A and B, difference uses A,
union uses the containing box of A and B, and intersection uses A intersect B.
The boxes are closed, so regularization cannot escape these bounds. Both operand
definitions are checked; malformed or unsupported second operands remain
UNKNOWN even for difference. The rules follow the declared
[regularized Boolean operations](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcBooleanResult.htm).
Negative dimensions, nonpositive depth, planar extrusion directions, self-crossing
profiles, unsupported arcs or halfspaces, cyclic operands and unresolved source
items are never silently repaired. The exact profile-validation budget also
returns UNKNOWN if exceeded.

The September 14 full Digital Hub architectural probe produced checked exact
source enclosures for all 705 represented physical elements under the explicit
face vertex-hull interpretation. Eight records with no product representation
remain UNKNOWN. The result is in
`evidence/math/source-enclosure-digital-hub-completion.json` (217 seconds).
All five previously blocked heating products 140318, 440872, 530979, 532121 and
534204 are also enclosed, with evidence in
`source-enclosure-digital-hub-heating-five.json`. These support-containment
results preserve the interpretation condition and do not establish solid
validity, route feasibility, or unseen physical extent.

## Complete item-local support memoization

`ExactIfcEncloser` now evaluates each supported item tree once in its own source
frame. Only a complete successful result enters the instance cache, keyed by the
immutable STEP source hash, import-time checker hash, interpretation policy and
STEP item identity. The entry contains a closed rational interval box, the full
operand/face coverage and the number of nonplanarity checks. Returned coverage
is copied, so a consumer cannot mutate later certificates through an earlier
result. UNKNOWN results are retried and never acquire a cached bound. Every
Body sibling and mapped occurrence still participates in completeness checking.

If source support S is contained in a local box E, then its affine image T(S)
is contained in T(E). Applying the full outward interval affine to all eight
corners encloses T(E), including uncertain normalized-axis arithmetic. Unit
conversion is applied afterward. This deliberately permits a larger box after
rotation. A larger box can reduce the ability to prove route separation; it
does not establish a collision. The source solid-validity and interpretation
conditions remain unchanged. Boolean operands are all checked before a parent
entry is cached, and recursive cycles remain UNKNOWN.

The `memoize_item_support=False` option preserves direct support evaluation for
comparison. Cache telemetry is outside the certificate, while cold and warm
memoized certificates are identical. Five additional tests check mapped reuse,
detached complete coverage, explicit enlargement, failed siblings, Boolean
subtrees, nonplanarity evidence and policy/source separation. The complete
owned mathematical test set passed 191 tests on September 14, including the
subsequently added causal quotient checker. The completed comparison in
`evidence/math/source-enclosure-plumbing-memoization.json` evaluates 34 actual
Digital Hub plumbing products. Direct evaluation took 838.125 seconds, a fresh
memoized pass 159.641 seconds, and a warm pass 1.703 seconds. These are observed
times on a shared workstation, approximately 5.25 times faster cold and 492
times faster warm; they are not a general performance bound.

All 102 product evaluations returned checked enclosures. All 34 cold and warm
certificates were exactly equal, all direct comparisons retained identical
source coverage, and each memoized box contained the corresponding direct
interval box. The fresh cache held 394 complete local item trees and recorded
222 repeated uses. This validates the measured support-enclosure operation;
it does not establish route feasibility or original IFC solid validity.
