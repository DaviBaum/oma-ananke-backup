# Actual whole-hospital purchasing results

The engine processed **all seven original Hospital IFC files**, accounting for **149,822 IFC products** and **47,716 service objects or unresolved physical candidates**. It measured **18,559 of 19,352 straight service segments (95.9%)**, totaling **22,395.595 m**. The remaining **793 segments** are explicitly unresolved. Original building geometry and project revisions remain unchanged.

The broader purchasing scenario estimates **$35,063.93 less straight-material purchasing** compared with buying each connected network separately. It requires **1,668.780 m less stock (6.68%)**, **687 fewer stock lengths**, and reduces modeled cutting/trim waste from **2,589.788 m to 921.008 m (64.44%)**. These are purchasing and cutting improvements across actual hospital quantities. They do not establish a redesigned or construction-approved hospital.

| Actual source quantities | Measured segments | Measured length | Stock purchase reduction | Estimated gross material saving |
|---|---:|---:|---:|---:|
| HVAC pipes and ducts | 7,944 | 10,739.703 m | 914.400 m | $24,089.29 |
| Plumbing | 4,308 | 3,899.094 m | 246.888 m | $2,459.91 |
| Sprinkler pipes | 6,227 | 7,339.284 m | 498.348 m | $8,430.75 |
| Electrical conduit and ladder tray | 80 | 417.514 m | 9.144 m | $83.99 |
| **Total** | **18,559** | **22,395.595 m** | **1,668.780 m** | **$35,063.93** |

Amounts use current supplier-based size estimates in USD. The comparison assumes separate purchasing for each explicit connected component. It is not the hospital contractor's measured purchasing bill. All required installed spans remain present and unchanged.

The central modeled material subtotal changes from **$556,773.58 to $521,709.65**, a **6.30%** reduction on the included straight stock. This is not a percentage of the total hospital construction cost. Low/high price sensitivity factors of 0.5x/1.5x produce **$17,531.97 / $52,595.90** saving scenarios; these are declared sensitivities, not confidence limits or guaranteed bounds.

The already-pooled first-fit baseline is much more efficient than separate purchases. Against that baseline, the new search saves an additional **$292.42**, **14.630 m** and **six stock lengths**. Most of the larger result comes from pooling compatible requirements. Both baselines are retained and independently reconstructed; the larger result must not be presented as the solver's improvement over an already pooled order.

The broader scenario splits long modeled spans into fixed fabrication pieces under explicitly assumed stock lengths. It has **22,016 fabrication cuts and 3,457 assumed additional splices**, identical in all three compared plans. Their joint feasibility and installation cost are not established. Required lengths are rounded upward in 1 mm increments, adding **9.436 m** of material allowance across the hospital. No original IFC dimension is changed.

A second complete seven-source run disallows these splits. It plans **16,446 spans / 12,488.404 m**, leaving **2,113 overlength measured spans / 9,907.191 m** unchanged and outside the cost comparison. In this scope, separate-network purchasing falls from **14,655.089 m / $232,197.40** to **13,148.158 m / $202,792.00**: **$29,405.40** estimated gross saving, **1,506.931 m less stock**, and **577 fewer purchased lengths**, with **zero assumed additional splices**. Against its already-pooled baseline, the additional solver saving is **$761.05**. The two scenarios have different included quantities and must not be added together or treated as identical total-cost alternatives.

The source failures remain visible: 788 mechanical segments, four electrical segments and one sprinkler segment lack supported usable geometry or unambiguous longitudinal evidence. This includes 412 flexible-duct BReps. The fire-control file's 861 devices and six proxies remain unchanged; it has no explicit wire routes to cost or optimize. Architecture and structure are fully counted but receive no purchasing-saving claim. Electrical savings cover conduit/tray, not conductors, circuits or power-system design. HVAC capacities, hydraulic duty, electrical loads and fire compliance were not redesigned or certified by this job.

The price model uses **23 public supplier references accessed October 22, 2026**, with explicit interpolation or proportional size extrapolation where the exact Hospital specification is unavailable. Examples include [US Supply steel pipe](https://www.ussupply.com/pipe-fittings/pipe/black-steel-pipe.html), [Master Flow rectangular duct sold as two half-sections](https://www.homedepot.com/p/Master-Flow-12-in-x-8-in-x-4-ft-Half-Section-Rectangular-Duct-RD12X8X48/100185410), [Master Flow round duct](https://www.homedepot.com/p/Master-Flow-12-in-x-5-ft-Round-Metal-Duct-Pipe-CP12X60/100144462), and [Hubbell ladder rack](https://www.gordonelectricsupply.com/p/Hubwire-Hls1024B-Cablemgt-Lad-Rck-10Ft-Lx24In-W-Bk/6340062). Non-PVC pipe uses an explicit steel price proxy. A matching dimension does not authenticate material, wall, gauge, end type, stock availability or a project quote. Cutting/recreating threads, grooves, crimps and other ends may add cost. Labor, joints, fittings, equipment, supports, insulation, shipping, tax and energy are excluded, so **net construction savings remain unverified**.

Both supervised jobs completed on frozen software `1ccc8728fbf6ba0ad1bbb16b2dd339896e8bb292b03e08754e3b1b93156b48c6`, in **231.625 s** and **224.859 s** while running concurrently. The relevant frozen regression contains **232 passing tests**, with no failures, errors or skips. A separate verifier importing no OMA or native geometry modules independently passed every group's three plans, exact quantity/cost aggregation, fixed fabrication demand, baseline reconstruction, source hashes and unchanged persisted records. A separate peer review checked declared-precision interval geometry, including six additional adversarial probes. These checks retain their exact purchasing/quantity scope; they are not structural or engineering approval.

The broader run used **55,984 search nodes**. Of 472 groups, 402 reached the declared capacity lower bound and 27 completed exhaustive partition search; 43 remain heuristic. These are bounded one-dimensional purchasing claims under the supplied stock catalogue, not full building-design optimality or proof of the original full mathematics.

Evidence and exact selected cut schedules:

- [Broader scenario handoff](../evidence/benchmarks/hospital-whole-procurement/2f25fd1064cb4547ae3667b9bbd4e69b/handoff.json) and [readable results](../evidence/benchmarks/hospital-whole-procurement/2f25fd1064cb4547ae3667b9bbd4e69b/campaign/readable-results.json).
- [No-split scenario handoff](../evidence/benchmarks/hospital-whole-procurement/3d9c5dc8a37b41f78b7a2233b2cb5c2d/handoff.json) and [readable results](../evidence/benchmarks/hospital-whole-procurement/3d9c5dc8a37b41f78b7a2233b2cb5c2d/campaign/readable-results.json).
- Each handoff retains the mission, independent replay, frozen source/tests, SQLite snapshot and content-addressed purchasing plans/takeoffs. Its artifact index resolves shared original audits; its original-source index resolves the already-backed-up original IFC archives. The selected plan identifies every cut and source piece. These artifacts do not contain an edited building IFC because no installed geometry was changed.
- [Backend usage and bounded model](whole-project-procurement.md).
