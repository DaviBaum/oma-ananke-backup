# Complete physical source inventory

`oma.ifc.inventory.physical_inventory(model)` enumerates every `IfcElement` except `IfcFeatureElementSubtraction`. Each original identity remains a represented object, an explicitly failed object, or a representation-free assembly whose complete physical descendant coverage is accounted. An arbitrary decomposition relation is insufficient to omit a parent.

The declaration graph combines `IsDecomposedBy` and `IsNestedBy`. An assembly exemption requires every branch to end at a representation-bearing physical leaf; empty branches, nonphysical or subtraction-only children, missing physical leaves and cycles remain unresolved. A represented leaf must also occur in the consumer's actual geometry or explicit failure ledger. An explicit failure accounts for an identity but still blocks verification. Selecting only an assembly without selecting its leaves cannot produce an empty successful source load.

Cyclic or excessively deep decomposition is rejected before native conversion, because the native implementation can traverse inverse decomposition even when converting a selected leaf. The audit retains all product records and declines recursive containment/geometry traversal for that source. This is a bounded fail-closed behavior, not a declaration that its geometry is empty.

The native cache key binds the inventory helper version and implementation hash. Cache loading independently reconstructs the source graph, all required inventory errors and the complete selected object/assembly denominator. A rewritten manifest cannot drop a represented leaf by changing cached assembly flags. Cache geometry retains its separate local checker conversion-provenance assumption; inventory equality does not establish hostile-cache BRep equality or geometry validity.

## Refreshing an existing display audit

```python
from oma.ifc.inventory import refresh_inventory_audit

amended = refresh_inventory_audit(old_audit, immutable_source_path,
                                  checkpoint=control.checkpoint)
```

This helper returns a new audit and writes nothing. It preserves mesh artifact references, checks exact source bytes before and after derivation, validates every source product's identity/type/GUID/physical role/representation declaration, and rejects duplicate, missing or extra audit product records. It updates assembly dispositions, counts, blockers and `physical_inventory.root`. A display assembly is nongeometric only if all its represented leaves have accounted display meshes. Missing or failed leaf meshes keep the parent unresolved. Geometry is not reconverted, so this refresh does not issue a new native coordination certificate.

Checkpoint stages are `inventory_source_before_parse`, `inventory_source_parsed` and `inventory_source_derived`. Callers persist the returned audit under a new content root rather than overwriting historical audit bytes.

## Corpus amendment

`scripts/ifc_inventory_amendment.py` retains the complete 50-file immutable IFC-Bench denominator, original audit hashes, old/corrected physical dispositions and per-source declaration certificates in `evidence/ifc/physical-inventory-amendment.json`. The earlier pre-provenance run is separately retained. The final run completed all 50 sources in 212.94 seconds and found no changed dispositions: 243,353 represented objects, 816 legitimate representation-free assemblies, 16,430 unresolved objects and five unsupported objects. This does not remove the unresolved geometry obligations. `physical-inventory-impact-summary.json` records the blocker amendment: the existing nine incomplete-geometry and two unit-ambiguity file counts remain; six already unresolved sources also receive the explicit physical-decomposition reason code.

`scripts/ifc_reconcile_native_inventory.py` can separately bind a retained native report's actual object IDs to newly reconstructed source closure. This produces denominator evidence only. It never recomputes or upgrades the native verdict. The retained Digital Hub federation has 4,828 physical records: 4,820 native object entries and eight valid ARC assemblies, with all descendants accounted.
