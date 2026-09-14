import { intervalDecimal, rationalDecimal } from "./rationalDisplay";

const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const words = (value: unknown) =>
  typeof value === "string" ? value.replaceAll("_", " ") : "Not reported";

export default function NetworkServiceEvidence({
  witness,
}: {
  witness: unknown;
}) {
  const c = record(record(witness).calculation),
    inputs = record(c.model_inputs);
  if (!Object.keys(c).length) return null;
  const components = Object.entries(record(c.components)),
    paths = Object.entries(record(c.paths));
  return (
    <div className="network-service-evidence">
      <div className="service-evidence-summary">
        <div>
          <span>Aggregate source flow</span>
          <strong>
            {rationalDecimal(c.source_flow_m3_s)} <small>m³/s</small>
          </strong>
        </div>
        <div>
          <span>Physical components</span>
          <strong>
            {String(c.unique_physical_components ?? components.length)}
          </strong>
        </div>
        <div>
          <span>Velocity limit</span>
          <strong>
            {rationalDecimal(inputs.maximum_velocity_m_s)} <small>m/s</small>
          </strong>
        </div>
      </div>
      <p className="service-evidence-condition">
        <strong>Prescribed demand flows.</strong>{" "}
        {words(inputs.fixed_flow_control_assumption)} Operating point:{" "}
        {words(c.operating_point_solution)}.
      </p>
      <div className="service-evidence-table">
        <table>
          <caption>
            Each demand's static pressure difference · source minus sink
          </caption>
          <thead>
            <tr>
              <th>Demand</th>
              <th>Required (Pa)</th>
              <th>Available (Pa)</th>
              <th>Recorded check</th>
            </tr>
          </thead>
          <tbody>
            {paths.map(([id, value]) => {
              const p = record(value);
              return (
                <tr key={id}>
                  <th>{String(p.demand_id ?? id)}</th>
                  <td>
                    {intervalDecimal(
                      p.required_source_minus_sink_static_pressure_pa,
                    )}
                  </td>
                  <td>
                    {rationalDecimal(
                      p.available_source_minus_sink_static_pressure_pa,
                      3,
                    )}
                  </td>
                  <td>{words(p.status)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <details>
        <summary>Per-component flow and port velocity</summary>
        <div className="service-evidence-table">
          <table>
            <thead>
              <tr>
                <th>Component / port</th>
                <th>Flow (m³/s)</th>
                <th>Velocity (m/s)</th>
                <th>Recorded check</th>
              </tr>
            </thead>
            <tbody>
              {components.flatMap(([id, value]) => {
                const p = record(value),
                  flow = record(p.flow_m3_s),
                  velocity = record(p.velocity_m_s),
                  checks = record(p.checks);
                return Object.entries(flow).map(([slot, q]) => (
                  <tr key={`${id}:${slot}`}>
                    <th>
                      {id} / {slot}
                    </th>
                    <td>{rationalDecimal(q)}</td>
                    <td>{intervalDecimal(velocity[slot], 6)}</td>
                    <td>{words(checks[slot])}</td>
                  </tr>
                ));
              })}
            </tbody>
          </table>
        </div>
      </details>
      <details>
        <summary>Physical assumptions and pressure terms</summary>
        <p>{words(inputs.applicability)}</p>
        <dl>
          {Object.entries(inputs)
            .filter(
              ([key]) =>
                !["applicability", "fixed_flow_control_assumption"].includes(
                  key,
                ),
            )
            .map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd>
                  {typeof value === "number"
                    ? rationalDecimal(value)
                    : words(value)}
                </dd>
              </div>
            ))}
        </dl>
        {paths.map(([id, value]) => {
          const p = record(value);
          return (
            <div key={id} className="service-pressure-terms">
              <strong>{String(p.demand_id ?? id)}</strong>
              <dl>
                <div>
                  <dt>Irreversible loss (Pa)</dt>
                  <dd>{intervalDecimal(p.irreversible_loss_pa)}</dd>
                </div>
                <div>
                  <dt>Elevation term (Pa)</dt>
                  <dd>{intervalDecimal(p.elevation_pressure_pa)}</dd>
                </div>
                <div>
                  <dt>Kinetic pressure term (Pa)</dt>
                  <dd>{intervalDecimal(p.kinetic_pressure_pa)}</dd>
                </div>
              </dl>
            </div>
          );
        })}
      </details>
      <p className="network-caption">
        These decimal intervals are rounded outward for display. Recorded
        verdicts and exact rational values remain in the evidence below. Fitting
        applicability: {words(c.geometry_and_fitting_catalog_applicability)}.
        Terminal equipment and pumps: {words(c.terminal_equipment_and_pumps)}.
      </p>
    </div>
  );
}
