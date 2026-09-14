# Native opening projection and explicit request UI

Verified locally on 2026-09-14 with the actual WBDG Office ARC IFC2X3 file. Browser screenshots are actual Chrome/WebGL views, not staged images.

## Selected state

Project `7c9ef52e1849446e9c356d3b85ee974e`, candidate `928f1e153cec4462a9257e476374c94c`. The live store records original revision **0** and accepted revision **1** (some earlier campaign messages called these 1/2; the stored history in `opening-native-projection.json` is authoritative). Source SHA `7108485ac8d2856922a83f1353aea8c6eaab60ff393546750bf648200617a544`, original wall STEP142 / GUID `1giqnsgvr6uA16isIlsm8L`.

The final materialized `route.ifc` is hash-checked and freshly tessellated for the effective host. The original host display mesh is suppressed exactly once, by source plus preserved entity ID. All 1,082 other original meshes are byte-for-byte equal as parsed JSON before/after. The route adds one mesh: 1,083 original versus 1,084 edited-state meshes. No geometric adequacy verdict comes from this projection.

| Actual host mesh | Vertices | Triangles | Enclosed mesh volume, m? |
| --- | ---: | ---: | ---: |
| Original revision0 | 8 | 12 | 4.894040957526856 |
| Accepted revision1 | 16 | 32 | 4.849400957526798 |

The imported Revit volume property remains 4.894040957526873, explicitly displayed as an imported fact. Effective geometry metadata points to the final materialized IFC. Structural, fire and access adequacy are not established by this scenario.

- `opening-effective-host.png`: selected, isolated native cut support with the real void.
- `opening-candidate-context.png`: real candidate context with explicit previous-host-not-loaded label and stale checker disclosure.
- `opening-original-host-replay.png`: historical original solid, same GUID/STEP, 12 triangles; opening preparation disabled in read-only history.
- `opening-native-projection.json`: actual immutable roots, permission, source identity and measured before/after mesh values.
- `opening-host-inspection.json`: actual browser-triggered isolated native eligibility response for existing untouched Office project `ce9005995bae48f7829d6499856fb190`, host STEP142. No duplicate import or engineering run was needed.
- `opening-inspected-form.png`: real host-bound form. Permission statement, evidence references, cut/allowed bounds and through-axis begin empty; consent unchecked.

## Guards and scope

The request form only supports one host opening attached to a single route. Inspection pins an imported revision and validates returned project/root/entity before opening the form. Submission binds source/hash/GUID/STEP/native-host root, forbids conflicting additional JSON, and disables itself if the current root changes or permission has not been explicitly supplied. The server remains authoritative for eligible host support, complete subtraction, permitted through-volume, other protected semantics and complete route checking. The UI's stop-waiting action aborts its read request; it does not claim to stop the bounded native server process.

Candidate comparison excludes the edited host from the source-context half. That half explicitly says the previous host is not loaded; use History for actual original native geometry. It is not presented as a simultaneous before/after host comparison.

Automated checks: 75 UI tests pass, including eight opening cases for missing permission, malformed/nonfinite bounds, volume escape, source/host injection, root changes, exact revision-zero endpoint binding, stale form disabled state and candidate membership. Production TypeScript/Vite build passes. Fifteen backend display/network/stream tests pass, including actual native meter and rotated millimeter fixtures plus seven failed identity/artifact binding variants.

The real candidate's engineering checks, acceptance and independent exported-file evidence belong to `evidence/benchmarks/opening/wbdg_office/`; this document verifies the UI/display contract and does not replace those records. The browser form was inspected without submitting a new permission or redundant run.
