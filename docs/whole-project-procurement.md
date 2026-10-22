# Whole-project material purchasing

The `optimize_procurement` job measures supported straight service segments in every imported IFC and compares stock purchasing/cutting plans. It keeps the building's installed geometry and project revision unchanged. It is a separate, bounded purchasing capability; it does not complete the original OMA/ANANKE mathematics or redesign an installed engineering network.

Run it through `POST /api/projects/{project_id}/runs` with `operation: "optimize_procurement"`, an empty scope, a mission and a finite job budget. The CLI exposes the same worker:

```powershell
.venv/Scripts/python.exe -m oma.cli optimize-procurement PROJECT_ID --mission MISSION.json --budget-seconds 1200 --data-dir STORE
```

The mission schema is `oma.whole-building-procurement/1`. Its required fields are `source_disciplines`, `stock_policies`, `group_policies`, `currency` and `search_node_budget`. Discipline keys are imported source identities. Group-specific policies override stock-kind defaults. A group override referring to an absent measured group is rejected. Missing policies leave the affected quantities explicitly unplanned.

Every policy declares `stock_lengths_m`, `kerf_m`, `end_trim_m`, `cut_increment_m`, `long_segments`, `unit_price_per_m`, `assumptions` and `price_basis`. Lengths and money accept exact rational strings. Prices are either null or ordered low/central/high scenario rates in the common currency. There is no default market price or implicit zero price.

`RETAIN_OVERSIZE` leaves an overlength span outside the purchasing plan. `ASSUME_FABRICATION_SPLITS` deterministically divides it into stock-sized cuts and records every assumed additional splice. All comparisons use the same upward-rounded required lengths and the same fixed splits. These are fabrication assumptions, not verified joint locations. The service does not authorize cutting, end preparation, splices or installation.

The quantity reader reconciles every original service candidate and FlowSegment against its persisted audit and source bytes. Supported quantity authority comes from an authored circular or rectangular extrusion. Rectangular length needs a unique independently authored longitudinal Axis or owned-port endpoint match; extrusion depth is not blindly treated as length. Irrational transforms use outward rational intervals. Any approximate endpoint match needs a positive source-declared precision, capped at 0.1 mm, and must prove one unique axis. The returned prism dimension remains the exact authored number. Missing global placement remains explicit and cannot become global geometry approval.

Nested physical children, unsupported bodies, absent or ambiguous longitudinal evidence and missing units remain in the retained ledger. Type/profile/material identities stay separate between sources. Matching IFC groups do not prove equivalent material specifications; procurement compatibility must be an explicit assumption.

The main baseline pools compatible requirements using first-fit decreasing. A second scenario buys each explicit connected component separately using the same algorithm. It represents a purchasing policy, not an observed contractor bill. The selected plan considers pooled first-fit/best-fit schedules, bounded partition search and bounded integer subset-fill repair. Complete demand is always retained; interrupted search does not publish a partial schedule as a complete plan. Only strictly better complete repair windows replace their incumbents. A search limit does not establish optimality.

Every plan is replayed for source/piece identity, exact-once coverage, stock compatibility, capacity, cut positions, kerf, trim, waste and prices. The Hospital evidence also contains a separate standard-library verifier that imports no OMA producer code and rebuilds both baseline definitions, fixed fabrication demand and all quantity/cost totals. It checks the persisted request, project, artifacts and unchanged original bytes; it does not independently certify physical engineering or supplier compatibility.

The final transaction checks the immutable request, project revision and run controls. Publication is fenced by fresh original-source hashes. The persisted `procurement_complete` event points to the report and every selected cut through content-addressed artifacts. Completion means that the declared purchasing calculation finished. Native geometry, network service adequacy, fire compliance and construction approval are not granted.

See [the actual Hospital results](hospital-whole-procurement.md) for quantities, both purchasing comparisons, price assumptions and retained evidence. No labor, equipment, fittings, wiring, support, freight, tax, operating-energy or total-building saving is inferred from this linear-stock calculation.
