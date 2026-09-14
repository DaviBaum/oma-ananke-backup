import type { Candidate } from "./types";

export function candidateEntityIds(
  candidate: Candidate | null | undefined,
): Set<string> {
  const ids = new Set<string>();
  if (candidate?.opening_edit) ids.add(candidate.opening_edit.host_entity_id);
  for (const route of candidate?.routes ?? []) if (route.id) ids.add(route.id);
  for (const network of candidate?.networks ?? [])
    for (const component of network.component_ids)
      ids.add(`${network.id}:${component}`);
  return ids;
}
