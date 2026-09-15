# Hospital: whole-project installed services

Build `b72cb24732b8b1d5ab08fdebda5e5649640a652b82bdda24a58f00d4da81b52c` completed the supervised `design_services` job against all seven original Hospital IFC4 models in **129.672 seconds**. Every imported product, port, connection and system was reconciled against the original IFC bytes. A separate implementation rebuilt the components and verified their complete partition, source identities and unchanged project state.

This is a whole-project installed-service inventory and engineering-input assessment. **The installed hospital has not been optimized or verified for construction.** All 5,463 connected components or isolated service candidates remain explicitly `MISSING_DESIGN_CONTRACT`; no demands, circuit assignments, prices or engineering approvals were invented to make them pass.

| Source | Service objects or unresolved candidates | Components / isolated candidates | Explicit ports | Explicit connections | Objects without ports |
|---|---:|---:|---:|---:|---:|
| Mechanical / HVAC | 19,670 | 340 | 39,532 | 19,766 | 159 |
| Plumbing | 9,121 | 313 | 17,814 | 8,907 | 264 |
| Electrical | 2,798 | 1,053 | 3,498 | 1,749 | 869 |
| Sprinkler | 13,490 | 1,120 | 24,758 | 12,379 | 1,079 |
| Fire alarm | 867 | 867 | 0 | 0 | 867 |
| Architecture: unresolved physical proxies | 1,770 | 1,770 | 0 | 0 | 1,770 |
| Structure | 0 | 0 | 0 | 0 | 0 |
| **Total** | **47,716** | **5,463** | **85,602** | **42,801** | **5,008** |

There are **45,946 confirmed service-class objects** plus 1,770 unresolved physical proxies. The proxies stay visible because generic architectural objects include potential equipment such as solar panels. An isolated product is not called a complete engineered network. Objects without ports are evidence of missing modeled connectivity, not proof that the installed object is defective. Shared `IfcSystem` membership never invents physical edges.

The complete denominator is **149,822 IfcProduct records**, including ports and spatial records, and **790 systems**. The graph contains 207 branched components and 32 cyclic components. These counts describe exported topology; they do not establish flow direction, terminal duty, circuit feasibility or physical connection quality. Structural and architectural records remain accounted for, but no structural design solver or structural safety result was added by this run.

## Recovered equipment information

Read-only recovery found 13 equipment types with explicit unit-bearing labels, covering 101 occurrences. Exact source hashes, STEP IDs, GUIDs, type and property references, and authored system memberships accompany each record. Recovered label values include:

- Five fans with a `489-2667 LPS` range, corresponding to 0.489–2.667 m³/s.
- Fourteen pumps labelled `38 LPS - 358 kPa Head`, corresponding to 0.038 m³/s and 358,000 Pa.
- Three boilers labelled `4909 kW` and three cooling towers labelled `177 kW`; these thermal labels are not treated as electrical input power.
- Electrical panel labels of 100, 125, 200 and 400 A, with explicitly labelled 208/480 V families; selected lighting labels include 100 W and 277 V.

Another 1,208 lighting occurrences have unitless `120` or `277` suffixes and remain ambiguous. **No complete installed-network engineering contract was recoverable.** Equipment nameplate-style text does not establish selected duty, simultaneous demand, a supply curve, conductor impedance, installation derating or approved design criteria. The five MEP models' property values contain identifiers and general metadata, without typed engineering-duty quantities or performance tables sufficient to fill those gaps.

## Implemented calculations and remaining work

The [backend operation and catalogue models](building-service-design.md) now cover duct pressure/velocity, pressure-pipe paths, fire-protection hydraulic paths, Manning drainage capacity, balanced three-phase electrical voltage drop/loss/ampacity/tray fill, and DC/fire-alarm loop voltage drop/loss/ampacity. They screen explicitly supplied catalogues with exact rational inputs and interval margins. They do not infer missing hospital duties or confer installation/code approval.

To produce the requested whole-hospital redesign, the backend still needs arbitrary installed-network coupled simulation and replacement/export verification, beyond the supported bounded tree workflows. This also requires network duties and supply conditions, applicable materials/equipment and catalogues, actual costs, approved federation alignment, and service-specific installation/design criteria. Fire protection additionally needs its design basis and supply data; fire alarm needs actual circuit topology and device/panel duties. Whole-building structural engineering remains a separate unimplemented capability. Data alone will not complete these software gaps.

No whole-hospital savings, physical revalidation, edited hospital export or construction approval is claimed. The earlier [two-terminal pipe result](hospital-results.md) retains its separate source build, assumptions and scope.

## Evidence

The [closed campaign handoff](../evidence/benchmarks/hospital-installed-services/1cbf8d8cc3c3485896f01b7a41a007fa-closed/handoff.json) retains the supervised execution, whole-project report, all content-addressed graphs and original-source reconciliation receipts, consistent SQLite snapshot, 117 frozen application files, independent graph review, equipment-label recovery and prior integrity-defect replays. Large text artifacts use lossless gzip; `file-mapping.json` records both byte hashes. `artifact-index.json` locates exact zlib blobs, including unchanged source audits already retained in the original seven-source archive. `original-source-index.json` binds the original IFC archives.

The worker created no candidates and changed no source IFC bytes or project revision. The historical server on port 8768 and existing portable packages remain separate build identities.

The [exact full regression and independent review](../evidence/release/installed-services-regression/c3482addaad441e5958746e2ab7a41ba/handoff.json) record **3,426 passing tests**, zero failures/errors/skips, 117 unchanged application files, 315 frozen inputs and six expected derived outputs. Passing these software tests does not turn the hospital's missing engineering contracts into a design approval.

The [validated local backend](../evidence/release/installed-services-live/b72cb-78c000e2088b477c9d04934338c364b3/handoff.json) runs at **http://127.0.0.1:8769**. Project `3b2ea6eaf87a42a5893caa3cbbe12a40` is named **Hospital - all installed MEP services**. Its [whole-project JSON report](http://127.0.0.1:8769/api/artifacts/db109fc15ce4712dd76b15673b7a0c909edb01633fedde7cd236c54031fa4df4) includes every network. The running Store is a separate verified clone; the closed campaign remains unchanged. The existing interface is served unchanged, and the new operation is available through the API and CLI.
