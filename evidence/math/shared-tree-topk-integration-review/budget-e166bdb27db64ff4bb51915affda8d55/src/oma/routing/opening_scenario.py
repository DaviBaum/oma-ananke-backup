"""Explicit local geometric permission for one bounded architectural opening.

This declaration is an immutable scenario input, not structural/fire approval.
Native host eligibility, subtraction and all affected route checks are separate.
"""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from oma.models import Bounds, Model

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class OpeningPermission(Model):
    mode: Literal["EXPLICIT_USER_GEOMETRIC_EDIT"]
    statement: Annotated[str, Field(min_length=10, max_length=4000)]
    evidence_roots: tuple[Hash, ...] = ()
    engineering_scope: Literal["SCENARIO_GEOMETRY_ONLY"]


class AuthorizedOpening(Model):
    source_sha256: Hash
    host_guid: Annotated[str, Field(min_length=1, max_length=64)]
    host_step_id: Annotated[int, Field(gt=0)]
    host_geometry_root: Hash
    opening_bounds_local_m: Bounds
    allowed_opening_bounds_local_m: Bounds
    through_axis: Literal[0, 1, 2]
    permission: OpeningPermission

    @model_validator(mode="after")
    def permitted_volume(self):
        opening, allowed = self.opening_bounds_local_m, self.allowed_opening_bounds_local_m
        if any(hi <= lo for lo, hi in zip(opening.min, opening.max)):
            raise ValueError("An opening needs three strictly positive dimensions")
        if any(lo < limit_lo or hi > limit_hi for lo, hi, limit_lo, limit_hi in
               zip(opening.min, opening.max, allowed.min, allowed.max)):
            raise ValueError("The complete proposed opening must fit inside the explicitly allowed local volume")
        return self
