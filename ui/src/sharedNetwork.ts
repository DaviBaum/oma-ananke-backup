import type { NetworkComponent, NetworkSpec, Vec3 } from "./types";

type JsonObject = Record<string, unknown>;
const object = (v: unknown, label: string): JsonObject => {
  if (!v || typeof v !== "object" || Array.isArray(v))
    throw new Error(`${label} must be an object.`);
  return v as JsonObject;
};
const list = (
  v: unknown,
  min: number,
  max: number,
  label: string,
): unknown[] => {
  if (!Array.isArray(v) || v.length < min || v.length > max)
    throw new Error(`${label} needs ${min}–${max} entries.`);
  return v;
};
const identifier = (v: unknown, label: string): string => {
  if (typeof v !== "string" || !/^[A-Za-z0-9_.:-]{1,120}$/.test(v))
    throw new Error(`${label} needs a valid, nonempty identifier.`);
  return v;
};
const number = (v: unknown, positive: boolean, label: string): number => {
  if (
    typeof v !== "number" ||
    !Number.isFinite(v) ||
    (positive ? v <= 0 : v < 0)
  )
    throw new Error(
      `${label} must be explicitly ${positive ? "positive" : "nonnegative"}.`,
    );
  return v;
};
const point = (v: unknown, label: string): Vec3 => {
  if (
    !Array.isArray(v) ||
    v.length !== 3 ||
    v.some((n) => typeof n !== "number" || !Number.isFinite(n))
  )
    throw new Error(`${label} needs three finite world-meter coordinates.`);
  return v as Vec3;
};
const same = (a: Vec3, b: Vec3) =>
  a.every((v, i) => Math.abs(v - b[i]) <= 1e-7);
const services = ["PRESSURE_PIPE", "ROUND_DUCT", "FIRE_PROTECTION"];

export function componentLines(component: NetworkComponent): Vec3[][] {
  const g = component.geometry;
  if (component.kind === "tee") {
    const f = g.frame_m!;
    const transform = (x: number, y: number): Vec3 =>
      [0, 1, 2].map((i) => f[i][0] * x + f[i][1] * y + f[i][3]) as Vec3;
    return [
      [transform(-g.trunk_takeout_m!, 0), transform(g.trunk_takeout_m!, 0)],
      [transform(0, 0), transform(0, g.branch_takeout_m!)],
    ];
  }
  if (component.kind === "elbow") {
    const center = g.center_m!,
      a = g.start_m!.map((v, i) => v - center[i]),
      n = g.normal!;
    const cross = [
      n[1] * a[2] - n[2] * a[1],
      n[2] * a[0] - n[0] * a[2],
      n[0] * a[1] - n[1] * a[0],
    ];
    return [
      Array.from({ length: 25 }, (_, i) => {
        const angle = (g.angle_rad! * i) / 24;
        return center.map(
          (v, j) => v + a[j] * Math.cos(angle) + cross[j] * Math.sin(angle),
        ) as Vec3;
      }),
    ];
  }
  return [[g.start_m!, g.end_m!]];
}

export function componentDemandIds(spec: NetworkSpec, id: string): string[] {
  return spec.demand_paths
    .filter((p) => p.steps.some((s) => s.component === id))
    .map((p) => p.demand_id);
}

function cap(component: NetworkComponent, slot: string): Vec3 {
  if (component.kind !== "tee")
    return slot === "a"
      ? component.geometry.start_m!
      : component.geometry.end_m!;
  const lines = componentLines(component);
  return slot === "a" ? lines[0][0] : slot === "b" ? lines[0][1] : lines[1][1];
}

