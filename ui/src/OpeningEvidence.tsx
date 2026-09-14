import { Scissors, Code2 } from "lucide-react";
import type { OpeningEdit } from "./types";
export default function OpeningEvidence({
  edit,
  onInspect,
  onSelect,
}: {
  edit: OpeningEdit;
  onInspect: (value: unknown) => void;
  onSelect?: (id: string) => void;
}) {
  return (
    <section className="network-revision-card opening-evidence">
      <div className="section-label">
        <span>AUTHORIZED OPENING</span>
        <Scissors size={15} />
      </div>
      <strong>Native host geometry replaced</strong>
      <p>
        The selected host shows the cut support from{" "}
        {edit.effective_source_file}. Its imported identity and properties
        remain preserved.
      </p>
      <div className="inline-note">
        Geometric scenario permission only. Structural, fire and access adequacy
        remain outside this edit's checks.
      </div>
      <p className="muted">
        Replay the base revision in History to inspect the original uncut host.
      </p>
      {onSelect && (
        <button
          className="secondary"
          onClick={() => onSelect(edit.host_entity_id)}
        >
          <Scissors size={14} /> Inspect edited host
        </button>
      )}
      <button className="secondary" onClick={() => onInspect(edit)}>
        <Code2 size={14} /> Permission and affected checks
      </button>
    </section>
  );
}
