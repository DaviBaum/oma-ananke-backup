# Bounded IFC tee and shared-network extension

Status: proposed contract for coordinated implementation. No tee exporter or checker is claimed implemented by this document.

A physical shared network must contain each trunk segment, elbow and tee once. Demand paths refer to the same component identities; they do not duplicate overlapping trunk solids. The optimizer supplies a candidate graph, while the independent checker reconstructs physical component geometry, port ownership, connections and demand coverage from the persisted IFC and the immutable network mission.

## First supported fitting family

The first family is an equal-round, orthogonal tee with an explicitly declared coordination envelope. Let its outer radius, including insulation, be R; its two axial takeouts are L and its branch takeout is B. Require positive finite dimensions, L > R and B > R with a declared cap-separation margin. The network mission fixes allowable fitting dimensions and section choices; export cannot enlarge or shrink them to make a candidate pass.

In the fitting's local frame, form the regularized union of a cylinder along X from (-L,0,0) to (L,0,0), and a cylinder along Y from (0,0,0) to (0,B,0), both radius R. IFC represents this as one Body item, `IfcBooleanResult(UNION, IfcExtrudedAreaSolid, IfcExtrudedAreaSolid)`. The output is one physical fitting with three external circular caps. The primitive overlap is internal CSG construction, not an exemption between separate components. [buildingSMART defines regularized Boolean solid operations](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcBooleanResult.htm).

The independent analytic volume oracle for this bounded geometry is pi R^2 (2L+B) - 8 R^3 / 3. A native checker must also establish a valid closed connected solid and complete Body-item coverage. The represented volume is an occupied coordination envelope; it does not establish a manufacturer's fitting wall, bore, fabrication shape or hydraulic loss coefficient.

IFC4 exports a pipe or duct fitting with `PredefinedType=JUNCTION`. IFC2X3 exports `IfcFlowFitting` linked to the corresponding pipe/duct fitting type with `PredefinedType=JUNCTION`. A junction redistributes flow through more than two ports. [IFC fitting classification](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcPipeFittingTypeEnum.htm), [IFC2X3 pipe fitting type](https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/FINAL/HTML/ifchvacdomain/lexical/ifcpipefittingtype.htm).

## Port and contact contract

The tee owns three unique ports at (-L,0,0), (L,0,0) and (0,B,0). Their physical outward normals are -X, +X and +Y. A distribution tee has one SINK and two SOURCE ports; collection reverses those roles. Terminal flow signs are fixed by the mission. Neighboring segments end at the actual tee caps, rather than passing into its body.

Physical outward normals and IFC placement axes are different quantities. IFC4 requires a SINK placement Axis to point into its owner; SOURCE points out, so connected SOURCE/SINK axes align. Each placement is relative to its owner. The current chain exporter and independent checks implement this convention; the earlier outward-SINK convention is retained as historical advisory IFC-PORT-001. All five first real proposals were regenerated from original sources, accepted and freshly checked as exported files after the correction. The numeric geometry and prior clearance evidence remain separate from the superseded semantic conclusion. [IFC4 ADD2 TC1 port placement and connectivity](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcsharedbldgserviceelements/lexical/ifcdistributionport.htm).

IFC2X3 expressly requires port placement relative to the owner's placement. Official Coordination View 2.0 implementation agreement CV-2x3-176 adopts the same IFC4 flow-dependent Axis rule, so both supported schemas use the same conversion. [IFC2X3 port placement](https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1/HTML/ifcproductextension/lexical/ifcport.htm), [CV-2x3-176](https://standards.buildingsmart.org/documents/Implementation/IFC_Implementation_Agreements/CV-2x3-176.html).

For fixed IFC4 ports, prefer `IfcRelNests`; IFC2X3 retains `IfcRelConnectsPortToElement`. A shared port ledger must enumerate both forms, retain every owner relationship and reject multiple or missing owners. Existing source relationships remain untouched. Each internal port has exactly one intended peer; unconnected ports must exactly match authorized network terminals. All port pairs require matching section and system, compatible flow, coincident cap centers and opposing physical normals.

Every distinct physical-component pair is checked. A positive common solid volume always fails, including a declared joint. Zero-volume contact may pass only when its entire common/contact topology is confined to the independently reconstructed interface disk and both ports actually lie on exterior caps of their own bodies. Adjacency alone grants no exemption. Nonincident pairs and separate networks receive the complete interference/clearance checks. Duplicate edges, duplicated trunks and undeclared intersections remain failures.

## Proposed APIs and responsibilities

`export_network(source, destination, network_spec)` accepts a unique physical component graph. Each component has a stable identity, kind, rigid frame, section and bounded geometric parameters. Each component exposes named ports. Connections identify two component/port identities; terminal bindings identify the remaining ports. A component may belong to several demand paths but is emitted exactly once. `export_route` remains a chain convenience wrapper over the common part writer.

The export manifest records every added physical component, its three-or-two port identities, explicit connection identities, terminal bindings and demand-to-component paths. It also retains all original-source hashes, inverse federation transforms and unchanged STEP-record evidence. Export/reimport must reconstruct the full network from one IFC replacement per edited source.

The checker independently parses the limited CSG tee structure and recovers both extrusion axes, radii, takeouts and the three actual cap disks. It does not trust `ObjectType`, producer labels or manifest geometry. Existing `_semantics` and reimport routines currently assume a single circular sweep and two ports per part; the extension must replace that assumption by the accepted component family and declared graph arity. `_explicit_joints` must obtain cap sections from independently parsed component geometry and a non-lossy ownership ledger.

At a tee, the incoming volume flow equals the sum of outgoing demand flows. Shared upstream trunks carry the aggregate demand once. Flow capacity, velocity limits and any pressure calculation require explicit section/fluid/catalog inputs and independently checked conservation. Missing hydraulic data remains an unresolved hydraulic obligation; no zero fitting loss or arbitrary diameter is inferred. Objective length, volume, installed cost and fitting count sum unique physical components, with any demand-path metrics reported separately.

## Required evidence before release

- Equal tee analytic/native volume agreement, native topology validity and complete cap reconstruction in rotated frames, metre and millimetre units, IFC4 and IFC2X3.
- Three unique owners and cap placements; independent failure for wrong flow axis, missing/ambiguous owner, extra Body sibling, interior fake port, duplicate connection, unsupported section and disconnected branch.
- Positive overlap with an attached neighbor fails; exact intended cap contact passes; near-threshold ambiguity blocks; nonincident and cross-network interference fails.
- A two-demand real IFC case materializes one trunk and one tee, conserves aggregate trunk flow, rejects a mutually interfering layout and exports/reimports the accepted complete network in a fresh process.
- Original IFC records remain unchanged. All source obstacles and all unique new-component pairs remain in the evidence denominator. Earlier chain exports retain their original versioned evidence and the discovered port-convention limitation.
