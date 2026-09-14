"""Independent exact polarization and adversarial univalence audit."""
from pathlib import Path
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
import sys
import time
import uuid

STAGE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enc(a, b=None):
    return {"lower": str(a), "upper": str(a if b is None else b)}


def inverse_det(matrix):
    n = len(matrix)
    augmented = [list(row) + [Q(int(i == j)) for j in range(n)] for i, row in enumerate(matrix)]
    determinant = Q(1)
    for j in range(n):
        pivot = next(i for i in range(j, n) if augmented[i][j])
        if pivot != j:
            augmented[j], augmented[pivot] = augmented[pivot], augmented[j]
            determinant = -determinant
        d = augmented[j][j]
        determinant *= d
        augmented[j] = [x / d for x in augmented[j]]
        for i in range(n):
            if i != j:
                factor = augmented[i][j]
                augmented[i] = [a - factor*b for a, b in zip(augmented[i], augmented[j])]
    return [row[n:] for row in augmented], determinant


def build(n, shape, local):
    leaves = [f"leaf{i}" for i in range(n)]
    terms, coefficients = [], {}
    def term(d, a, value):
        name = f"loss{len(terms):02}"
        coefficient = "reused" if len(terms) % 5 == 4 else name
        if coefficient not in coefficients:
            coefficients[coefficient] = enc(value)
        terms.append({"id": name, "coefficient_id": coefficient,
            "descendant_leaves": list(d), "applies_to_leaves": list(a)})
    for i, leaf in enumerate(leaves):
        term([leaf], [leaf], Q(i+2, 7))
    def split(group):
        if len(group) < 2:
            return
        k = 1 if shape == 0 else len(group)-1 if shape == 1 else len(group)//2
        left, right = group[:k], group[k:]
        term(group, group, Q(len(group), 11))
        term(group, left, Q(2*len(terms)+1, 19))
        term(group, right, Q(3*len(terms)+2, 23))
        split(left); split(right)
    split(leaves)
    q = {leaf: Q(i+2, 100*(n+1)) for i, leaf in enumerate(leaves)}
    heads = {leaf: enc(sum(Q(coefficients[t["coefficient_id"]]["lower"])*sum(q[j] for j in t["descendant_leaves"])**2
        for t in terms if leaf in t["applies_to_leaves"])) for leaf in leaves}
    model = {"schema": local.MODEL_SCHEMA, "leaves": leaves, "terms": terms, "coefficients": coefficients,
        "available_heads": heads, "context_root": "5"*64, "physical_model_root": "6"*64,
        "assumptions": deepcopy(local.MODEL_ASSUMPTIONS)}
    box = {leaf: enc(value-Q(1,100000), value+Q(1,100000)) for leaf, value in q.items()}
    return model, q, box


def reroot(packet):
    body = {k: v for k, v in packet.items() if k != "certificate_root"}
    packet["certificate_root"] = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return packet


