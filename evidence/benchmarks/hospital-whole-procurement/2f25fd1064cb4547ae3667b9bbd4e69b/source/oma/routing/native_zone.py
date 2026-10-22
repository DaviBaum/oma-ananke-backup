"""Numerical whole-shape containment with explicit native bound evidence."""
import math

from oma.ifc.cad import _has_native_geometry


def check_native_zone(objects, allowed, *, expected_count, errors=(), checkpoint=None):
    """Rebuild tight, tolerance-expanded BRep bounds, independently of meshes.

    OCCT AddOptimal uses precise underlying geometry bounds and numerical
    minimization where necessary. This remains a native numerical contract,
    not exact real-arithmetic enclosure or proof of physical infeasibility.
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from oma.models import Bounds

    # Revalidate even a caller-constructed model_copy, which can bypass normal
    # model validation. Invalid bounds must not turn NaN comparisons into PASS.
    allowed = Bounds.model_validate(allowed.model_dump())
    if type(expected_count) is not int or expected_count < 1:
        raise ValueError("Positive complete native-part count required")

    witness = {"method":"OCCT_ADD_OPTIMAL_NO_TRIANGULATION_WITH_SHAPE_TOLERANCE",
        "allowed_bounds_m":[list(allowed.min),list(allowed.max)],
        "expected_parts":expected_count,"loaded_parts":len(objects),
        "geometry_errors":list(errors),"numerical_allowance_m":1e-6,
        "exact_enclosure_claim":False,"parts":[]}
    failed = bool(errors) or len(objects) != expected_count or len({obj.guid for obj in objects}) != len(objects)
    unknown = False
    for obj in objects:
        if checkpoint:
            checkpoint("native_permitted_zone_bound")
        row = {"ifc_guid":obj.guid,
            "kernel_tolerance_m":obj.kernel_tolerance_m if math.isfinite(obj.kernel_tolerance_m) else None,
            "broad_bounds_m":[x if math.isfinite(x) else None for x in obj.bounds] if obj.bounds is not None else None}
        witness["parts"].append(row)
        if not _has_native_geometry(obj):
            row.update(status="FAIL",reason="VALID_NATIVE_SOLID_REQUIRED")
            failed = True
            continue
        try:
            box = Bnd_Box()
            BRepBndLib.AddOptimal_s(obj.shape,box,False,True)
            if box.IsVoid() or box.IsOpen():
                raise ValueError("Finite complete native bounds unavailable")
            lower, upper = box.CornerMin(), box.CornerMax()
            bounds = [math.nextafter(x,-math.inf) for x in (lower.X(),lower.Y(),lower.Z())]+[
                math.nextafter(x,math.inf) for x in (upper.X(),upper.Y(),upper.Z())]
            if not all(math.isfinite(x) for x in bounds) or any(bounds[i]>bounds[i+3] for i in range(3)):
                raise ValueError("Nonfinite or reversed native bounds")
            gaps = [bounds[i]-allowed.min[i] for i in range(3)]+[allowed.max[i]-bounds[i+3] for i in range(3)]
            minimum = min(gaps)
            threshold = 1e-6 + obj.kernel_tolerance_m
            status = "FAIL" if minimum < 0 else "UNKNOWN" if minimum <= threshold else "PASS"
            row.update(status=status,optimal_bounds_m=bounds,face_gaps_m=gaps,
                minimum_gap_m=minimum,required_gap_exclusive_m=threshold)
            failed |= status == "FAIL"
            unknown |= status == "UNKNOWN"
        except (ValueError,RuntimeError,OverflowError) as error:
            unknown = True
            row.update(status="UNKNOWN",reason=f"NATIVE_BOUND_UNRESOLVED: {type(error).__name__}: {error}")
    if checkpoint:
        checkpoint("native_permitted_zone_complete")
    return {"status":"FAIL" if failed else "UNKNOWN" if unknown else "PASS","witness":witness}
