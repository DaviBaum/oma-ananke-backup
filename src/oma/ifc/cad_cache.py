"""Immutable, digest-validated checker native-source cache (never verdict cache)."""
from __future__ import annotations

from dataclasses import asdict
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import time
import sys
import uuid

import numpy as np

from .audit import atomic_json, sha256_file

CODE_SHA256 = sha256_file(__file__)


def _key(source,guids,source_representation_policy):
    from . import cad, enclosure
    return {"source_sha256":sha256_file(source),"guids":sorted(guids) if guids is not None else None,
            "cad_code_sha256":cad.CODE_SHA256,"enclosure_code_sha256":enclosure.CODE_SHA256,"cache_code_sha256":CODE_SHA256,
            "ifcopenshell_version":importlib.metadata.version("ifcopenshell"),
            "python_version":sys.version,"numpy_version":np.__version__,
            "ocp_version":importlib.metadata.version("cadquery-ocp"),"format":"checker-native-source-cache/1",
            "geometry_policy":{"world_coordinates":True,"canonical_unit":"m","sewing_tolerance_m":1e-7,"source_representation_policy":source_representation_policy}}


def _same_native_applicability(previous, current):
    """Only enclosure and cache-reader changes permit native-artifact reuse.

    CAD conversion/promotion code, immutable source, complete selected product
    set, Python/native versions, units and every geometry parameter must match.
    The current reader revalidates every BRep and reconstructs source support.
    """
    if previous.get("format") != "checker-native-source-cache/1":
        return False
    ignored = {"enclosure_code_sha256", "cache_code_sha256"}
    return ({k:v for k,v in previous.items() if k not in ignored}
            == {k:v for k,v in current.items() if k not in ignored})


