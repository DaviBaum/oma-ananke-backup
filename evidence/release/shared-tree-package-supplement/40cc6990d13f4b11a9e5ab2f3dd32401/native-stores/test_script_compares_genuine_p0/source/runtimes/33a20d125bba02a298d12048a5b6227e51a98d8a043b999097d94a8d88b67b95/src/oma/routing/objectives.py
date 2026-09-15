"""Exact scalarization of reported route objectives, without another float sum.

The report's numerical lengths remain measured values with their own model
limits. This preserves their declared decimal values and explicit priorities;
it does not turn native length measurements into exact geometric lengths.
"""
from fractions import Fraction

from oma.optimization.master import rational


def reported_route_cost(objective, weights):
    if not weights or set(weights) - {"length_m", "fitting_count"}:
        raise ValueError("An explicit supported route objective policy is required")
    total, positive = Fraction(0), False
    for name, weight in weights.items():
        if isinstance(weight, bool) or isinstance(objective.get(name), bool):
            raise ValueError("Boolean objective values are not engineering quantities")
        if name not in objective:
            raise ValueError("Checked report omits a declared objective dimension")
        scale, value = rational(weight), rational(objective[name])
        if scale < 0 or value < 0:
            raise ValueError("Route priorities and measured objectives must be nonnegative")
        positive |= scale > 0
        total += scale * value
    if not positive:
        raise ValueError("At least one route objective priority must be positive")
    return total
