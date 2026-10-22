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
  { id: "hvac", label: "HVAC", color: "#2e8b79", icon: Wind },
  { id: "plumbing", label: "Plumbing", color: "#447eaf", icon: Droplets },
  { id: "electrical", label: "Electrical", color: "#b98632", icon: Cable },
  { id: "fire", label: "Sprinklers", color: "#be675d", icon: Flame },
];
const nav = [
  { id: "overview", label: "Project overview", icon: Box },
  { id: "scenarios", label: "Scenario lab", icon: SlidersHorizontal },
  { id: "evidence", label: "Evidence & checks", icon: ClipboardIcon },
  { id: "history", label: "Saved scenarios", icon: Clock3 },
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
        setToast("Scenario calculated · all 48 pieces accounted for");
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
      setToast("Scenario saved in this browser");
    } catch {
      setToast(
        "Scenario saved for this session; browser storage is unavailable",
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
            ANANKE workspace<small>Customer preview</small>
          </div>
          <span className="preview-dot" />
        </div>
        <p className="nav-label">WORKSPACE</p>
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
        <p className="nav-label">REFERENCE PROJECT</p>
        <button className="project-link" onClick={() => go("overview")}>
          <Building2 size={17} />
          <span>
            Hospital<small>Healthcare · 7 source models</small>
          </span>
        </button>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="tiny-label">BUILT TO BE INSPECTED</span>
            <p>
              Better decisions.
              <br />A clear trail of evidence.
            </p>
            <button onClick={() => go("evidence")}>
              See the methodology <ArrowUpRight size={15} />
            </button>
          </div>
          <button className="help-button" onClick={() => setDialog("guide")}>
            <CircleHelp size={17} /> Demo guide <span>?</span>
          </button>
          <div className="sidebar-foot">
            <span className="user-avatar">G</span>
            <div>
              Guest workspace<small>Interactive demo</small>
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
                  ? "BUILDING INTELLIGENCE"
                  : page === "scenarios"
                    ? "MAKE THE TRADE-OFFS TANGIBLE"
                    : page === "evidence"
                      ? "TRACE EVERY CLAIM"
                      : "YOUR WORKSPACE"}
              </div>
              <h1>
                {page === "overview"
                  ? "See the whole picture."
                  : page === "scenarios"
                    ? "Less waste. Same requirements."
                    : page === "evidence"
                      ? "Confidence has a paper trail."
                      : "Pick up where you left off."}
              </h1>
              <p>
                {page === "overview"
                  ? "Every discipline. One building. A clearer way forward."
                  : page === "scenarios"
                    ? "Change the inputs. Compare the plan. Keep every required piece."
                    : page === "evidence"
                      ? "Recorded results, explicit assumptions, and a result you can inspect."
                      : "Your sample calculations, saved locally in this browser."}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                onClick={() => setDialog("import")}
              >
                <Upload size={16} /> Inspect IFC
              </button>
              <button className="button primary" onClick={report}>
                <Download size={16} /> Export report
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
                    <strong>Hospital reference project</strong>
                    <span>
                      Healthcare <i /> IFC4 federation <i /> Recorded study
                    </span>
                  </div>
                </div>
                <Pill>Inventory reconciled</Pill>
              </div>
              <section
                className="metrics"
                aria-label="Hospital inventory totals"
              >
                {[
                  ["149,822", "IFC products", "Across all source models"],
                  ["45,946", "Service objects", "Five MEP source models"],
                  [
                    "42,801",
                    "Explicit connections",
                    "Reconciled against source",
                  ],
                  ["7", "Source models", "Architecture through fire alarm"],
                ].map(([value, label, note], i) => (
                  <div className="metric" key={label}>
                    <div className="metric-label">
                      {label}
                      <span>0{i + 1}</span>
                    </div>
                    <div className="metric-value">{value}</div>
                    <small>{note}</small>
                  </div>
                ))}
              </section>
              <div className="workspace-grid">
                <section
                  className={`viewer-card ${fullscreen ? "expanded" : ""}`}
                  aria-label="Interactive building viewer"
                >
                  <div className="panel-header">
                    <div>
                      <span className="panel-title">Building explorer</span>
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
                      <span>HOSPITAL / STUDY MODEL</span>
                      <small>Illustrative geometry</small>
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
                      10 m <small>schematic</small>
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
                      Illustrative model · not source IFC geometry
                    </span>
                    <span>Drag to orbit · Scroll to zoom</span>
                  </div>
                </section>
                <aside className="insights">
                  <div className="insight-header">
                    <span className="eyebrow">A CLOSER LOOK</span>
                    <span className="round-arrow">
                      <ArrowUpRight size={18} />
                    </span>
                  </div>
                  <h2>
                    From complexity
                    <br />
                    to a clear decision.
                  </h2>
                  <p className="insight-intro">
                    Explore a checked route study, then test a purchasing
                    scenario yourself.
                  </p>
                  <button
                    className="opportunity"
                    onClick={() => setDialog("route")}
                  >
                    <div className="opportunity-top">
                      <span className="tiny-label">RECORDED ROUTING STUDY</span>
                      <ArrowUpRight size={18} />
                    </div>
                    <div className="opportunity-number">
                      13.6<span>%</span>
                      <span className="decrease">↘</span>
                    </div>
                    <h3>Shorter route. Fewer fittings.</h3>
                    <p>
                      A two-terminal comparison checked against 14,409
                      architectural obstacles.
                    </p>
                    <div className="opportunity-foot">
                      <span>View the comparison</span>
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
                      <strong>What could less waste look like?</strong>
                      <span>Try an interactive stock-cutting example.</span>
                    </div>
                    <ChevronRight size={18} />
                  </button>
                  <div className="evidence-note">
                    <CheckCircle2 size={17} />
                    <p>
                      Evidence first.
                      <br />
                      <span>
                        Recorded inventory. Explicit assumptions. No hidden
                        savings claims.
                      </span>
                    </p>
                  </div>
                </aside>
              </div>
              <section className="discipline-section">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">THE FULL PROJECT</span>
                    <h2>Every discipline, accounted for.</h2>
                  </div>
                  <span className="table-subtitle">
                    Retained source inventory · 15 Sep 2026
                  </span>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Source discipline</th>
                        <th>IFC products</th>
                        <th>Service objects / candidates</th>
                        <th>Explicit connections</th>
                        <th>Inventory status</th>
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
                  Service inventory includes 45,946 service-class objects and
                  1,770 unresolved architectural candidates. Counts do not imply
                  design approval.
                </div>
              </section>
              <div className="bottom-cta">
                <div>
                  <span className="eyebrow">
                    LESS GUESSWORK. MORE VISIBILITY.
                  </span>
                  <h2>Take a scenario for a test drive.</h2>
                </div>
                <button
                  className="button primary"
                  onClick={() => go("scenarios")}
                >
                  Open scenario lab <ArrowRight size={16} />
                </button>
              </div>
            </>
          )}

          {page === "scenarios" && (
            <>
              <div className="context-banner">
                <span className="sample-tag">SAMPLE DATA</span>
                <p>
                  A working stock-cutting calculation with 48 illustrative
                  pieces. These are not the hospital’s quantities or prices.
                </p>
              </div>
              <div className="scenario-grid">
                <section className="scenario-inputs panel">
                  <div className="panel-header">
                    <span className="panel-title">Define your scenario</span>
                    <SlidersHorizontal size={18} />
                  </div>
                  <div className="input-body">
                    <label>
                      Service type
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
                      <legend>Available stock length</legend>
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
                      Assumed material price <span>USD / metre</span>
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
                      Cutting allowance
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
                        <span>Purchasing batches</span>
                        <strong>12</strong>
                      </div>
                      <div>
                        <span>Required length</span>
                        <strong>{scenario.requiredM.toFixed(2)} m</strong>
                      </div>
                      <div>
                        <span>Piece dimensions</span>
                        <strong>Preserved</strong>
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
                      {running ? "Calculating…" : "Calculate scenario"}
                    </button>
                    {scenarioError && (
                      <p className="form-error" role="alert">
                        {scenarioError}
                      </p>
                    )}
                    <p className="input-note">
                      Calculated in your browser. Prices are editable
                      assumptions, not supplier quotes.
                    </p>
                  </div>
                </section>
                <section className="scenario-results">
                  <div className="result-heading">
                    <div>
                      <span className="eyebrow">
                        {scenarioDirty
                          ? "INPUTS CHANGED · RECALCULATE TO UPDATE"
                          : "CALCULATED SAMPLE RESULT"}
                      </span>
                      <h2>A better plan for the same pieces.</h2>
                    </div>
                    <Pill neutral={scenarioDirty}>
                      {scenarioDirty
                        ? "Previous calculation"
                        : "48 / 48 pieces checked"}
                    </Pill>
                  </div>
                  <div className="saving-summary">
                    <div>
                      <span>Illustrative material difference</span>
                      <strong>
                        {money(scenario.savedCost)}
                        <small>less stock spend</small>
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
                        SEPARATE BATCH PURCHASING
                      </span>
                      <strong>
                        {scenario.baseline.purchasedM.toFixed(0)}
                        <small> m</small>
                      </strong>
                      <p>
                        {scenario.baseline.bars} stock lengths <i />{" "}
                        {money(scenario.baseline.cost)}
                      </p>
                      <div className="comparison-bar">
                        <span style={{ width: "100%" }} />
                      </div>
                    </div>
                    <div className="after">
                      <span className="tiny-label">POOLED CUTTING PLAN</span>
                      <strong>
                        {scenario.selected.purchasedM.toFixed(0)}
                        <small> m</small>
                      </strong>
                      <p>
                        {scenario.selected.bars} stock lengths <i />{" "}
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
                      <h3>Inside the cutting plan</h3>
                      <span>
                        First {Math.min(6, scenario.after.length)} of{" "}
                        {scenario.after.length} stock lengths
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
                        Remaining offcut
                      </span>
                      <span>{scenario.kerfMm} mm cut allowance included</span>
                    </div>
                  </div>
                  <div className="result-actions">
                    <button className="button secondary" onClick={saveScenario}>
                      <Plus size={16} />
                      Save scenario
                    </button>
                    <button
                      className="text-button"
                      onClick={() => {
                        download(scenario, "oma-sample-cutting-plan.json");
                        setToast("Complete cutting plan downloaded");
                      }}
                    >
                      Download all cuts <Download size={16} />
                    </button>
                  </div>
                  <p className="scenario-scope">
                    Comparison: first-fit cutting within each batch versus
                    pooled best-fit cutting. Same pieces and allowances in both
                    plans. Feasible heuristic, not a global optimum. Material
                    only; excludes labor, connections and delivery. No installed
                    geometry is changed.
                  </p>
                </section>
              </div>
            </>
          )}

          {page === "evidence" && (
            <>
              <div className="evidence-hero">
                <div>
                  <span className="eyebrow">RETAINED ENGINE RESULTS</span>
                  <h2>
                    A result is only as useful
                    <br />
                    as the evidence behind it.
                  </h2>
                  <p>
                    OMA separates what was counted, what was calculated, and
                    what was independently checked. Explore those boundaries
                    here.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => setDialog("route")}
                  >
                    Inspect routing comparison <ArrowRight size={16} />
                  </button>
                </div>
                <div className="evidence-stats">
                  <div>
                    <strong>
                      7<span>/7</span>
                    </strong>
                    <span>Source models reconciled</span>
                  </div>
                  <div>
                    <strong>3,426</strong>
                    <span>Passing tests on the retained inventory build</span>
                  </div>
                  <div>
                    <strong>0</strong>
                    <span>Original source files changed</span>
                  </div>
                </div>
              </div>
              <section className="workflow">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">THE WORKFLOW</span>
                    <h2>Each decision has a next check.</h2>
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
                  <span className="panel-title">What this demo represents</span>
                  <span className="subtle-tag">DEVELOPMENT PREVIEW</span>
                </div>
                {capabilities.map((c) => (
                  <div className="capability" key={c.id}>
                    <div>
                      <h3>{c.label}</h3>
                      <p>{c.text}</p>
                    </div>
                    <span
                      className={`capability-status ${c.status === "In development" ? "development" : ""}`}
                    >
                      {c.status}
                    </span>
                  </div>
                ))}
              </section>
              <p className="evidence-source">
                Evidence recorded 15 September 2026. Interactive visuals and the
                scenario lab are browser demonstrations; they do not invoke the
                engineering backend. Full installed-system redesign and
                construction approval are not demonstrated.
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
                  <h2>Your next decision starts here.</h2>
                  <p>
                    Calculate a sample scenario and save it to compare your
                    options later.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => go("scenarios")}
                  >
                    Create a scenario <ArrowRight size={16} />
                  </button>
                </div>
              ) : (
                <>
                  <div className="history-header">
                    <span>
                      {history.length} saved{" "}
                      {history.length === 1 ? "scenario" : "scenarios"}
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
                          {h.result.label} · {h.result.stockM} m stock
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
                        <small>illustrative difference</small>
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
              <strong>oma.</strong> Built for the decisions that matter.
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
          title="A few good places to start."
          eyebrow="WELCOME TO OMA"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            A hands-on introduction to building-system decisions. No account
            required.
          </p>
          <div className="guide-steps">
            {[
              [
                "01",
                "Explore the building",
                "Orbit the illustrative model, isolate a floor, and toggle individual systems.",
              ],
              [
                "02",
                "Try the scenario lab",
                "Change stock lengths and material prices. A local solver computes a real cut plan for the sample pieces.",
              ],
              [
                "03",
                "Inspect the evidence",
                "Open the recorded route comparison and review what was independently checked.",
              ],
              [
                "04",
                "Take the work with you",
                "Download a report or cutting plan. Saved scenarios stay in this browser.",
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
            This customer demo uses retained project evidence and clearly
            labeled examples. It is not a live engineering service or
            construction approval.
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
          eyebrow="SOURCE INVENTORY"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">{discipline.detail}</p>
          <div className="detail-metrics">
            {[
              ["IFC products", discipline.products],
              ["Objects / candidates", discipline.objects],
              ["Components", discipline.components],
              ["Connections", discipline.connections],
            ].map(([k, v]) => (
              <div key={k}>
                <span>{k}</span>
                <strong>{n(v)}</strong>
              </div>
            ))}
          </div>
          <div className="detail-info">
            <h3>What the source tells us</h3>
            <p>
              {n(discipline.ports)} authored ports · {n(discipline.systems)}{" "}
              systems · {n(discipline.objectsWithoutPorts)} objects without
              ports.
            </p>
            <h3>Inputs for the next design step</h3>
            <p>{discipline.designInput}.</p>
          </div>
          <div className="dialog-notice">
            Inventory reconciliation confirms source accounting. It does not
            establish system performance or design approval.
          </div>
        </Dialog>
      )}
      {dialog === "route" && (
        <Dialog
          title="A simpler route. A checked result."
          eyebrow="RECORDED TWO-TERMINAL STUDY"
          wide
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            Two generated alternatives, compared against 14,409 architectural
            obstacles.
          </p>
          <div className="route-visuals">
            <div>
              <span>ALTERNATIVE A</span>
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
              <span>SELECTED ALTERNATIVE</span>
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
            Concept sketches, not exported route geometry.
          </p>
          <div className="route-metrics">
            <div>
              <strong>13.6%</strong>
              <span>Less centerline length</span>
            </div>
            <div>
              <strong>80%</strong>
              <span>Fewer fittings</span>
            </div>
            <div>
              <strong>4.625 m</strong>
              <span>Same straight stock in both</span>
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
            <strong>Scope of this result</strong>
            <p>{routeComparison.scopeNote}</p>
            <p>{routeComparison.costNote}</p>
            <p>
              Checks assume prescribed flow, ideal bore and declared loss
              coefficients. They are not an unrestricted system or structural
              approval.
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
          title="Take a look inside your IFC."
          eyebrow="LOCAL FILE INSPECTOR"
          close={() => setDialog(null)}
        >
          <p className="dialog-intro">
            Check a file’s schema and entity counts. Your file stays in this
            browser and is never uploaded.
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
                <strong>{n(ifc.records)}</strong> STEP entity records ·{" "}
                {ifc.classes.length} entity classes
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
                Download inspection <Download size={16} />
              </button>
            </div>
          )}
          <div className="dialog-notice">
            A lightweight record scan, not a semantic IFC import or geometry
            validation. The Hospital reference project and illustrative viewer
            remain unchanged.
          </div>
        </Dialog>
      )}
    </div>
  );
}
