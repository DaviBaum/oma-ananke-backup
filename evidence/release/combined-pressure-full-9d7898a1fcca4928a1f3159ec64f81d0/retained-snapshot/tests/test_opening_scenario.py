import copy

import pytest
from pydantic import ValidationError

from oma.routing.opening_scenario import AuthorizedOpening


def request():
    return {"source_sha256": "a" * 64, "host_guid": "fixture-host", "host_step_id": 21,
        "host_geometry_root": "b" * 64, "through_axis": 2,
        "opening_bounds_local_m": {"min": [-.2, -.2, -.05], "max": [.2, .2, .35]},
        "allowed_opening_bounds_local_m": {"min": [-.3, -.3, -.1], "max": [.3, .3, .4]},
        "permission": {"mode": "EXPLICIT_USER_GEOMETRIC_EDIT", "statement": "Permit this scenario's bounded geometric opening only",
            "engineering_scope": "SCENARIO_GEOMETRY_ONLY", "evidence_roots": []}}


def test_opening_permission_is_explicit_and_never_an_engineering_approval():
    parsed = AuthorizedOpening.model_validate(request())
    assert parsed.permission.engineering_scope == "SCENARIO_GEOMETRY_ONLY"
    assert AuthorizedOpening.model_validate(parsed.model_dump(mode="json")) == parsed
    for field in ("permission", "host_geometry_root", "source_sha256"):
        missing = request()
        missing.pop(field)
        with pytest.raises(ValidationError):
            AuthorizedOpening.model_validate(missing)
    promoted = request()
    promoted["permission"]["engineering_scope"] = "STRUCTURAL_APPROVAL"
    with pytest.raises(ValidationError):
        AuthorizedOpening.model_validate(promoted)


@pytest.mark.parametrize("point", [[.31, .2, .35], [.2, .2, .41], [.2, .2, float("nan")]])
def test_whole_opening_must_fit_declared_permission_volume(point):
    raw = request()
    raw["opening_bounds_local_m"]["max"] = point
    with pytest.raises(ValidationError):
        AuthorizedOpening.model_validate(raw)


def test_zero_thickness_and_unrecorded_permission_fields_are_rejected():
    raw = request()
    raw["opening_bounds_local_m"]["max"][0] = -.2
    with pytest.raises(ValidationError):
        AuthorizedOpening.model_validate(raw)
    raw = copy.deepcopy(request())
    raw["permission"]["approve_all_future_openings"] = True
    with pytest.raises(ValidationError):
        AuthorizedOpening.model_validate(raw)
