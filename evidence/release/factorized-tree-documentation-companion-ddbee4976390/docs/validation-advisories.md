# Known validation advisories

## IFC-PORT-001 — historical authored route port semantics

Identified 2026-09-14 during physical tee-extension review. Previous authored route exports encoded both SOURCE and SINK placement axes as physical outward normals. They also used absolute port placements and reversed the external sink connection order. The earlier independent checker shared these conventions, so its port-semantic PASS must be superseded.

The official [IFC2X3 CV2.0 agreement CV-2x3-176](https://standards.buildingsmart.org/documents/Implementation/IFC_Implementation_Agreements/CV-2x3-176.html) adopts the IFC4 convention: SOURCE axes follow the outward connection direction, while SINK axes point inward. Port placement is relative to the owning product. The [IFC4 distribution-port contract](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcsharedbldgserviceelements/lexical/ifcdistributionport.htm) also specifies source-to-sink connection semantics.

`oma.validation_advisories` identifies older application-authored route manifests without the corrected convention. Acceptance and checked export refuse them. Assurance cases retain historical dispositions but cannot derive current supported engineering claims through an unresolved advisory. The UI exposes the advisory with affected route identities. Original imports, prior candidate roots and prior export bytes remain immutable.

Resolution requires corrected IFC authoring and independent native checks of flow axes, owner-relative placement, connection order, endpoint compatibility and actual cap attachment. New manifests identify `IFC_FLOW_AXIS_V1`, but that annotation is not evidence that the native checks passed. Existing real examples must be regenerated and rechecked from their fixed original missions. Numerical clearance evidence has its own declared scope and is not a substitute for corrected IFC semantics.

Status: correction and real-example regeneration in progress. No production-ready export claim is made.
