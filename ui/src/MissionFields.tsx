import { Info } from "lucide-react";
import type { MissionForm } from "./mission";
export default function MissionFields({
  value,
  onChange,
}: {
  value: MissionForm;
  onChange: (value: MissionForm) => void;
}) {
  const update = (key: keyof MissionForm, v: string) =>
    onChange({ ...value, [key]: v });
  return (
    <div className="scenario-form">
      <div className="section-label">
        <span>EXPLICIT SCENARIO OVERLAY</span>
        <span className="badge warn">USER INPUT</span>
      </div>
      <p>
        Every value below is an explicit engineering assumption. The engine
        preserves its provenance and checks whether the requested service is
        supported.
      </p>
      <div className="form-grid">
        <label className="field">
          Service family
          <select
            value={value.system_type}
            onChange={(e) => update("system_type", e.target.value)}
          >
            <option value="PRESSURE_PIPE">Pressure pipe</option>
            <option value="GRAVITY_DRAINAGE">Gravity drainage</option>
            <option value="ROUND_DUCT">Round duct</option>
            <option value="FIRE_PROTECTION">Fire protection</option>
          </select>
        </label>
        <label className="field">
          Terminal evidence
          <select
            value={value.terminals}
            onChange={(e) => update("terminals", e.target.value)}
          >
            <option value="scenario">Explicit scenario terminals</option>
            <option value="imported">Existing IFC distribution ports</option>
          </select>
        </label>
      </div>
      {value.terminals === "imported" && (
        <div className="form-grid">
          <label className="field">
            Source port IFC GUID
            <input
              value={value.source_port_guid}
              onChange={(e) => update("source_port_guid", e.target.value)}
              placeholder="Required · source IFC port"
            />
          </label>
          <label className="field">
            Sink port IFC GUID
            <input
              value={value.sink_port_guid}
              onChange={(e) => update("sink_port_guid", e.target.value)}
              placeholder="Required · sink IFC port"
            />
          </label>
        </div>
      )}
      <div className="form-grid">
        {[
          { key: "start", label: "Source · X, Y, Z (m)" },
          { key: "end", label: "Sink · X, Y, Z (m)" },
          { key: "zone_min", label: "Allowed zone minimum · X, Y, Z" },
          { key: "zone_max", label: "Allowed zone maximum · X, Y, Z" },
        ].map((f) => (
          <label className="field" key={f.key}>
            {f.label}
            <input
              value={value[f.key as keyof MissionForm]}
              onChange={(e) =>
                update(f.key as keyof MissionForm, e.target.value)
              }
              placeholder="World coordinates · meters"
            />
          </label>
        ))}
        {[
          { key: "diameter_m", label: "Physical diameter (m)" },
          { key: "insulation_m", label: "Insulation thickness (m)" },
          { key: "bend_radius_m", label: "Fitting bend radius (m)" },
          { key: "minimum_straight_m", label: "Minimum straight length (m)" },
          { key: "clearance_m", label: "Required clearance (m)" },
        ].map((f) => (
          <label className="field" key={f.key}>
            {f.label}
            <input
              type="number"
              min="0"
              step="0.001"
              value={value[f.key as keyof MissionForm]}
              onChange={(e) =>
                update(f.key as keyof MissionForm, e.target.value)
              }
              placeholder="Explicit value required"
            />
          </label>
        ))}
      </div>
      <details className="advanced-mission">
        <summary>Additional engineering inputs · JSON</summary>
        <p>
          Provide applicable flow, material, pressure, drainage, objective
          weights, catalog, and maintenance requirements. Missing prerequisites
          remain blocked.
        </p>
        <label className="field">
          Additional mission inputs
          <textarea
            value={value.advanced}
            onChange={(e) => update("advanced", e.target.value)}
            rows={5}
            spellCheck={false}
            placeholder="{}"
          />
        </label>
      </details>
      <div className="inline-note">
        <Info size={15} />
        {value.terminals === "scenario"
          ? "Scenario terminals are added assumptions. This mode does not claim pre-existing service connectivity."
          : "The engine must match and validate both IFC ports; proximity alone is not connection evidence."}
      </div>
    </div>
  );
}
