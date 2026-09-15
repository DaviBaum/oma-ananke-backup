# Whole-project installed-service design jobs

The `design_services` operation processes every imported IFC source and accounts for installed HVAC, piping, electrical and fire-service networks. It does not require manually inventing a small route first. Every service product, including portless devices and unresolved physical proxies, stays in the reported population. Original architecture/structure and non-service records remain accounted separately.

This operation provides installed topology and local engineering catalogue screens. It **does not yet optimize and physically revalidate a whole installed hospital**. Arbitrary interconnected/looped multi-service simulation, authoritative demands and design criteria, existing-network replacement/export, full-system installation/code checks and seven-discipline alignment remain required for that result. A completed accounting run is not a successful building design.

## Backend entry points

Use `POST /api/projects/{project_id}/runs` with operation `design_services`. Its mission has schema `oma.building-service-design/1`, optional `source_disciplines` mapping source SHA-256 IDs to explicit discipline labels, and optional `contracts`. Omit contracts for the first whole-project inventory. Nonempty `scope` filters are rejected because this operation must retain all imported sources.

The CLI provides the same supervised worker:

```
oma design-services PROJECT_ID --mission mission.json --data-dir STORE
```

Without `--mission`, it processes all sources using unknown source discipline labels and IFC class evidence. Labels do not establish source/sink roles, duty, circuit characteristics or coordinate alignment. Unknown physical proxies in architectural files remain unresolved candidates because equipment such as solar panels can be exported under generic classes.

The final event contains `service_design_artifact_root`. Retrieve it through `/api/artifacts/{root}`. Each source points to a detailed network inventory and original-IFC semantic reconciliation receipt. Each network records its content-bound identity, topology, coverage, anomalies and missing engineering inputs. Shared system membership never invents a physical connection. Explicit port direction never invents an engineering source or demand.

## Engineering catalogue models

| Service | Implemented calculation | Required assumptions remain explicit |
|---|---|---|
| HVAC duct | Circular/rectangular area, hydraulic diameter, Darcy pressure loss, velocity and power | Supplied airflow, density, friction/loss coefficients, allowed velocity/pressure and fan efficiency |
| Pressure pipe | Circular fixed-flow pressure loss, velocity and power | Supplied duty, hydraulic diameter/bore applicability, boundary budget and loss coefficients |
| Fire protection | Supplied hydraulic path calculation | Does not establish hazard classification, coverage, sprinkler discharge/demand areas or fire-code compliance |
| Gravity drainage | Manning capacity with rational cube/square-root enclosures and slope checks | Supplied wetted area/perimeter at an explicitly declared design depth; steady uniform flow |
| Electrical | Balanced three-phase voltage drop, resistive loss, supplied ampacity and tray-fill checks | Supplied full-path impedance, load, power factor and installation limits |
| Electrical DC / fire-alarm DC | Full-loop `I R` voltage drop, `I² R` loss and supplied ampacity | Supplied loop resistance and circuit duty; no guessed return multiplier or alarm/battery/code approval |

`oma.optimization.service_design.screen_service_catalog` evaluates every supplied option without changing fixed requirements. Results contain normalized parameters, quantitative metrics and signed rational-enclosure margins. Missing physics or applicability labels yield `UNKNOWN`; invalid, negative or unsupported fields are rejected. Exact total-price selection is claimed only for a declared complete catalogue with all options resolved and all candidate prices supplied in one common unit. Candidate applicability labels remain caller assumptions. Geometry, network coupling, code compliance and whole-building adequacy remain separate checks.

Manning's hydraulic-radius model is documented by [USACE](https://www.hec.usace.army.mil/confluence/rasdocs/d2sd/ras2dsedtr/6.5/numerical-methods/face-hydraulic-properties). Fixed-flow duct pressure-loss modeling is described in the [DOE duct-system evaluation](https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/osti-ibacos-plug-and-play.pdf). Those models do not provide the hospital's missing duty or design-authority inputs.

## Binding and publication

A design contract identifies `network_id`, `network_root`, `source_sha256`, `service`, `options`, `requirements` and `catalogue_complete`. Use identities returned by the preceding inventory. The network root includes the full source inventory and source-audit roots, so corrected port ownership or material metadata invalidates earlier contracts even if component IDs remain the same.

Workers enforce budgets and cancellation, compare original source bytes before/after analysis, reject incomplete source denominators, and validate request/control state at publication. A final source check occurs after all potentially blocking control callbacks. Results cannot accept a revision or export unchecked edits. Every unresolved network stays visible; supplying a successful local electrical calculation cannot hide an unresolved HVAC network.

The historical `06aa8656` server and prior routing benchmark retain their distinct source identities. New tests and whole-project runs must be cited by their own saved build/receipts. Full original OMA/ANANKE mathematics and production readiness remain incomplete.

The completed [seven-source Hospital run](hospital-installed-services.md) documents actual network counts, unresolved connectivity, equipment-label recovery and the closed source-bound evidence.
