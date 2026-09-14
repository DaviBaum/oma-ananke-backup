import type { Candidate } from "./types";

export function currentPassingCheck(candidate?: Candidate | null): boolean {
  return (
    !!candidate &&
    !candidate.validation_advisories?.length &&
    /^(CHECKED|ACCEPTED)$/.test(candidate.status) &&
    /^(PASS|CHECKED)$/.test(candidate.check?.status ?? "") &&
    candidate.check?.applicability === "CURRENT"
  );
}
export function applicabilityReason(candidate?: Candidate | null): string {
  if (!candidate) return "No checked candidate is associated with this state.";
  if (candidate.validation_advisories?.length)
    return `Known validation advisory ${candidate.validation_advisories.map((item) => item.id).join(", ")}. Regeneration and fresh checks are required before acceptance or checked export.`;
  switch (candidate.check?.applicability) {
    case "STALE_EXECUTABLE":
      return "Historical verdict · checker changed. Recheck this candidate before acceptance or checked export.";
    case "WRONG_ROOT":
      return "Historical verdict · evidence belongs to a different state root. Recheck this candidate.";
    case "CURRENT":
      return currentPassingCheck(candidate)
        ? "Current check · this candidate root and checker version."
        : "Current check · this candidate has no passing release verdict.";
    default:
      return "Check applicability is not reported. Reconnect to the updated engine before acceptance or checked export.";
  }
}
