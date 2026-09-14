"""Bounded physical network component and oriented tree contract."""
from __future__ import annotations

import math
import numpy as np


def vector(value):
    result = np.asarray(value, dtype=float)
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError("Finite xyz vector required")
    return result


def rigid_frame(value):
    matrix = np.asarray(value, dtype=float)
    if (matrix.shape != (4, 4) or not np.isfinite(matrix).all() or
            not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-12, rtol=0) or
            not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-10, rtol=0) or
            abs(np.linalg.det(matrix[:3, :3])-1) > 1e-10):
        raise ValueError("Orientation-preserving rigid frame required")
    return matrix


def endpoint(value):
    if set(value) != {"component", "port"}:
        raise ValueError("Endpoint requires component and port identities")
    return value["component"], value["port"]


def component_geometry(component):
    """Compute requested cap facts. Independent IFC parsing is separate."""
    diameter, insulation = float(component["diameter_m"]), float(component["insulation_m"])
    if not math.isfinite(diameter) or not math.isfinite(insulation) or diameter <= 0 or insulation < 0:
        raise ValueError("Positive diameter and nonnegative insulation required")
    radius = diameter / 2 + insulation
    kind, geometry = component["kind"], component["geometry"]
    if kind == "segment":
        start, end = vector(geometry["start_m"]), vector(geometry["end_m"])
        length = float(np.linalg.norm(end-start))
        if length <= 1e-7:
            raise ValueError("Positive physical segment length required")
        direction = (end-start)/length
        caps = {"a": (start, -direction), "b": (end, direction)}
        paths = {"a:b": length}
        volume = math.pi * radius**2 * length
    elif kind == "elbow":
        center, start, end = (vector(geometry[k]) for k in ("center_m", "start_m", "end_m"))
        normal = vector(geometry["normal"])
        if abs(np.linalg.norm(normal)-1) > 1e-10:
            raise ValueError("Unit elbow normal required")
        bend = float(geometry["bend_radius_m"])
        angle = float(geometry["angle_rad"])
        radial = start-center
        if not (math.isfinite(bend) and math.isfinite(angle) and bend > radius and 0 < angle < math.pi):
            raise ValueError("Bounded positive circular elbow required")
        if abs(np.linalg.norm(radial)-bend) > 1e-8 or abs(np.dot(radial, normal)) > 1e-8:
            raise ValueError("Elbow start is inconsistent with its circle")
        rotated = radial*math.cos(angle) + np.cross(normal, radial)*math.sin(angle)
        if np.linalg.norm(center+rotated-end) > 1e-8:
            raise ValueError("Elbow end is inconsistent with its angle")
        caps = {"a": (start, -np.cross(normal, radial)/bend), "b": (end, np.cross(normal, end-center)/bend)}
        length = bend*angle
        paths = {"a:b": length}
        volume = math.pi*radius**2*length
    elif kind == "tee":
        frame = rigid_frame(geometry["frame_m"])
        takeout, branch = float(geometry["trunk_takeout_m"]), float(geometry["branch_takeout_m"])
        if not math.isfinite(takeout) or not math.isfinite(branch) or min(takeout, branch) <= radius+1e-6:
            raise ValueError("Tee takeouts must expose three full external disk caps")
        center, x, y = frame[:3, 3], frame[:3, 0], frame[:3, 1]
        caps = {"a": (center-takeout*x, -x), "b": (center+takeout*x, x), "branch": (center+branch*y, y)}
        length = 2*takeout+branch
        paths = {"a:b": 2*takeout, "a:branch": takeout+branch}
        volume = math.pi*radius**2*length - 8*radius**3/3
    else:
        raise ValueError("Unsupported physical component kind")
    roles = {"a": "SINK", "b": "SOURCE", **({"branch": "SOURCE"} if kind == "tee" else {})}
    if component["ports"] != roles:
        raise ValueError("First network family requires a directed inlet and declared outlet slots")
    return {"kind": kind, "radius_m": radius, "length_m": length, "analytic_volume_m3": volume,
        "fitting_count": int(kind != "segment"), "path_lengths_m": paths,
        "caps": {slot: {"position_m": point.tolist(), "outward_normal": axis.tolist(), "flow_direction": roles[slot]}
                 for slot, (point, axis) in caps.items()}}


