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
- Historical Hospital inventory, per-source details and a separately scoped recorded routing comparison.
- Browser-computed cutting plans for a synthetic 48-piece sample: change stock size, discipline, price or cutting allowance; compare identical demands across purchasing policies.
- Save scenarios locally, restore them, download the complete cut plan or demonstration report.
- Inspect an IFC STEP file up to 25 MB locally for schema and record counts. Files are not uploaded; the inspector does not perform semantic IFC or geometry validation.
- Responsive navigation, native accessible dialogs, reduced motion and WebGL fallback.

## Evidence boundaries

`src/evidence.js` contains only public-safe aggregate counts from the retained 15 September 2026 Hospital studies, sourced from `../docs/hospital-installed-services.md` and the retained routing/cost evidence. The model rendering is illustrative and is not extracted IFC geometry.

The routing study's 13.6% centerline reduction is a two-terminal comparison, not whole-Hospital optimization. Both alternatives use 4.625 m of straight stock. The scenario lab uses synthetic lengths and assumed editable prices, not Hospital quantities or supplier quotes. It verifies quantity preservation and stock capacity for a feasible heuristic; no global optimum, full-system design or construction approval is claimed.

## Verify

```powershell
npm test
npm run build
# With the dev server running:
npx playwright install chromium
npm run test:e2e
```

Calculation tests cover 36 combinations of discipline, stock length and kerf. Browser checks cover the desktop customer journey, downloads, scenario persistence, local IFC errors, mobile navigation and overflow. Screenshots and temporary QA artifacts are ignored under `qa/`.

## Vercel

The project contains `vercel.json`; Vercel builds with `npm run build` and publishes `dist/`. `.vercelignore` excludes local credentials, dependencies, QA and test source. Do not deploy from the parent repository.

```powershell
npx vercel deploy --prod
```

For a logged-out temporary deployment, the CLI supports `--temporary`. Such a deployment must be claimed into a Vercel account before its returned expiry to remain live. Keep `.vercel/anonymous.json` and claim links private; they are not part of the public demo.

Manrope is self-hosted under its bundled SIL Open Font License. The static deployment has no customer telemetry, server-side secrets or external runtime dependencies.
