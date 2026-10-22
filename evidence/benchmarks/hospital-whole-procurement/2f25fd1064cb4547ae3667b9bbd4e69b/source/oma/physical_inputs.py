"""Fresh byte applicability at physical PASS publication and acceptance.

Call while holding the Store publication transaction so relocation aliases and
the original baseline cannot change during the sweep. This checks bytes, not
geometry, and does not claim atomicity against arbitrary filesystem writers.
"""
from __future__ import annotations

import hashlib
import os
import time

from .store import IntegrityError, digest, utcnow


PHYSICAL_KINDS = {"physical_route", "physical_route_set", "physical_network", "baseline_check"}


def check_current_physical_inputs(store, candidate, state, baseline, *, deadline=None):
    records = [*state.get("routes", []), *state.get("physical_networks", [])]
    if (candidate.get("kind") not in PHYSICAL_KINDS and not state.get("sources")
            and not any(record.get("geometry_artifact") for record in records)):
        return None  # Explicit analytic protocol fixtures have no physical files.
    if not state.get("sources"):
        raise IntegrityError("Physical input applicability has no complete original IFC source set")
    files = {}
    def add(value, expected, reference):
        if (not isinstance(value, str) or not value or not isinstance(expected, str)
                or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected)):
            raise IntegrityError("Physical input applicability has an incomplete path/hash binding")
        path = store.resolve_path(value).resolve()
        if path in files and files[path]["sha256"] != expected:
            raise IntegrityError("Physical input applicability binds one current file to conflicting hashes")
        files.setdefault(path, {"path": str(path), "sha256": expected, "references": []})["references"].append(reference)
    try:
        for label, current in (("current", state), ("protected-baseline", baseline)):
            for source in current.get("sources", []):
                add(source["immutable_path"], source["sha256"], f"{label}:source:{source['id']}")
            for record in [*current.get("routes", []), *current.get("physical_networks", [])]:
                material = store.get(record["geometry_artifact"])
                add(material["export_path"], material["export_sha256"], f"{label}:materialization:{record['id']}")
        if not files:
            raise IntegrityError("Physical input applicability has an empty file denominator")
        for path, row in sorted(files.items(), key=lambda pair: str(pair[0])):
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                before = os.fstat(stream.fileno())
                while True:
                    if deadline is not None and time.monotonic() >= deadline:
                        raise IntegrityError("Verification deadline expired during current physical input validation")
                    chunk = stream.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                after = os.fstat(stream.fileno())
                current_path = path.stat()
            identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            if identity(before) != identity(after) or identity(after) != identity(current_path) or hasher.hexdigest() != row["sha256"]:
                raise IntegrityError("Current physical input bytes changed after the independent check: " + str(path))
            row["bytes"] = after.st_size
    except (OSError, KeyError, TypeError) as exc:
        raise IntegrityError("Current physical input bytes are missing or their bindings are incomplete: " + str(exc)) from exc
    return {"schema": "oma.current-physical-input-bytes/1", "candidate_id": candidate["id"],
        "candidate_root": candidate["state_root"], "baseline_root": digest(baseline), "checked_at": utcnow(),
        "files": list(files.values()), "file_count": len(files), "all_expected_hashes_match": True,
        "native_geometry_rechecked": False, "arbitrary_filesystem_mutations_locked_out": False}
