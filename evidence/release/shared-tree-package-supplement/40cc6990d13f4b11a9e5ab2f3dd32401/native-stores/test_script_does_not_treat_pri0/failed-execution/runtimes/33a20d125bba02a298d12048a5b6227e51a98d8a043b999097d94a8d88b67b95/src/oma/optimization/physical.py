"""Exact rational enclosures for selected declared route physical models.

Integration DEF-RTR54–59, THM-RTR53–66; conservation corrected by A003.
These are engineering model calculations, not code compliance or a complete
route certificate. Geometry, fitting catalogs, access, supports and applicability
must be checked separately. SI quantities are explicit in every parameter name.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import isqrt

from .master import rational


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction

    def __post_init__(self):
        object.__setattr__(self, "lo", rational(self.lo))
        object.__setattr__(self, "hi", rational(self.hi))
        if self.lo > self.hi:
            raise ValueError("Interval bounds reversed")

    @classmethod
    def point(cls, value):
        return cls(value, value)

    def __add__(self, other):
        other = as_interval(other)
        return Interval(self.lo + other.lo, self.hi + other.hi)

    __radd__ = __add__

    def __neg__(self):
        return Interval(-self.hi, -self.lo)

    def __sub__(self, other):
        return self + -as_interval(other)

    def __mul__(self, other):
        other = as_interval(other)
        values = (self.lo * other.lo, self.lo * other.hi, self.hi * other.lo, self.hi * other.hi)
        return Interval(min(values), max(values))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = as_interval(other)
        if other.lo <= 0 <= other.hi:
            raise ValueError("Division by an interval containing zero")
        return self * Interval(1 / other.hi, 1 / other.lo)

    def square(self):
        return Interval(0 if self.lo <= 0 <= self.hi else min(self.lo**2, self.hi**2), max(self.lo**2, self.hi**2))

    def encoded(self):
        return {"lower": str(self.lo), "upper": str(self.hi), "arithmetic": "exact_rational_enclosure"}


def as_interval(value):
    return value if isinstance(value, Interval) else Interval.point(value)


@lru_cache(maxsize=1)
def pi_interval():
    # Machin identity pi = 16 atan(1/5) - 4 atan(1/239), enclosed by
    # alternating-series partial sums. No platform float constants are trusted.
    def atan_bound(inverse):
        n = 24
        total = sum((Fraction((-1)**k, (2 * k + 1) * inverse**(2 * k + 1)) for k in range(n)), Fraction(0))
        following = total + Fraction((-1)**n, (2 * n + 1) * inverse**(2 * n + 1))
        return Interval(min(total, following), max(total, following))
    return 16 * atan_bound(5) - 4 * atan_bound(239)


def sqrt_interval(value, digits=24):
    value = rational(value)
    if value < 0 or digits < 1:
        raise ValueError("Nonnegative square root and positive precision required")
    scale = 10**digits
    floor = isqrt(value.numerator * scale * scale // value.denominator)
    lower = Fraction(floor, scale)
    upper = lower if lower * lower == value else Fraction(floor + 1, scale)
    return Interval(lower, upper)


@dataclass(frozen=True)
class SectionOption:
    id: str
    area_m2: Interval
    hydraulic_diameter_m: Interval
    envelope_width_m: Fraction
    envelope_height_m: Fraction
    cost_per_m: Fraction

    def __post_init__(self):
        for key in ("area_m2", "hydraulic_diameter_m"):
            object.__setattr__(self, key, as_interval(getattr(self, key)))
            if getattr(self, key).lo <= 0:
                raise ValueError("Section area and hydraulic diameter must be positive")
        for key in ("envelope_width_m", "envelope_height_m", "cost_per_m"):
            object.__setattr__(self, key, rational(getattr(self, key)))
        if not self.id or min(self.envelope_width_m, self.envelope_height_m) <= 0 or self.cost_per_m < 0:
            raise ValueError("Invalid catalog section")


def circular_section(identifier, diameter_m, *, insulation_m, cost_per_m):
    diameter, insulation = rational(diameter_m), rational(insulation_m)
    if diameter <= 0 or insulation < 0:
        raise ValueError("Invalid diameter/insulation")
    return SectionOption(identifier, pi_interval() * diameter**2 / 4, Interval.point(diameter),
                         diameter + 2 * insulation, diameter + 2 * insulation, rational(cost_per_m))


def rectangular_section(identifier, width_m, height_m, *, insulation_m, cost_per_m):
    width, height, insulation = map(rational, (width_m, height_m, insulation_m))
    if min(width, height) <= 0 or insulation < 0:
        raise ValueError("Invalid section/insulation")
    area = width * height
    return SectionOption(identifier, Interval.point(area), Interval.point(2 * area / (width + height)),
                         width + 2 * insulation, height + 2 * insulation, rational(cost_per_m))


def bounded_le(value: Interval, maximum) -> str:
    maximum = rational(maximum)
    if value.hi <= maximum:
        return "PASS"
    if value.lo > maximum:
        return "FAIL"
    return "UNKNOWN"


def combine_verdicts(verdicts):
    if "FAIL" in verdicts:
        return "FAIL"
    if not verdicts or any(v != "PASS" for v in verdicts):
        return "UNKNOWN"
    return "PASS"


def evaluate_fluid_path(*, section: SectionOption, length_m, flow_m3_s, density_kg_m3,
                        darcy_friction, fitting_loss_coefficient, maximum_velocity_m_s,
                        available_pressure_pa, efficiency):
    """Fixed-section Darcy–Weisbach path model, with declared friction enclosure.

    Applies to one path with constant flow. A branched network must aggregate
    trunk flow and evaluate each demand path; summing unrelated branches is not
    a pressure-head calculation. Reynolds/friction derivation is not inferred.
    """
    parameters = dict(length_m=length_m, flow_m3_s=flow_m3_s, density_kg_m3=density_kg_m3,
                      darcy_friction=darcy_friction, fitting_loss_coefficient=fitting_loss_coefficient,
                      maximum_velocity_m_s=maximum_velocity_m_s, available_pressure_pa=available_pressure_pa,
                      efficiency=efficiency)
    missing = [key for key, value in parameters.items() if value is None]
    if missing:
        return {"verdict": "UNKNOWN", "missing": missing, "geometry": "NOT_RUN", "section": section.id}
    length, flow, density, friction, fitting, velocity_limit, pressure_limit, eta = [as_interval(v) for v in parameters.values()]
    if min(length.lo, flow.lo, friction.lo, fitting.lo, velocity_limit.lo, pressure_limit.lo) < 0 or density.lo <= 0 or eta.lo <= 0 or eta.hi > 1:
        raise ValueError("Physical inputs outside declared SI domain")
    velocity = flow / section.area_m2
    loss = (friction * length / section.hydraulic_diameter_m + fitting) * density * velocity.square() / 2
    power = flow * loss / eta
    checks = {"velocity": bounded_le(velocity, velocity_limit.lo), "pressure": bounded_le(loss, pressure_limit.lo)}
    return {"verdict": combine_verdicts(list(checks.values())), "checks": checks, "section": section.id,
            "velocity_m_s": velocity.encoded(), "pressure_drop_pa": loss.encoded(), "power_w": power.encoded(),
            "geometry": "NOT_RUN", "model": "fixed_section_constant_flow_Darcy_Weisbach",
            "source": "OMA integration DEF-RTR55/56", "friction_applicability": "CALLER_DECLARED"}


def select_fluid_catalog(options, *, geometry_check, **path_parameters):
    """Evaluate every catalog option and join separately supplied envelope verdicts.

    Exact finite choice under declared length-times-unit-cost policy. An UNKNOWN
    option can hide a better design, so optimality is withheld until all options
    are disposed. Full-route checks remain distinct from this scoped selection.
    """
    if not options or len({s.id for s in options}) != len(options):
        raise ValueError("Nonempty catalog with unique IDs required")
    length = path_parameters.get("length_m")
    records, feasible = [], []
    for section in sorted(options, key=lambda s: s.id):
        physical = evaluate_fluid_path(section=section, **path_parameters)
        geometry = geometry_check(section)
        if geometry not in ("PASS", "FAIL", "UNKNOWN"):
            raise ValueError("Geometry checker must return PASS, FAIL or UNKNOWN")
        verdict = combine_verdicts([physical["verdict"], geometry])
        record = {"section": section.id, "physical": physical, "geometry": geometry, "verdict": verdict}
        if verdict == "PASS" and length is not None:
            cost = rational(length) * section.cost_per_m
            record["cost"] = str(cost)
            feasible.append((cost, section.id))
        records.append(record)
    unresolved = any(r["verdict"] == "UNKNOWN" for r in records)
    return {"status": "CATALOG_FEASIBLE" if feasible and unresolved else "CATALOG_OPTIMAL" if feasible else "UNKNOWN" if unresolved else "CATALOG_INFEASIBLE",
            "selected": min(feasible)[1] if feasible else None, "objective": str(min(feasible)[0]) if feasible else None,
            "options": records, "scope": "SUPPLIED_CATALOG_FIXED_PATH", "unresolved_options": unresolved}


def evaluate_electrical_path(*, current_a, resistance_ohm, reactance_ohm, cos_phi,
                             ampacity_a, voltage_drop_limit_v, tray_fill, maximum_tray_fill):
    values = locals().copy()
    missing = [key for key, value in values.items() if value is None]
    if missing:
        return {"verdict": "UNKNOWN", "missing": missing, "geometry": "NOT_RUN"}
    current, resistance, reactance, cosine, ampacity, drop_limit, fill, fill_limit = map(rational, values.values())
    if min(current, resistance, reactance, ampacity, drop_limit, fill, fill_limit) < 0 or not 0 <= cosine <= 1 or fill_limit > 1:
        raise ValueError("Invalid balanced three-phase electrical parameters")
    sine = sqrt_interval(1 - cosine * cosine)
    drop = sqrt_interval(3) * current * (resistance * cosine + reactance * sine)
    checks = {"ampacity": "PASS" if current <= ampacity else "FAIL",
              "voltage_drop": bounded_le(drop, drop_limit), "tray_fill": "PASS" if fill <= fill_limit else "FAIL"}
    return {"verdict": combine_verdicts(list(checks.values())), "checks": checks, "voltage_drop_v": drop.encoded(),
            "resistive_loss_w": str(3 * current**2 * resistance), "geometry": "NOT_RUN",
            "model": "balanced_three_phase_fixed_catalog_impedance", "source": "DEF-RTR57"}


def check_conservation(edges, injection_minus_withdrawal, *, storage_rate=None, losses=None, conversion=None):
    """A003: B(head=+1,tail=-1)f=storage+loss-injection-conversion."""
    storage_rate, losses, conversion = storage_rate or {}, losses or {}, conversion or {}
    nodes = set(injection_minus_withdrawal) | set(storage_rate) | set(losses) | set(conversion)
    nodes |= {node for tail, head, _ in edges for node in (tail, head)}
    missing = nodes - set(injection_minus_withdrawal)
    if missing:
        return {"verdict": "UNKNOWN", "missing_node_balances": sorted(missing)}
    balance = {node: Fraction(0) for node in nodes}
    for tail, head, flow in edges:
        flow = rational(flow)
        balance[tail] -= flow
        balance[head] += flow
    residual = {node: balance[node] - (rational(storage_rate.get(node, 0)) + rational(losses.get(node, 0))
                - rational(injection_minus_withdrawal[node]) - rational(conversion.get(node, 0))) for node in sorted(nodes)}
    return {"verdict": "PASS" if all(v == 0 for v in residual.values()) else "FAIL",
            "residuals": {k: str(v) for k, v in residual.items()}, "incidence": "head_plus_tail_minus",
            "amendment": "OMA-MATH-A003"}


def aggregate_tree_flows(root, edges, terminal_demands):
    """Compute exact shared-trunk demand in a finite directed arborescence."""
    children, parents = {}, {}
    for tail, head in edges:
        if head == root or head in parents:
            raise ValueError("Topology is not a rooted arborescence")
        parents[head] = tail
        children.setdefault(tail, []).append(head)
    seen, active, flows = set(), set(), {}
    def visit(node):
        if node in active:
            raise ValueError("Directed cycle")
        active.add(node)
        seen.add(node)
        demand = rational(terminal_demands.get(node, 0))
        if demand < 0:
            raise ValueError("Terminal demand must be nonnegative")
        for child in sorted(children.get(node, [])):
            child_demand = visit(child)
            flows[(node, child)] = child_demand
            demand += child_demand
        active.remove(node)
        return demand
    total = visit(root)
    if (set(parents) | set(children) | set(terminal_demands)) - seen:
        raise ValueError("Disconnected terminal or component")
    return {"source_flow": total, "edge_flows": flows}


def solve_gravity_elevations(nodes, edges, elevation_bounds):
    """Exact difference constraints for fixed-topology gravity drainage.

    edges=(tail,head,horizontal_length_m,min_slope,max_slope). Vertical drops
    require explicit separate bounds and must not be misrepresented as zero
    horizontal-length slope constraints. Negative-cycle witness is returned for
    the finite constraint system; checker independently replays all inequalities.
    """
    nodes = tuple(sorted(nodes))
    if not nodes or len(set(nodes)) != len(nodes) or set(elevation_bounds) != set(nodes):
        raise ValueError("All unique nodes require explicit elevation intervals")
    anchor = "__gravity_reference__"
    if anchor in nodes:
        raise ValueError("Reserved node identity")
    constraints = []
    for node in nodes:
        lo, hi = map(rational, elevation_bounds[node])
        if lo > hi:
            raise ValueError("Elevation interval reversed")
        constraints.extend([(anchor, node, hi, "upper:" + node), (node, anchor, -lo, "lower:" + node)])
    for number, (tail, head, length, low_slope, high_slope) in enumerate(edges):
        length, low_slope, high_slope = map(rational, (length, low_slope, high_slope))
        if tail not in nodes or head not in nodes or length <= 0 or low_slope < 0 or high_slope < low_slope:
            raise ValueError("Invalid gravity edge; vertical drops need separate model")
        constraints.extend([(tail, head, -low_slope * length, f"slope-min:{number}"),
                            (head, tail, high_slope * length, f"slope-max:{number}")])
    distance = {node: Fraction(0) for node in (*nodes, anchor)}
    predecessor = {}
    updated = None
    for _ in range(len(distance)):
        updated = None
        for index, (u, v, weight, _) in enumerate(constraints):
            if distance[v] > distance[u] + weight:
                distance[v] = distance[u] + weight
                predecessor[v] = index
                updated = v
        if updated is None:
            elevations = {node: distance[node] - distance[anchor] for node in nodes}
            return {"status": "FEASIBLE", "elevations_m": {k: str(v) for k, v in elevations.items()},
                    "constraints": [(u, v, str(w), label) for u, v, w, label in constraints], "model": "fixed_topology_rational_difference_constraints"}
    cursor = updated
    for _ in distance:
        cursor = constraints[predecessor[cursor]][0]
    cycle_start, cycle = cursor, []
    while True:
        index = predecessor[cursor]
        cycle.append(index)
        cursor = constraints[index][0]
        if cursor == cycle_start:
            break
    return {"status": "INFEASIBLE", "negative_cycle": cycle,
            "constraints": [(u, v, str(w), label) for u, v, w, label in constraints], "model": "fixed_topology_rational_difference_constraints"}


def verify_gravity_result(result, nodes, edges, elevation_bounds):
    """Rebuild input inequalities, then replay feasibility or a negative cycle."""
    constraints = result["constraints"]
    expected = []
    for node in sorted(nodes):
        low, high = map(rational, elevation_bounds[node])
        expected.extend([("__gravity_reference__", node, str(high), "upper:" + node),
                         (node, "__gravity_reference__", str(-low), "lower:" + node)])
    for index, (tail, head, length, minimum, maximum) in enumerate(edges):
        expected.extend([(tail, head, str(-rational(minimum) * rational(length)), f"slope-min:{index}"),
                         (head, tail, str(rational(maximum) * rational(length)), f"slope-max:{index}")])
    if [tuple(c) for c in constraints] != expected:
        return "FAIL"
    if result["status"] == "FEASIBLE":
        elevations = {k: rational(v) for k, v in result["elevations_m"].items()}
        elevations["__gravity_reference__"] = Fraction(0)
        try:
            valid = all(elevations[v] - elevations[u] <= rational(weight) for u, v, weight, _ in constraints)
        except KeyError:
            valid = False
        return "PASS" if valid else "FAIL"
    if result["status"] != "INFEASIBLE":
        return "UNKNOWN"
    try:
        cycle = [constraints[i] for i in result["negative_cycle"]]
        linked = bool(cycle) and all(cycle[i][0] == cycle[(i + 1) % len(cycle)][1] for i in range(len(cycle)))
        valid = linked and sum((rational(c[2]) for c in cycle), Fraction(0)) < 0
    except (IndexError, TypeError):
        valid = False
    return "PASS" if valid else "FAIL"
