"""Acceptance must recheck build identity after potentially slow derivations."""
import time

import pytest

from oma import build_identity, project_dependencies
from oma.models import VerificationReport
from oma.store import IntegrityError, Store, digest, utcnow


def managed_candidate(tmp_path):
    store = Store(tmp_path/"store")
    project = store.create_project("Acceptance executable boundary",{
        "schema_version":1,"mission":{"rule_hash":"synthetic-publication-rules"}})
    run = store.create_run(project["id"],{"operation":"route","budget_seconds":30})
    candidate = store.add_candidate(run["id"],store.get(project["state_root"]),{"kind":"publication-fixture"})
    version = build_identity.checker_version()
    report = VerificationReport.model_validate({"schema_version":1,"candidate_root":candidate["state_root"],
        "mission_hash":digest(store.get(candidate["state_root"])["mission"]),"rule_hash":"synthetic-publication-rules",
        "checker_version":version,"status":"PASS","scope":"Synthetic publication protocol; no physical claim",
        "objective":{},"created_at":utcnow(),
        "results":[{"id":"fixture","status":"PASS","reason":"Protocol fixture","scope":"Synthetic"}]})
    store.begin_check_execution(candidate["id"],"managed-build-boundary",checker_version=version,deadline=time.monotonic()+30)
    store.finish_check_execution(candidate["id"],"managed-build-boundary",status="COMPLETED",report=report)
    assert store.candidate(candidate["id"])["status"] == "CHECKED"
    return store,project,candidate,version


@pytest.mark.parametrize("change_build",[False,True])
def test_acceptance_build_is_checked_after_actual_derivation_before_commit(tmp_path,monkeypatch,change_build):
    store,project,candidate,version = managed_candidate(tmp_path)
    derive = project_dependencies.derive_transition
    observed = []
    def after_derivation(*args,**kwargs):
        answer = derive(*args,**kwargs)
        assert answer["cold_equivalent"]
        observed.append(kwargs["executable"])
        if change_build:
            # Change the version provider only, never the shared source files.
            other = "oma-independent-checker/2:"+("0" if not version.endswith("0"*64) else "1")*64
            monkeypatch.setattr(build_identity,"checker_version",lambda:other)
        return answer
    monkeypatch.setattr(project_dependencies,"derive_transition",after_derivation)
    before_events = store.events(project["id"],limit=1000)
    if change_build:
        with pytest.raises(IntegrityError,match="[Ee]xecutable|[Cc]hecker|[Bb]uild"):
            store.accept(project["id"],candidate["id"],0,"build-race",checker_version=version)
        assert store.project(project["id"])["revision"] == 0
        assert len(store.history(project["id"])) == 1
        assert store.events(project["id"],limit=1000) == before_events
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM requests WHERE project_id=? AND key='build-race'",(project["id"],)).fetchone()[0] == 0
    else:
        accepted = store.accept(project["id"],candidate["id"],0,"build-race",checker_version=version)
        assert accepted["status"] == "ACCEPTED" and accepted["revision"] == 1
    assert observed == [version]
