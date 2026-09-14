import type { Candidate, CheckRecord, Issue } from "./types";

/** Evidence follows the immutable selected state, never a later project head. */
export function scopeEvidence<T extends CheckRecord | Issue>(
  records: T[],
  candidates: Candidate[],
  root?: string,
  candidateId?: string,
): T[] {
  const ids = new Set(
    candidates
      .filter((c) =>
        candidateId ? c.id === candidateId : !!root && c.state_root === root,
      )
      .map((c) => c.id),
  );
  return records.filter((record) =>
    ids.has(
      "candidate_id" in record
        ? String(record.candidate_id)
        : record.id.split(":")[0],
    ),
  );
}
