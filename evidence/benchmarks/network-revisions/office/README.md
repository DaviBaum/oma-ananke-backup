# Actual Office accepted-network revision

Recorded 2026-09-14 against the original WBDG Office IFC2X3 architecture source. Project `a561fdf78fcc411295e4821cb560c829` advanced from accepted revision 1 to accepted revision 2. The original 803 source obstacles remain in the physical check scope. The service is an explicitly supplied fixed-flow scenario, not an inferred building operating point.

The equal tee's trunk and branch takeouts increased from 0.20 m to 0.22 m. Three linked straight-component caps moved to their new fitting ports. External terminals, diameter, insulation, clearance, allowed zone, two prescribed flows, pressure allowances, physical model, source identity and every other fixed scenario field were preserved. The new unique network ID is `office-tee-revision-bf8f08107d`; the replaced network is `office-direct-tee`. Four previous and four new physical component IDs form the eight-ID change set. Both versions measure 1.8 m and one fitting; **no objective improvement is asserted**.

`scripts/benchmark_network_revision_ui.py` freezes executable sources before work, binds the input to the exact accepted root/revision, runs a real durable optimization operation, demands fresh checking under that frozen fingerprint, accepts, exports, and independently reopens the exported IFC. The result is in [cac5b1d92b144ddd8e37697aa7b74acf/result.json](cac5b1d92b144ddd8e37697aa7b74acf/result.json), with frozen input and before/candidate/after snapshots alongside it. The earlier `progress.json` is a stage observation; `result.json` is the completed outcome.

| Record | Value |
|---|---|
| Candidate | `590c0708699545fba30ec816c3a4cd4a` |
| Durable run | `e6602a24d9704012906aa0e08cc79b9f` |
| Accepted revision | 2 |
| Fresh checks | 11 PASS |
| Materialized geometry | 4 unique native parts, 538 display triangles |
| Export | `bd0e1f7cf90e4f72a1dcf594975a71a8`, CHECKED_LOCAL_SCOPE, fresh round-trip PASS |
| Exported IFC SHA-256 | `428dd075826bc686f44b51eeb9e8a5af47b4e1e5da4ce0e250ad52b558ef802b` |
| Frozen checker | `oma-independent-checker/2:665047d440b6e1e3ac80423e7e7e2455ee43b9ba3e3516aa5b6a1dd1bab76e29` |
| Campaign wall time | 54.0028 seconds |

Browser QA used the built local UI in Chrome, at its ordinary 1599 × 661 browser viewport. The editor loaded the accepted contract with every fixed requirement read-only and only replacement alternatives editable. The real campaign ran through the frozen script while this editor remained open. When the accepted head advanced, the UI disabled submission and explained that the editor was stale. Reopening the action loaded the new network/revision. No claim is made that this campaign was submitted using the dialog button.

Screenshots in the same result folder:

- `ui-fixed-requirements-header.png`: revision entry and immutable service requirements.
- `ui-stale-editor-blocked.png`: actual changed-head guard with disabled submission.
- `ui-before-native-replay.png`: actual revision 1 historical meshes, original tee GUID, read-only controls.
- `ui-after-native.png`: actual revision 2 meshes, replacement tee GUID and dimensions.
- `ui-lineage.png`: four prior and four proposed component IDs, bound revision metadata.
- `ui-replacement-comparison.png`: selected candidate geometry with the explicit label that the previous network is not loaded in split view. Historical replay supplies the actual earlier native geometry separately.

The old graph preview is a nominal centerline graph read from the pinned previous geometry artifact. It is not a second native mesh in the selected state. Later source edits made the frozen report's current applicability stale; the UI correctly retains historical PASS while disabling acceptance/checked export under the changed executable. Scope remains local physical coordination and conditional prescribed-flow evidence. Whole-building adequacy, a solved operating point, and global optimality are not established.
