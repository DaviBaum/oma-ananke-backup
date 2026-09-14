import { Info } from "lucide-react";
import type { OpeningHostInspection } from "./types";
import type { OpeningForm } from "./opening";
export default function OpeningFields({
  probe,
  value,
  onChange,
  stale,
}: {
  probe: OpeningHostInspection;
  value: OpeningForm;
  onChange: (value: OpeningForm) => void;
  stale: boolean;
}) {
  const host = probe.host;
  return (
    <section className="scenario-form opening-fields">
      <div className="section-label">
        <span>ONE EXPLICIT HOST OPENING</span>
        <span className="badge warn">GEOMETRY ONLY</span>
      </div>
      <p>
        Host {host?.host_guid} · STEP {host?.host_step_id}. Every cut coordinate
        below is in this host's local frame, in meters.
      </p>
      {stale && (
        <div role="alert" className="inline-note">
          The project head changed. Close this form and inspect the host again
          before submitting.
        </div>
      )}
      <details className="advanced-mission">
        <summary>Inspected host bounds, frame and source binding</summary>
        <pre>{JSON.stringify(probe, null, 2)}</pre>
      </details>
      <fieldset disabled={stale}>
        <div className="form-grid">
          {(
            [
              { key: "cutMin", label: "Opening minimum · local X, Y, Z (m)" },
              { key: "cutMax", label: "Opening maximum · local X, Y, Z (m)" },
              {
                key: "allowedMin",
                label: "Permitted volume minimum · local X, Y, Z (m)",
              },
              {
                key: "allowedMax",
                label: "Permitted volume maximum · local X, Y, Z (m)",
              },
            ] as const
          ).map(({ key, label }) => (
            <label className="field" key={key}>
              {label}
              <input
                value={value[key]}
                onChange={(e) => onChange({ ...value, [key]: e.target.value })}
                placeholder="Explicit local coordinates required"
              />
            </label>
          ))}
          <label className="field">
            Through-axis · host local frame
            <select
              value={value.axis}
              onChange={(e) => onChange({ ...value, axis: e.target.value })}
            >
              <option value="">Choose an axis</option>
              <option value="0">Local X</option>
              <option value="1">Local Y</option>
              <option value="2">Local Z</option>
            </select>
          </label>
        </div>
        <label className="field">
          Geometric edit permission statement
          <textarea
            rows={3}
            value={value.statement}
            maxLength={4000}
            onChange={(e) => onChange({ ...value, statement: e.target.value })}
            placeholder="State the specific permission and its geometric scope."
          />
        </label>
        <label className="field">
          Supporting evidence roots · optional
          <textarea
            rows={2}
            value={value.evidence}
            onChange={(e) => onChange({ ...value, evidence: e.target.value })}
            placeholder="SHA-256 roots, separated by spaces or newlines"
          />
        </label>
        <label className="opening-consent">
          <input
            type="checkbox"
            checked={value.confirmed}
            onChange={(e) =>
              onChange({ ...value, confirmed: e.target.checked })
            }
          />
          I explicitly authorize this geometric edit within the permitted volume
          above.
        </label>
      </fieldset>
      <div className="inline-note">
        <Info size={15} />
        This permission does not establish structural or fire suitability. The
        engine must independently verify the cut host, route clearance and
        affected semantics before acceptance.
      </div>
    </section>
  );
}
