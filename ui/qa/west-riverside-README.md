# West Riverside IFC4 browser campaign

Observed on 2026-09-14 against the local production workbench in Chrome 153, with NVIDIA RTX 3090. Project `8f8f27ba52654051a638ce5f1d3572d8`, revision 1, immutable root `e4f16b62a5b8c89baf79596602f5c73358914a72fd4812e16d64c3c629dd9091`.

All seven IFC4 sources were imported together using completed audit caches whose source hashes, versions, geometry parameters and copied artifact hashes were checked before reuse. The actual import took 186.902 seconds: source cache reads finished in about 11 seconds, followed by native federation and legacy port normalization. The import did not run engineering coordination checks. `west-riverside-import.json` retains the exact paths/request and durable run; `west-riverside-import-final.json` records completion.

| Accounting denominator | Count |
|---|---:|
| All source products | 149,822 |
| Represented product meshes, including opening representations | 63,917 |
| Explicitly non-geometric products | 85,905 |
| Physical objects | 63,415 |
| Represented physical objects | 63,182 |
| Explicitly non-geometric physical objects | 233 |
| Failed geometry in these audits | 0 |
| Rendered display triangles | 39,068,829 |

The browser rendered exactly the complete represented-product/triangle inventory with all seven sources visible, without clipping, x-ray, comparison, or a reduced mesh set. Per-source source hashes/counts/contracts are in `west-riverside-source-coverage.json`; the independent physical denominator is in `evidence/ifc/west-riverside-ifc4-render-inventory.json`. The display includes subtractive opening representations, so represented-product counts are not a physical-obstacle count.

The local federation audit remains **UNRESOLVED**, with inconsistent anchor identities, true-north declarations and some named level elevations. All 85,602 explicitly normalized source ports retain `UNRESOLVED_FEDERATION`; 42,801 declared connections are preserved and none inferred. The view retains original world-meter source coordinates. It does not establish engineering registration or a surveyed global datum. `west-riverside-state-record.json` preserves those facts. QA found that the overview read `status` instead of the manifest's actual `alignment_status`; the corrected projection and three regression tests now expose the datum obligation. `west-riverside-missing-inputs.json` and `west-riverside-datum-evidence.png` retain the resulting evidence. The overview summarizes the reason and opens the complete record separately.

## Actual navigation measurements

The fixed camera test warms up for two seconds, then renders the full scene along a ten-second orbit. Native viewport: 994 × 305 CSS pixels, actual drawing buffer 1988 × 610, pixel ratio 2, 103 draw calls. No browser viewport override was applied.

| Measurement | Mean FPS | Frame p95 | GPU evidence | Record |
|---|---:|---:|---|---|
| First full scene | 0.998 | 1002.9 ms | No samples, only 9 measured frames | `west-riverside-navigation-native-gpu.json` |
| Repeated after selecting browser surface | about 1 | 1119.7 ms | No samples | `west-riverside-navigation-selected-surface.json` |
| Office control, 1,087 objects / 71,093 triangles | about 1 | 1002.9 ms | No samples | `west-riverside-office-control.json` |
| Tiny control, 4 IFC parts / 538 triangles | 0.998 | 1002.3 ms | No samples | `west-riverside-tiny-scheduling-control.json` |
| Full scene after browser lifecycle/reload and earlier GPU sampling | 59.366 | 16.9 ms | GPU p95 6.1696 ms; 60 valid queries | `west-riverside-navigation-scheduling-gpu.json` |
| Full scene with GPU queries explicitly disabled | 59.465 | 16.9 ms | DISABLED, zero queries | `west-riverside-navigation-no-gpu-query.json` |

The early failures are retained. The tiny control's document remained visible and focused while the separate requested 100 ms timer had p95 111.5 ms, and RAF stayed near one second. CPU submission p95 was 0.5 ms on that tiny scene. This separates the observed frame cadence from ordinary timer cadence but **does not identify its cause**. Later recovery followed a tab lifecycle/reload and an instrumentation change: GPU queries now start with the first measured frame and recur every ten frames, allowing even very low-FPS tests to obtain a sample. The GPU-off control confirms that current recovered performance does not require ongoing GPU queries. It does not retroactively explain the earlier failure.

The browser policy blocked `chrome://gpu` inspection; no workaround or browser setting change was attempted. The workbench's own WebGL and scheduling observations are the available evidence. Chromium documents browser visibility/occlusion throttling ([Windows occlusion](https://blog.chromium.org/2021/12/chrome-windows-performance-improvements-native-window-occlusion.html), [timer throttling](https://developer.chrome.com/blog/timer-throttling-in-chrome-88)); those general mechanisms do not establish the cause of this particular observation.

`west-riverside-navigation-recovered.png` shows the full scene and measured GPU result. The navigation gate is an observed result for this machine, immutable scene and browser state, not a universal performance claim.

## Loading and interaction

- Full observed stream: 49.079 s, then 8.675 s complete buffer preparation (`west-riverside-stream-timings.json`). A workbench reload during the preceding import transition restarted loading; this is not claimed as an untouched first-load measurement.
- Later cached stream: 13.7768 s, followed by 5.3301 s buffer preparation (`west-riverside-cached-stream-picking.json`).
- Real GPU selection chose source ARC entity `230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09:1368566`, IFC plate GUID `3064w0y0nDv9wdb1cWL$vQ`, in 115.1 ms. Inspector showed the actual STEP ID, file, Level 3 and world-meter bounds (`west-riverside-native-selection.png`).
- Switching from the complete hospital scene to Office committed only Office's matching geometry 427 ms after the project request, with no stale hospital scene or crash (`west-riverside-project-switch.json`).
- Explicit benchmark cancellation produced `CANCELLED` and `NOT_EVALUATED`, not a passing performance result (`west-riverside-benchmark-cancelled.json`).

The original empty-view wording was ambiguous during a running import; it now reports import in progress/paused from the actual run state. QA also exposed benchmark results overlapping viewport tools; the result panel was moved beside the toolbar and made dismissible. These UI corrections do not change engineering state or geometry.

Validation at this checkpoint: 67 frontend tests in 15 files and production build passed; the datum projection regression has 3 passing cases. The original complete import, unresolved datum, navigation failures, recovered measurements, selection and teardown all remain inspectable in the records above.
