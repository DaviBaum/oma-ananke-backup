# Bounded native failure witness

`oma.ifc.negative_witness.find_forbidden_volume_witness` searches for one positive common volume between an actual newly authored route solid and one original IFC obstacle. It returns `FAIL` only when that counterexample is independently reproduced. Every other outcome is `NO_COUNTEREXAMPLE_FOUND` and requires the ordinary full checker to continue.

```python
result = find_forbidden_volume_witness(
    original_paths, export_path, route_guids,
    expected_source_sha256s=ordered_original_hashes,
    expected_export_sha256=actual_materialized_hash,
    authoring_source_sha256=original_authoring_source_hash,
    coordinate_evidence=persisted_federation_evidence,  # None for one unchanged source
    obstacle_hints=[{"source_sha256": source_hash, "ifc_guid": obstacle_guid}],
    max_probes=16, max_seconds=30, checkpoint=control.checkpoint,
)
```

Hashes are required and ordered like the original paths. Each hint may optionally select `route_guid`; otherwise the selected original obstacle is tried against the requested new route parts in order. Hints select work only. Their bounds, claimed validity, clearance and other producer fields are not evidence. Duplicate proposed pairs are not recounted. Missing or ambiguous GUIDs, subtraction features and hints outside the bound source or route sets cannot establish a witness.

The fresh child reopens all original source hashes and the exported hash, compares every original authoring-source STEP record, and rejects original objects masquerading as new routes. A single source uses the resulting exact identity correspondence. A federation rederives shared-anchor transforms from actual IFC bytes and compares the requested transforms. Native geometry uses those same independently established transforms; no co-centering is allowed. Source/export hashes are checked again immediately before a positive result.

For each selected member the child checks one complete supported Body representation, conversion diagnostics and native topology, including loose faces, edges and vertices. It requires a valid positive-volume solid. An incomplete native fragment, open shell, missing shape or conversion failure is skipped. There is no shell promotion, exact-source support extraction or occupied bounding-box fallback in this early phase. A persisted box is never an interference verdict.

The actual native Boolean common volume must be positive, with native distance evaluation completed and both transformed shapes still valid. Contact, numerical ambiguity, separation and a clearance-only violation cannot trigger this phase's `FAIL`. The underlying numerical CAD contract remains explicit; this is not a formal interval proof. Port, service, mission membership, self-interference, existing terminal-interface authorization and full-source feasibility remain caller obligations.

The result always records `scope=ONE_COUNTEREXAMPLE`, `full_source_denominator=NOT_RUN`, `feasibility_verdict=NOT_RUN`, and `acceptance_authority=NONE`. A positive result carries source/export hashes, module hashes, native versions, transforms, participant GUIDs/STEP identities, complete representation evidence, common volume and native witness points. It rejects the candidate only; it cannot accept any candidate or replace full-source denominators. Nested native pair reports may describe local separation, but the phase itself has no `PASS` outcome.

A separate child process enforces the wall limit even during one long native operation. A timer can terminate that child while a parent checkpoint is paused; no partial child output receives failure authority after timeout or abnormal exit. Cancellation propagates and kills the child. Ordinary unsuccessful probes are retained, including skipped invalid geometry and exhausted limits. Defaults are 16 proposed pairs and 30 seconds; the API caps requests at 256 pairs and 120 seconds.
