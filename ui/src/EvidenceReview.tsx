import { useEffect, useMemo, useState } from "react";
import {
  Download,
  GitBranch,
  RefreshCw,
  Search,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { api, type StateSelection } from "./api";
import ValidationAdvisories from "./ValidationAdvisories";
import NetworkServiceEvidence from "./NetworkServiceEvidence";
import type { AssuranceRecord, Candidate, DependencyRecord } from "./types";

export interface EvidenceTarget {
  projectId: string;
  root: string;
  revision?: number;
  candidate?: Candidate;
  initialTab?: "assurance" | "dependencies";
}
const text = (v: unknown): string =>
  typeof v === "string" ? v : (JSON.stringify(v, null, 2) ?? "Not reported");
const label = (v: string) => v.replaceAll("_", " ");

function Statement({ value }: { value: string }) {
  let parsed: Record<string, unknown> | null = null;
  try {
    const result: unknown = JSON.parse(value);
    if (result && typeof result === "object" && !Array.isArray(result))
      parsed = result as Record<string, unknown>;
  } catch {
    /* Ordinary prose is already readable. */
  }
  if (!parsed) return <p>{value}</p>;
  if (
    parsed.kind === "explicit_scenario" &&
    parsed.data &&
    typeof parsed.data === "object"
  ) {
    const scenario = parsed.data as Record<string, unknown>;
    return (
      <div className="condition-statement">
        <p>
          <strong>Explicit scenario inputs</strong> ·{" "}
          {label(String(scenario.system_type ?? "service not reported"))}
        </p>
        {Array.isArray(scenario.assumptions) && (
          <ul>
            {scenario.assumptions.map((item, i) => (
              <li key={i}>{text(item)}</li>
            ))}
          </ul>
        )}
        <p>
          Source representation:{" "}
          {label(
            String(scenario.source_representation_policy ?? "not reported"),
          )}
          .
        </p>
        <JsonDetail
          value={parsed}
          title="Complete declared scenario and provenance"
        />
      </div>
    );
  }
  if (typeof parsed.source_representation_policy === "string")
    return (
      <p>
        Source representation policy:{" "}
        <strong>{label(parsed.source_representation_policy)}</strong>.
      </p>
    );
  return (
    <JsonDetail
      value={parsed}
      title={
        parsed.physical_model_inputs
          ? "Declared physical model inputs and source"
          : "Structured declared condition"
      }
    />
  );
}

function JsonDetail({
  value,
  title = "Complete record",
}: {
  value: unknown;
  title?: string;
}) {
  return (
    <details className="evidence-json">
      <summary>{title}</summary>
      <pre>{text(value)}</pre>
    </details>
  );
}
function ListDetail({
  title,
  values,
  descriptions,
}: {
  title: string;
  values: string[];
  descriptions?: Map<string, string>;
}) {
  return (
    <details className="evidence-list-detail">
      <summary>
        {title}
        <span>{values.length}</span>
      </summary>
      {values.length ? (
        <ul>
          {values.map((value, i) => (
            <li key={`${value}:${i}`}>
              <Statement value={descriptions?.get(value) ?? value} />
              {descriptions?.has(value) && <small>{value}</small>}
            </li>
          ))}
        </ul>
      ) : (
        <p>No entries reported.</p>
      )}
    </details>
  );
}
function AssuranceView({ data }: { data: AssuranceRecord }) {
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(40);
  const assumptions = data.assumption_ledger ?? [];
  const dispositions = useMemo(
    () =>
      (data.dispositions ?? []).filter((row) =>
        text(row).toLowerCase().includes(search.toLowerCase()),
      ),
    [data, search],
  );
  const descriptions = new Map(
    (data.theory?.foundations ?? []).map((f) => [f.id, f.description]),
  );
  const excluded = Object.entries(data.certificate?.excluded_foundations ?? {});
  const changedContext = Object.keys(data.assessment_context ?? {}).filter(
    (key) =>
      text(data.assessment_context?.[key]) !==
      text(data.recorded_context?.[key]),
  );
  return (
    <>
      <ValidationAdvisories advisories={data.validation_advisories} />
      <div className="assurance-summary">
        <ShieldCheck size={26} />
        <div>
          <span className="eyebrow">CONDITIONAL EVIDENCE SUPPORT</span>
          <h3>{label(data.support_status)}</h3>
          <p>{data.scope ?? data.reason ?? "No scope reported."}</p>
        </div>
      </div>
      <div className="evidence-metrics">
        <div>
          <span>Recorded engineering verdict</span>
          <strong>{data.recorded_engineering_status ?? "NOT REPORTED"}</strong>
        </div>
        <div>
          <span>Assurance derivation check</span>
          <strong>
            {data.independent_assurance_check?.status ?? "NOT RUN"}
          </strong>
        </div>
        <div>
          <span>Fresh physical recheck</span>
          <strong>{label(data.fresh_physical_recheck ?? "NOT_RUN")}</strong>
        </div>
      </div>
      <p className="evidence-explanation">
        This query evaluates support for the recorded scope under its listed
        conditions. It does not rerun geometry or simulation, and does not
        establish whole-building certification or global optimality.
      </p>
      <div className="evidence-caution">
        <TriangleAlert size={17} />
        <div>
          <strong>
            External artifact bytes are not rehashed by this evidence query.
          </strong>
          <p>
            Authenticity and recorded support do not establish the technical
            truth of assumptions.
          </p>
        </div>
      </div>
      {data.independent_assurance_check?.reason && (
        <p className="evidence-explanation">
          Assurance check: {data.independent_assurance_check.reason}
        </p>
      )}
      {!!changedContext.length && (
        <div className="evidence-caution">
          <TriangleAlert size={17} />
          <div>
            <strong>Recorded and current contexts differ.</strong>
            <p>
              {changedContext.map(label).join(", ")}. The historical verdict is
              retained; excluded evidence cannot support this current context.
            </p>
          </div>
        </div>
      )}
      <details className="evidence-list-detail" open={excluded.length > 0}>
        <summary>
          Excluded foundations and applicability reasons
          <span>{excluded.length}</span>
        </summary>
        {excluded.length ? (
          <ul>
            {excluded.map(([id, reason]) => (
              <li key={id}>
                <strong>{label(reason)}</strong>
                <Statement value={descriptions.get(id) ?? id} />
                <small>{id}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>
            No foundations were excluded by the reported applicability
            assessment.
          </p>
        )}
      </details>
      <section className="evidence-section">
        <div className="evidence-section-title">
          <h4>Assumptions and trusted implementation</h4>
          <span>{assumptions.length} conditions</span>
        </div>
        <p className="evidence-explanation">
          Each item is a declared condition. TCB identifies implementation or
          checking policy that the result trusts.
        </p>
        {assumptions.length ? (
          <div className="assumption-ledger">
            {assumptions.map((item) => (
              <article key={item.id}>
                <span className="evidence-kind">{item.kind}</span>
                <Statement value={item.statement} />
                <small>
                  {label(item.status)} ·{" "}
                  {label(item.technical_truth ?? "NOT_ESTABLISHED")}
                </small>
              </article>
            ))}
          </div>
        ) : (
          <p className="evidence-explanation">
            No assumption ledger was returned.
          </p>
        )}
      </section>
      <section className="evidence-section">
        <div className="evidence-section-title">
          <h4>Recorded dispositions</h4>
          <span>{dispositions.length} matching</span>
        </div>
        <label className="evidence-search">
          <Search size={14} />
          <input
            aria-label="Filter assurance dispositions"
            placeholder="Find a check, status, scope, or reason"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setLimit(40);
            }}
          />
        </label>
        <div className="disposition-list">
          {dispositions.slice(0, limit).map((row, i) => (
            <details key={`${row.id}:${i}`}>
              <summary>
                <span
                  className={`disposition-status ${row.status === "FAIL" ? "failed" : ""}`}
                >
                  {row.status}
                </span>
                <strong>{row.id}</strong>
              </summary>
              <p>{row.reason}</p>
              <small>Scope: {row.scope}</small>
              {row.id === "network-demand-conditioned-service" && (
                <NetworkServiceEvidence witness={row.witness} />
              )}
              <JsonDetail value={row} title="Numerical and model evidence" />
            </details>
          ))}
        </div>
        {limit < dispositions.length && (
          <button className="secondary" onClick={() => setLimit((n) => n + 40)}>
            Show next {Math.min(40, dispositions.length - limit)} dispositions
          </button>
        )}
      </section>
      <section className="evidence-section">
        <h4>Support cores</h4>
        <p className="evidence-explanation">
          Each returned core is a set of foundations supporting the declared
          target under the supplied theory. Completeness:{" "}
          {data.certificate?.complete === true
            ? "established by the assurance checker"
            : "not established"}
          .
        </p>
        {data.certificate?.cores?.length ? (
          data.certificate.cores.map((core, i) => (
            <ListDetail
              key={i}
              title={`Core ${i + 1}`}
              values={core}
              descriptions={descriptions}
            />
          ))
        ) : (
          <p className="evidence-explanation">
            No supporting core was returned.
          </p>
        )}
      </section>
      <section className="evidence-section">
        <h4>External evidence cuts</h4>
        <p className="evidence-explanation">
          A reported cut identifies evidence whose revocation disables every
          currently grounded target proof. Resolving a cut does not guarantee a
          successful repair.
        </p>
        <p className="evidence-explanation">
          Reported cut status:{" "}
          {label(data.external_evidence_cuts?.status ?? "NOT_RUN")}.
        </p>
        {data.external_evidence_cuts?.cuts?.map((cut, i) => (
          <ListDetail
            key={i}
            title={`Cut ${i + 1}`}
            values={cut}
            descriptions={descriptions}
          />
        ))}
        <JsonDetail
          value={data.external_evidence_cuts}
          title="Cut interpretation and scope"
        />
      </section>
      <JsonDetail
        value={{
          current: data.assessment_context,
          recorded: data.recorded_context,
        }}
        title="Current and recorded context bindings"
      />
    </>
  );
}

function DependencyView({ data }: { data: DependencyRecord }) {
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(40);
  const nodes = Object.entries(data.dependencies).filter(([id, inputs]) =>
    `${id} ${inputs.join(" ")}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="assurance-summary dependency-summary">
        <GitBranch size={26} />
        <div>
          <span className="eyebrow">ACTUAL REVISION DERIVATION</span>
          <h3>
            {data.cold_equivalent
              ? "Incremental result matches cold derivation"
              : "Cold equivalence not established"}
          </h3>
          <p>{data.scope}</p>
        </div>
      </div>
      <div className="evidence-metrics">
        <div>
          <span>Authoritative inputs changed</span>
          <strong>{data.changed_authoritative_inputs.length}</strong>
        </div>
        <div>
          <span>Artifacts recomputed</span>
          <strong>{data.recomputed.length}</strong>
        </div>
        <div>
          <span>Artifacts reused</span>
          <strong>{data.reused.length}</strong>
        </div>
      </div>
      <p className="evidence-explanation">
        This compares derived inventory, declared connectivity, mission
        coverage, applicability, and input fingerprints. Physical checks reused
        across roots:{" "}
        <strong>
          {data.physical_checks_reused_across_roots === true
            ? "reported by engine — inspect scope"
            : "none"}
        </strong>
        . Native geometry and simulation require their separate checker
        operation.
      </p>
      <div className="dependency-lists">
        <ListDetail
          title="Changed authoritative inputs"
          values={data.changed_authoritative_inputs}
        />
        <ListDetail
          title="Conservatively affected outputs"
          values={data.conservatively_affected}
        />
        <ListDetail
          title="Semantic output changes"
          values={data.semantic_output_changes}
        />
        <ListDetail title="Recomputed artifacts" values={data.recomputed} />
        <ListDetail title="Reused artifacts" values={data.reused} />
      </div>
      <section className="evidence-section">
        <div className="evidence-section-title">
          <h4>Dependency graph and actual outputs</h4>
          <span>{nodes.length} matching nodes</span>
        </div>
        <label className="evidence-search">
          <Search size={14} />
          <input
            aria-label="Filter dependency nodes"
            placeholder="Find an output or authoritative input"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setLimit(40);
            }}
          />
        </label>
        <div className="dependency-nodes">
          {nodes.slice(0, limit).map(([id, inputs]) => (
            <details key={id}>
              <summary>
                <GitBranch size={14} />
                <strong>{id}</strong>
                <span>
                  {data.reused.includes(id)
                    ? "reused"
                    : data.recomputed.includes(id)
                      ? "recomputed"
                      : "reported"}
                </span>
              </summary>
              <ListDetail title="Declared input dependencies" values={inputs} />
              <JsonDetail
                value={data.artifacts[id]}
                title="Derived output and provenance"
              />
            </details>
          ))}
        </div>
        {limit < nodes.length && (
          <button className="secondary" onClick={() => setLimit((n) => n + 40)}>
            Show next {Math.min(40, nodes.length - limit)} nodes
          </button>
        )}
      </section>
      <JsonDetail
        value={{
          before_root: data.before_root,
          after_root: data.after_root,
          incremental_root: data.incremental_root,
          cold_root: data.cold_root,
          input_roots: data.input_roots,
          elapsed_seconds: data.elapsed_seconds,
        }}
        title="Revision roots, input fingerprints, and measured derivation time"
      />
    </>
  );
}

export default function EvidenceReview({ target }: { target: EvidenceTarget }) {
  const [tab, setTab] = useState(
    target.initialTab ?? (target.candidate ? "assurance" : "dependencies"),
  );
  const [result, setResult] = useState<{
    key: string;
    data: AssuranceRecord | DependencyRecord;
  } | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [cancelled, setCancelled] = useState(false);
  const [abort, setAbort] = useState<AbortController | null>(null);
  const key = `${target.projectId}:${target.root}:${target.candidate?.id ?? target.revision}:${tab}:${retry}`;
  const data = result?.key === key ? result.data : null;
  useEffect(() => {
    const controller = new AbortController();
    setAbort(controller);
    setError("");
    setCancelled(false);
    const selection: StateSelection = target.candidate
      ? { candidate_id: target.candidate.id }
      : { revision: target.revision };
    const query =
      tab === "assurance" && target.candidate
        ? api.assurance(
            target.projectId,
            target.candidate.id,
            target.root,
            controller.signal,
          )
        : api.dependencies(
            target.projectId,
            selection,
            target.root,
            controller.signal,
          );
    void query
      .then((value) => {
        if (!controller.signal.aborted) setResult({ key, data: value });
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError((cause as Error).message);
      });
    return () => controller.abort();
  }, [key, tab, target]);
  return (
    <div className="evidence-review">
      <div
        className="evidence-review-tabs"
        role="tablist"
        aria-label="Engineering evidence sections"
      >
        <button
          role="tab"
          aria-selected={tab === "assurance"}
          disabled={!target.candidate}
          onClick={() => setTab("assurance")}
        >
          <ShieldCheck size={15} />
          Evidence support
        </button>
        <button
          role="tab"
          aria-selected={tab === "dependencies"}
          onClick={() => setTab("dependencies")}
        >
          <GitBranch size={15} />
          Dependencies
        </button>
      </div>
      <p className="evidence-target">
        {target.candidate
          ? `Candidate ${target.candidate.id.slice(0, 12)}`
          : `Revision ${target.revision}`}{" "}
        · root <code title={target.root}>{target.root.slice(0, 12)}…</code>
      </p>
      {target.candidate && (
        <JsonDetail
          value={target.candidate}
          title="Original candidate record and historical verdict"
        />
      )}
      {data ? (
        <>
          <div
            role="tabpanel"
            aria-label={
              tab === "assurance" ? "Evidence support" : "Dependencies"
            }
          >
            {tab === "assurance" ? (
              <AssuranceView data={data as AssuranceRecord} />
            ) : (
              <DependencyView data={data as DependencyRecord} />
            )}
          </div>
          <JsonDetail value={data} />
          <button
            className="secondary"
            onClick={() => {
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(data, null, 2)], {
                  type: "application/json",
                }),
              );
              const link = document.createElement("a");
              link.href = url;
              link.download = `oma-${tab}-${target.root.slice(0, 12)}.json`;
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}
          >
            <Download size={14} />
            Download evidence JSON
          </button>
        </>
      ) : error ? (
        <div className="evidence-query-state" role="alert">
          <TriangleAlert size={24} />
          <strong>Evidence query unavailable</strong>
          <p>{error}</p>
          <button className="secondary" onClick={() => setRetry((n) => n + 1)}>
            <RefreshCw size={14} />
            Retry query
          </button>
        </div>
      ) : cancelled ? (
        <div className="evidence-query-state">
          <strong>Stopped waiting for the evidence query</strong>
          <p>
            The local derivation may finish in the background. The selected
            state and recorded checks are unchanged.
          </p>
          <button className="secondary" onClick={() => setRetry((n) => n + 1)}>
            Retry query
          </button>
        </div>
      ) : (
        <div className="evidence-query-state" role="status">
          <span className="spinner" />
          <strong>
            {tab === "assurance"
              ? "Deriving evidence support"
              : "Comparing incremental and cold derivations"}
          </strong>
          <p>Reading actual persisted records for this state root.</p>
          <button
            className="secondary"
            onClick={() => {
              abort?.abort();
              setCancelled(true);
            }}
          >
            Stop waiting
          </button>
        </div>
      )}
      {data && (
        <button
          className="evidence-refresh"
          onClick={() => setRetry((n) => n + 1)}
        >
          <RefreshCw size={13} />
          Refresh against the current checker context
        </button>
      )}
    </div>
  );
}
