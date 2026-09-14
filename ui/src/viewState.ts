import type { Geometry, Snapshot } from "./types";

/** Reject stale project data during the render before passive request cleanup. */
export function projectView(
  projectId: string | null,
  snapshot: Snapshot | null,
  geometry: Geometry | null,
) {
  if (!projectId || snapshot?.project.id !== projectId)
    return { snapshot: null, geometry: null };
  return {
    snapshot,
    geometry:
      geometry?.project_id === projectId &&
      geometry.state_root === snapshot.project.state_root
        ? geometry
        : null,
  };
}
