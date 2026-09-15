# Native authorized opening adapter

`oma.ifc.openings` implements one bounded rectangular through-opening in a directly represented rectangular `IfcWall` or `IfcSlab`. The original source must have one complete rectangular extrusion, known units, a proper rigid placement, no existing host voids and one independently validated closed native solid. Unsupported source geometry remains ineligible.

The source-local host frame includes the product placement chain, extrusion placement and rectangular profile placement. Dimensions come from raw STEP decimal rationals. The frame is a numerical rigid transform in source-world metres; it is not a federation or GIS certificate.

```python
host = inspect_host(source_path, host_guid, host_step_id=None)
manifest = export_opening(source_path, opening_path, request, fresh_recheck=True)
report = check_opening_semantics(opening_path, source_path, request, manifest)
effective_host, report = load_checked_effective_host(
    opening_path, source_path, request, manifest)
```

`request` is the root-owned `AuthorizedOpening` schema. It binds source hash, host GUID/STEP/geometry root, opening and allowed local boxes, through-axis and the explicit geometric permission statement/evidence. Permission is supplied scenario input; the adapter does not authenticate structural or fire approval. It never infers permission from a route clash.

The exact local kernel constructs four residual boxes and independently verifies their closed regularized union against the host-minus-opening set on every endpoint-arrangement stratum. The native checker reconstructs the effective host from the actual exported IFC and compares it with the independent four-cell native union using both directed Boolean difference volumes, closed-solid validity and total volume under the declared numerical budget. These numerical native comparisons are not a formal proof of native geometric equality. The exact certificate is limited to the rational local represented set.

The writer appends one `IfcOpeningElement` and one `IfcRelVoidsElement`, with host-relative placement, preserving every original STEP record. IFC4 and IFC2X3 fixtures are tested. The subtraction relation and through-opening interpretation follow the official [IfcRelVoidsElement](https://standards.buildingsmart.org/IFC/DEV/IFC4_3/HTML/lexical/IfcRelVoidsElement.html) and [IfcOpeningElement](https://standards.buildingsmart.org/IFC/DEV/IFC4_3/HTML/lexical/IfcOpeningElement.html) definitions. Exported IFC2X3 profiles include their required explicit profile placement.

## A final route file containing the opening

For an opening artifact followed by a route export, the final checker accepts these keyword arguments:

```python
report = check_opening_semantics(
    final_route_path, original_path, request, opening_manifest,
    allowed_new_step_ids=independently_accounted_route_steps,
    allowed_new_element_guids=independently_checked_route_guids,
    allowed_existing_terminal_guids=explicit_requested_original_terminal_guids,
    expected_export_sha256=immutable_final_export_hash,
)
```

`load_checked_effective_host` accepts the same arguments. The caller must separately check the complete route record inventory and semantics. The opening checker requires the exact original records and authored opening record digest, and independently rederives actual opening geometry, location, relation and expected remaining support. An allowance cannot authorize any additional feature or void/project relation. New relationships into original objects, including property assignments to original spaces, are rejected. The specific permitted exception is spatial containment of separately checked new route elements in an original spatial structure. Extra void relations reusing an existing opening are rejected too.

An additional exact exception permits a connection to each explicitly requested original terminal port. Each original terminal must be unique and initially unconnected; every named terminal must be used once, and the actual new link must satisfy IFC flow/placement semantics and name a separately checked new route part as its realizing element. Unnamed ports, unused blanket exemptions and repeated attachments are rejected. Physical cap attachment and route-to-existing-owner contact remain obligations of the complete route checker.

The returned `CadObject` keeps the original full source SHA, GUID and STEP identity for exact inventory replacement. Its native shape is the **edited** effective host in source-world metres. Its support metadata binds the edited IFC hash, request root and edited geometry root. The caller must replace exactly that original obstacle, retain all other source obstacles, apply an independently audited federation transform consistently, and check every route/obstacle pair. An optional `source_to_federation_matrix` argument applies a proper rigid transform but leaves authentication of that matrix as an explicit caller obligation.

The adapter's report always leaves all-other-obstacle and route-clearance status `NOT_RUN`. Tests include an actual round route through the edited host, a colliding residual edge and an uncut baseline failure. This local demonstration does not grant application acceptance or whole-building certification.

Validation: `tests/test_ifc_openings.py` covers both IFC schemas, millimetres and rotated frames, complete source preservation, exact/native subtraction, final route-file integration, malformed/ambiguous source forms, wrong-host or absent relations, shifted equal-volume cuts, blind recesses, hidden siblings, changed original records, extra/reused voids, detached appended geometry, changed permission and stale uncut native geometry.
