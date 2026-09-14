import type { Geometry, MeshData } from "./types";
import { isValidMesh } from "./spatial";
export interface MeshProgress {
  received_bytes: number;
  received_meshes: number;
  total_meshes?: number;
}

/** Complete immutable geometry only: a truncated stream can never masquerade as a model. */
export async function readMeshStream(
  response: Response,
  onProgress?: (progress: MeshProgress) => void,
): Promise<Geometry> {
  if (!response.body)
    throw new Error("The geometry stream has no readable body.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let pending = "",
    scan = 0,
    bytes = 0,
    lastUpdate = 0,
    complete = false;
  let header: (Partial<Geometry> & { mesh_count?: number }) | null = null;
  const meshes: MeshData[] = [];
  const line = (text: string) => {
    if (!text.trim()) return;
    const value = JSON.parse(text);
    if (value.type === "error")
      throw new Error(
        value.message ?? value.detail ?? "The geometry stream failed.",
      );
    if (complete)
      throw new Error("Unexpected data after completed geometry stream.");
    if (value.type === "header") {
      if (header || meshes.length)
        throw new Error("Duplicate geometry stream header.");
      if (
        value.units !== "m" ||
        value.coordinate_system !== "world" ||
        typeof value.state_root !== "string"
      )
        throw new Error(
          "Geometry stream must declare immutable world coordinates in meters.",
        );
      header = value;
      return;
    }
    if (!header) throw new Error("Geometry stream header is missing.");
    if (value.type === "mesh") {
      const raw = value.mesh ?? value;
      if (
        !Array.isArray(raw.vertices) ||
        !Array.isArray(raw.faces) ||
        typeof raw.entity_id !== "string" ||
        !isValidMesh(raw)
      )
        throw new Error(
          "Invalid mesh coordinates or topology in geometry stream.",
        );
      meshes.push({
        ...raw,
        vertices: new Float64Array(raw.vertices),
        faces: new Uint32Array(raw.faces),
      });
    } else if (value.type === "complete") {
      if (
        value.mesh_count !== meshes.length ||
        (header.mesh_count !== undefined &&
          header.mesh_count !== meshes.length) ||
        (value.state_root !== undefined &&
          value.state_root !== header.state_root)
      )
        throw new Error(
          "Geometry stream count or state root did not match its completion record.",
        );
      complete = true;
    } else throw new Error("Unknown record in geometry stream.");
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        pending += decoder.decode();
        break;
      }
      bytes += value.byteLength;
      pending += decoder.decode(value, { stream: true });
      let end: number;
      while ((end = pending.indexOf("\n", scan)) >= 0) {
        line(pending.slice(0, end));
        pending = pending.slice(end + 1);
        scan = 0;
      }
      scan = pending.length;
      if (pending.length > 128 * 1024 * 1024)
        throw new Error(
          "One mesh record exceeded the 128 MiB browser stream budget.",
        );
      if (performance.now() - lastUpdate > 250) {
        lastUpdate = performance.now();
        onProgress?.({
          received_bytes: bytes,
          received_meshes: meshes.length,
          total_meshes: (header as { mesh_count?: number } | null)?.mesh_count,
        });
      }
    }
    if (pending.trim()) line(pending);
    if (!header || !complete)
      throw new Error(
        "Geometry stream ended before its completion record. Retry loading the immutable state.",
      );
    onProgress?.({
      received_bytes: bytes,
      received_meshes: meshes.length,
      total_meshes: meshes.length,
    });
    return { ...(header as Partial<Geometry>), meshes } as Geometry;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
