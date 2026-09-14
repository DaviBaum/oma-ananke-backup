import { useState } from "react";
import { Plus, Trash2, Copy, GitBranch } from "lucide-react";
import MissionFields from "./MissionFields";
import { emptyMission } from "./mission";
import { newDemand, type JointMissionForm } from "./jointMission";
export default function JointMissionFields({
  value,
  onChange,
}: {
  value: JointMissionForm;
  onChange: (value: JointMissionForm) => void;
}) {
  const [active, setActive] = useState(value.demands[0]?.key),
    [option, setOption] = useState(0);
  const demand =
    value.demands.find((d) => d.key === active) ?? value.demands[0];
  const index = Math.min(option, demand.alternatives.length - 1);
  const update = (change: Partial<typeof demand>) =>
    onChange({
      ...value,
      demands: value.demands.map((d) =>
        d.key === demand.key ? { ...d, ...change } : d,
      ),
    });
  return (
    <div className="joint-editor">
      <div className="section-label">
        <span>SIMULTANEOUS ROUTE DEMANDS</span>
        <span>{value.demands.length} / 16</span>
      </div>
      <p className="joint-explanation">
        Each candidate must satisfy every demand. The engine checks complete
        assignments against the building and against every other route. Shared
        tees and trunks require a separate supported representation.
      </p>
      <div className="demand-table" role="table" aria-label="Route demands">
        <div role="row" className="demand-head">
          <span role="columnheader">Demand</span>
          <span role="columnheader">Service</span>
          <span role="columnheader">Options</span>
        </div>
        {value.demands.map((d) => (
          <div
            key={d.key}
            role="row"
            className={`demand-row ${d.key === demand.key ? "selected" : ""}`}
          >
            <span role="cell">
              <button
                onClick={() => {
                  setActive(d.key);
                  setOption(0);
                }}
                aria-label={`Edit demand ${d.id}`}
              >
                <strong>{d.id || "Unnamed demand"}</strong>
              </button>
            </span>
            <span role="cell">
              {d.alternatives[0]?.system_type.replaceAll("_", " ")}
            </span>
            <span role="cell">{d.alternatives.length}</span>
          </div>
        ))}
      </div>
      <div className="joint-actions">
        <button
          className="secondary"
          disabled={value.demands.length >= 16}
          onClick={() => {
            let n = value.demands.length + 1;
            while (value.demands.some((d) => d.id === `demand-${n}`)) n++;
            const next = newDemand(`demand-${n}`);
            onChange({ ...value, demands: [...value.demands, next] });
            setActive(next.key);
            setOption(0);
          }}
        >
          <Plus size={13} />
          Add demand
        </button>
        <button
          className="text-button danger"
          disabled={value.demands.length <= 1}
          onClick={() => {
            const next = value.demands.filter((d) => d.key !== demand.key);
            onChange({ ...value, demands: next });
            setActive(next[0].key);
            setOption(0);
          }}
        >
          <Trash2 size={13} />
          Remove demand
        </button>
      </div>
      <div className="form-grid">
        <label className="field">
          Demand identifier
          <input
            value={demand.id}
            onChange={(e) => update({ id: e.target.value })}
          />
        </label>
        <label className="field">
          Editing alternative
          <select
            value={index}
            onChange={(e) => setOption(Number(e.target.value))}
          >
            {demand.alternatives.map((_, i) => (
              <option key={i} value={i}>
                Alternative {i + 1}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="joint-actions">
        <button
          className="secondary"
          disabled={demand.alternatives.length >= 16}
          onClick={() => {
            update({
              alternatives: [
                ...demand.alternatives,
                { ...demand.alternatives[index] },
              ],
            });
            setOption(demand.alternatives.length);
          }}
        >
          <Copy size={13} />
          Copy as alternative
        </button>
        <button
          className="text-button"
          disabled={demand.alternatives.length >= 16}
          onClick={() => {
            update({
              alternatives: [...demand.alternatives, { ...emptyMission }],
            });
            setOption(demand.alternatives.length);
          }}
        >
          <Plus size={13} />
          Blank alternative
        </button>
        <button
          className="text-button danger"
          disabled={demand.alternatives.length <= 1}
          onClick={() => {
            update({
              alternatives: demand.alternatives.filter((_, i) => i !== index),
            });
            setOption(Math.max(0, index - 1));
          }}
        >
          <Trash2 size={13} />
          Remove option
        </button>
      </div>
      <div className="inline-note">
        <GitBranch size={15} />
        Alternatives must preserve the demand's service, loads, clearance, slope
        and assurance policy. All demands use the same objective weights. The
        engine validates these invariants.
      </div>
      <MissionFields
        value={demand.alternatives[index]}
        onChange={(a) =>
          update({
            alternatives: demand.alternatives.map((v, i) =>
              i === index ? a : v,
            ),
          })
        }
      />
      <div className="form-grid">
        <label className="field">
          Joint candidate limit
          <input
            type="number"
            min="1"
            max="256"
            value={value.max_joint_candidates}
            onChange={(e) =>
              onChange({ ...value, max_joint_candidates: e.target.value })
            }
          />
        </label>
        <label className="field">
          Paths per alternative
          <input
            type="number"
            min="1"
            max="32"
            value={value.max_paths_per_alternative}
            onChange={(e) =>
              onChange({ ...value, max_paths_per_alternative: e.target.value })
            }
          />
        </label>
      </div>
      <p className="joint-explanation">
        These limits bound search work. Unexamined combinations do not establish
        global infeasibility or global optimality.
      </p>
    </div>
  );
}