def main():
    assert len(sys.argv) == 2, "Provide exact frozen runtime src"
    source = Path(sys.argv[1]).resolve()
    module = source / "oma/optimization/coupled_tree_univalence.py"
    before = sha(module)
    sys.path.insert(0, str(source))
    from oma.optimization import coupled_tree_univalence as u, coupled_tree_pressure as local
    out = STAGE / "evidence/root-independent-review" / uuid.uuid4().hex
    out.mkdir(parents=True)
    result = {"status": "RUNNING", "source_directory": str(source), "module_sha256": before,
        "source_bundle": source.parent.name,
        "source_files": {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*.py")},
        "audit_script_sha256": sha(Path(__file__))}
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    started = time.perf_counter()
    records, attacks, composition = [], [], []
    try:
        for n in range(1, 9):
            for shape in range(3):
                model, q, box = build(n, shape, local)
                cert = u.compile_coupled_tree_univalence(model)
                assert cert["status"] == "CERTIFIED_UNIVALENCE", cert
                assert u.verify_coupled_tree_univalence(model, cert)["status"] == "PASS"
                leaves, terms = model["leaves"], model["terms"]
                coefficients = {name: Q(value["lower"]) for name, value in model["coefficients"].items()}
                r = {leaf: Q(0) if i % 3 == 0 else q[leaf]*Q(i+2, i+1) for i, leaf in enumerate(leaves)}
                matrix = [[sum(coefficients[t["coefficient_id"]]*(sum(q[k] for k in t["descendant_leaves"])+sum(r[k] for k in t["descendant_leaves"]))
                    for t in terms if a in t["applies_to_leaves"] and b in t["descendant_leaves"]) for b in leaves] for a in leaves]
                inverse, determinant = inverse_det(matrix)
                assert determinant > 0
                inverse_row = [sum(inverse[i][j] for i in range(n)) for j in range(n)]
                assert min(inverse_row) > 0
                def F(x, leaf):
                    return sum(coefficients[t["coefficient_id"]]*sum(x[k] for k in t["descendant_leaves"])**2
                        for t in terms if leaf in t["applies_to_leaves"])-Q(model["available_heads"][leaf]["lower"])
                assert all(F(q, a)-F(r, a) == sum(matrix[i][j]*(q[b]-r[b]) for j,b in enumerate(leaves)) for i,a in enumerate(leaves))
                local_cert = local.compile_coupled_tree_pressure(model, box)
                assert local_cert["status"] == "CERTIFIED_BOX", local_cert
                combined = u.verify_coupled_tree_nonnegative_family(model, box, local_cert, cert)
                assert combined["status"] == "PASS", combined
                composition.append({"variables": n, "shape": shape, "status": combined["status"]})
                mutations = []
                x=deepcopy(cert); x["polarization"]["same_parameter_tuple"]=1; mutations.append(("typed_same_tuple", x))
                x=deepcopy(cert); x["polarization"]["entrywise_nonnegative_inverse_required"]=0; mutations.append(("typed_inverse_premise", x))
                x=deepcopy(cert); x["limitations"]["reverse_or_negative_flow_uniqueness"]=0; mutations.append(("typed_limitation", x))
                x=deepcopy(cert); x["leaf_witnesses"].pop(leaves[0]); mutations.append(("omitted_leaf",x))
                x=deepcopy(cert); x["leaf_witnesses"][leaves[0]]["coefficient_lower_sum"]="999"; mutations.append(("forged_singleton_sum",x))
                x=deepcopy(cert); x["hierarchy"].pop(); mutations.append(("omitted_group",x))
                x=deepcopy(cert); x["hierarchy"][0]["term_ids"]=[]; mutations.append(("omitted_term",x))
                x=deepcopy(cert); x["hierarchy"][0]["parent"]=x["hierarchy"][0]["id"]; mutations.append(("cyclic_parent",x))
                x=deepcopy(cert); x["model_manifest"]["coefficients"][terms[0]["coefficient_id"]]=enc(99); mutations.append(("changed_coefficient",x))
                x=deepcopy(cert); x["scope"]="GLOBAL_INFEASIBILITY"; mutations.append(("wrong_scope",x))
                for name, packet in mutations:
                    check = u.verify_coupled_tree_univalence(model, reroot(packet))
                    assert check["status"] != "PASS", (n, shape, name)
                    attacks.append({"variables":n,"shape":shape,"attack":name,"status":check["status"]})
                changed = deepcopy(model); changed["available_heads"][leaves[0]]=enc(99)
                assert u.verify_coupled_tree_nonnegative_family(changed, box, local_cert, cert)["status"] != "PASS"
                # Producer-disabled verification must retain both independent proofs.
                saved = u._produce_hierarchy
                u._produce_hierarchy = lambda *_: (_ for _ in ()).throw(AssertionError("Producer called"))
                try:
                    assert u.verify_coupled_tree_univalence(model, cert)["status"] == "PASS"
                finally:
                    u._produce_hierarchy = saved
                records.append({"model":model,"q":{k:str(v) for k,v in q.items()},"r":{k:str(v) for k,v in r.items()},
                    "determinant":str(determinant),"inverse_row":[str(v) for v in inverse_row],
                    "negative_inverse_entries":sum(v<0 for row in inverse for v in row), "certificate_root":cert["certificate_root"]})
        assert any(r["negative_inverse_entries"] for r in records)
        assert sha(module) == before
        result.update(status="INDEPENDENT_POLARIZATION_HIERARCHY_AND_COMPOSITION_AUDIT_PASS", models=len(records),
            resealed_attacks=len(attacks), composed_positive_families=len(composition),
            producer_disabled_replay=True, seconds=time.perf_counter()-started)
    except BaseException as exc:
        result.update(status="FAIL", error=repr(exc), models_completed=len(records), attacks_completed=len(attacks))
        raise
    finally:
        for name, value in (("models",records),("attacks",attacks),("composition",composition),("result",result)):
            (out / (name+".json")).write_text(json.dumps(value,indent=2)+"\n",encoding="utf8")
        print(json.dumps({**{k:v for k,v in result.items() if k not in {"source_directory"}},"out":str(out)}),flush=True)


if __name__ == "__main__":
    main()
