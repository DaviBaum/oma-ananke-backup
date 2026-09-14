"""Finite grounded assurance, with complete antichains and replayable witnesses.

Original ANANKE Prompt 11, ASS evidence/cores/cuts. A proof is conditional on
the supplied inference theory and explicit foundations. Authentic bytes do not
establish technical truth. A cycle without a grounded premise proves nothing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from typing import Literal

from .store import digest


@dataclass(frozen=True)
class Claim:
    id: str
    statement: str
    scope: str


@dataclass(frozen=True)
class Foundation:
    id: str
    claims: tuple[str, ...]
    kind: Literal["EVIDENCE", "ASSUMPTION", "TCB"]
    bindings: dict[str, str]
    description: str
    valid_from: str | None = None
    valid_until: str | None = None
    time_basis: Literal["ASSESSMENT_TIME", "OBSERVATION_TIME"] = "ASSESSMENT_TIME"
    observed_at: str | None = None


@dataclass(frozen=True)
class Inference:
    id: str
    conclusion: str
    premises: tuple[str, ...]
    justification: str


@dataclass(frozen=True)
class Theory:
    claims: tuple[Claim, ...]
    foundations: tuple[Foundation, ...]
    inferences: tuple[Inference, ...]
    targets: tuple[str, ...]

    def validate(self):
        for records in (self.claims, self.foundations, self.inferences):
            if len({r.id for r in records}) != len(records) or any(not r.id for r in records):
                raise ValueError("Assurance identities must be unique and nonempty within their type")
        claims = {c.id for c in self.claims}
        if not self.targets or not set(self.targets) <= claims:
            raise ValueError("Nonempty targets must name declared claims")
        for foundation in self.foundations:
            if (not foundation.claims or not set(foundation.claims) <= claims
                    or foundation.kind not in {"EVIDENCE", "ASSUMPTION", "TCB"}
                    or foundation.time_basis not in {"ASSESSMENT_TIME", "OBSERVATION_TIME"}):
                raise ValueError("Invalid foundation")
        for rule in self.inferences:
            if (not rule.premises or len(set(rule.premises)) != len(rule.premises)
                    or rule.conclusion not in claims or not set(rule.premises) <= claims):
                raise ValueError("Inference requires nonempty distinct declared premises")
        return self


def _instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Assurance time requires an explicit time zone")
    return parsed


def applicability(foundation, family, authenticated, assessment_time):
    """Every member of an explicitly enumerated family must match every binding.

    No missing key is a wildcard. A validity interval is [from, until).
    Observation-time calibration remains usable after its later expiry, unless
    its attestation is revoked or a different assessment policy is selected.
    """
    if foundation.id not in authenticated:
        return "UNAUTHENTICATED_OR_REVOKED"
    if not family or any(dict(context) != foundation.bindings for context in family):
        return "INAPPLICABLE_CONTEXT"
    try:
        clock = foundation.observed_at if foundation.time_basis == "OBSERVATION_TIME" else assessment_time
        now = _instant(clock)
        if foundation.observed_at and _instant(foundation.observed_at) > _instant(assessment_time):
            return "OBSERVATION_NOT_YET_AVAILABLE"
        if foundation.valid_from and now < _instant(foundation.valid_from):
            return "BEFORE_VALIDITY"
        if foundation.valid_until and now >= _instant(foundation.valid_until):
            return "EXPIRED"
        if foundation.valid_from and foundation.valid_until and _instant(foundation.valid_from) >= _instant(foundation.valid_until):
            return "INVALID_VALIDITY_INTERVAL"
    except (TypeError, AttributeError, ValueError):
        return "INVALID_TIME_EVIDENCE"
    return "APPLICABLE"


class _Budget(Exception):
    pass


class _Counter:
    def __init__(self, maximum):
        if type(maximum) is not int or maximum < 1:
            raise ValueError("A positive finite assurance work budget is required")
        self.maximum, self.used = maximum, 0

    def tick(self):
        self.used += 1
        if self.used > self.maximum:
            raise _Budget


def _minimal(sets):
    ordered = sorted(set(sets), key=lambda s: (len(s), tuple(sorted(s))))
    result = []
    for candidate in ordered:
        if not any(prior <= candidate for prior in result):
            result.append(candidate)
    return result


def _target_cores(frontiers, targets, counter):
    cores = [frozenset()]
    for target in targets:
        expanded = []
        for left, right in product(cores, frontiers[target]):
            counter.tick()
            expanded.append(left | right)
        cores = _minimal(expanded)
    return cores


def solve_assurance(theory, family, authenticated, assessment_time, *, max_work=100_000):
    theory.validate()
    counter = _Counter(max_work)
    frontiers = {claim.id: {} for claim in theory.claims}
    steps, complete = [], True
    excluded = {f.id: status for f in theory.foundations
                if (status := applicability(f, family, authenticated, assessment_time)) != "APPLICABLE"}

    def insert(claim, support, proof):
        if any(prior <= support for prior in frontiers[claim]):
            return False
        for prior in tuple(frontiers[claim]):
            if support < prior:
                del frontiers[claim][prior]
        step = {"claim": claim, "support": sorted(support), **proof}
        step["id"] = digest(step)
        steps.append(step)
        frontiers[claim][support] = step["id"]
        return True

    try:
        for foundation in theory.foundations:
            if foundation.id in excluded:
                continue
            for claim in foundation.claims:
                counter.tick()
                insert(claim, frozenset({foundation.id}), {"foundation": foundation.id})
        changed = True
        while changed:
            changed = False
            for rule in theory.inferences:
                # Snapshot avoids mutating a cyclic premise during iteration.
                families = [list(frontiers[p].items()) for p in rule.premises]
                for combination in product(*families):
                    counter.tick()
                    support = frozenset().union(*(s for s, _ in combination))
                    changed |= insert(rule.conclusion, support, {"inference": rule.id,
                        "premises": [node for _, node in combination]})
        cores = _target_cores(frontiers, theory.targets, counter)
    except _Budget:
        complete, cores = False, []
    encoded = {claim: [{"support": sorted(support), "step": step}
                      for support, step in sorted(values.items(), key=lambda p: (len(p[0]), tuple(sorted(p[0]))))]
               for claim, values in sorted(frontiers.items())}
    return {"theory_hash": digest(asdict(theory)), "family_hash": digest(family),
            "assessment_time": assessment_time, "complete": complete,
            "status": "SUPPORTED_CONDITIONALLY" if cores else "UNSUPPORTED" if complete else "UNKNOWN_BUDGET",
            "frontiers": encoded, "steps": steps, "cores": [sorted(c) for c in cores],
            "excluded_foundations": excluded, "work": min(counter.used, max_work),
            "claim_scope": "Only listed targets under the supplied inference theory and foundation assumptions"}


def verify_assurance(theory, family, authenticated, assessment_time, certificate, *, max_work=200_000):
    """Replay grounded steps and check antichain closure; never run refinement.

    Grounded witnesses give one inclusion in the least fixed point. Coverage of
    all applicable leaves and all premise combinations gives the reverse one.
    Thus COMPLETE is independently checked rather than trusted from the producer.
    """
    try:
        theory.validate()
        counter = _Counter(max_work)
        if (certificate["theory_hash"] != digest(asdict(theory)) or certificate["family_hash"] != digest(family)
                or certificate["assessment_time"] != assessment_time):
            return {"status": "FAIL", "reason": "Theory, context family or assessment time mismatch"}
        foundations = {f.id: f for f in theory.foundations}
        rules = {r.id: r for r in theory.inferences}
        applicable = {f.id for f in theory.foundations if applicability(f, family, authenticated, assessment_time) == "APPLICABLE"}
        expected_excluded = {f.id: applicability(f, family, authenticated, assessment_time)
                             for f in theory.foundations if f.id not in applicable}
        if certificate["excluded_foundations"] != expected_excluded:
            raise ValueError("Incorrect applicability ledger")
        proofs = {}
        for raw in certificate["steps"]:
            counter.tick()
            step = dict(raw)
            identifier = step.pop("id")
            if identifier in proofs or identifier != digest(step):
                raise ValueError("Changed or duplicate derivation witness")
            support = frozenset(step["support"])
            if not support or len(support) != len(step["support"]):
                raise ValueError("Empty or repeated foundation")
            if "foundation" in step:
                atom = foundations[step["foundation"]]
                if atom.id not in applicable or step["claim"] not in atom.claims or support != {atom.id}:
                    raise ValueError("Invalid direct foundation")
            else:
                rule = rules[step["inference"]]
                premises = [proofs[p] for p in step["premises"]]
                if (step["claim"] != rule.conclusion or [p[0] for p in premises] != list(rule.premises)
                        or support != frozenset().union(*(p[1] for p in premises))):
                    raise ValueError("Invalid grounded inference")
            proofs[identifier] = step["claim"], support
        if set(certificate["frontiers"]) != {c.id for c in theory.claims}:
            raise ValueError("Missing claim frontier")
        fronts = {}
        for claim, records in certificate["frontiers"].items():
            sets = []
            for record in records:
                counter.tick()
                support = frozenset(record["support"])
                if proofs[record["step"]] != (claim, support):
                    raise ValueError("Frontier does not have its grounded witness")
                sets.append(support)
            if len(_minimal(sets)) != len(sets):
                raise ValueError("Frontier is not an antichain")
            fronts[claim] = sets
        if not certificate["complete"]:
            if certificate["status"] != "UNKNOWN_BUDGET" or certificate["cores"]:
                raise ValueError("Incomplete closure cannot assert complete cores")
            return {"status": "UNKNOWN", "reason": "Grounded partial witnesses replay, completeness not established"}
        for atom in theory.foundations:
            if atom.id in applicable:
                for claim in atom.claims:
                    if not any(s <= {atom.id} for s in fronts[claim]):
                        raise ValueError("Missing direct support")
        for rule in theory.inferences:
            for premise_sets in product(*(fronts[p] for p in rule.premises)):
                counter.tick()
                union = frozenset().union(*premise_sets)
                if not any(s <= union for s in fronts[rule.conclusion]):
                    raise ValueError("Frontier is not closed under an admitted inference")
        cores = _target_cores(fronts, theory.targets, counter)
        if certificate["cores"] != [sorted(c) for c in cores]:
            raise ValueError("Target core family differs from full conjunction")
        expected = "SUPPORTED_CONDITIONALLY" if cores else "UNSUPPORTED"
        if certificate["status"] != expected:
            raise ValueError("False support status")
        return {"status": "PASS", "reason": "Grounded witnesses and complete finite antichain closure verified", "work": counter.used}
    except _Budget:
        return {"status": "UNKNOWN", "reason": "Independent assurance checker budget exhausted"}
    except (ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"status": "FAIL", "reason": "Malformed or unsound assurance certificate"}


def evidence_cuts(theory, certificate, *, max_work=100_000):
    """Minimal external-evidence hitting sets, not sufficient repair plans.

    Trust assumptions remain displayed in cores but are excluded from these
    cuts. An evidence-free proof means no external-evidence cut can disable it.
    Call only after independent verification of the input certificate.
    """
    if not certificate["complete"]:
        return {"status": "UNKNOWN", "cuts": [], "reason": "Complete core family required"}
    if not certificate["cores"]:
        return {"status": "NOT_APPLICABLE", "cuts": [], "reason": "Targets currently lack support"}
    evidence = {f.id for f in theory.foundations if f.kind == "EVIDENCE"}
    family = [set(core) & evidence for core in certificate["cores"]]
    if any(not core for core in family):
        return {"status": "NO_EXTERNAL_EVIDENCE_CUT", "cuts": [], "reason": "A core contains only trusted assumptions"}
    counter, cuts = _Counter(max_work), [frozenset()]
    try:
        for core in family:
            expanded = []
            for cut in cuts:
                if cut & core:
                    expanded.append(cut)
                else:
                    for atom in sorted(core):
                        counter.tick()
                        expanded.append(cut | {atom})
            cuts = _minimal(expanded)
        return {"status": "COMPLETE", "cuts": [sorted(c) for c in cuts],
                "meaning": "Revoking every item in a cut disables all currently grounded target proofs; resolving it is not a repair guarantee"}
    except _Budget:
        return {"status": "UNKNOWN", "cuts": [], "reason": "Cut enumeration budget exhausted"}
