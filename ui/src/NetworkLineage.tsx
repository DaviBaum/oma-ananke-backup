import { GitBranch } from "lucide-react";
import NetworkDiagram from "./NetworkDiagram";
import { networkChangedIds } from "./networkRevision";
import type { PhysicalNetwork } from "./types";

export default function NetworkLineage({
  network,
  onInspect,
}: {
  network: PhysicalNetwork;
  onInspect: (value: unknown) => void;
}) {
  const revision = network.network_contract?.revision;
  if (!revision) return null;
  const added = network.component_ids.map((id) => `${network.id}:${id}`);
  return (
    <div className="network-lineage">
      <strong>
        <GitBranch size={14} /> {revision.replaced_network_id} → {network.id}
      </strong>
      <p>
        {revision.previous_component_ids.length} prior parts · {added.length}{" "}
        proposed parts · {networkChangedIds(network).size} unique changed IDs
      </p>
      <p>
        This revision targets the accepted service requirements; its checks
        record verification separately. The viewport shows this selected state;
        the earlier graph below comes from its recorded geometry artifact.
      </p>
      <details>
        <summary>Changed parts and revision lineage</summary>
        <div className="network-changed-parts">
          <div>
            <strong>Previous parts</strong>
            {revision.previous_component_ids.map((id) => (
              <code key={id}>{id}</code>
            ))}
          </div>
          <div>
            <strong>Proposed parts</strong>
            {added.map((id) => (
              <code key={id}>{id}</code>
            ))}
          </div>
        </div>
        <button className="text-button" onClick={() => onInspect(revision)}>
          Inspect pinned revision record
        </button>
      </details>
      {network.previous_network && (
        <details>
          <summary>Previous graph · {network.previous_network.id}</summary>
          <NetworkDiagram
            spec={network.previous_network.network_spec}
            selected={null}
            onSelect={() => {}}
          />
        </details>
      )}
    </div>
  );
}
