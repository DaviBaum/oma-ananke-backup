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
