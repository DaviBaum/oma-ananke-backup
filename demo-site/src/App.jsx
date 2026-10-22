import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Box,
  Building2,
  Cable,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  Download,
  Droplets,
  FileText,
  Flame,
  GitBranch,
  Layers,
  Maximize2,
  Menu,
  Minus,
  Network,
  Play,
  Plus,
  RotateCw,
  SlidersHorizontal,
  Upload,
  Wind,
  X,
} from "lucide-react";
import evidence, {
  project,
  disciplines,
  routeComparison,
  workflow,
  capabilities,
} from "./evidence.js";
import { calculateScenario, inspectIfcText, sampleTypes } from "./scenario.js";

const BuildingViewer = lazy(() => import("./BuildingViewer.jsx"));
const n = (value) => new Intl.NumberFormat("en-US").format(value);
const money = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
const systems = [
  { id: "hvac", label: "Heating & cooling", color: "#2e8b79", icon: Wind },
  { id: "plumbing", label: "Plumbing", color: "#447eaf", icon: Droplets },
  { id: "electrical", label: "Electrical", color: "#b98632", icon: Cable },
  { id: "fire", label: "Sprinklers", color: "#be675d", icon: Flame },
];
const nav = [
  { id: "overview", label: "Results", icon: Box },
  { id: "scenarios", label: "Cost calculator", icon: SlidersHorizontal },
  { id: "evidence", label: "What was tested", icon: ClipboardIcon },
  { id: "history", label: "Saved calculations", icon: Clock3 },
];
function ClipboardIcon(props) {
  return <FileText {...props} />;
}
function Mark() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <path
        d="M7 32 20 8l13 24M12 23h16M20 8v24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function Pill({ children, neutral = false }) {
  return (
    <span className={`pill ${neutral ? "neutral" : ""}`}>
      <span />
      {children}
    </span>
  );
}
function IconButton({ label, children, active, ...props }) {
  return (
    <button
      className={`icon-btn ${active ? "active" : ""}`}
      title={label}
      aria-label={label}
      aria-pressed={active === undefined ? undefined : active}
      {...props}
    >
      {children}
    </button>
  );
}
function download(value, name) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function readHistory() {
  try {
    const records = JSON.parse(
      localStorage.getItem("oma-demo-scenarios") || "[]",
    );
    if (!Array.isArray(records)) return [];
    return records.slice(0, 12).flatMap((r) => {
      try {
        if (
          typeof r?.id !== "string" ||
          !Number.isFinite(Date.parse(r?.at)) ||
          !r?.result
        )
          return [];
        return [{ id: r.id, at: r.at, result: calculateScenario(r.result) }];
      } catch {
        return [];
      }
    });
  } catch {
    return [];
  }
}

function Dialog({ title, eyebrow, children, close, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
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
      <div className="dialog-head">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <IconButton label="Close dialog" onClick={close}>
          <X size={20} />
        </IconButton>
      </div>
      {children}
    </dialog>
  );
}

