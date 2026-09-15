"""Expose every new canonical paragraph after conservative template substitution.

This is a reading aid, never a review-completion attestation. Every source
paragraph remains in the map, including equations replaced with manifest LaTeX
plus original OMML. Exact normalized matches point to their first occurrence;
novel content must still be read in context before a ledger entry is recorded.
"""
from pathlib import Path
import hashlib
import json
import re
import argparse
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge", type=int)
    parser.add_argument("--notes")
    args = parser.parse_args()
    if args.acknowledge is not None:
        if not args.notes or not 1 <= args.acknowledge <= 30:
            raise ValueError("Prompt1-30 and substantive review notes required")
        path = OUT / "template-review/map.json"
        mapping = json.loads(path.read_text(encoding="utf8"))
        rows = [r for r in mapping["paragraphs"] if r.get("prompt") == args.acknowledge]
        owner = {r["paragraph"]:r.get("prompt") for r in mapping["paragraphs"]}
        report = OUT / "template-review" / f"P{args.acknowledge:02d}-novel.txt"
        rec = {"prompt": args.acknowledge, "status": "NOVEL_TEXT_AND_PARAMETER_CONTEXT_READ",
            "notes": args.notes, "utc": datetime.now(timezone.utc).isoformat(),
            "map_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "read_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
            "referent_prompts": sorted({owner[r["first_equivalent_paragraph"]] for r in rows if r.get("first_equivalent_paragraph") is not None and owner[r["first_equivalent_paragraph"]] != args.acknowledge}),
            "notice": "All duplicate referents must also have been reviewed; text review does not establish mathematical applicability, implementation, visual review or whole-corpus completion."}
        with (OUT / "template-review/review_ledger.jsonl").open("a", encoding="utf8") as stream:
            stream.write(json.dumps(rec, ensure_ascii=False)+"\n")
        print(json.dumps(rec, ensure_ascii=False))
        return
    ns = json.loads((OUT / "canonical_namespace.json").read_text(encoding="utf8"))
    records = [json.loads(line) for line in (OUT / "extracted/ananke-canonical.jsonl").read_text(encoding="utf8").splitlines()]
    equations = {e["id"]: e["latex"] for e in ns["equations"]}
    metadata = {p["n"]: p for p in ns["prompts"]}
    starts = [(r["location"], int(m.group(1))) for r in records if (m := re.fullmatch(r"ANANKE MATHEMATICS PROGRAM — PROMPT (\d+) OF 30", r["text"]))]
    starts.append((next(r["location"] for r in records if r["location"] > starts[-1][0] and r["text"] == "BACK MATTER"), 31))
    seen, mapped, reports = {}, [], []
    for (start, number), (end, _) in zip(starts, starts[1:]):
        p = metadata[number]
        report = [f"PROMPT {number}: {p['title']}", f"Role: {p['role']}; domain: {p['short']}; namespace {p['prefix']}; package {p['package']}; fiber {p['fiber']}",
            "READING AID ONLY: duplicate matches do not themselves establish dependency applicability or implementation."]
        omit_math_tokens = False
        for record in records[start-1:end-1]:
            text = record["text"]
            if omit_math_tokens:
                omit_math_tokens = False
                mapped.append({"paragraph": record["location"], "method": "EQUATION_TOKENS_HAVE_LOSSLESS_MANIFEST_SOURCE_IN_PRECEDING_RECORD", "sha256": record["text_sha256"]})
                continue
            em = re.match(r"Equation (P\d+-E\d+) — (.*)", text)
            if em:
                text = em.group(2) + "\nLATEX: " + equations[em.group(1)]
                omit_math_tokens = record["location"] < len(records) and records[record["location"]]["omml_count"] > 0
            normalized = text.replace(p["short"], "<DOMAIN>")
            normalized = re.sub(r"\b"+re.escape(p["package"])+r"\b", "<PACKAGE>", normalized)
            prefix = re.escape(p["prefix"])
            normalized = re.sub(r"(?<=-)"+prefix+r"(?=\d)", "<NAMESPACE>", normalized)
            normalized = re.sub(r"(?<=_)\{"+prefix+r"\}", "{<NAMESPACE>}", normalized)
            normalized = re.sub(r"(?<=_)"+prefix+r"\b", "<NAMESPACE>", normalized)
            normalized = re.sub(r"\b"+prefix+r"State\b", "<NAMESPACE>State", normalized)
            key = hashlib.sha256(normalized.encode()).hexdigest()
            match = seen.get(key)
            row = {"paragraph": record["location"], "source_sha256": record["text_sha256"], "normalized_sha256": key,
                "prompt": number, "normalized_text": normalized, "first_equivalent_paragraph": match,
                "method": "NOVEL_REQUIRES_READING" if match is None else "EXPLICIT_PARAMETER_SUBSTITUTION_MATCH_REQUIRES_CONTEXT_CHECK"}
            mapped.append(row)
            if match is None:
                seen[key] = record["location"]
                report.append(f"[{record['location']}] {text}")
        reports.append({"prompt": number, "start": start, "end": end-1, "novel_paragraphs": len(report)-3})
        target = OUT / "template-review" / f"P{number:02d}-novel.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(report)+"\n", encoding="utf8")
    (OUT / "template-review/map.json").write_text(json.dumps({"notice": "READING AID, NOT COMPLETION OR DEPENDENCY AUDIT", "prompts": reports, "paragraphs": mapped}, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
