# West Riverside Hospital: complete IFC4 federation

The validated 33a backend imported all seven disciplines, but correctly blocked generated routing because their alignment is unresolved. No candidate, acceptance or checked export was produced. This handoff contains no partial architecture-only result.

| Operation | Actual result | Time |
|---|---|---:|
| Complete seven-source import | 149,822 product records; 85,602 ports; 42,801 explicit connections | 279.593 s |
| Independent IFC datum inventory | Alignment unresolved | 37.406 s |
| Supervised finite generation request | `MISSING_INPUTS`; no candidate or head change | 4.375 s |

The sources total 223,562,189 bytes: architecture, structure, mechanical, plumbing, electrical, fire alarm and sprinklers. None declares an `IfcMapConversion`, `IfcProjectedCRS` or `IfcGrid`. Every non-architectural source has differing Site, Building and Project GUIDs. Several also disagree on TrueNorth or named storey elevations. Exact declarations and per-source reasons are retained under `datums/`. No identity transform was silently approved and no discipline was removed.

The request was a predeclared hypothetical two-sink, fixed-flow design generated from finite tee sites and connector templates, not complete input trees. The source-frame admission gate rejected it before native route checks. This is an input-alignment blocker, not proof that hospital routing is physically infeasible.

All seven original IFC byte hashes remain unchanged. Their exact decoded bytes are retained as gzip files with the supplied model card and license, crediting Wawan Solihin and the OpenIFC Model Repository, University of Auckland. The 112 frozen Python source files and actual executed scripts are retained. Mesh caches and live Stores are excluded; fresh imports can regenerate meshes from the original IFCs.

The initial import-report wrapper read the wrong public project key after successful import. Its raw failure remains alongside a separate reconciliation against the completed managed worker and actual project state. No import was rerun or original receipt rewritten.

`files.json`, `handoff.json` and `public-mapping.json` bind the retained files and decoded originals. Verify with `python scripts/verify_retention.py <this-directory>` using only the standard library. Verification checks retained bytes; it does not upgrade native or engineering scope.
