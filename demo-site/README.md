# OMA customer demonstration

A standalone customer-facing demonstration of OMA + ANANKE. React, Vite and Three.js; static hosting; no engineering service or original IFC upload to the host. Independent of the existing `ui/` workbench and Python backend.

## Run

```powershell
cd demo-site
npm ci
npm run dev
```

Local preview: `http://127.0.0.1:5188/`.

## Working interactions

- Orbit, zoom, keyboard navigation, floor isolation, floor separation and discipline visibility in an illustrative five-level model.
- Hospital results across all seven source files, a before-and-after purchasing comparison, and per-discipline quantities.
- A paired 3D before-and-after view with synchronized building controls and material-purchasing figures. Both sides deliberately show the same illustrative geometry because the purchasing study did not redesign the building.
- Switch the purchasing baseline, compare a smaller plan with no additional joints, and filter the before-and-after view by trade.
- Browser-computed cutting plans for a synthetic 48-piece sample: change stock size, discipline, price or cutting allowance; compare identical demands across purchasing policies.
- Save scenarios locally, restore them, download the complete cut plan or demonstration report.
- Inspect an IFC STEP file up to 25 MB locally for schema and record counts. Files are not uploaded; the inspector does not perform semantic IFC or geometry validation.
- Responsive navigation, native accessible dialogs, reduced motion and WebGL fallback.

## Evidence boundaries

`src/hospital.js` contains the current purchasing results and code-review status; `src/evidence.js` retains the earlier inventory and bounded routing evidence. The whole-hospital purchasing study was run on 22 October 2026. All seven source files were included in the inventory: 149,822 objects, including 19,352 pipe, duct, conduit and tray segments. Lengths were recovered for 18,559 segments; 793 were excluded because their geometry was unsupported or ambiguous. The rendered building is an illustration, not extracted hospital geometry.

The main comparison uses identical measured demands, assumed stock lengths, prices, cutting allowances and permitted splits. It compares ordering separately for each network with the selected combined purchasing plan:

| Measure | Separate orders | Combined plan | Difference |
| --- | ---: | ---: | ---: |
| Estimated straight-material cost | $556,773.58 | $521,709.65 | $35,063.93 less |
| Purchased length | 24,994.8192 m | 23,326.0392 m | 1,668.78 m less |
| Stock lengths | 10,052 | 9,365 | 687 fewer |

Neither the before nor the after figure is the cost of building the hospital. Both cover only the included straight pipe, duct, conduit and cable-tray material. The $35,063.93 is a conditional gross material estimate, not a construction quote or verified net project saving. It excludes labor, extra joints, fittings, equipment and installation costs. Most of the reduction comes from combining orders: the selected plan saves another $292.42 against a basic combined-order calculation. The installed building geometry was not changed.

The wider purchasing plan assumes 3,457 new joints. A subsequent review found missing product and fabrication constraints, including 149 new pieces shorter than 100 mm. Neither this plan nor the separate no-new-splice scenario is approved for construction. The figures remain useful for demonstrating purchasing analysis, but must not be presented as a safe, code-compliant redesign. See `../docs/hospital-whole-procurement.md` and `../docs/hospital-code-review.md` for the full evidence and limitations.

The 3D comparison separates the two purchasing alternatives visually; it does not depict changed installed pipework, smaller building systems or savings on the hospital construction budget. Its before/after prices and purchased quantities use the selected recorded scenario and baseline. The model itself is an illustration shared by both sides, with linked camera, floor and system controls.

The older routing evidence in the downloadable report describes a two-terminal comparison, not whole-Hospital optimization. The interactive calculator uses synthetic lengths and assumed editable prices, not Hospital quantities or supplier quotes. It verifies quantity preservation and stock capacity for a feasible heuristic; no global optimum, full-system design or construction approval is claimed.

## Verify

```powershell
npm test
npm run build
# With the dev server running:
npx playwright install chromium
npm run test:e2e
```

Calculation tests exercise the synthetic sample independently of the saved Hospital results. Browser checks cover the customer journey, downloads, scenario persistence, local IFC errors, mobile navigation and overflow. Screenshots and temporary QA artifacts are ignored under `qa/`.

## Vercel

Production: **https://oma-ananke-demo.vercel.app**. Direct 3D comparison: **https://oma-ananke-demo.vercel.app/#model-comparison**.

The demo is deployed to the authenticated `davibaum` account's `dave-ce1c` team as `oma-ananke-demo`, on the existing Hobby plan. This is an account-owned production deployment with a stable alias, not an anonymous temporary preview. The earlier `tmp.now` links are superseded.

The project contains `vercel.json`; Vercel builds with `npm run build` and publishes `dist/`. The local `demo-site/` checkout is linked to the production project. `.vercelignore` excludes dependencies, QA and test source; production releases are staged from an explicit source/public/config allowlist. Do not deploy the parent repository or copy private deployment state into a release.

```powershell
vercel deploy --prod --scope dave-ce1c --project oma-ananke-demo --yes
```

Production was verified on 22 October 2026: all nine hosted build files match the checked local build byte for byte, and all four desktop/mobile browser journeys passed against the production alias. Checks include direct navigation to `/#model-comparison`, paired and single model modes, pricing scope, controls, persistence and downloads. Old anonymous state and the CLI-generated local token were preserved privately outside the active app folder. Keep `.vercel/`, `.env` files, private receipts and claim links out of source control and public artifacts.

Manrope is self-hosted under its bundled SIL Open Font License. The static deployment has no customer telemetry, server-side secrets or external runtime dependencies.