export function parseSharedNetwork(text: string): {
  mission: JsonObject;
  networks: NetworkSpec[];
} {
  if (!text.trim())
    throw new Error(
      "Supply a shared-network mission or create an editable example.",
    );
  if (text.length > 2_000_000)
    throw new Error("The editable mission exceeds the 2 MB input limit.");
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("Shared-network mission must be valid JSON.");
  }
  const m = object(parsed, "Mission");
  if (m.mission_type !== "shared_network")
    throw new Error('mission_type must be "shared_network".');
  if (!services.includes(String(m.system_type)))
    throw new Error(
      "Choose a supported round pressure, duct or fire-protection service.",
    );
  if (m.scenario_terminals !== true)
    throw new Error("This mode requires explicit scenario terminals.");
  if (
    !["LOCAL_GEOMETRIC_COORDINATION", "ENGINEERING_SERVICE"].includes(
      String(m.target_modality),
    )
  )
    throw new Error("Declare the target assurance modality.");
  if (
    ![
      "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES",
      "NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES",
    ].includes(String(m.source_representation_policy))
  )
    throw new Error("Declare the source representation policy.");
  const start = point(m.start_m, "Source"),
    diameter = number(m.diameter_m, true, "Diameter"),
    insulation = number(m.insulation_m, false, "Insulation");
  number(m.clearance_m, false, "Clearance");
  number(m.minimum_straight_m, false, "Minimum straight length");
  number(m.minimum_bend_radius_m, true, "Minimum bend radius");
  const zone = object(m.allowed_zone, "Allowed zone"),
    min = point(zone.min, "Zone minimum"),
    max = point(zone.max, "Zone maximum");
  if (min.some((v, i) => v >= max[i]))
    throw new Error(
      "Allowed-zone minimum must be below its maximum on every axis.",
    );
  const sinks = new Map<string, { demand: string; point: Vec3 }>(),
    demandIds = new Set<string>();
  for (const raw of list(m.sinks, 2, 32, "Sinks")) {
    const s = object(raw, "Sink"),
      id = identifier(s.id, "Sink ID"),
      demand = identifier(s.demand_id, "Demand ID");
    if (sinks.has(id) || demandIds.has(demand))
      throw new Error("Sink and demand IDs must be unique.");
    sinks.set(id, { demand, point: point(s.end_m, `Sink ${id}`) });
    demandIds.add(demand);
    if (m.target_modality === "ENGINEERING_SERVICE") {
      number(s.required_flow_m3_s, true, `Flow for ${id}`);
      number(
        s.available_static_pressure_pa,
        false,
        `Available pressure for ${id}`,
      );
    }
  }
  if (
    [start, ...[...sinks.values()].map((s) => s.point)].some((p) =>
      p.some((v, i) => v < min[i] || v > max[i]),
    )
  )
    throw new Error("Every fixed terminal must lie in the allowed zone.");
  if (m.target_modality === "ENGINEERING_SERVICE" && !m.physics)
    throw new Error(
      "Engineering service needs explicit fluid, friction, loss, boundary and flow-control assumptions in physics.",
    );
  const networkIds = new Set<string>();
  const networks = list(
    m.network_alternatives,
    1,
    32,
    "Network alternatives",
  ).map((raw) => {
    const n = object(raw, "Network"),
      id = identifier(n.network_id, "Network ID");
    if (networkIds.has(id)) throw new Error(`Network ID ${id} is repeated.`);
    networkIds.add(id);
    if (
      n.schema !== "oma-physical-network/1" ||
      n.system_type !== m.system_type
    )
      throw new Error(
        `${id} needs the supported schema and fixed mission service.`,
      );
    if ("source_to_federation_matrix" in n)
      throw new Error(
        "Remove source_to_federation_matrix from proposals; the server supplies the pinned source datum.",
      );
    const components = new Map<string, NetworkComponent>();
    for (const rawComponent of list(
      n.components,
      1,
      512,
      "Unique physical components",
    )) {
      const c = object(rawComponent, "Component"),
        cid = identifier(c.id, "Component ID");
      if (components.has(cid))
        throw new Error(
          `Physical component ${cid} is duplicated. Shared trunks are declared once.`,
        );
      if (
        c.system_type !== m.system_type ||
        c.diameter_m !== diameter ||
        c.insulation_m !== insulation
      )
        throw new Error(
          `${cid} changes the fixed service or circular section.`,
        );
      if (!["segment", "tee", "elbow"].includes(String(c.kind)))
        throw new Error(`${cid} has an unsupported component kind.`);
      const g = object(c.geometry, `Geometry for ${cid}`),
        ports = object(c.ports, `Ports for ${cid}`);
      if (
        ports.a !== "SINK" ||
        ports.b !== "SOURCE" ||
        (c.kind === "tee" && ports.branch !== "SOURCE")
      )
        throw new Error(`${cid} needs oriented inlet and outlet slots.`);
      if (c.kind === "tee") {
        const frame = list(g.frame_m, 4, 4, "Tee frame");
        for (const row of frame)
          if (
            !Array.isArray(row) ||
            row.length !== 4 ||
            row.some((v) => typeof v !== "number" || !Number.isFinite(v))
          )
            throw new Error("Tee frame needs sixteen finite values.");
        number(g.trunk_takeout_m, true, "Trunk takeout");
        number(g.branch_takeout_m, true, "Branch takeout");
      } else {
        point(g.start_m, "Component start");
        point(g.end_m, "Component end");
        if (c.kind === "elbow") {
          point(g.center_m, "Elbow center");
          point(g.normal, "Elbow normal");
          number(g.bend_radius_m, true, "Elbow radius");
          number(g.angle_rad, true, "Elbow angle");
        }
      }
      components.set(cid, c as unknown as NetworkComponent);
    }
    const endpoint = (rawEndpoint: unknown) => {
      const e = object(rawEndpoint, "Endpoint"),
        c = components.get(String(e.component));
      if (!c || !Object.keys(c.ports).includes(String(e.port)))
        throw new Error(
          "An endpoint references an absent physical component or port.",
        );
      return { component: c, port: String(e.port) };
    };
    const source = endpoint(n.source);
    if (!same(cap(source.component, source.port), start))
      throw new Error(`${id} moves the fixed source terminal.`);
    for (const rawLink of list(n.connections, 0, 511, "Connections")) {
      const link = object(rawLink, "Connection");
      endpoint(link.source);
      endpoint(link.sink);
    }
    const covered = new Set<string>();
    for (const rawSink of list(n.sinks, 2, 32, "Network sinks")) {
      const s = object(rawSink, "Network sink"),
        sid = identifier(s.id, "Network sink ID"),
        expected = sinks.get(sid),
        e = endpoint(s.endpoint);
      if (
        !expected ||
        covered.has(sid) ||
        !same(cap(e.component, e.port), expected.point)
      )
        throw new Error(`${id} changes fixed sink coverage or positions.`);
      covered.add(sid);
    }
    if (covered.size !== sinks.size)
      throw new Error(`${id} omits a fixed sink.`);
    const paths = new Set<string>();
    for (const rawPath of list(n.demand_paths, 2, 32, "Demand paths")) {
      const p = object(rawPath, "Demand path"),
        expected = sinks.get(String(p.sink_id));
      if (
        !expected ||
        expected.demand !== p.demand_id ||
        paths.has(expected.demand)
      )
        throw new Error(`${id} changes fixed demand-to-sink membership.`);
      paths.add(expected.demand);
      for (const rawStep of list(p.steps, 1, 512, "Path steps")) {
        const step = object(rawStep, "Path step");
        endpoint({ component: step.component, port: step.entry_port });
        endpoint({ component: step.component, port: step.exit_port });
      }
    }
    if (paths.size !== sinks.size)
      throw new Error(`${id} omits a fixed demand path.`);
    return n as unknown as NetworkSpec;
  });
  return { mission: m, networks };
}

