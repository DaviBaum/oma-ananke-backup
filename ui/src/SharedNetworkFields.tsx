import { useMemo, useState } from "react";
import { GitBranch, Plus, Code2 } from "lucide-react";
import NetworkDiagram from "./NetworkDiagram";
import { parseSharedNetwork, sharedNetworkExample } from "./sharedNetwork";
import { vector } from "./mission";

export default function SharedNetworkFields({
  value,
  onChange,
  baselineBlocked = false,
}: {
  value: string;
  onChange: (value: string) => void;
  baselineBlocked?: boolean;
}) {
  const [example, setExample] = useState({
    center: "0, 0, 0",
    diameter: "0.1",
    insulation: "0.02",
    reach: "1",
    takeout: "0.2",
  });
  const [exampleError, setExampleError] = useState(""),
    [index, setIndex] = useState(0),
    [selected, setSelected] = useState<string | null>(null);
  const result = useMemo(() => {
    try {
      return { data: parseSharedNetwork(value), error: null };
    } catch (e) {
      return { data: null, error: (e as Error).message };
    }
  }, [value]);
  const active =
    result.data?.networks[Math.min(index, result.data.networks.length - 1)];
  return (
    <div className="shared-network-editor">
      {baselineBlocked && (
        <p className="form-error" role="status">
          Shared-network runs require an imported baseline with no engineered
          mission. Select or import that baseline to run. You can prepare this
          mission here.
        </p>
      )}
      <div className="section-label">
        <span>ONE NETWORK · EVERY DEMAND</span>
        <GitBranch size={16} />
      </div>
      <p className="joint-explanation">
        Declare each segment, elbow and tee once. Demand paths refer to those
        physical components, so shared trunk lengths and solids are counted
        once. Every alternative preserves the fixed terminals, section, service,
        zone and assurance policy.
      </p>
      <details className="network-example" open={!value.trim()}>
        <summary>
          <Plus size={14} /> Create an editable two-sink example
        </summary>
        <p>
          This creates a geometric scenario at the coordinates below. Review the
          generated mission before starting a run.
        </p>
        <div className="form-grid">
          {Object.entries({
            center: "Tee center X, Y, Z (m)",
            diameter: "Nominal diameter (m)",
            insulation: "Insulation thickness (m)",
            reach: "Center-to-terminal reach (m)",
            takeout: "Tee takeout (m)",
          }).map(([key, label]) => (
            <label key={key} className="field">
              {label}
              <input
                value={example[key as keyof typeof example]}
                onChange={(e) =>
                  setExample({ ...example, [key]: e.target.value })
                }
              />
            </label>
          ))}
        </div>
        {exampleError && (
          <p className="form-error" role="alert">
            {exampleError}
          </p>
        )}
        <button
          className="secondary"
          onClick={() => {
            try {
              if (Object.values(example).some((v) => !v.trim()))
                throw new Error("Every example field needs an explicit value.");
              const mission = sharedNetworkExample(
                vector(example.center),
                Number(example.diameter),
                Number(example.insulation),
                Number(example.reach),
                Number(example.takeout),
              );
              onChange(JSON.stringify(mission, null, 2));
              setExampleError("");
              setIndex(0);
            } catch (e) {
              setExampleError((e as Error).message);
            }
          }}
        >
          <Plus size={14} />
          {value.trim()
            ? "Replace JSON with this example"
            : "Create example JSON"}
        </button>
      </details>
      <label className="field network-json-label">
        <span>
          <Code2 size={14} /> Shared-network mission JSON
        </span>
        <textarea
          className="network-json"
          aria-label="Shared-network mission JSON"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            '{\n  "mission_type": "shared_network",\n  "network_alternatives": []\n}'
          }
          spellCheck={false}
        />
      </label>
      {result.error ? (
        <p className="form-error" role="status">
          {result.error}
        </p>
      ) : (
        <p className="network-input-ready">
          Input structure is ready for server validation.{" "}
          {result.data!.networks.length} explicit alternative
          {result.data!.networks.length === 1 ? "" : "s"}; no physical verdict
          yet.
        </p>
      )}
      {active && (
        <>
          <label className="field">
            Inspect graph alternative
            <select
              value={index}
              onChange={(e) => {
                setIndex(Number(e.target.value));
                setSelected(null);
              }}
            >
              {result.data!.networks.map((n, i) => (
                <option value={i} key={n.network_id}>
                  {n.network_id}
                </option>
              ))}
            </select>
          </label>
          <NetworkDiagram
            spec={active}
            selected={selected}
            onSelect={setSelected}
          />
        </>
      )}
      <div className="inline-note">
        <GitBranch size={15} />
        <span>
          The server supplies the pinned federation datum. Engineering-service
          checks require explicit sink flows, available pressures, fluid
          properties, fitting losses and applicability assumptions in the JSON.
          The example supplies no hydraulic evidence.
        </span>
      </div>
    </div>
  );
}