def load_or_build(source,*,guids,threads,directory,report,build,source_representation_policy,checkpoint=None):
    from OCP.BRepTools import BRepTools
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Shape
    from .cad import CadObject,_inspect_shape,CACHE_TRUST
    start=time.perf_counter()
    key=_key(source,guids,source_representation_policy)
    root=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
    directory=Path(directory)
    entry=directory / "entries" / root
    manifest_path=entry / "manifest.json"
    manifest_hash=entry / "manifest.sha256"
    disposition="MISS"
    invalid_reason=None
    objects=None
    errors=None
    migration_from=None
    read_path,read_hash=manifest_path,manifest_hash
    if not manifest_path.exists() or not manifest_hash.exists():
        # A different source/kernel/CAD policy is never a migration candidate.
        # An old enclosure certificate is not adopted, even if its bounds look
        # unchanged. The current implementation recomputes every invalid source
        # product below and publishes a new complete applicability manifest.
        for prior in sorted((directory / "entries").glob("*/manifest.json"),key=lambda p:p.stat().st_mtime,reverse=True):
            prior_hash=prior.with_name("manifest.sha256")
            try:
                raw=prior.read_bytes()
                if not prior_hash.exists() or hashlib.sha256(raw).hexdigest()!=prior_hash.read_text().strip():
                    continue
                previous=json.loads(raw)
                if _same_native_applicability(previous["key"],key):
                    read_path,read_hash=prior,prior_hash
                    migration_from=prior.parent.name
                    break
            except (OSError,ValueError,KeyError,TypeError):
                continue
    checkpoint_error=None
    def consistent_checkpoint(stage):
        nonlocal checkpoint_error
        if checkpoint:
            try:
                checkpoint(stage)
            except BaseException as exc:
                checkpoint_error=exc
                raise
    if read_path.exists() and read_hash.exists():
        try:
            raw=read_path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=read_hash.read_text().strip():
                raise ValueError("Cache manifest digest mismatch")
            manifest=json.loads(raw)
            if manifest["key"]!=key and not (migration_from and _same_native_applicability(manifest["key"],key)):
                raise ValueError("Cache applicability key mismatch")
            import ifcopenshell
            model=ifcopenshell.open(str(source))
            expected={e.id():e for e in model.by_type("IfcElement") if not e.is_a("IfcFeatureElementSubtraction")
                      and (guids is None or e.GlobalId in guids)}
            accounted={i["metadata"]["step_id"] for i in manifest["objects"]}
            if len(accounted)!=len(manifest["objects"]):
                raise ValueError("Duplicate cached source object identities")
            accounted.update(int(e["entity_id"].rsplit(":",1)[1]) for e in manifest["errors"] if e.get("entity_id"))
            assemblies={e.id() for e in expected.values() if e.Representation is None and
                        any(r.RelatedObjects for r in getattr(e,"IsDecomposedBy",()))}
            if accounted|assemblies != set(expected):
                raise ValueError("Cached physical object accounting differs from original source")
            objects=[]
            native_bounds={}
            for item in manifest["objects"]:
                consistent_checkpoint("cad_cache_native_object")
                stored=directory / "objects" / (item["brep_sha256"]+".brep.gz")
                compressed=stored.read_bytes()
                if hashlib.sha256(compressed).hexdigest()!=item["compressed_sha256"]:
                    raise ValueError("Native BRep compressed digest mismatch")
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as bounded_stream:
                    raw_shape=bounded_stream.read(128*1024*1024+1)
                if len(raw_shape)>128*1024*1024 or hashlib.sha256(raw_shape).hexdigest()!=item["brep_sha256"]:
                    raise ValueError("Native BRep digest/size mismatch")
                shape=TopoDS_Shape()
                BRepTools.Read_s(shape,io.BytesIO(raw_shape),BRep_Builder())
                bounds,volume,tolerance,valid,reason=_inspect_shape(shape)
                # Recompute native validity, not a persisted Boolean PASS flag.
                metadata=item["metadata"]
                original=expected.get(metadata["step_id"])
                if original is None or original.GlobalId!=metadata["guid"] or original.is_a()!=metadata["ifc_type"]:
                    raise ValueError("Cached object identity does not match original source")
                if (metadata["source_sha256"]!=key["source_sha256"]
                        or metadata["entity_id"]!=f"{key['source_sha256']}:{original.id()}"):
                    raise ValueError("Cached source identity/hash binding differs from original source")
                expected_native_valid=(metadata.get("support_evidence") or {}).get("native_topology_valid",metadata["valid"])
                if valid != expected_native_valid:
                    raise ValueError("Cached topology disposition differs from fresh kernel validation")
                if valid and metadata["support_kind"] != "exact_source_support_enclosure" and (not np.isclose(volume,metadata["volume_m3"],atol=1e-10,rtol=1e-10)
                              or not np.allclose(bounds,metadata["bounds"],atol=1e-10,rtol=0)):
                    raise ValueError("Cached geometry volume/bounds differs on reload")
                # Exact source-enclosure certificates are independently rebuilt
                # from source bytes below, not adopted from metadata alone.
                obj=CadObject(shape=shape,**metadata)
                obj.volume_m3=volume
                obj.kernel_tolerance_m=tolerance
                obj.bounds=bounds
                native_bounds[obj.step_id]=bounds
                objects.append(obj)
            enclosed=[o for o in objects if not o.valid] if migration_from else [o for o in objects if o.support_kind=="exact_source_support_enclosure"]
            if enclosed:
                from .enclosure import ExactIfcEncloser
                encloser=ExactIfcEncloser(source,model,vertex_hull_completion=source_representation_policy == "NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES")
                for obj in enclosed:
                    consistent_checkpoint("cad_cache_exact_enclosure")
                    rechecked=encloser.enclose_product(model.by_id(obj.step_id))
                    if migration_from:
                        obj.support_evidence=dict(obj.support_evidence or {})
                        obj.support_evidence["exact_source_enclosure"]=rechecked
                        obj.bounds=native_bounds[obj.step_id]
                        obj.support_kind="unresolved_native_support"
                    elif rechecked!=obj.support_evidence["exact_source_enclosure"]:
                        raise ValueError("Source enclosure certificate differs from cold rational recomputation")
                    if rechecked["status"]=="ENCLOSURE_CHECKED":
                        from fractions import Fraction
                        lo,hi=rechecked["bounds_m"]
                        obj.bounds=tuple(np.nextafter(float(Fraction(v)),-np.inf) for v in lo)+tuple(np.nextafter(float(Fraction(v)),np.inf) for v in hi)
                        obj.support_kind="exact_source_support_enclosure"
            if not migration_from:
                if report is not None:
                    report.update(status="HIT_REVALIDATED",key=root,seconds=time.perf_counter()-start,objects=len(objects),cache_trust=CACHE_TRUST)
                return objects,manifest["errors"]
            errors=manifest["errors"]
            disposition="REUSED_NATIVE_RECHECKED_SOURCE_SUPPORT"
        except Exception as exc:
            if exc is checkpoint_error:
                raise
            disposition="CORRUPT_REBUILT"
            invalid_reason=f"{type(exc).__name__}: {exc}"
            objects=None
    if objects is None:
        objects,errors=build(source,guids=guids,threads=threads,source_representation_policy=source_representation_policy,checkpoint=checkpoint)
    stored=[]
    blobs=directory / "objects";blobs.mkdir(parents=True,exist_ok=True)
    for obj in sorted(objects,key=lambda o:o.step_id):
        consistent_checkpoint("cad_cache_publish_object")
        if obj.shape is None:
            raise ValueError("A transformed enclosure-only object cannot be published as native source geometry")
        stream=io.BytesIO(); BRepTools.Write_s(obj.shape,stream);raw=stream.getvalue()
        sha=hashlib.sha256(raw).hexdigest();compressed=gzip.compress(raw,compresslevel=3,mtime=0)
        destination=blobs / (sha+".brep.gz")
        if not destination.exists() or hashlib.sha256(destination.read_bytes()).hexdigest()!=hashlib.sha256(compressed).hexdigest():
            temporary=destination.with_suffix(".tmp-"+uuid.uuid4().hex)
            temporary.write_bytes(compressed);temporary.replace(destination)
        metadata={k:v for k,v in obj.__dict__.items() if k!="shape"}
        stored.append({"metadata":metadata,"brep_sha256":sha,"compressed_sha256":hashlib.sha256(compressed).hexdigest()})
    manifest_path.parent.mkdir(parents=True,exist_ok=True)
    temporary=manifest_path.with_suffix(".tmp-"+uuid.uuid4().hex)
    temporary.write_text(json.dumps({"key":key,"objects":stored,"errors":errors,"cache_trust":CACHE_TRUST},allow_nan=False),encoding="utf-8")
    temporary.replace(manifest_path)
    manifest_hash.write_text(sha256_file(manifest_path),encoding="ascii")
    if report is not None:
        report.update(status=disposition,key=root,seconds=time.perf_counter()-start,objects=len(objects),invalid_reason=invalid_reason,
                      native_artifact_source_key=migration_from if disposition=="REUSED_NATIVE_RECHECKED_SOURCE_SUPPORT" else None,cache_trust=CACHE_TRUST)
    return objects,errors