def validate_network_spec(spec):
    if spec.get("schema") != "oma-physical-network/1" or not spec.get("network_id"):
        raise ValueError("Explicit network schema and identity required")
    if spec.get("system_type") not in {"PRESSURE_PIPE", "FIRE_PROTECTION", "ROUND_DUCT"}:
        raise ValueError("Unsupported network system; gravity fitting slope is not implemented")
    rigid_frame(spec.get("source_to_federation_matrix", np.eye(4)))
    items = spec["components"]
    components = {c["id"]: c for c in items}
    if not components or len(components) != len(items) or any(not isinstance(k, str) or not k for k in components):
        raise ValueError("Unique nonempty physical component IDs required")
    if any(c["system_type"] != spec["system_type"] for c in items):
        raise ValueError("Every physical component must belong to the fixed network system")
    geometry = {identity: component_geometry(c) for identity, c in components.items()}
    slots = {(cid, slot): cap for cid, facts in geometry.items() for slot, cap in facts["caps"].items()}
    root = endpoint(spec["source"])
    sinks = {s["id"]: endpoint(s["endpoint"]) for s in spec["sinks"]}
    if len(sinks) != len(spec["sinks"]) or not sinks or len(set(sinks.values())) != len(sinks):
        raise ValueError("Unique terminal sink identities and slots required")
    if root not in slots or slots[root]["flow_direction"] != "SINK":
        raise ValueError("Network source must bind its one physical inlet SINK slot")
    if any(s not in slots or slots[s]["flow_direction"] != "SOURCE" for s in sinks.values()):
        raise ValueError("Network sinks must bind physical outlet SOURCE slots")
    boundaries = {root, *sinks.values()}
    used, connections = set(), set()
    graph = {cid: set() for cid in components}
    incoming = {cid: 0 for cid in components}
    for connection in spec["connections"]:
        first, second = endpoint(connection["source"]), endpoint(connection["sink"])
        if first not in slots or second not in slots or first[0] == second[0]:
            raise ValueError("Connection endpoints must belong to distinct known components")
        if slots[first]["flow_direction"] != "SOURCE" or slots[second]["flow_direction"] != "SINK":
            raise ValueError("All physical connections must be SOURCE to SINK")
        if first in used or second in used or first in boundaries or second in boundaries:
            raise ValueError("A physical port is multiply connected or consumes a boundary terminal")
        a, b = slots[first], slots[second]
        if np.linalg.norm(vector(a["position_m"])-vector(b["position_m"])) > 1e-7 or np.linalg.norm(vector(a["outward_normal"])+vector(b["outward_normal"])) > 1e-7:
            raise ValueError("Connected cap positions or physical normals are incompatible")
        if abs(geometry[first[0]]["radius_m"]-geometry[second[0]]["radius_m"]) > 1e-10:
            raise ValueError("Connected sections differ")
        used.update((first, second)); connections.add((first, second))
        graph[first[0]].add(second[0]); incoming[second[0]] += 1
    if used | boundaries != set(slots) or used & boundaries:
        raise ValueError("Every nonterminal physical slot must have exactly one connection")
    if len(connections) != len(components)-1 or incoming[root[0]] != 0 or any(n != 1 for cid, n in incoming.items() if cid != root[0]):
        raise ValueError("Network must be a directed tree with exactly one source")
    seen, stack = set(), [root[0]]
    while stack:
        node = stack.pop()
        if node in seen:
            raise ValueError("Network contains a directed cycle or reconvergence")
        seen.add(node); stack.extend(graph[node])
    if seen != set(components):
        raise ValueError("Physical network is disconnected")
    demands = spec["demand_paths"]
    if len({d["demand_id"] for d in demands}) != len(demands) or len({d["sink_id"] for d in demands}) != len(demands) or {d["sink_id"] for d in demands} != set(sinks):
        raise ValueError("Every demand and sink must have one explicit oriented physical path")
    reached = set()
    path_lengths = {}
    for demand in demands:
        steps = demand["steps"]
        if not steps:
            raise ValueError("Empty physical demand path")
        entries = [(s["component"], s["entry_port"]) for s in steps]
        exits = [(s["component"], s["exit_port"]) for s in steps]
        if entries[0] != root or exits[-1] != sinks[demand["sink_id"]] or len({s[0] for s in entries}) != len(steps):
            raise ValueError("Demand path endpoints or repeated components violate its tree binding")
        if any((a, b) not in connections for a, b in zip(exits, entries[1:])):
            raise ValueError("Demand path traverses an undeclared physical connection")
        length = 0.
        for step in steps:
            cid = step["component"]
            key = step["entry_port"]+":"+step["exit_port"]
            if cid not in geometry or key not in geometry[cid]["path_lengths_m"]:
                raise ValueError("Unsupported or reversed component port transition")
            length += geometry[cid]["path_lengths_m"][key]
            reached.add(cid)
        path_lengths[demand["demand_id"]] = length
    if reached != set(components):
        raise ValueError("A physical component serves no declared demand")
    return {"components": geometry, "unique_length_m": sum(g["length_m"] for g in geometry.values()),
        "fitting_count": sum(g["fitting_count"] for g in geometry.values()), "demand_path_lengths_m": path_lengths,
        "physical_components": len(components), "physical_ports": len(slots), "physical_connections": len(connections)}
