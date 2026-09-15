---
project: west_riverside_hospital
models:
  - file: arc_ifc2x3.ifc
    discipline: Architecture
    schema: IFC2X3
  - file: arc_ifc4.ifc
    discipline: Architecture
    schema: IFC4
  - file: str_ifc2x3.ifc
    discipline: Structural
    schema: IFC2X3
  - file: str_ifc4.ifc
    discipline: Structural
    schema: IFC4
  - file: mech_ifc2x3.ifc
    discipline: Mechanical
    schema: IFC2X3
  - file: mech_ifc4.ifc
    discipline: Mechanical
    schema: IFC4
  - file: plumb_ifc2x3.ifc
    discipline: Plumbing
    schema: IFC2X3
  - file: plumb_ifc4.ifc
    discipline: Plumbing
    schema: IFC4
  - file: elec_ifc2x3.ifc
    discipline: Electrical
    schema: IFC2X3
  - file: elec_ifc4.ifc
    discipline: Electrical
    schema: IFC4
  - file: fire_ifc2x3.ifc
    discipline: Fire Alarm
    schema: IFC2X3
  - file: fire_ifc4.ifc
    discipline: Fire Alarm
    schema: IFC4
  - file: sprinkle_ifc2x3.ifc
    discipline: Sprinklers
    schema: IFC2X3
  - file: sprinkle_ifc4.ifc
    discipline: Sprinklers
    schema: IFC4
license: CC BY 3.0
usage: healthcare
author: "Solihin, W. West Riverside Hospital IFC Models. OpenIFC Model Repository, University of Auckland."
source: "https://openifcmodel.cs.auckland.ac.nz/"
---

# west_riverside_hospital

## Description

A large multi-storey hospital building donated by Wawan Solihin (Singapore) and hosted on the
OpenIFC Model Repository by Professor Robert Amor at the University of Auckland. The dataset
provides seven disciplines each available in both IFC 2X3 and IFC 4, making it one of the most
comprehensive multi-schema, multi-discipline BIM datasets in the public domain.

The architectural model covers 8 levels (Level 1 through Level 7A, elevations 0--34000 mm).
The structural model covers 15 levels. The mechanical model is exceptionally detailed with
59,215 products across 11 levels.

## Models

| File | Discipline | Schema | Storeys | Products | Description |
|------|-----------|--------|---------|----------|-------------|
| `arc_ifc2x3.ifc` | Architecture | IFC2X3 | 8 | 15,316 | Full architectural model incl. walls, doors, windows, columns, members, plates |
| `arc_ifc4.ifc` | Architecture | IFC4 | 8 | 15,316 | IFC4 counterpart -- identical product count |
| `str_ifc2x3.ifc` | Structural | IFC2X3 | 15 | 2,915 | Structural frame: 1970 beams, 255 columns, slabs |
| `str_ifc4.ifc` | Structural | IFC4 | 15 | 2,915 | IFC4 counterpart |
| `mech_ifc2x3.ifc` | Mechanical | IFC2X3 | 11 | 59,215 | HVAC system: 8,732 duct/pipe segments, 1,064 terminals |
| `mech_ifc4.ifc` | Mechanical | IFC4 | 11 | 59,215 | IFC4 counterpart -- 3,916 IfcPipeSegment elements |
| `plumb_ifc2x3.ifc` | Plumbing | IFC2X3 | 5 | 26,942 | 4,308 pipe segments, 474 terminals |
| `plumb_ifc4.ifc` | Plumbing | IFC4 | 5 | 26,942 | IFC4 counterpart |
| `elec_ifc2x3.ifc` | Electrical | IFC2X3 | 7 | 6,305 | 1,410 flow terminals, 84 segments |
| `elec_ifc4.ifc` | Electrical | IFC4 | 7 | 6,305 | IFC4 counterpart -- 1,272 IfcLightFixture elements |
| `fire_ifc2x3.ifc` | Fire Alarm | IFC2X3 | 5 | 874 | Fire alarm devices |
| `fire_ifc4.ifc` | Fire Alarm | IFC4 | 5 | 874 | IFC4 counterpart |
| `sprinkle_ifc2x3.ifc` | Sprinklers | IFC2X3 | 5 | 38,255 | 6,228 pipe segments, 1,354 sprinkler heads |
| `sprinkle_ifc4.ifc` | Sprinklers | IFC4 | 5 | 38,255 | IFC4 counterpart -- 1,354 IfcFireSuppressionTerminal |

## Known Limitations

- **No IfcSpace elements** in any model including the architectural file. Rooms and spaces are
  not explicitly modelled as IFC spatial units; spatial analysis must rely on storey containment.
- **IFC4 MEP files have fewer property sets** than their IFC2X3 counterparts. The
  `Pset_DistributionFlowElementCommon` property set (containing `Reference`) was not carried
  over during schema conversion for the mechanical, plumbing, and sprinkler models.
- **Empty building name**: the `IfcBuilding.Name` attribute is blank in all files; the
  `IfcProject.Name` is set to `"Project Number"`.
- **Large unplaced element counts** in MEP files (e.g. 39,532 in mech): these are fitting and
  accessory elements without direct spatial containment, which is typical for Revit MEP exports.
- The fire alarm model (874 products, 12 property sets) contains minimal property data.

## Architectural Level Breakdown

| Level | Elevation (mm) | Elements |
|-------|---------------|----------|
| Level 1 | 0 | 844 |
| Level 2 | 6,000 | 909 |
| Level 3 | 11,000 | 1,167 |
| Level 4 | 16,000 | 856 |
| Level 5 | 21,000 | 788 |
| Level 6 | 26,000 | 448 |
| Level 7A | 31,000 | 154 |
| Level 7 | 34,000 | 21 |
