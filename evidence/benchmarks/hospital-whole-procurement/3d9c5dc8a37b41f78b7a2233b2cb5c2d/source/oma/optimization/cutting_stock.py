"""Exact-quantity procurement packing; no routing, fabrication or code approval.

Every requested piece is preserved without splicing. Compatibility groups and
stock availability are caller assertions. One kerf is charged per piece, even
when a piece could consume an uncut stock length; end_trim_m is the TOTAL trim
allowance per purchased bar. The default comparison is pooled FFD versus pooled
packing, with optional per-batch procurement shown as a separate scenario.
"""
from __future__ import annotations

from bisect import bisect_left, insort
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
import time

from .master import rational


SCHEMA = "oma.cutting-stock/1"


def _num(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Fraction)):
        raise ValueError(f"{name} must be an exact finite scalar")
    if isinstance(value, str) and len(value) > 256:
        raise ValueError(f"{name} numeric encoding too long")
    try:
        n = rational(value)
    except (ValueError, ZeroDivisionError, OverflowError, TypeError) as exc:
        raise ValueError(f"{name} must be an exact finite scalar") from exc
    if max(abs(n.numerator).bit_length(), n.denominator.bit_length()) > 2048:
        raise ValueError(f"{name} numeric encoding too large")
    if n < 0 or (positive and n == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return n


def _label(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{name} must be a nonempty bounded string")
    return value


def _normalise(pieces, stocks, kerf_m, end_trim_m, currency):
    if not isinstance(pieces, (list, tuple)) or not pieces or len(pieces) > 200_000:
        raise ValueError("Provide 1..200000 individually identified required pieces")
    if not isinstance(stocks, (list, tuple)) or not stocks or len(stocks) > 50_000:
        raise ValueError("Provide 1..50000 stock catalogue entries")
    kerf, trim = _num(kerf_m, "kerf_m"), _num(end_trim_m, "end_trim_m")
    pp, ss, ids = [], [], set()
    for raw in pieces:
        if not isinstance(raw, dict) or set(raw) - {"id", "source_id", "group", "length_m", "batch_id"}:
            raise ValueError("Unsupported piece fields")
        p = {k: _label(raw.get(k), k) for k in ("id", "source_id", "group")}
        p["length_m"] = _num(raw.get("length_m"), "length_m", positive=True)
        p["batch_id"] = _label(raw["batch_id"], "batch_id") if "batch_id" in raw else None
        if p["id"] in ids:
            raise ValueError("Duplicate required piece ID")
        ids.add(p["id"])
        pp.append(p)
    ids = set()
    for raw in stocks:
        if not isinstance(raw, dict) or set(raw) - {"id", "group", "length_m", "unit_price", "currency"}:
            raise ValueError("Unsupported stock fields")
        s = {k: _label(raw.get(k), k) for k in ("id", "group")}
        s["length_m"] = _num(raw.get("length_m"), "stock length_m", positive=True)
        s["unit_price"] = None if raw.get("unit_price") is None else _num(raw["unit_price"], "unit_price")
        s["currency"] = raw.get("currency")
        if s["unit_price"] is not None:
            s["currency"] = _label(s["currency"], "currency")
        elif s["currency"] is not None:
            raise ValueError("An unpriced stock must not declare a currency")
        if s["length_m"] <= trim:
            raise ValueError("Stock length must exceed total end trim")
        if s["id"] in ids:
            raise ValueError("Duplicate stock ID")
        ids.add(s["id"])
        ss.append(s)
    priced = [s["unit_price"] is not None for s in ss]
    if any(priced) and not all(priced):
        raise ValueError("Partial stock prices cannot be treated as zero; price all or none")
    units = {s["currency"] for s in ss}
    if len(units) != 1 or (currency is not None and units != {currency}):
        raise ValueError("All stock prices must use one identical declared currency")
    groups = defaultdict(list)
    for s in ss:
        groups[s["group"]].append(s)
    for p in pp:
        if p["group"] not in groups:
            raise ValueError(f"Missing compatible stock for group {p['group']}")
        if p["length_m"] + kerf > max(s["length_m"] - trim for s in groups[p["group"]]):
            raise ValueError(f"Piece {p['id']} exceeds stock capacity; splicing is not inferred")
    pp.sort(key=lambda p: p["id"])
    ss.sort(key=lambda s: s["id"])
    source = {"pieces": [{**p, "length_m": str(p["length_m"])} for p in pp],
              "stock_catalogue": [{**s, "length_m": str(s["length_m"]),
                  "unit_price": None if s["unit_price"] is None else str(s["unit_price"])} for s in ss],
              "kerf_m": str(kerf), "end_trim_m": str(trim), "currency": next(iter(units)),
              "kerf_policy": "ONE_ALLOWANCE_PER_REQUIRED_PIECE", "trim_policy": "TOTAL_PER_BAR"}
    root = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return pp, ss, kerf, trim, source, root


def _stock(load, catalogue, trim, objective):
    feasible = [s for s in catalogue if load + trim <= s["length_m"]]
    return min(feasible, key=lambda s: (s["unit_price"] if objective == "TOTAL_PRICE" else s["length_m"],
                                      s["length_m"], s["id"]))


def _score(bins, catalogue, trim, objective):
    selected = [_stock(b[0], catalogue, trim, objective) for b in bins]
    length = sum((s["length_m"] for s in selected), Fraction())
    primary = sum((s["unit_price"] for s in selected), Fraction()) if objective == "TOTAL_PRICE" else length
    return primary, length, len(bins)


class _Budget:
    def __init__(self, nodes, seconds, checkpoint):
        self.limit, self.used, self.exhausted = nodes, 0, False
        self.deadline = None if seconds is None else time.monotonic() + seconds
        self.checkpoint = checkpoint

    def take(self):
        if self.used >= self.limit or (self.deadline is not None and time.monotonic() >= self.deadline):
            self.exhausted = True
            return False
        self.used += 1
        if self.checkpoint is not None and self.used % 256 == 1:
            self.checkpoint()
        return True


def _greedy(pieces, catalogue, kerf, trim, best_fit=False, checkpoint=None):
    """FFD uses a maximum-residual segment tree; BFD a sorted residual index."""
    capacity = max(s["length_m"] - trim for s in catalogue)
    ordered = sorted(pieces, key=lambda p: (-p["length_m"], p["id"]))
    bins, available = [], []
    width = 1 << (len(ordered) - 1).bit_length()
    tree = [Fraction(-1)] * (width * 2)
    for number, p in enumerate(ordered):
        if checkpoint is not None and number % 512 == 0:
            checkpoint()
        w = p["length_m"] + kerf
        if best_fit:
            index = bisect_left(available, (w, -1))
            b = available.pop(index)[1] if index < len(available) else len(bins)
        elif tree[1] < w:
            b = len(bins)
        else:
            node = 1
            while node < width:
                node = 2 * node if tree[2 * node] >= w else 2 * node + 1
            b = node - width
        if b == len(bins):
            bins.append([Fraction(), []])
        bins[b][0] += w
        bins[b][1].append(p)
        free = capacity - bins[b][0]
        if best_fit:
            insort(available, (free, b))
        else:
            node = width + b
            tree[node] = free
            while node > 1:
                node //= 2
                tree[node] = max(tree[2 * node], tree[2 * node + 1])
    return bins


def _lower_bound(pieces, catalogue, kerf, trim, objective):
    total = sum((p["length_m"] + kerf for p in pieces), Fraction())
    capacity = max(s["length_m"] - trim for s in catalogue)
    count = math.ceil(total / capacity)
    length = max(total + count * trim, count * min(s["length_m"] for s in catalogue))
    if len({s["length_m"] for s in catalogue}) == 1:
        length = count * catalogue[0]["length_m"]
    primary = length
    if objective == "TOTAL_PRICE":
        primary = max(total * min(s["unit_price"] / (s["length_m"] - trim) for s in catalogue),
                      count * min(s["unit_price"] for s in catalogue))
        if len({(s["length_m"], s["unit_price"]) for s in catalogue}) == 1:
            primary = count * catalogue[0]["unit_price"]
    return {"stock_count": count, "purchased_length_m": str(length), "primary_objective": str(primary),
            "derivation": "TOTAL_PIECE_PLUS_KERF_OVER_MAX_USABLE_CAPACITY_AND_MIN_STOCK_COST_DENSITY"}


def _exact(pieces, catalogue, kerf, trim, objective, incumbent, budget, max_nodes):
    """Enumerate unlabeled feasible partitions; stock choice is exact for each bin."""
    ordered = sorted(pieces, key=lambda p: (-p["length_m"], p["id"]))
    capacity = max(s["length_m"] - trim for s in catalogue)
    best = [[b[0], list(b[1])] for b in incumbent]
    score = _score(best, catalogue, trim, objective)
    initial_nodes, complete, memo = budget.used, True, set()
    bins = []

    def visit(i):
        nonlocal best, score, complete
        if budget.used - initial_nodes >= max_nodes or not budget.take():
            complete = False
            return
        if i == len(ordered):
            candidate = _score(bins, catalogue, trim, objective)
            if candidate < score:
                score, best = candidate, [[b[0], list(b[1])] for b in bins]
            return
        state = (i, tuple(sorted(b[0] for b in bins)))
        if state in memo:
            return
        memo.add(state)
        # Adding pieces cannot lower the cheapest feasible stock price or length.
        if _score(bins, catalogue, trim, objective)[0] >= score[0]:
            return
        p = ordered[i]
        w = p["length_m"] + kerf
        seen = set()
        for b in sorted(bins, key=lambda b: -b[0]):
            if b[0] in seen or b[0] + w > capacity:
                continue
            seen.add(b[0])
            b[0] += w
            b[1].append(p)
            visit(i + 1)
            b[1].pop()
            b[0] -= w
            if not complete:
                return
        bins.append([w, [p]])
        visit(i + 1)
        bins.pop()

    visit(0)
    return best, complete, budget.used - initial_nodes


def _subset_repair(incumbent, catalogue, kerf, trim, objective, budget):
    """Bounded local subset-fill heuristic with exact integer capacities.

    At most eight windows of sixteen bins / 128 pieces are reconsidered. Each
    window uses at most 100000 integer capacity cells after exact common-unit
    reduction. Each subset transition consumes one search node. This heuristic
    has no completeness or optimality authority; interrupted windows are
    discarded, and only strictly better complete schedules replace incumbents.
    """
    ordered = sorted(incumbent, key=lambda b: (b[0], tuple(p['id'] for p in b[1])))
    capacity = max(s['length_m'] - trim for s in catalogue)
    result = list(incumbent)
    windows, start = 0, 0
    while start < len(ordered) and windows < 8:
        window, count = [], 0
        for b in ordered[start:start + 16]:
            if count + len(b[1]) > 128:
                break
            window.append(b); count += len(b[1])
        start += max(1, len(window))
        windows += 1
        if len(window) < 2:
            continue
        pieces = sorted((p for b in window for p in b[1]), key=lambda p: (-p['length_m'], p['id']))
        weights = [p['length_m'] + kerf for p in pieces]
        scale = capacity.denominator
        for w in weights:
            scale = math.lcm(scale, w.denominator)
            if scale.bit_length() > 4096:
                break
        else:
            cap = int(capacity * scale)
            integers = [int(w * scale) for w in weights]
            divisor = math.gcd(cap, *integers)
            cap //= divisor
            integers = [w // divisor for w in integers]
            if cap > 100000:
                continue
            remaining = list(zip(pieces, integers))
            candidate = []
            while remaining:
                if not budget.take():
                    return result
                first, anchor = remaining[0]
                target = cap - anchor
                mask = (1 << (target + 1)) - 1
                reachable, prefixes = 1, []
                for _, w in remaining[1:]:
                    if not budget.take():
                        return result
                    prefixes.append(reachable)
                    reachable |= (reachable << w) & mask
                # An exact maximum subset sum for this fixed anchor/window is
                # useful locally, but repeated greedy anchors are not global proof.
                residual = reachable.bit_length() - 1
                chosen = {0}
                for index in range(len(remaining) - 1, 0, -1):
                    before = prefixes[index - 1]
                    if not ((before >> residual) & 1):
                        chosen.add(index)
                        residual -= remaining[index][1]
                assert residual == 0
                selected = [p for i, (p, _) in enumerate(remaining) if i in chosen]
                candidate.append([sum((p['length_m'] + kerf for p in selected), Fraction()), selected])
                remaining = [entry for i, entry in enumerate(remaining) if i not in chosen]
            if _score(candidate, catalogue, trim, objective) < _score(window, catalogue, trim, objective):
                removed = {id(b) for b in window}
                result = [b for b in result if id(b) not in removed] + candidate
    return result


def _encode_plan(group_bins, stocks, kerf, trim, objective, root):
    by_group = defaultdict(list)
    for s in stocks:
        by_group[s["group"]].append(s)
    rows = []
    totals = {k: Fraction() for k in ("required_length_m", "purchased_length_m", "kerf_loss_m",
                                     "trim_loss_m", "offcut_length_m", "total_waste_m")}
    priced = stocks[0]["unit_price"] is not None
    price = Fraction()
    for group, bins in sorted(group_bins.items()):
        for load, pieces in bins:
            s = _stock(load, by_group[group], trim, objective)
            cursor, cuts = trim, []
            for p in sorted(pieces, key=lambda p: p["id"]):
                end = cursor + p["length_m"]
                cuts.append({"piece_id": p["id"], "source_id": p["source_id"],
                             "length_m": str(p["length_m"]), "start_m": str(cursor),
                             "end_m": str(end), "kerf_after_m": str(kerf)})
                cursor = end + kerf
            required = sum((p["length_m"] for p in pieces), Fraction())
            offcut = s["length_m"] - cursor
            rows.append({"id": f"bar-{len(rows) + 1:08d}", "group": group, "stock_id": s["id"],
                         "stock_length_m": str(s["length_m"]), "cuts": cuts,
                         "end_trim_m": str(trim), "offcut_length_m": str(offcut),
                         "unit_price": None if s["unit_price"] is None else str(s["unit_price"])})
            totals["required_length_m"] += required
            totals["purchased_length_m"] += s["length_m"]
            totals["kerf_loss_m"] += len(pieces) * kerf
            totals["trim_loss_m"] += trim
            totals["offcut_length_m"] += offcut
            totals["total_waste_m"] += s["length_m"] - required
            if priced:
                price += s["unit_price"]
    return {"schema": "oma.cut-plan/1", "input_sha256": root, "bins": rows,
            "totals": {**{k: str(v) for k, v in totals.items()}, "stock_count": len(rows),
                       "piece_count": sum(len(b["cuts"]) for b in rows),
                       "total_price": str(price) if priced else None, "currency": stocks[0]["currency"]}}


def verify_cut_plan(pieces, stock_catalogue, plan, *, kerf_m=0, end_trim_m=0, currency=None):
    """Independent exact replay: identity, coverage, position, stock, waste, price.

    This checker never invokes packing or search, and certifies only the supplied
    one-dimensional procurement model. Invalid plans raise ValueError.
    """
    pp, ss, kerf, trim, _, root = _normalise(pieces, stock_catalogue, kerf_m, end_trim_m, currency)
    if not isinstance(plan, dict) or set(plan) != {"schema", "input_sha256", "bins", "totals"}:
        raise ValueError("Malformed cut plan")
    if plan["schema"] != "oma.cut-plan/1" or plan["input_sha256"] != root:
        raise ValueError("Cut plan is not bound to these inputs")
    lookup, catalogue = {p["id"]: p for p in pp}, {s["id"]: s for s in ss}
    seen, bar_ids = set(), set()
    values = {k: Fraction() for k in ("required_length_m", "purchased_length_m", "kerf_loss_m",
                                     "trim_loss_m", "offcut_length_m", "total_waste_m")}
    price, priced = Fraction(), ss[0]["unit_price"] is not None
    if not isinstance(plan["bins"], list) or len(plan["bins"]) > len(pp):
        raise ValueError("Invalid bin collection")
    for b in plan["bins"]:
        if not isinstance(b, dict) or set(b) != {"id", "group", "stock_id", "stock_length_m", "cuts",
                                                "end_trim_m", "offcut_length_m", "unit_price"}:
            raise ValueError("Malformed bin")
        identity = _label(b["id"], "bar id")
        if identity in bar_ids:
            raise ValueError("Duplicate bar ID")
        bar_ids.add(identity)
        _label(b["group"], "bin group")
        _label(b["stock_id"], "stock id")
        if b["stock_id"] not in catalogue:
            raise ValueError("Unknown stock ID")
        stock = catalogue[b["stock_id"]]
        if b["group"] != stock["group"] or _num(b["stock_length_m"], "stock length") != stock["length_m"]:
            raise ValueError("Stock/group substitution")
        if _num(b["end_trim_m"], "end trim") != trim:
            raise ValueError("Changed trim policy")
        if b["unit_price"] != (None if stock["unit_price"] is None else str(stock["unit_price"])):
            raise ValueError("Changed stock price")
        if not isinstance(b["cuts"], list) or not b["cuts"] or len(b["cuts"]) > len(pp):
            raise ValueError("Empty or invalid purchased stock")
        cursor, required = trim, Fraction()
        for c in b["cuts"]:
            if not isinstance(c, dict) or set(c) != {"piece_id", "source_id", "length_m", "start_m", "end_m", "kerf_after_m"}:
                raise ValueError("Malformed cut")
            ident = _label(c["piece_id"], "piece id")
            if ident not in lookup or ident in seen:
                raise ValueError("Unknown or duplicate required piece")
            seen.add(ident)
            p = lookup[ident]
            if p["group"] != b["group"] or p["source_id"] != c["source_id"]:
                raise ValueError("Piece identity or compatibility group changed")
            if _num(c["length_m"], "cut length", positive=True) != p["length_m"]:
                raise ValueError("Required piece length changed")
            if _num(c["start_m"], "cut start") != cursor or _num(c["end_m"], "cut end") != cursor + p["length_m"]:
                raise ValueError("Overlapping, misplaced or missing cut length")
            if _num(c["kerf_after_m"], "cut kerf") != kerf:
                raise ValueError("Kerf policy changed")
            cursor += p["length_m"] + kerf
            required += p["length_m"]
        if cursor > stock["length_m"]:
            raise ValueError("Cuts exceed stock capacity")
        offcut = stock["length_m"] - cursor
        if _num(b["offcut_length_m"], "offcut") != offcut:
            raise ValueError("Incorrect offcut")
        values["required_length_m"] += required
        values["purchased_length_m"] += stock["length_m"]
        values["kerf_loss_m"] += len(b["cuts"]) * kerf
        values["trim_loss_m"] += trim
        values["offcut_length_m"] += offcut
        values["total_waste_m"] += stock["length_m"] - required
        if priced:
            price += stock["unit_price"]
    if seen != set(lookup):
        raise ValueError("Required pieces are missing")
    expected = {**{k: str(v) for k, v in values.items()}, "stock_count": len(bar_ids),
                "piece_count": len(pp), "total_price": str(price) if priced else None,
                "currency": ss[0]["currency"]}
    if (not isinstance(plan["totals"], dict)
            or type(plan["totals"].get("stock_count")) is not int
            or type(plan["totals"].get("piece_count")) is not int
            or plan["totals"] != expected):
        raise ValueError("Cut plan totals do not match independent replay")
    return {"status": "PASS", "scope": "EXACT_DECLARED_PROCUREMENT_MODEL_ONLY", "input_sha256": root,
            "all_required_pieces_exactly_once": True, "no_splices_inferred": True, "totals": expected}


def optimize_cutting_stock(pieces, stock_catalogue, *, kerf_m=0, end_trim_m=0,
                           budget_nodes=200_000, max_exact_pieces=24, baseline_policy="POOLED_FFD",
                           currency=None, objective="PURCHASED_LENGTH", include_batch_scenario=True,
                           max_seconds=None, checkpoint=None):
    """Return verified pooled plans and an explicit, bounded search ledger.

    Exact partition searches are restricted to max_exact_pieces and 20,000 nodes
    per group. Large groups receive a bounded local exact repair of up to six
    least-filled bins, followed by bounded exact-integer subset-fill repair.
    Exhaustion retains verified incumbents and never proves
    optimality. The search budget does not truncate required input accounting or
    the mandatory baseline/verification passes.
    """
    if baseline_policy != "POOLED_FFD":
        raise ValueError("Primary baseline must be POOLED_FFD; batching is a separate scenario")
    if objective not in {"PURCHASED_LENGTH", "TOTAL_PRICE"}:
        raise ValueError("Unsupported objective")
    if isinstance(budget_nodes, bool) or not isinstance(budget_nodes, int) or not 0 <= budget_nodes <= 10_000_000:
        raise ValueError("budget_nodes must be an integer in 0..10000000")
    if isinstance(max_exact_pieces, bool) or not isinstance(max_exact_pieces, int) or not 0 <= max_exact_pieces <= 32:
        raise ValueError("max_exact_pieces must be an integer in 0..32")
    if not isinstance(include_batch_scenario, bool):
        raise ValueError("include_batch_scenario must be Boolean")
    if max_seconds is not None:
        seconds = _num(max_seconds, "max_seconds", positive=True)
        if seconds > 86_400:
            raise ValueError("max_seconds must not exceed 86400")
        max_seconds = float(seconds)
    if checkpoint is not None and not callable(checkpoint):
        raise ValueError("checkpoint must be callable")
    pp, ss, kerf, trim, inputs, root = _normalise(pieces, stock_catalogue, kerf_m, end_trim_m, currency)
    if objective == "TOTAL_PRICE" and ss[0]["unit_price"] is None:
        raise ValueError("TOTAL_PRICE requires complete stock prices")
    budget = _Budget(budget_nodes, max_seconds, checkpoint)
    groups, catalogues = defaultdict(list), defaultdict(list)
    for p in pp:
        groups[p["group"]].append(p)
    for s in ss:
        catalogues[s["group"]].append(s)
    baseline, selected, batched, ledger = {}, {}, defaultdict(list), []
    for group in sorted(groups):
        if checkpoint is not None:
            checkpoint()
        gp, gs = groups[group], catalogues[group]
        ffd = _greedy(gp, gs, kerf, trim, checkpoint=checkpoint)
        bfd = _greedy(gp, gs, kerf, trim, True, checkpoint)
        baseline[group] = ffd
        alternatives = [(ffd, "POOLED_FFD"), (bfd, "POOLED_BFD")]
        if include_batch_scenario and all(p["batch_id"] is not None for p in gp):
            batches = defaultdict(list)
            for p in gp:
                batches[p["batch_id"]].append(p)
            for batch in sorted(batches):
                batched[group].extend(_greedy(batches[batch], gs, kerf, trim, checkpoint=checkpoint))
            alternatives.append((batched[group], "PER_BATCH_FFD_FEASIBLE_INCUMBENT"))
        winner, method = min(alternatives, key=lambda item: _score(item[0], gs, trim, objective))
        bound = _lower_bound(gp, gs, kerf, trim, objective)
        proof = "PRIMARY_OBJECTIVE_OPTIMAL_BY_LOWER_BOUND" if _score(winner, gs, trim, objective)[0] == Fraction(bound["primary_objective"]) else "HEURISTIC"
        before = budget.used
        exact_complete = False
        if proof == "HEURISTIC" and len(gp) <= max_exact_pieces:
            improved, exact_complete, _ = _exact(gp, gs, kerf, trim, objective, winner, budget, 20_000)
            if _score(improved, gs, trim, objective) < _score(winner, gs, trim, objective):
                winner, method = improved, "BOUNDED_EXACT_PARTITION_SEARCH"
            if exact_complete:
                proof = "PRIMARY_OBJECTIVE_OPTIMAL_BY_EXHAUSTIVE_PARTITION_SEARCH"
        elif proof == "HEURISTIC" and max_exact_pieces > 0:
            # Preserve all other bins, and re-pack a small selected window exactly.
            window = []
            for b in sorted(winner, key=lambda b: (b[0], tuple(p["id"] for p in b[1]))):
                if len(window) >= 6 or sum(len(x[1]) for x in window) + len(b[1]) > max_exact_pieces:
                    break
                window.append(b)
            if len(window) > 1:
                local_pieces = [p for b in window for p in b[1]]
                repaired, _, _ = _exact(local_pieces, gs, kerf, trim, objective, window, budget, 10_000)
                if _score(repaired, gs, trim, objective) < _score(window, gs, trim, objective):
                    removed = {id(b) for b in window}
                    winner = [b for b in winner if id(b) not in removed] + repaired
                    method = "BOUNDED_LOCAL_PARTITION_REPAIR"
            if _score(winner, gs, trim, objective)[0] > Fraction(bound["primary_objective"]) and not budget.exhausted:
                repaired = _subset_repair(winner, gs, kerf, trim, objective, budget)
                if _score(repaired, gs, trim, objective) < _score(winner, gs, trim, objective):
                    winner, method = repaired, "BOUNDED_INTEGER_SUBSET_REPAIR"
        if _score(winner, gs, trim, objective)[0] == Fraction(bound["primary_objective"]):
            proof = "PRIMARY_OBJECTIVE_OPTIMAL_BY_LOWER_BOUND"
        selected[group] = winner
        ledger.append({"group": group, "piece_count": len(gp), "method": method, "optimality": proof,
                       "exact_search_complete": exact_complete, "search_nodes": budget.used - before,
                       "group_partition_node_limit": 20_000 if len(gp) <= max_exact_pieces else 10_000,
                       "lower_bound": bound, "baseline_primary_objective": str(_score(ffd, gs, trim, objective)[0]),
                       "selected_primary_objective": str(_score(winner, gs, trim, objective)[0])})
    baseline_plan = _encode_plan(baseline, ss, kerf, trim, objective, root)
    selected_plan = _encode_plan(selected, ss, kerf, trim, objective, root)
    batch_plan = _encode_plan(batched, ss, kerf, trim, objective, root) if len(batched) == len(groups) else None
    plans = {"baseline": baseline_plan, "selected": selected_plan}
    if batch_plan is not None:
        plans["per_batch_scenario"] = batch_plan
    checks = {name: verify_cut_plan(pieces, stock_catalogue, plan, kerf_m=kerf_m, end_trim_m=end_trim_m,
                                    currency=currency) for name, plan in plans.items()}
    improvements = {}
    for name, old in (("versus_pooled_ffd", baseline_plan), ("versus_per_batch_scenario", batch_plan)):
        if old is None:
            continue
        a, b = old["totals"], selected_plan["totals"]
        improvements[name] = {"stock_count_reduction": a["stock_count"] - b["stock_count"],
                             "purchased_length_reduction_m": str(Fraction(a["purchased_length_m"]) - Fraction(b["purchased_length_m"])),
                             "waste_reduction_m": str(Fraction(a["total_waste_m"]) - Fraction(b["total_waste_m"])),
                             "price_reduction": None if a["total_price"] is None else str(Fraction(a["total_price"]) - Fraction(b["total_price"])),
                             "currency": a["currency"]}
    return {"schema": SCHEMA, "input_sha256": root, "inputs": inputs, "objective": objective,
            "baseline_policy": "POOLED_FIRST_FIT_DECREASING_MAX_CAPACITY_THEN_CHEAPEST_FEASIBLE_STOCK",
            "batch_scenario_policy": "INDEPENDENT_BATCH_FIRST_FIT_DECREASING" if batch_plan is not None else "NOT_RUN_INCOMPLETE_BATCH_IDS_OR_DISABLED",
            "plans": plans, "verification": checks, "improvements": improvements,
            "search": {"node_budget": budget_nodes, "nodes_used": budget.used, "budget_exhausted": budget.exhausted,
                       "max_seconds": max_seconds, "deterministic_order": "DECREASING_LENGTH_THEN_PIECE_ID",
                       "groups": ledger},
            "optimality": "PRIMARY_OBJECTIVE_OPTIMAL_FOR_DECLARED_GROUPS" if all(r["optimality"] != "HEURISTIC" for r in ledger) else "VERIFIED_FEASIBLE_HEURISTIC",
            "scope": {"installed_geometry_changed": False, "required_piece_lengths_changed": False,
                      "splices_inferred": False, "procurement_compatibility": "CALLER_SUPPLIED_GROUPS",
                      "stock_catalogue_completeness": "CALLER_SUPPLIED",
                      "fabrication_and_installation_approval": "NOT_CHECKED",
                      "whole_building_engineering_optimization": False}}
