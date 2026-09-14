import { useState } from "react";
import { componentDemandIds, componentLines } from "./sharedNetwork";
import type { NetworkSpec } from "./types";

export default function NetworkDiagram({
  spec,
  selected,
  onSelect,
}: {
  spec: NetworkSpec;
  selected?: string | null;
  onSelect?: (id: string) => void;
}) {
  const [demand, setDemand] = useState("");
  const components = spec.components.map((c) => ({
    c,
    lines: componentLines(c),
    demands: componentDemandIds(spec, c.id),
  }));
  const points = components.flatMap((c) => c.lines.flat());
  if (!points.length || points.some((p) => p.some((v) => !Number.isFinite(v))))
    return (
      <p className="form-error">
        Finite component geometry is required for this diagram.
      </p>
    );
  // A declared-coordinate axonometric diagram. It is never a substitute for IFC geometry.
  const origin = points[0];
  const projected = (p: number[]) => [
    p[0] - origin[0] - 0.65 * (p[1] - origin[1]),
    0.35 * (p[0] - origin[0] + (p[1] - origin[1])) - (p[2] - origin[2]),
  ];
  const coordinates = points.map(projected),
    xs = coordinates.map((p) => p[0]),
    ys = coordinates.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys),
    scale = Math.min(
      470 / Math.max(maxX - minX, 0.01),
      190 / Math.max(maxY - minY, 0.01),
    );
  const position = (p: number[]) => {
    const [x, y] = projected(p);
    return [
      285 + (x - (minX + maxX) / 2) * scale,
      125 + (y - (minY + maxY) / 2) * scale,
    ];
  };
  return (
    <div className="network-diagram">
      <div className="network-diagram-header">
        <span>DECLARED COMPONENT GRAPH</span>
        <select
          aria-label="Highlight network demand"
          value={demand}
          onChange={(e) => setDemand(e.target.value)}
        >
          <option value="">All demands</option>
          {spec.demand_paths.map((p) => (
            <option key={p.demand_id}>{p.demand_id}</option>
          ))}
        </select>
      </div>
      <svg
        viewBox="0 0 570 255"
        role="img"
        aria-label={`${spec.network_id}: ${spec.components.length} unique physical components, ${spec.demand_paths.length} demand paths`}
      >
        {components.map(({ c, lines, demands }) => (
          <g
            key={c.id}
            className={`${selected === c.id ? "selected" : ""} ${demand && !demands.includes(demand) ? "dimmed" : ""} ${demands.length > 1 ? "shared" : ""}`}
          >
            {lines.map((line, i) => (
              <polyline
                key={i}
                points={line.map((p) => position(p).join(",")).join(" ")}
              />
            ))}
            {(() => {
              const p =
                  lines[0].length === 2
                    ? lines[0][0].map((v, i) => (v + lines[0][1][i]) / 2)
                    : lines[0][Math.floor((lines[0].length - 1) / 2)],
                [x, y] = position(p);
              return (
                <text x={x + 6} y={y - 13}>
                  {c.id}
                </text>
              );
            })()}
          </g>
        ))}
      </svg>
      <div
        className="network-component-table"
        role="group"
        aria-label="Unique network components"
      >
        {components.map(({ c, demands }) => (
          <button
            key={c.id}
            className={selected === c.id ? "selected" : ""}
            onClick={() => onSelect?.(c.id)}
            disabled={!onSelect}
            aria-label={`Select network component ${c.id}`}
          >
            <strong>
              {c.id}
              <small>{c.kind}</small>
            </strong>
            <span>
              {demands.join(" · ") || "No demand membership"}
              <small>
                {demands.length > 1
                  ? "Shared physical component · counted once"
                  : "Single-demand component"}
              </small>
            </span>
          </button>
        ))}
      </div>
      <p className="network-caption">
        Nominal centerlines from the graph. Native solids and independent checks
        are available after materialization.
      </p>
    </div>
  );
}