export function sharedNetworkExample(
  center: Vec3,
  diameter: number,
  insulation: number,
  reach: number,
  takeout: number,
): JsonObject {
  if (
    ![diameter, insulation, reach, takeout].every(Number.isFinite) ||
    diameter <= 0 ||
    insulation < 0 ||
    takeout <= diameter / 2 + insulation ||
    reach <= takeout
  )
    throw new Error(
      "Use a positive diameter, nonnegative insulation, takeout beyond the outer radius, and arm reach greater than takeout.",
    );
  const at = (x: number, y: number): Vec3 => [
    center[0] + x,
    center[1] + y,
    center[2],
  ];
  const base = {
    system_type: "PRESSURE_PIPE",
    diameter_m: diameter,
    insulation_m: insulation,
  };
  const segment = (id: string, start: Vec3, end: Vec3) => ({
    ...base,
    id,
    kind: "segment",
    geometry: { start_m: start, end_m: end },
    ports: { a: "SINK", b: "SOURCE" },
  });
  const network = {
    schema: "oma-physical-network/1",
    network_id: "editable-example",
    system_type: base.system_type,
    components: [
      segment("trunk", at(-reach, 0), at(-takeout, 0)),
      {
        ...base,
        id: "junction",
        kind: "tee",
        geometry: {
          frame_m: [
            [1, 0, 0, center[0]],
            [0, 1, 0, center[1]],
            [0, 0, 1, center[2]],
            [0, 0, 0, 1],
          ],
          trunk_takeout_m: takeout,
          branch_takeout_m: takeout,
        },
        ports: { a: "SINK", b: "SOURCE", branch: "SOURCE" },
      },
      segment("arm-a", at(takeout, 0), at(reach, 0)),
      segment("arm-b", at(0, takeout), at(0, reach)),
    ],
    connections: [
      {
        source: { component: "trunk", port: "b" },
        sink: { component: "junction", port: "a" },
      },
      {
        source: { component: "junction", port: "b" },
        sink: { component: "arm-a", port: "a" },
      },
      {
        source: { component: "junction", port: "branch" },
        sink: { component: "arm-b", port: "a" },
      },
    ],
    source: { component: "trunk", port: "a" },
    sinks: [
      { id: "sink-a", endpoint: { component: "arm-a", port: "b" } },
      { id: "sink-b", endpoint: { component: "arm-b", port: "b" } },
    ],
    demand_paths: ["a", "b"].map((letter) => ({
      demand_id: `demand-${letter}`,
      sink_id: `sink-${letter}`,
      steps: [
        { component: "trunk", entry_port: "a", exit_port: "b" },
        {
          component: "junction",
          entry_port: "a",
          exit_port: letter === "a" ? "b" : "branch",
        },
        { component: `arm-${letter}`, entry_port: "a", exit_port: "b" },
      ],
    })),
  };
  return {
    mission_type: "shared_network",
    system_type: base.system_type,
    start_m: at(-reach, 0),
    sinks: [
      { id: "sink-a", demand_id: "demand-a", end_m: at(reach, 0) },
      { id: "sink-b", demand_id: "demand-b", end_m: at(0, reach) },
    ],
    diameter_m: diameter,
    insulation_m: insulation,
    clearance_m: 0.01,
    minimum_straight_m: Math.min(0.05, reach - takeout),
    minimum_bend_radius_m: diameter + 2 * insulation,
    allowed_zone: {
      min: center.map((v) => v - reach - 0.25),
      max: center.map((v) => v + reach + 0.25),
    },
    scenario_terminals: true,
    target_modality: "LOCAL_GEOMETRIC_COORDINATION",
    source_representation_policy: "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES",
    network_alternatives: [network],
    objective_weights: { length_m: 1 },
    assumptions: [
      "User-created geometric example with explicit scenario terminals. Review all coordinates, section, zone and source policy before running. Flow, pressure and service performance have not been supplied.",
    ],
  };
}