export default function App() {
  const [page, setPage] = useState("overview");
  const [mobileNav, setMobileNav] = useState(false);
  const [visible, setVisible] = useState(systems.map((s) => s.id));
  const [level, setLevel] = useState("all");
  const [exploded, setExploded] = useState(false);
  const [rotation, setRotation] = useState(false);
  const [reset, setReset] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [dialog, setDialog] = useState(null);
  const [discipline, setDiscipline] = useState(null);
  const [history, setHistory] = useState(readHistory);
  const [toast, setToast] = useState("");
  const [scenario, setScenario] = useState(() => calculateScenario());
  const [inputs, setInputs] = useState({
    type: "plumbing",
    stockM: 6,
    price: 18,
    kerfMm: 3,
  });
  const [running, setRunning] = useState(false);
  const [scenarioError, setScenarioError] = useState("");
  const [ifc, setIfc] = useState(null);
  const [ifcError, setIfcError] = useState("");
  const [reading, setReading] = useState(false);
  const fileRef = useRef(null);
  const runTimer = useRef(null);
  const readGeneration = useRef(0);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(""), 4500);
      return () => clearTimeout(t);
    }
  }, [toast]);
  useEffect(() => () => clearTimeout(runTimer.current), []);
  useEffect(() => {
    const escape = (e) => {
      if (e.key === "Escape") {
        setFullscreen(false);
        setMobileNav(false);
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  const go = (id) => {
    setPage(id);
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const toggle = (id) =>
    setVisible((current) =>
      current.includes(id) ? current.filter((i) => i !== id) : [...current, id],
    );
  const report = () => {
    download(
      {
        title: "OMA customer demonstration",
        exportedAt: new Date().toISOString(),
        evidence,
        sampleScenario: scenario,
        notice:
          "Historical evidence and a separate synthetic purchasing example. No live engineering backend or whole-hospital savings claim.",
      },
      "oma-demonstration-report.json",
    );
    setToast("Demonstration report downloaded");
  };
  const runScenario = () => {
    setRunning(true);
    setScenarioError("");
    runTimer.current = setTimeout(() => {
      try {
        const result = calculateScenario(inputs);
        setScenario(result);
        setToast("Calculated · all 48 required pieces fit");
      } catch (error) {
        setScenarioError(error.message);
      } finally {
        setRunning(false);
      }
    }, 220);
  };
  const saveScenario = () => {
    const record = {
      id: crypto.randomUUID(),
      at: new Date().toISOString(),
      result: scenario,
    };
    const next = [record, ...history].slice(0, 12);
    setHistory(next);
    try {
      localStorage.setItem("oma-demo-scenarios", JSON.stringify(next));
      setToast("Calculation saved on this device");
    } catch {
      setToast(
        "Saved for this visit; this browser cannot keep it after closing",
      );
    }
  };
  async function inspectFile(file) {
    if (!file) return;
    const generation = ++readGeneration.current;
    setIfc(null);
    setIfcError("");
    setReading(true);
    try {
      if (!/\.ifc$/i.test(file.name))
        throw new Error("Choose an .ifc file for the local inspector.");
      if (file.size > 25 * 1024 * 1024)
        throw new Error(
          "The browser inspector supports files up to 25 MB. The full engine handles larger models.",
        );
      const text = await file.text();
      const result = inspectIfcText(text, file.name);
      if (generation === readGeneration.current) setIfc(result);
    } catch (error) {
      if (generation === readGeneration.current) setIfcError(error.message);
    } finally {
      if (generation === readGeneration.current) setReading(false);
    }
  }
  const scenarioDirty =
    inputs.type !== scenario.type ||
    Number(inputs.stockM) !== scenario.stockM ||
    Number(inputs.price) !== scenario.price ||
    Number(inputs.kerfMm) !== scenario.kerfMm;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {mobileNav && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <button
          className="brand"
          onClick={() => go("overview")}
          aria-label="OMA home"
        >
          <span className="brand-symbol">
            <Mark />
          </span>
          <span>
            oma<span className="brand-period">.</span>
          </span>
        </button>
        <div className="workspace-picker">
          <span className="workspace-avatar">A</span>
          <div>
            OMA + ANANKE<small>Customer preview</small>
          </div>
          <span className="preview-dot" />
        </div>
        <p className="nav-label">EXPLORE THE DEMO</p>
        <nav aria-label="Main navigation">
          {nav.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "selected" : ""}`}
              onClick={() => go(item.id)}
              aria-current={page === item.id ? "page" : undefined}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {item.id === "history" && history.length > 0 && (
                <span className="nav-count">{history.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-divider" />
        <p className="nav-label">BUILDING EXAMPLE</p>
        <button className="project-link" onClick={() => go("overview")}>
          <Building2 size={17} />
          <span>
            Hospital<small>Hospital · 7 building files</small>
          </span>
        </button>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="tiny-label">WHAT CHANGES?</span>
            <p>
              Fewer parts.
              <br />
              Less material to buy.
            </p>
            <button onClick={() => go("evidence")}>
              See the test results <ArrowUpRight size={15} />
            </button>
          </div>
          <button className="help-button" onClick={() => setDialog("guide")}>
            <CircleHelp size={17} /> Demo guide <span>?</span>
          </button>
          <div className="sidebar-foot">
            <span className="user-avatar">G</span>
            <div>
              No sign-in needed<small>Interactive demo</small>
            </div>
            <span className="version">v0.1</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <IconButton
              label="Open navigation"
              onClick={() => setMobileNav(!mobileNav)}
            >
              <Menu size={19} />
            </IconButton>
            <span>Projects</span>
            <ChevronRight size={14} />
            <span>Hospital</span>
            <span className="header-divider" />
            <span className="demo-tag">PRODUCT DEMO</span>
          </div>
          <button
            className="text-button top-help"
            onClick={() => setDialog("guide")}
          >
            How to explore <CircleHelp size={16} />
          </button>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="heading-line" />
                {page === "overview"
                  ? "LESS MATERIAL. FEWER FITTINGS."
                  : page === "scenarios"
                    ? "TRY THE NUMBERS"
                    : page === "evidence"
                      ? "RESULTS FROM THE PIPE TEST"
                      : "YOUR SAVED CALCULATIONS"}
              </div>
              <h1>
                {page === "overview"
                  ? "Build with less waste."
                  : page === "scenarios"
                    ? "How much could you save on material?"
                    : page === "evidence"
                      ? "See how the results were checked."
                      : "Your saved cost comparisons."}
              </h1>
              <p>
                {page === "overview"
                  ? "Shorter pipe routes. Fewer fittings. Less leftover material. See the difference below."
                  : page === "scenarios"
                    ? "Change the purchase length and price. See how buying and cutting together changes the bill."
                    : page === "evidence"
                      ? "What changed, what was checked, and what still needs an engineer."
                      : "Reopen a calculation or compare different prices. Saved on this device only."}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                onClick={() => setDialog("import")}
              >
                <Upload size={16} /> Open building file
              </button>
              <button
                className="button primary"
                onClick={page === "overview" ? () => go("scenarios") : report}
              >
                {page === "overview" ? (
                  <>
                    <ArrowRight size={16} /> Try the cost calculator
                  </>
                ) : (
                  <>
                    <Download size={16} /> Download results
                  </>
                )}
              </button>
            </div>
          </div>

          {page === "overview" && (
            <>
              <div className="project-strip">
                <div>
                  <span className="project-icon">
                    <Building2 size={21} />
                  </span>
                  <div>
                    <strong>Hospital example</strong>
                    <span>
                      7 building files <i /> Recorded test
                    </span>
                  </div>
                </div>
                <Pill>Files counted</Pill>
              </div>
              <section
                className="impact-grid"
                aria-label="What improved in the examples"
              >
                <button
                  className="impact-card"
                  onClick={() => setDialog("route")}
                >
                  <span className="impact-source">RECORDED PIPE TEST</span>
                  <strong>4 fewer</strong>
                  <h2>fittings to install</h2>
                  <p>
                    One fitting instead of five. Fewer parts to join together.
                  </p>
                  <span className="impact-link">
                    See the change <ArrowUpRight size={17} />
                  </span>
                </button>
                <button
                  className="impact-card"
                  onClick={() => setDialog("route")}
                >
                  <span className="impact-source">SAME PIPE TEST</span>
                  <strong>13.6% shorter</strong>
                  <h2>pipe route</h2>
                  <p>5.79 m down to 5.00 m. The same water delivery points.</p>
                  <span className="impact-link">
                    Compare the routes <ArrowUpRight size={17} />
                  </span>
                </button>
                <button
                  className="impact-card cost-impact"
                  onClick={() => go("scenarios")}
                >
                  <span className="impact-source">
                    SEPARATE SAMPLE COST CALCULATION
                  </span>
                  <strong>$972 less</strong>
                  <h2>spent on material</h2>
                  <p>
                    Buy 90 m instead of 144 m at an assumed $18/m. All 48 pieces
                    still fit.
                  </p>
                  <span className="impact-link">
                    Try your own price <ArrowRight size={17} />
                  </span>
                </button>
              </section>
              <p className="impact-scope">
                The pipe test is a small route comparison. The cost example uses
                sample lengths and prices; neither is a whole-hospital savings
                estimate.
              </p>
              <div className="workspace-grid">
                <section
                  className={`viewer-card ${fullscreen ? "expanded" : ""}`}
                  aria-label="Interactive building viewer"
                >
                  <div className="panel-header">
                    <div>
                      <span className="panel-title">
                        Look inside the building
                      </span>
                      <span className="subtle-tag">3D VIEW</span>
                    </div>
                    <div className="viewer-options">
                      <label className="level-select">
                        <Layers size={15} />
                        <select
                          aria-label="Visible building level"
                          value={level}
                          onChange={(e) =>
                            setLevel(
                              e.target.value === "all"
                                ? "all"
                                : Number(e.target.value),
                            )
                          }
                        >
                          <option value="all">All levels</option>
                          {[0, 1, 2, 3, 4].map((l) => (
                            <option value={l} key={l}>
                              Level {String(l + 1).padStart(2, "0")}
                            </option>
                          ))}
                        </select>
                      </label>
                      <IconButton
                        label={
                          fullscreen ? "Exit expanded view" : "Expand viewer"
                        }
                        active={fullscreen}
                        onClick={() => setFullscreen(!fullscreen)}
                      >
                        {fullscreen ? <X size={17} /> : <Maximize2 size={16} />}
                      </IconButton>
                    </div>
                  </div>
                  <div className="viewer-stage">
                    <div className="viewer-caption">
                      <span>HOSPITAL / EXAMPLE VIEW</span>
                      <small>Simplified demonstration</small>
                    </div>
                    <Suspense
                      fallback={
                        <div className="viewer-loading">
                          <Box size={28} />
                          <span>Preparing the building view…</span>
                        </div>
                      }
                    >
                      <BuildingViewer
                        visibleSystems={visible}
                        level={level}
                        exploded={exploded}
                        rotation={rotation}
                        resetKey={reset}
                      />
                    </Suspense>
                    <div className="viewer-tools">
                      <IconButton
                        label="Reset camera"
                        onClick={() => setReset((r) => r + 1)}
                      >
                        <RotateCw size={17} />
                      </IconButton>
                      <IconButton
                        label="Separate floors"
                        active={exploded}
                        onClick={() => setExploded(!exploded)}
                      >
                        <Layers size={17} />
                      </IconButton>
                      <IconButton
                        label="Auto rotate model"
                        active={rotation}
                        onClick={() => setRotation(!rotation)}
                      >
                        <Play size={16} />
                      </IconButton>
                    </div>
                    <div className="viewer-scale">
                      <span />
                      10 m <small>example scale</small>
                    </div>
                    <div className="orientation">
                      <span>N</span>
                      <svg viewBox="0 0 40 40">
                        <path d="m20 6 7 25-7-5-7 5Z" fill="#6e7e75" />
                        <path d="m20 6 0 20-7 5Z" fill="#c1c9c1" />
                      </svg>
                    </div>
                  </div>
                  <div className="system-controls">
                    {systems.map((s) => (
                      <button
                        key={s.id}
                        className={`system-toggle ${visible.includes(s.id) ? "on" : ""}`}
                        style={{ "--system-color": s.color }}
                        aria-pressed={visible.includes(s.id)}
                        onClick={() => toggle(s.id)}
                      >
                        <span className="system-check">
                          {visible.includes(s.id) && <Check size={10} />}
                        </span>
                        {s.label}
                      </button>
                    ))}
                    <button
                      className="show-all"
                      onClick={() =>
                        setVisible(
                          visible.length === 4 ? [] : systems.map((s) => s.id),
                        )
                      }
                    >
                      {visible.length === 4 ? "Hide all" : "Show all"}
                    </button>
                  </div>
                  <div className="viewer-foot">
                    <span>
                      <span className="small-dot" />
                      Example 3D view, not the actual hospital design
                    </span>
                    <span>Drag to rotate · Scroll to zoom</span>
                  </div>
                </section>
                <aside className="insights">
                  <div className="insight-header">
                    <span className="eyebrow">WHAT THE CHANGES MEAN</span>
                    <span className="round-arrow">
                      <ArrowUpRight size={18} />
                    </span>
                  </div>
                  <h2>
                    Fewer parts to fit. <br /> Less waste to pay for.
                  </h2>
                  <p className="insight-intro">
                    Compare the pipe change, or try a price in the calculator.
                  </p>
                  <button
                    className="opportunity"
                    onClick={() => setDialog("route")}
                  >
                    <div className="opportunity-top">
                      <span className="tiny-label">PIPE ROUTE TEST</span>
                      <ArrowUpRight size={18} />
                    </div>
                    <div className="opportunity-number">
                      5 <span>→</span> 1<span className="decrease">↘</span>
                    </div>
                    <h3>Four fewer fittings to install.</h3>
                    <p>
                      The shorter option uses one fitting instead of five. Open
                      the test to see what changed.
                    </p>
                    <div className="opportunity-foot">
                      <span>See the two routes</span>
                      <ArrowRight size={17} />
                    </div>
                  </button>
                  <button
                    className="lab-teaser"
                    onClick={() => go("scenarios")}
                  >
                    <span className="lab-icon">
                      <SlidersHorizontal size={20} />
                    </span>
                    <div>
                      <strong>Buy fewer lengths. Cut the same pieces.</strong>
                      <span>Change the price and see the cost difference.</span>
                    </div>
                    <ChevronRight size={18} />
                  </button>
                  <div className="evidence-note">
                    <CheckCircle2 size={17} />
                    <p>
                      See the change before deciding.
                      <br />
                      <span>See both options and the numbers behind them.</span>
                    </p>
                  </div>
                </aside>
              </div>
              <details className="discipline-section source-details">
                <summary className="section-heading">
                  <div>
                    <span className="eyebrow">THE HOSPITAL FILES</span>
                    <h2>What is included in the building example?</h2>
                  </div>
                  <span className="table-subtitle">
                    Open file details <ChevronDown size={16} />
                  </span>
                </summary>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Part of the building</th>
                        <th>File entries</th>
                        <th>Parts to review</th>
                        <th>Recorded connections</th>
                        <th>File review</th>
                        <th>
                          <span className="sr-only">Inspect</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {disciplines.map((d) => (
                        <tr
                          key={d.id}
                          onClick={() => {
                            setDiscipline(d);
                            setDialog("discipline");
                          }}
                        >
                          <td>
                            <span
                              className="discipline-code"
                              style={{ "--system-color": d.color }}
                            >
                              {d.code}
                            </span>
                            <strong>{d.label}</strong>
                          </td>
                          <td>{n(d.products)}</td>
                          <td>{n(d.objects)}</td>
                          <td>{n(d.connections)}</td>
                          <td>
                            <span
                              className={`table-status ${d.id === "architecture" ? "review" : ""}`}
                            >
                              <span />
                              {d.status}
                            </span>
                          </td>
                          <td>
                            <button
                              className="row-open"
                              aria-label={`Inspect ${d.label}`}
                            >
                              <ArrowUpRight size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="table-note">
                  The files contain 45,946 service parts and 1,770 items that
                  still need identifying. File entries also include rooms and
                  connection points. These counts are not savings or a design
                  approval.
                </div>
              </details>
              <div className="bottom-cta">
                <div>
                  <span className="eyebrow">
                    TRY A PRICE THAT MAKES SENSE TO YOU
                  </span>
                  <h2>See the effect on the material bill.</h2>
                </div>
                <button
                  className="button primary"
                  onClick={() => go("scenarios")}
                >
                  Try the cost calculator <ArrowRight size={16} />
                </button>
              </div>
            </>
          )}

          {page === "scenarios" && (
            <>
              <div className="context-banner">
                <span className="sample-tag">SAMPLE DATA</span>
                <p>
                  This example needs 48 finished pieces. See how cutting them
                  together reduces leftover material. Lengths and prices are
                  sample inputs, not hospital costs.
                </p>
              </div>
              <div className="scenario-grid">
                <section className="scenario-inputs panel">
                  <div className="panel-header">
                    <span className="panel-title">
                      Choose your prices and lengths
                    </span>
                    <SlidersHorizontal size={18} />
                  </div>
                  <div className="input-body">
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
                    <fieldset className="stock-fieldset">
                      <legend>Length sold by the supplier</legend>
                      <div className="segmented">
                        {[3, 6, 12].map((m) => (
                          <button
                            className={
                              Number(inputs.stockM) === m ? "selected" : ""
                            }
                            key={m}
                            onClick={() => setInputs({ ...inputs, stockM: m })}
                          >
                            {m} m
                          </button>
                        ))}
                      </div>
                    </fieldset>
                    <label>
                      Your assumed price <span>USD / metre</span>
                      <div className="price-input">
                        <span>$</span>
                        <input
                          type="number"
                          min="0"
                          max="1000"
                          step="1"
                          aria-label="Material price per metre"
                          value={inputs.price}
                          onChange={(e) =>
                            setInputs({ ...inputs, price: e.target.value })
                          }
                        />
                      </div>
                    </label>
                    <label>
                      Material lost in each cut
                      <select
                        value={inputs.kerfMm}
                        onChange={(e) =>
                          setInputs({
                            ...inputs,
                            kerfMm: Number(e.target.value),
                          })
                        }
                      >
                        <option value="0">0 mm per piece</option>
                        <option value="3">3 mm per piece</option>
                        <option value="5">5 mm per piece</option>
                      </select>
                    </label>
                    <div className="fixed-inputs">
                      <div>
                        <span>Required pieces</span>
                        <strong>48</strong>
                      </div>
                      <div>
                        <span>Separate orders</span>
                        <strong>12</strong>
                      </div>
                      <div>
                        <span>Required length</span>
                        <strong>{scenario.requiredM.toFixed(2)} m</strong>
                      </div>
                      <div>
                        <span>Finished piece sizes</span>
                        <strong>Unchanged</strong>
                      </div>
                    </div>
                    <button
                      className="button primary full"
                      disabled={running}
                      onClick={runScenario}
                    >
                      {running ? (
                        <RotateCw className="spin" size={16} />
                      ) : (
                        <Play size={16} />
                      )}{" "}
                      {running ? "Calculating…" : "Calculate savings"}
                    </button>
                    {scenarioError && (
                      <p className="form-error" role="alert">
                        {scenarioError}
                      </p>
                    )}
                    <p className="input-note">
                      Use your own price. The starting price is an example, not
                      a supplier quote.
                    </p>
                  </div>
                </section>
                <section className="scenario-results">
                  <div className="result-heading">
                    <div>
                      <span className="eyebrow">
                        {scenarioDirty
                          ? "INPUTS CHANGED · RECALCULATE TO UPDATE"
                          : "COST DIFFERENCE IN THIS EXAMPLE"}
                      </span>
                      <h2>Same 48 pieces. Less material to buy.</h2>
                    </div>
                    <Pill neutral={scenarioDirty}>
                      {scenarioDirty
                        ? "Previous calculation"
                        : "All 48 pieces still fit"}
                    </Pill>
                  </div>
                  <div className="saving-summary">
                    <div>
                      <span>Estimated savings in this sample</span>
                      <strong>
                        {money(scenario.savedCost)}
                        <small>less to spend on material</small>
                      </strong>
                      <p>
                        {scenario.savedM.toFixed(1)} m less purchased ·{" "}
                        {scenario.savedPercent.toFixed(1)}% reduction
                      </p>
                    </div>
                    <div
                      className="saving-ring"
                      style={{ "--percent": `${scenario.savedPercent}%` }}
                    >
                      <span>
                        {scenario.savedPercent.toFixed(0)}
                        <small>% less</small>
                      </span>
                    </div>
                  </div>
                  <div className="comparison-columns">
                    <div>
                      <span className="tiny-label">
                        BUYING FOR EACH ORDER SEPARATELY
                      </span>
                      <strong>
                        {scenario.baseline.purchasedM.toFixed(0)}
                        <small> m</small>
                      </strong>
                      <p>
                        {scenario.baseline.bars} full lengths <i />{" "}
                        {money(scenario.baseline.cost)}
                      </p>
                      <div className="comparison-bar">
                        <span style={{ width: "100%" }} />
                      </div>
                    </div>
                    <div className="after">
                      <span className="tiny-label">
                        BUYING AND CUTTING TOGETHER
                      </span>
                      <strong>
                        {scenario.selected.purchasedM.toFixed(0)}
                        <small> m</small>
                      </strong>
                      <p>
                        {scenario.selected.bars} full lengths <i />{" "}
                        {money(scenario.selected.cost)}
                      </p>
                      <div className="comparison-bar">
                        <span
                          style={{
                            width: `${(scenario.selected.purchasedM / scenario.baseline.purchasedM) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="cut-plan">
                    <div className="cut-plan-head">
                      <h3>Where each piece comes from</h3>
                      <span>
                        First {Math.min(6, scenario.after.length)} of{" "}
                        {scenario.after.length} full lengths
                      </span>
                    </div>
                    {scenario.after.slice(0, 6).map((bar, i) => (
                      <div className="cut-row" key={i}>
                        <span>{String(i + 1).padStart(2, "0")}</span>
                        <div className="cut-bar">
                          {bar.cuts.map((piece, j) => (
                            <span
                              title={`${piece.id}: ${(piece.length / 1000).toFixed(2)} m`}
                              key={piece.id}
                              style={{
                                width: `${((piece.length + scenario.kerfMm) / (scenario.stockM * 1000)) * 100}%`,
                                background: j % 2 ? "#90ac99" : "#668975",
                              }}
                            >
                              {piece.length >= 1200 &&
                                (piece.length / 1000).toFixed(2)}
                            </span>
                          ))}
                        </div>
                        <small>
                          {((scenario.stockM * 1000 - bar.used) / 1000).toFixed(
                            2,
                          )}{" "}
                          m
                        </small>
                      </div>
                    ))}
                    <div className="cut-legend">
                      <span>
                        <i />
                        Required pieces
                      </span>
                      <span>
                        <i />
                        Material left over
                      </span>
                      <span>{scenario.kerfMm} mm lost per cut included</span>
                    </div>
                  </div>
                  <div className="result-actions">
                    <button className="button secondary" onClick={saveScenario}>
                      <Plus size={16} />
                      Save calculation
                    </button>
                    <button
                      className="text-button"
                      onClick={() => {
                        download(scenario, "oma-sample-cutting-plan.json");
                        setToast("Complete cutting plan downloaded");
                      }}
                    >
                      Download cutting list <Download size={16} />
                    </button>
                  </div>
                  <p className="scenario-scope">
                    The first plan buys material for each of 12 orders
                    separately. The second combines them and uses leftovers for
                    other pieces. Both supply the same 48 pieces and allow for
                    material lost while cutting. Savings cover material only,
                    before labor, fittings and delivery. This is one workable
                    plan; a better one may exist.
                  </p>
                </section>
              </div>
            </>
          )}

          {page === "evidence" && (
            <>
              <div className="evidence-hero">
                <div>
                  <span className="eyebrow">ONE PIPE ROUTE, TWO OPTIONS</span>
                  <h2>
                    Four fewer fittings. <br /> The same water delivery points.
                  </h2>
                  <p>
                    The shorter route uses one fitting instead of five. That
                    means four fewer parts to join. It also passed the test’s
                    space, connection and water-flow checks. Installation time
                    was not measured.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => setDialog("route")}
                  >
                    See what changed <ArrowRight size={16} />
                  </button>
                </div>
                <div className="evidence-stats">
                  <div>
                    <strong>5 → 1</strong>
                    <span>Fittings needed</span>
                  </div>
                  <div>
                    <strong>5.79 → 5.00 m</strong>
                    <span>Length of the pipe route</span>
                  </div>
                  <div>
                    <strong>4.625 m</strong>
                    <span>Straight pipe needed in either option</span>
                  </div>
                </div>
              </div>
              <section className="workflow">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">HOW IT WORKS</span>
                    <h2>From a building file to a comparison.</h2>
                  </div>
                </div>
                <div className="workflow-steps">
                  {workflow.map((w) => (
                    <div key={w.number}>
                      <span className="step-number">{w.number}</span>
                      <h3>{w.title}</h3>
                      <p>{w.text}</p>
                    </div>
                  ))}
                </div>
              </section>
              <section className="capabilities panel">
                <div className="panel-header">
                  <span className="panel-title">
                    What you can do, and what is still being built
                  </span>
                  <span className="subtle-tag">DEVELOPMENT PREVIEW</span>
                </div>
                {capabilities.map((c) => (
                  <div className="capability" key={c.id}>
                    <div>
                      <h3>{c.label}</h3>
                      <p>{c.text}</p>
                    </div>
                    <span
                      className={`capability-status ${c.status === "Still being developed" ? "development" : ""}`}
                    >
                      {c.status}
                    </span>
                  </div>
                ))}
              </section>
              <p className="evidence-source">
                These tests were recorded on 15 September 2026. This website
                shows those results and runs a separate sample cost calculation.
                It does not redesign the hospital or approve it for
                construction.
              </p>
            </>
          )}

          {page === "history" && (
            <section className="history-section">
              {history.length === 0 ? (
                <div className="empty-state">
                  <div>
                    <Clock3 size={30} />
                  </div>
                  <span className="eyebrow">A CLEAN SLATE</span>
                  <h2>No saved calculations yet.</h2>
                  <p>
                    Try different prices and purchase lengths, then save a
                    calculation here.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => go("scenarios")}
                  >
                    Try the cost calculator <ArrowRight size={16} />
                  </button>
                </div>
              ) : (
                <>
                  <div className="history-header">
                    <span>
                      {history.length} saved{" "}
                      {history.length === 1 ? "calculation" : "calculations"}
                    </span>
                    <span>Stored on this device only</span>
                  </div>
                  {history.map((h, i) => (
                    <button
                      className="history-row"
                      key={h.id}
                      onClick={() => {
                        setScenario(h.result);
                        setInputs({
                          type: h.result.type,
                          stockM: h.result.stockM,
                          price: h.result.price,
                          kerfMm: h.result.kerfMm,
                        });
                        go("scenarios");
                      }}
                    >
                      <span className="history-icon">
                        <SlidersHorizontal size={21} />
                      </span>
                      <div>
                        <strong>
                          {h.result.label} · {h.result.stockM} m purchase
                          lengths
                        </strong>
                        <p>
                          48 sample pieces · {money(h.result.price)} / m ·{" "}
                          {new Date(h.at).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })}
                        </p>
                      </div>
                      <span className="history-saving">
                        {money(h.result.savedCost)}
                        <small>sample savings</small>
                      </span>
                      <ArrowUpRight size={19} />
                    </button>
                  ))}
                </>
              )}
            </section>
          )}
          <footer className="page-footer">
            <span>
              <strong>oma.</strong> Compare the changes and the costs.
            </span>
            <span>
              OMA + ANANKE <i /> Interactive product demo
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          {toast}
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {dialog === "guide" && (
        <Dialog
          title="Try these four things."
          eyebrow="WELCOME TO OMA"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            See a pipe-route test, try a sample cost calculation, or look inside
            the example building.
          </p>
          <div className="guide-steps">
            {[
              [
                "01",
                "Explore the building",
                "Drag to rotate the example building. Choose a floor or turn pipes and cables on and off.",
              ],
              [
                "02",
                "Try the cost calculator",
                "Enter a price and choose a purchase length. See the bill for two ways of cutting the same 48 pieces.",
              ],
              [
                "03",
                "See what was tested",
                "Compare the two pipe routes and see the checks that were run.",
              ],
              [
                "04",
                "Download the results",
                "Get the numbers and cutting list. Your saved calculations stay in this browser.",
              ],
            ].map(([i, t, b]) => (
              <div key={i}>
                <span>{i}</span>
                <div>
                  <h3>{t}</h3>
                  <p>{b}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="dialog-notice">
            The pipe test is a recorded result. The building view and cost
            calculator use examples. The demo does not approve a design for
            construction.
          </div>
          <button
            className="button primary full"
            onClick={() => setDialog(null)}
          >
            Start exploring <ArrowRight size={16} />
          </button>
        </Dialog>
      )}
      {dialog === "discipline" && discipline && (
        <Dialog
          title={discipline.label}
          eyebrow="WHAT IS IN THIS BUILDING FILE"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">{discipline.detail}</p>
          <div className="detail-metrics">
            {[
              ["File entries", discipline.products],
              ["Parts to review", discipline.objects],
              ["Connected groups or single parts", discipline.components],
              ["Connections", discipline.connections],
            ].map(([k, v]) => (
              <div key={k}>
                <span>{k}</span>
                <strong>{n(v)}</strong>
              </div>
            ))}
          </div>
          <div className="detail-info">
            <h3>What the file contains</h3>
            <p>
              {n(discipline.ports)} connection points · {n(discipline.systems)}{" "}
              systems · {n(discipline.objectsWithoutPorts)} parts with no
              connection points listed.
            </p>
            <h3>What an engineer still needs</h3>
            <p>{discipline.designInput}.</p>
          </div>
          <div className="dialog-notice">
            These numbers show what is in the file. An engineer still needs to
            check whether the system will work for this building.
          </div>
        </Dialog>
      )}
      {dialog === "route" && (
        <Dialog
          title="From five fittings to one."
          eyebrow="PIPE TEST · SMALL EXAMPLE"
          wide
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            Two possible pipe routes were tested in the hospital’s architectural
            model. The shorter option uses four fewer fittings. This was a small
            route test, not a whole-building redesign.
          </p>
          <div className="route-visuals">
            <div>
              <span>FIRST ROUTE OPTION</span>
              <svg
                viewBox="0 0 300 100"
                role="img"
                aria-label="Schematic indirect route"
              >
                <path
                  d="M25 65H85V30H165V65H260"
                  fill="none"
                  stroke="#a7aea7"
                  strokeWidth="7"
                  strokeLinejoin="round"
                />
                <circle cx="25" cy="65" r="7" fill="#4c6657" />
                <circle cx="260" cy="65" r="7" fill="#4c6657" />
              </svg>
              <strong>
                5.785 m <small>5 fittings</small>
              </strong>
            </div>
            <div>
              <span>SHORTER ROUTE OPTION</span>
              <svg
                viewBox="0 0 300 100"
                role="img"
                aria-label="Schematic direct route"
              >
                <path
                  d="M25 65H260"
                  fill="none"
                  stroke="#3d7159"
                  strokeWidth="7"
                />
                <circle cx="25" cy="65" r="7" fill="#294d3c" />
                <circle cx="260" cy="65" r="7" fill="#294d3c" />
              </svg>
              <strong>
                5.000 m <small>1 fitting</small>
              </strong>
            </div>
          </div>
          <p className="figure-caption">
            Simple sketches showing the idea, not construction drawings.
          </p>
          <div className="route-metrics">
            <div>
              <strong>13.6%</strong>
              <span>Shorter pipe route</span>
            </div>
            <div>
              <strong>80%</strong>
              <span>Fewer fittings</span>
            </div>
            <div>
              <strong>4.625 m</strong>
              <span>Straight pipe needed in both</span>
            </div>
          </div>
          <div className="route-checks">
            {routeComparison.checks.map((c) => (
              <div key={c.label}>
                <CheckCircle2 size={18} />
                <div>
                  <strong>{c.label}</strong>
                  <span>{c.note}</span>
                </div>
                <span>Passed</span>
              </div>
            ))}
          </div>
          <div className="dialog-notice">
            <strong>What these numbers cover</strong>
            <p>{routeComparison.scopeNote}</p>
            <p>{routeComparison.costNote}</p>
            <p>
              The test uses stated pipe dimensions, flow rates and resistance
              values. Those assumptions still need to match the real
              installation; these checks are not construction approval.
            </p>
          </div>
          <button
            className="button primary"
            onClick={() => {
              download(routeComparison, "oma-recorded-route-study.json");
              setToast("Routing study downloaded");
            }}
          >
            <Download size={16} />
            Download this study
          </button>
        </Dialog>
      )}
      {dialog === "import" && (
        <Dialog
          title="Open a building design file."
          eyebrow="YOUR FILE STAYS ON THIS DEVICE"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            IFC is a file format for sharing 3D building designs. Open one to
            see its version and the types of records it contains. Your file is
            never uploaded.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".ifc"
            className="sr-only"
            tabIndex={-1}
            onChange={(e) => inspectFile(e.target.files?.[0])}
          />
          <button
            className="drop-zone"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              inspectFile(e.dataTransfer.files?.[0]);
            }}
          >
            <Upload size={25} />
            <strong>
              {reading ? "Reading local file…" : "Drop an IFC file here"}
            </strong>
            <span>or click to browse · .ifc · up to 25 MB</span>
          </button>
          {ifcError && (
            <p className="form-error" role="alert">
              {ifcError}
            </p>
          )}
          {ifc && (
            <div className="file-result">
              <div>
                <FileText size={21} />
                <strong>{ifc.filename}</strong>
                <span>{ifc.schema}</span>
              </div>
              <p>
                <strong>{n(ifc.records)}</strong> file records ·{" "}
                {ifc.classes.length} record types
              </p>
              <ul>
                {ifc.classes.slice(0, 5).map(([key, count]) => (
                  <li key={key}>
                    <span>{key}</span>
                    <strong>{n(count)}</strong>
                  </li>
                ))}
              </ul>
              <button
                className="text-button"
                onClick={() => download(ifc, "oma-local-ifc-inspection.json")}
              >
                Download file summary <Download size={16} />
              </button>
            </div>
          )}
          <div className="dialog-notice">
            This tool reads and counts records. It does not display your
            building, check its shape, or test its engineering.
          </div>
        </Dialog>
      )}
    </div>
  );
}
