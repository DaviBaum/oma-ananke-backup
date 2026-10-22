import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  Download,
  Layers,
  Menu,
  RotateCcw,
  X,
  Plus,
  FileText,
  Upload,
  Maximize2,
  Minimize2,
} from "lucide-react";
import evidence, { disciplines } from "./evidence.js";
import { hospital, comparison } from "./hospital.js";
import { calculateScenario, inspectIfcText, sampleTypes } from "./scenario.js";

const BuildingViewer = lazy(() => import("./BuildingViewer.jsx"));
const number = (v, digits = 0) =>
  new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(v);
const money = (v) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(v);
const tradeNames = {
  all: "All trades",
  hvac: "Heating & cooling",
  plumbing: "Plumbing",
  sprinkler: "Sprinklers",
  electrical: "Electrical",
};
const viewerSystems = [
  { id: "hvac", label: "Heating & cooling", color: "#347e73" },
  { id: "plumbing", label: "Plumbing", color: "#547b9b" },
  { id: "electrical", label: "Electrical", color: "#b58b4b" },
  { id: "fire", label: "Sprinklers", color: "#b5695f" },
];

function saveFile(value, name) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M3 27 16 4l13 23M8 19h16M16 4v23"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      />
    </svg>
  );
}
function IconButton({ label, children, ...props }) {
  return (
    <button className="icon-button" aria-label={label} title={label} {...props}>
      {children}
    </button>
  );
}
function Dialog({ title, label, children, close, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    d.showModal();
    return () => d.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "wide" : ""}`}
      onCancel={close}
      onClick={(e) => {
        if (e.target === ref.current) close();
      }}
    >
      <header className="dialog-head">
        <div>
          <span className="eyebrow">{label}</span>
          <h2>{title}</h2>
        </div>
        <IconButton label="Close dialog" onClick={close}>
          <X size={20} />
        </IconButton>
      </header>
      {children}
    </dialog>
  );
}
function StockBar({ data, max, tone }) {
  return (
    <div className={`stock-bar ${tone}`} aria-hidden="true">
      <span
        className="stock-used"
        style={{ width: `${(data.requiredM / max) * 100}%` }}
      />
      <span
        className="stock-waste"
        style={{ width: `${(data.wasteM / max) * 100}%` }}
      />
    </div>
  );
}
function OrderPanel({ title, subtitle, data, max, after = false }) {
  return (
    <article className={`order-panel ${after ? "after" : "before"}`}>
      <div className="order-title">
        <span className="eyebrow">{title}</span>
        <span className="order-index">{after ? "02" : "01"}</span>
      </div>
      <h3>{subtitle}</h3>
      <p className="price-scope">Pipe, duct, conduit &amp; tray only</p>
      <div className="order-cost">{money(data.costUsd)}</div>
      <span className="cost-caption">
        Material purchase estimate · installation excluded
      </span>
      <StockBar data={data} max={max} tone={after ? "selected" : "original"} />
      <dl className="order-details">
        <div>
          <dt>Material purchased</dt>
          <dd>
            {number(data.purchasedM)} <small>m</small>
          </dd>
        </div>
        <div>
          <dt>Lengths to buy</dt>
          <dd>{number(data.stockCount)}</dd>
        </div>
        <div>
          <dt>Material waste</dt>
          <dd>
            {number(data.wasteM)} <small>m</small>
          </dd>
        </div>
      </dl>
    </article>
  );
}

function ModelComparison({ scenarioId, baselineId }) {
  const [mode, setMode] = useState("compare");
  const [modelTrade, setModelTrade] = useState("all");
  const [floor, setFloor] = useState("all");
  const [separated, setSeparated] = useState(false);
  const [cameraReset, setCameraReset] = useState(0);
  const result = comparison(scenarioId, baselineId, modelTrade);
  const systems =
    modelTrade === "all"
      ? viewerSystems.map((s) => s.id)
      : [modelTrade === "sprinkler" ? "fire" : modelTrade];
  const states = mode === "compare" ? ["before", "after"] : [mode];
  const maxOrder = Math.max(result.before.purchasedM, result.after.purchasedM);

  return (
    <section
      className="model-comparison"
      id="model-comparison"
      aria-label="3D before and after"
    >
      <header className="model-comparison-header">
        <div>
          <span className="eyebrow">Explore the change in 3D</span>
          <h3>Same hospital. Less material to buy.</h3>
        </div>
        <div
          className="segmented model-view-switch"
          aria-label="3D comparison view"
        >
          {[
            ["before", "Before"],
            ["after", "After"],
            ["compare", "Side by side"],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-label={
                value === "compare" ? "Compare models" : `${label} model`
              }
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </header>
      <div className={`model-comparison-stage mode-${mode}`}>
        <Suspense
          fallback={
            <div className="model-loading">Preparing the comparison…</div>
          }
        >
          <BuildingViewer
            paired={mode === "compare"}
            visibleSystems={systems}
            level={floor}
            exploded={separated}
            resetKey={cameraReset}
          />
        </Suspense>
        {states.map((state) => (
          <React.Fragment key={state}>
            <div className={`model-view-label ${state}`}>
              <span className="model-state-name">
                {state === "before" ? "Before" : "After"}
              </span>
              <p>
                {state === "before"
                  ? baselineId === "perNetwork"
                    ? "Separate network orders"
                    : "Orders already combined"
                  : "Combined cutting plan"}
              </p>
              <strong>{money(result[state].costUsd)}</strong>
              <span className="model-price-caption">
                Estimated material purchase
              </span>
            </div>
            <div className={`model-purchase ${state}`}>
              <StockBar
                data={result[state]}
                max={maxOrder}
                tone={state === "after" ? "selected" : "original"}
              />
              <div>
                <span>
                  <strong>{number(result[state].purchasedM)} m</strong> ordered
                </span>
                <span>
                  <i aria-hidden="true" />
                  <strong>{number(result[state].wasteM)} m</strong> waste
                </span>
              </div>
            </div>
          </React.Fragment>
        ))}
        <span className="model-same-layout">Building geometry unchanged</span>
      </div>
      <div className="model-comparison-toolbar">
        <div className="model-display-options">
          <label>
            <span>Systems</span>
            <select
              aria-label="Model comparison trade"
              value={modelTrade}
              onChange={(e) => setModelTrade(e.target.value)}
            >
              {Object.entries(tradeNames).map(([value, name]) => (
                <option key={value} value={value}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Floor</span>
            <select
              aria-label="Model comparison floor"
              value={floor}
              onChange={(e) => setFloor(e.target.value)}
            >
              <option value="all">All floors</option>
              {[0, 1, 2, 3, 4].map((value) => (
                <option key={value} value={value}>
                  Level {value + 1}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="model-camera-tools">
          <span>
            {mode === "compare"
              ? "Drag either view to rotate both"
              : "Drag to rotate · scroll to zoom"}
          </span>
          <IconButton
            label="Separate comparison floors"
            aria-pressed={separated}
            onClick={() => setSeparated(!separated)}
          >
            <Layers size={17} />
          </IconButton>
          <IconButton
            label="Reset comparison camera"
            onClick={() => setCameraReset((n) => n + 1)}
          >
            <RotateCcw size={17} />
          </IconButton>
        </div>
      </div>
      <div className="model-comparison-note">
        <p>
          <strong>The layout stays the same.</strong> This run changes material
          orders and cutting plans. Both views use the same illustrative model,
          not the source hospital geometry.
        </p>
        <span>
          Pipe, duct, conduit &amp; tray only. Prices cover all floors.
          Installation excluded.
        </span>
      </div>
    </section>
  );
}

function loadHistory() {
  try {
    const saved = JSON.parse(
      localStorage.getItem("oma-demo-scenarios") || "[]",
    );
    return Array.isArray(saved)
      ? saved.slice(0, 8).flatMap((item) => {
          try {
            return [{ id: item.id, result: calculateScenario(item.result) }];
          } catch {
            return [];
          }
        })
      : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [scenarioId, setScenarioId] = useState("broad");
  const [baselineId, setBaselineId] = useState("perNetwork");
  const [trade, setTrade] = useState("all");
  const [visibleSystems, setVisibleSystems] = useState(
    viewerSystems.map((s) => s.id),
  );
  const [level, setLevel] = useState("all");
  const [exploded, setExploded] = useState(false);
  const [reset, setReset] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [dialog, setDialog] = useState(null);
  const [toast, setToast] = useState("");
  const [inputs, setInputs] = useState({
    type: "plumbing",
    stockM: 6,
    price: 18,
    kerfMm: 3,
  });
  const [sample, setSample] = useState(() => calculateScenario());
  const [history, setHistory] = useState(loadHistory);
  const [error, setError] = useState("");
  const [fileInfo, setFileInfo] = useState(null);
  const [fileError, setFileError] = useState("");
  const [reading, setReading] = useState(false);
  const fileRef = useRef(null),
    readGeneration = useRef(0);
  const total = comparison(scenarioId, baselineId),
    view = comparison(scenarioId, baselineId, trade);
  const tradeIds = ["hvac", "plumbing", "sprinkler", "electrical"];
  useEffect(() => {
    const target = document.getElementById(window.location.hash.slice(1));
    target?.scrollIntoView({ behavior: "instant" });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const escape = (e) => {
      if (e.key === "Escape") {
        setExpanded(false);
        setNavOpen(false);
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  const downloadReport = () => {
    saveFile(
      {
        title: "OMA — Hospital purchasing study",
        exportedAt: new Date().toISOString(),
        evidence,
        hospital,
        selectedComparison: total,
        sampleScenario: sample,
        notice:
          "Recorded purchasing estimates. Original installed geometry unchanged. Engineering and code compliance are unverified. The separate calculator uses synthetic sample data.",
      },
      "oma-hospital-results.json",
    );
    setToast("Hospital results downloaded");
  };
  const toggleSystem = (id) =>
    setVisibleSystems((old) =>
      old.includes(id) ? old.filter((s) => s !== id) : [...old, id],
    );
  const saveSample = () => {
    const next = [
      { id: crypto.randomUUID(), result: sample },
      ...history,
    ].slice(0, 8);
    setHistory(next);
    try {
      localStorage.setItem("oma-demo-scenarios", JSON.stringify(next));
      setToast("Calculation saved on this device");
    } catch {
      setToast("Saved for this visit; browser storage is unavailable");
    }
  };
  async function inspectFile(file) {
    if (!file) return;
    const generation = ++readGeneration.current;
    setFileError("");
    setFileInfo(null);
    setReading(true);
    try {
      if (!/\.ifc$/i.test(file.name))
        throw new Error("Choose an .ifc building file.");
      if (file.size > 25 * 1024 * 1024)
        throw new Error("The local file preview supports files up to 25 MB.");
      const result = inspectIfcText(await file.text(), file.name);
      if (generation === readGeneration.current) setFileInfo(result);
    } catch (e) {
      if (generation === readGeneration.current) setFileError(e.message);
    } finally {
      if (generation === readGeneration.current) setReading(false);
    }
  }

  return (
    <div className="site-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <a className="wordmark" href="#" aria-label="OMA home">
          <Mark />
          <span>
            oma<span className="brand-stop">.</span>
          </span>
        </a>
        <span className="brand-descriptor">
          Material planning,
          <br />
          with the whole building in view.
        </span>
        <nav className={navOpen ? "open" : ""} aria-label="Main navigation">
          <a href="#comparison" onClick={() => setNavOpen(false)}>
            Before & after
          </a>
          <a href="#breakdown" onClick={() => setNavOpen(false)}>
            By trade
          </a>
          <a href="#scope" onClick={() => setNavOpen(false)}>
            Study details
          </a>
        </nav>
        <button className="button header-download" onClick={downloadReport}>
          Download study <ArrowDown size={15} />
        </button>
        <IconButton
          label={navOpen ? "Close navigation" : "Open navigation"}
          onClick={() => setNavOpen(!navOpen)}
          aria-expanded={navOpen}
          className="icon-button mobile-menu"
        >
          {navOpen ? <X size={22} /> : <Menu size={22} />}
        </IconButton>
      </header>
      <main id="main">
        <section className="hero section-width" aria-labelledby="hero-title">
          <div className="hero-copy">
            <div className="eyebrow project-eyebrow">
              <span className="signal-dot" /> Hospital material-purchasing study{" "}
              <span className="study-number">No. 001</span>
            </div>
            <h1 id="hero-title">
              The hospital.
              <br />
              <em>Less waste.</em>
            </h1>
            <p className="hero-description">
              Purchase planning for straight pipe, duct, conduit and cable tray
              across the hospital.
            </p>
            <div className="hero-result">
              <span className="eyebrow">
                Estimated saving on these materials
              </span>
              <strong>
                {money(total.savings.costUsd)}
                <span>USD</span>
              </strong>
              <p>
                {baselineId === "perNetwork"
                  ? "Compared with purchasing each network separately."
                  : "Compared with purchases already combined."}
              </p>
            </div>
            <p className="hero-budget-note">
              Materials only. This is not the hospital construction budget.
            </p>
            <a className="button dark" href="#model-comparison">
              See the 3D before & after <ArrowDownRight size={18} />
            </a>
            <p className="hero-note">
              A purchasing estimate. Engineering review required.
              <br />
              Installation costs and additional joints are not priced.
            </p>
          </div>
          <div className={`model-panel ${expanded ? "expanded" : ""}`}>
            <div className="model-header">
              <div>
                <span className="eyebrow">West Riverside</span>
                <span className="model-name">Hospital study</span>
              </div>
              <span className="outline-label">7 source files</span>
            </div>
            <div className="model-stage">
              <div className="model-axis">
                N <span>↑</span>
              </div>
              <Suspense
                fallback={
                  <div className="model-loading">
                    Preparing the building view…
                  </div>
                }
              >
                <BuildingViewer
                  visibleSystems={visibleSystems}
                  level={level}
                  exploded={exploded}
                  resetKey={reset}
                />
              </Suspense>
            </div>
            <div className="model-tools">
              <label>
                <span className="sr-only">Visible building level</span>
                <select
                  aria-label="Visible building level"
                  value={level}
                  onChange={(e) =>
                    setLevel(
                      e.target.value === "all" ? "all" : Number(e.target.value),
                    )
                  }
                >
                  <option value="all">All floors</option>
                  {[0, 1, 2, 3, 4].map((v) => (
                    <option key={v} value={v}>
                      Level {v + 1}
                    </option>
                  ))}
                </select>
                <ChevronDown size={12} />
              </label>
              <div>
                <IconButton
                  label="Separate floors"
                  aria-pressed={exploded}
                  onClick={() => setExploded(!exploded)}
                >
                  <Layers size={16} />
                </IconButton>
                <IconButton
                  label="Reset camera"
                  onClick={() => setReset((v) => v + 1)}
                >
                  <RotateCcw size={16} />
                </IconButton>
                <IconButton
                  label={expanded ? "Collapse viewer" : "Expand viewer"}
                  onClick={() => setExpanded(!expanded)}
                >
                  {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </IconButton>
              </div>
            </div>
            <div className="model-trades" aria-label="Visible building systems">
              {viewerSystems.map((s) => (
                <button
                  key={s.id}
                  onClick={() => toggleSystem(s.id)}
                  aria-pressed={visibleSystems.includes(s.id)}
                  style={{ "--trade-color": s.color }}
                >
                  <span />
                  {s.label}
                </button>
              ))}
            </div>
            <div className="model-caption">
              <span>Illustrative model · not the source hospital geometry</span>
              <span>Drag to explore</span>
            </div>
          </div>
        </section>
        <div className="study-strip section-width">
          <div>
            <strong>7</strong>
            <span>
              building files
              <br />
              processed
            </span>
          </div>
          <div>
            <strong>
              {number(hospital.scenarios[scenarioId].plannedOriginalSegments)}
            </strong>
            <span>
              measured sections
              <br />
              included
            </span>
          </div>
          <div>
            <strong>{number(total.savings.purchasedM)}</strong>
            <span>
              metres less
              <br />
              material to buy
            </span>
          </div>
          <div>
            <strong>
              {number(total.savings.wastePercent, 1)}
              <small>%</small>
            </strong>
            <span>
              less material
              <br />
              waste
            </span>
          </div>
        </div>

        <section
          className="comparison-section section-width"
          id="comparison"
          aria-labelledby="comparison-title"
        >
          <div className="section-top">
            <div className="section-number">01 / THE CHANGE</div>
            <div>
              <h2 id="comparison-title">Materials, before &amp; after.</h2>
              <p>Straight pipe, duct, conduit and cable tray purchases only.</p>
            </div>
            <a href="#breakdown" className="text-link">
              See each trade <ArrowDown size={15} />
            </a>
          </div>
          <div className="budget-scope">
            <strong>Not a total construction budget.</strong>
            <span>
              These prices exclude the structure, finishes, equipment, wiring,
              labor and other building costs.
            </span>
          </div>
          <div className="comparison-controls">
            <div>
              <span className="control-label">Compare with</span>
              <div className="segmented" aria-label="Purchasing baseline">
                <button
                  aria-pressed={baselineId === "perNetwork"}
                  onClick={() => setBaselineId("perNetwork")}
                >
                  Separate orders
                </button>
                <button
                  aria-pressed={baselineId === "pooled"}
                  onClick={() => setBaselineId("pooled")}
                >
                  Orders already combined
                </button>
              </div>
            </div>
            <label className="scenario-select">
              <span className="control-label">Purchasing option</span>
              <select
                aria-label="Purchasing option"
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
              >
                <option value="broad">
                  Include long runs · added joints assumed
                </option>
                <option value="noSplice">No new joints · smaller scope</option>
              </select>
            </label>
          </div>
          <ModelComparison scenarioId={scenarioId} baselineId={baselineId} />
          <div className="comparison-context">
            <span>{tradeNames[trade]}</span>
            <p>
              {baselineId === "perNetwork"
                ? "Before: each connected network ordered separately. After: matching stock planned together."
                : "Before: purchases already combined using a standard cutting plan. After: the selected cutting plan."}
            </p>
            {trade !== "all" && (
              <button className="text-link" onClick={() => setTrade("all")}>
                Show all trades <X size={13} />
              </button>
            )}
          </div>
          <div className="order-comparison" aria-live="polite">
            <OrderPanel
              title="Before"
              subtitle={
                baselineId === "perNetwork"
                  ? "Separate network orders"
                  : "Orders already combined"
              }
              data={view.before}
              max={Math.max(view.before.purchasedM, view.after.purchasedM)}
            />
            <span className="comparison-arrow" aria-hidden="true">
              <ArrowRight size={22} />
            </span>
            <OrderPanel
              title="After"
              subtitle="Combined cutting plan"
              data={view.after}
              max={Math.max(view.before.purchasedM, view.after.purchasedM)}
              after
            />
          </div>
          <div className="comparison-bottom">
            <div className="bar-legend">
              <span>
                <i className="used-key" />
                Required pieces
              </span>
              <span>
                <i className="waste-key" />
                Material waste
              </span>
            </div>
            <div className="saving-line">
              <ArrowDownRight size={23} />
              <strong>{money(view.savings.costUsd)}</strong>
              <span>
                estimated material saving{" "}
                <small>({number(view.savings.costPercent, 2)}%)</small>
              </span>
            </div>
          </div>
          <p className="comparison-footnote">
            {scenarioId === "broad"
              ? "18,559 measured sections. Assumes 3,457 added joints in both purchasing alternatives. Joint costs are excluded."
              : "16,446 measured sections. No new splits; 2,113 longer sections remain outside this plan. This is a smaller included scope."}{" "}
            Materials and fabrication details remain unverified.
          </p>
        </section>

        <section
          className="trade-section section-width"
          id="breakdown"
          aria-labelledby="trade-title"
        >
          <div className="section-top">
            <div className="section-number">02 / THE BREAKDOWN</div>
            <div>
              <h2 id="trade-title">Where the difference comes from.</h2>
              <p>Four trades. One view of the material bill.</p>
            </div>
            <span className="table-unit">USD · estimated material costs</span>
          </div>
          <div
            className="trade-table-wrap"
            tabIndex="0"
            role="region"
            aria-label="Material costs by trade; scroll horizontally on small screens"
          >
            <table className="trade-table">
              <thead>
                <tr>
                  <th>Trade</th>
                  <th>Before</th>
                  <th>After</th>
                  <th>Estimated saving</th>
                  <th>
                    <span className="sr-only">Compare trade</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tradeIds.map((id, i) => {
                  const c = comparison(scenarioId, baselineId, id);
                  return (
                    <tr key={id} className={trade === id ? "selected" : ""}>
                      <th scope="row">
                        <span className={`trade-index trade-${id}`}>
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        {tradeNames[id]}
                        <small>
                          {id === "hvac"
                            ? "Straight pipe & duct"
                            : id === "plumbing"
                              ? "Straight pipe"
                              : id === "sprinkler"
                                ? "Sprinkler pipe"
                                : "Conduit & cable tray"}
                        </small>
                      </th>
                      <td>{money(c.before.costUsd)}</td>
                      <td>{money(c.after.costUsd)}</td>
                      <td className="trade-saving">
                        {money(c.savings.costUsd)}
                        <span className="trade-spark" aria-hidden="true">
                          <i
                            style={{
                              width: `${Math.max(2, (c.savings.costUsd / Math.max(total.savings.costUsd, 1)) * 100)}%`,
                            }}
                          />
                        </span>
                      </td>
                      <td>
                        <a
                          href="#comparison"
                          aria-label={`Compare ${tradeNames[id]}`}
                          onClick={() => setTrade(id)}
                        >
                          <ArrowUpRight size={19} />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <th>Total included</th>
                  <td>{money(total.before.costUsd)}</td>
                  <td>{money(total.after.costUsd)}</td>
                  <td>{money(total.savings.costUsd)}</td>
                  <td>
                    <a
                      href="#comparison"
                      aria-label="Compare all trades"
                      onClick={() => setTrade("all")}
                    >
                      <ArrowUpRight size={19} />
                    </a>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="trade-note">
            Fire alarm, architecture and structure were also processed. No
            purchasing savings are claimed for those files. Electrical savings
            cover conduit and tray, not wires or equipment. Totals use unrounded
            values.
          </p>
        </section>

        <section className="scope-section" id="scope">
          <div className="section-width scope-layout">
            <div className="scope-intro">
              <span className="section-number">03 / BEHIND THE NUMBERS</span>
              <h2>
                What the numbers
                <br />
                <em>include.</em>
              </h2>
              <p>
                This study brings the hospital’s files together and compares how
                its measured stock could be purchased and cut.
              </p>
              <p>
                The original building geometry stays unchanged. This is not a
                redesign of every installed system.
              </p>
              <button className="text-link" onClick={downloadReport}>
                Download the numbers <Download size={16} />
              </button>
            </div>
            <div className="scope-content">
              <div className="scope-row">
                <span className="scope-symbol">
                  <Check size={17} />
                </span>
                <div>
                  <h3>The purchasing arithmetic was checked.</h3>
                  <p>
                    Piece quantities, cut lengths, stock capacity and costs were
                    independently recalculated for both plans.
                  </p>
                </div>
              </div>
              <div className="scope-row">
                <span className="scope-symbol neutral">≈</span>
                <div>
                  <h3>The price is an estimate.</h3>
                  <p>
                    Supplier price references and size estimates, not a
                    contractor quote. Labor, added joints, equipment, delivery
                    and taxes are excluded.
                  </p>
                </div>
              </div>
              <details className="review-details">
                <summary>
                  <span className="scope-symbol review-symbol">!</span>
                  <span>
                    <strong>Engineering review is still required.</strong>
                    <small>See what needs to be resolved</small>
                  </span>
                  <Plus size={19} />
                </summary>
                <div className="review-body">
                  <p>
                    <strong>
                      Neither plan is cleared for construction or confirmed
                      code-compliant.
                    </strong>{" "}
                    Material specifications, design requirements and the
                    governing code remain unresolved.
                  </p>
                  <ul>
                    <li>The broader plan assumes 3,457 additional joints.</li>
                    <li>
                      149 new cut pieces are shorter than 100 mm, including a 3
                      mm duct piece. Product-specific minimum lengths and
                      connection allowances need to be added. The 100 mm
                      threshold is a review flag, not a code limit.
                    </li>
                    <li>
                      Ventilation, circuit protection, sprinkler hydraulics,
                      fire alarm performance and structural safety have not been
                      verified for this hospital.
                    </li>
                  </ul>
                  <p>
                    These are open design and fabrication questions. Missing
                    model data alone does not prove a code violation.
                  </p>
                </div>
              </details>
              <details className="source-details">
                <summary>
                  <span>
                    <strong>All seven building files, accounted for.</strong>
                    <small>
                      149,822 model entries · 19,352 pipe, duct & tray sections
                    </small>
                  </span>
                  <Plus size={19} />
                </summary>
                <div className="source-list">
                  {disciplines.map((d) => (
                    <div key={d.id}>
                      <span>{d.label}</span>
                      <span>{number(d.products)} entries</span>
                    </div>
                  ))}
                  <p>
                    18,559 sections measured; 793 could not be measured
                    reliably. These are counts from the files, not the number of
                    code checks.
                  </p>
                </div>
              </details>
            </div>
          </div>
        </section>
        <section className="explore-section section-width">
          <div>
            <span className="eyebrow">A closer look at the method</span>
            <h2>Try the numbers yourself.</h2>
            <p>
              Adjust a material price and stock length in a small, separate
              example.
            </p>
          </div>
          <button
            className="button dark"
            onClick={() => setDialog("calculator")}
          >
            Open cost calculator <ArrowUpRight size={18} />
          </button>
        </section>
      </main>
      <footer className="site-footer section-width">
        <a className="wordmark" href="#" aria-label="Back to top">
          <Mark />
          <span>oma.</span>
        </a>
        <p>
          OMA + ANANKE
          <br />
          <span>Hospital purchasing study · October 2026</span>
        </p>
        <div>
          <button onClick={() => setDialog("import")}>
            Open a building file <Upload size={14} />
          </button>
          <button onClick={downloadReport}>
            Download study <ArrowDown size={14} />
          </button>
        </div>
        <span className="footer-note">Customer demonstration</span>
      </footer>

      {dialog === "calculator" && (
        <Dialog
          title="A smaller order, piece by piece."
          label="Interactive example · sample data"
          close={() => setDialog(null)}
          wide
        >
          <p className="dialog-intro">
            These 48 sample pieces are separate from the hospital. Change a
            price or length to see how pooling orders changes the material bill.
          </p>
          <div className="calculator-layout">
            <form
              className="calculator-inputs"
              onSubmit={(e) => {
                e.preventDefault();
                try {
                  setSample(calculateScenario(inputs));
                  setError("");
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              <label>
                Material
                <select
                  value={inputs.type}
                  onChange={(e) =>
                    setInputs({
                      ...inputs,
                      type: e.target.value,
                      price: sampleTypes[e.target.value].rate,
                    })
                  }
                >
                  {Object.entries(sampleTypes).map(([key, v]) => (
                    <option key={key} value={key}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Length sold by the supplier
                <select
                  value={inputs.stockM}
                  onChange={(e) =>
                    setInputs({ ...inputs, stockM: Number(e.target.value) })
                  }
                >
                  {[3, 6, 12].map((m) => (
                    <option value={m} key={m}>
                      {m} m
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Material price per metre
                <input
                  type="number"
                  min="0"
                  max="1000"
                  step="0.01"
                  value={inputs.price}
                  onChange={(e) =>
                    setInputs({ ...inputs, price: e.target.value })
                  }
                  required
                />
              </label>
              <label>
                Material lost per cut
                <select
                  value={inputs.kerfMm}
                  onChange={(e) =>
                    setInputs({ ...inputs, kerfMm: Number(e.target.value) })
                  }
                >
                  {[0, 3, 5].map((v) => (
                    <option value={v} key={v}>
                      {v} mm
                    </option>
                  ))}
                </select>
              </label>
              <button className="button dark" type="submit">
                Calculate savings <ArrowRight size={17} />
              </button>
              {error && <p role="alert">{error}</p>}
            </form>
            <div className="calculator-results" aria-live="polite">
              <span className="eyebrow">Sample material saving</span>
              <strong className="sample-saving">
                {money(sample.savedCost)}
              </strong>
              <div className="sample-costs">
                <span>
                  Separate orders <strong>{money(sample.baseline.cost)}</strong>
                </span>
                <span>
                  Pooled order <strong>{money(sample.selected.cost)}</strong>
                </span>
              </div>
              <div className="sample-stock">
                <div>
                  <span>Before · {sample.baseline.bars} lengths</span>
                  <div>
                    {sample.before.map((b, i) => (
                      <i
                        key={i}
                        style={{
                          "--filled": `${(b.used / (sample.stockM * 1000)) * 100}%`,
                        }}
                      />
                    ))}
                  </div>
                </div>
                <div>
                  <span>After · {sample.selected.bars} lengths</span>
                  <div>
                    {sample.after.map((b, i) => (
                      <i
                        key={i}
                        style={{
                          "--filled": `${(b.used / (sample.stockM * 1000)) * 100}%`,
                        }}
                      />
                    ))}
                  </div>
                </div>
              </div>
              <p>
                <Check size={15} /> All 48 pieces still fit
              </p>
              <div className="sample-actions">
                <button className="text-link" onClick={saveSample}>
                  Save calculation <Plus size={15} />
                </button>
                <button
                  className="text-link"
                  onClick={() =>
                    saveFile(sample, "oma-sample-cutting-plan.json")
                  }
                >
                  Download cuts <Download size={15} />
                </button>
              </div>
            </div>
          </div>
          {history.length > 0 && (
            <details className="saved-calculations">
              <summary>
                Saved calculations on this device <ChevronDown size={15} />
              </summary>
              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setSample(item.result);
                    setInputs({
                      type: item.result.type,
                      stockM: item.result.stockM,
                      price: item.result.price,
                      kerfMm: item.result.kerfMm,
                    });
                  }}
                >
                  {item.result.label} · {item.result.stockM} m stock{" "}
                  <span>
                    {money(item.result.savedCost)} saved{" "}
                    <ArrowUpRight size={15} />
                  </span>
                </button>
              ))}
            </details>
          )}
          <p className="dialog-small">
            Sample lengths and editable prices. A feasible cutting calculation;
            no engineering or code approval.
          </p>
        </Dialog>
      )}
      {dialog === "import" && (
        <Dialog
          title="Take a look inside a file."
          label="Local file preview"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            Count the entries in an IFC building file. The file stays in this
            browser; it is not uploaded.
          </p>
          <button
            className="file-picker"
            onClick={() => fileRef.current.click()}
          >
            <Upload size={28} />
            <strong>Choose a building file</strong>
            <span>.ifc · up to 25 MB</span>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".ifc"
            className="sr-only"
            onChange={(e) => inspectFile(e.target.files[0])}
          />
          {reading && <p role="status">Reading file…</p>}
          {fileError && (
            <p role="alert" className="form-error">
              {fileError}
            </p>
          )}
          {fileInfo && (
            <div className="file-result">
              <FileText size={20} />
              <div>
                <strong>{fileInfo.filename}</strong>
                <p>
                  {number(fileInfo.records)} file records · {fileInfo.schema}
                </p>
              </div>
            </div>
          )}
          <p className="dialog-small">
            A file-content preview only. This does not import geometry,
            calculate a design or assess code compliance.
          </p>
        </Dialog>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
    </div>
  );
}
