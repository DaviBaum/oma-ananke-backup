import { parseSharedNetwork } from "./sharedNetwork";
import type { PhysicalNetwork, Snapshot } from "./types";

export interface NetworkRevisionSeed {
  projectId: string;
  baseRoot: string;
  baseRevision: number;
  network: PhysicalNetwork;
  fixed: Record<string, unknown>;
  alternatives: unknown[];
}

export function prepareNetworkRevision(
  snapshot: Snapshot,
): NetworkRevisionSeed {
  const { project } = snapshot;
  if (
    project.selected_candidate_id ||
    (project.current_state_root &&
      project.current_state_root !== project.state_root) ||
    (project.current_revision !== undefined &&
      project.current_revision !== project.revision)
  )
    throw new Error(
      "Return to the current accepted head before revising its network.",
    );
  const accepted =
    project.status === "ACCEPTED" ||
    snapshot.history.some(
      (h) =>
        h.revision === project.revision &&
        h.state_root === project.state_root &&
        h.status === "ACCEPTED",
    );
  if (!accepted)
    throw new Error("Publish a checked network before preparing its revision.");
  if (
    snapshot.networks?.length !== 1 ||
    snapshot.entities.some((e) => e.ifc_type === "PhysicalRoute")
  )
    throw new Error(
      "Revision requires exactly one existing shared network and no separate route mission.",
    );
  const network = snapshot.networks[0],
    contract = network.network_contract;
  if (
    !contract ||
    contract.selected_alternative !== network.id ||
    !contract.source_id
  )
    throw new Error(
      "The accepted network's immutable scenario and source binding are unavailable.",
    );
  const { network_alternatives, ...fixed } = structuredClone(contract.scenario);
  if (!Array.isArray(network_alternatives))
    throw new Error(
      "The accepted scenario has no recorded network alternatives.",
    );
  fixed.source_id = contract.source_id;
  fixed.replace_network_id = network.id;
  return {
    projectId: project.id,
    baseRoot: project.state_root,
    baseRevision: project.revision,
    network: structuredClone(network),
    fixed,
    alternatives: network_alternatives,
  };
}

export function networkRevisionIsCurrent(
  seed: NetworkRevisionSeed,
  snapshot: Snapshot | null,
  viewingOtherState: boolean,
): boolean {
  return (
    !viewingOtherState &&
    !!snapshot &&
    snapshot.project.id === seed.projectId &&
    snapshot.project.state_root === seed.baseRoot &&
    snapshot.project.revision === seed.baseRevision
  );
}

export function buildNetworkRevision(
  seed: NetworkRevisionSeed,
  alternativesText: string,
) {
  if (alternativesText.length > 2_000_000)
    throw new Error("The editable alternatives exceed the 2 MB input limit.");
  let alternatives: unknown;
  try {
    alternatives = JSON.parse(alternativesText);
  } catch {
    throw new Error("Network alternatives must be a valid JSON array.");
  }
  if (!Array.isArray(alternatives))
    throw new Error(
      "Edit the network_alternatives array only; fixed requirements are read-only.",
    );
  return parseSharedNetwork(
    JSON.stringify({ ...seed.fixed, network_alternatives: alternatives }),
  );
}

export function networkChangedIds(network: PhysicalNetwork): Set<string> {
  return new Set([
    ...(network.network_contract?.revision?.previous_component_ids ?? []),
    ...network.component_ids.map((id) => `${network.id}:${id}`),
  ]);
}
