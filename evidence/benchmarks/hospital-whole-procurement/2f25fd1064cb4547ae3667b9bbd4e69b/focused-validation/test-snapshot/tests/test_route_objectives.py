"""A small declared priority must survive a much larger weighted dimension."""
import pytest

from oma.optimization.master import MasterProblem, RouteColumn, solve_master
from oma.optimization.checker import verify_master_result
from oma.routing.objectives import reported_route_cost


def test_reported_fitting_priority_is_not_erased_before_exact_selection():
    weights = {"length_m": 1e16, "fitting_count": 1.}
    reports = {"a-more-fittings": {"length_m": 1., "fitting_count": 1.},
               "b-fewer-fittings": {"length_m": 1., "fitting_count": 0.}}
    # Float scalarization destroys the user's remaining fitting preference.
    rounded = [sum(weights[k]*v for k,v in report.items()) for report in reports.values()]
    assert rounded[0] == rounded[1]
    problem = MasterProblem(net_ids=("route",), columns=tuple(
        RouteColumn(name, "route", reported_route_cost(report, weights), artifact_ref=name)
        for name, report in reports.items()), state_root="fixed-reported-objective-values")
    result = solve_master(problem)
    assert result.selected == ("b-fewer-fittings",)
    assert verify_master_result(problem, result)["verdict"] == "PASS"


@pytest.mark.parametrize("objective,weights", [
    ({"length_m":1.}, {"length_m":1.,"fitting_count":1.}),
    ({"length_m":float("nan")}, {"length_m":1.}),
    ({"length_m":1.}, {"length_m":float("inf")}),
    ({"length_m":True}, {"length_m":1.}),
    ({"length_m":1.}, {"length_m":-1.}),
    ({"length_m":1.}, {"length_m":0.}),
])
def test_invalid_or_incomplete_objective_never_enters_finite_master(objective,weights):
    with pytest.raises(ValueError):
        reported_route_cost(objective,weights)
