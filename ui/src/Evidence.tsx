import { Code2, FileCheck2, ArrowUpRight } from "lucide-react";
import type { CheckRecord, Issue } from "./types";
export function checkIssue(check: CheckRecord): Issue {
  return {
    id: `${check.candidate_id}:${check.id}`,
    rule: check.id,
    status: check.status,
    participants: check.participants ?? [],
    message: check.reason,
    scope: check.scope,
    witness: check.witness,
    artifact: check.report_root,
  };
}
export function artifactRoots(record: unknown) {
  if (!record || typeof record !== "object") return [];
  const value = record as Record<string, unknown>;
  const roots = new Map<string, string>();
  for (const [key, item] of Object.entries(value)) {
    if (
      /root|artifact/.test(key) &&
      typeof item === "string" &&
      /^[a-f0-9]{64}$/.test(item)
    )
      roots.set(item, key.replaceAll("_", " "));
    if (key === "artifacts" && Array.isArray(item))
      for (const root of item)
        if (typeof root === "string" && /^[a-f0-9]{64}$/.test(root))
          roots.set(root, "artifact");
  }
  return [...roots.entries()];
}
export function ArtifactLinks({
  record,
  onOpen,
}: {
  record: unknown;
  onOpen: (root: string) => void;
}) {
  const roots = artifactRoots(record);
  return roots.length ? (
    <div className="artifact-links">
      <div className="section-label">REFERENCED ARTIFACTS</div>
      {roots.map(([root, label]) => (
        <button key={root} onClick={() => onOpen(root)}>
          <Code2 size={13} />
          <span>{label}</span>
          <code>{root.slice(0, 12)}…</code>
          <ArrowUpRight size={12} />
        </button>
      ))}
    </div>
  ) : null;
}
export function SourceAudits({
  sources,
  onOpen,
}: {
  sources: Record<string, unknown>[];
  onOpen: (source: Record<string, unknown>) => void;
}) {
  return (
    <div className="source-audits">
      <div className="section-label">
        <span>SOURCE AUDITS</span>
        <span>{sources.length} originals</span>
      </div>
      {sources.map((source, i) => (
        <button key={String(source.id ?? i)} onClick={() => onOpen(source)}>
          <FileCheck2 size={16} />
          <span>
            <strong>{String(source.name ?? "IFC source")}</strong>
            <small>
              {String(source.schema ?? "Unknown schema")} ·{" "}
              {Number(source.product_count ?? 0).toLocaleString()} objects
            </small>
          </span>
          <ArrowUpRight size={13} />
        </button>
      ))}
    </div>
  );
}
