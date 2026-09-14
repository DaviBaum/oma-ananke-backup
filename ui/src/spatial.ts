import * as THREE from "three";
import type { MeshData, Vec3 } from "./types";
/** Rebase every source through exactly one shared origin, before float32 upload. */
export function rebasePositions(vertices: ArrayLike<number>, origin: Vec3) {
  const positions = new Float32Array(vertices.length);
  for (let i = 0; i < vertices.length; i += 3) {
    positions[i] = vertices[i] - origin[0];
    positions[i + 1] = vertices[i + 1] - origin[1];
    positions[i + 2] = vertices[i + 2] - origin[2];
  }
  return positions;
}
export function frameBox(
  box: THREE.Box3,
  direction: THREE.Vector3,
  aspect: number,
  fovDegrees = 38,
) {
  const center = box.getCenter(new THREE.Vector3()),
    right = new THREE.Vector3(0, 0, 1).cross(direction).normalize(),
    up = direction.clone().cross(right).normalize(),
    tan = Math.tan(THREE.MathUtils.degToRad(fovDegrees / 2));
  let distance = 1,
    halfHeight = 1;
  for (const x of [box.min.x, box.max.x])
    for (const y of [box.min.y, box.max.y])
      for (const z of [box.min.z, box.max.z]) {
        const delta = new THREE.Vector3(x, y, z).sub(center),
          horizontal = Math.abs(delta.dot(right)),
          vertical = Math.abs(delta.dot(up)),
          depth = delta.dot(direction);
        distance = Math.max(
          distance,
          vertical / tan + depth,
          horizontal / (tan * Math.max(aspect, 0.1)) + depth,
        );
        halfHeight = Math.max(
          halfHeight,
          vertical,
          horizontal / Math.max(aspect, 0.1),
        );
      }
  return { center, distance: distance * 1.2, halfHeight: halfHeight * 1.15 };
}
export function isValidMesh(mesh: MeshData) {
  return (
    mesh.vertices.length % 3 === 0 &&
    mesh.faces.length % 3 === 0 &&
    mesh.vertices.every(Number.isFinite) &&
    mesh.faces.every(
      (i) => Number.isInteger(i) && i >= 0 && i < mesh.vertices.length / 3,
    )
  );
}
export function indexEntityMeshes(meshes: MeshData[]) {
  const map = new Map<string, MeshData>();
  for (const mesh of meshes) {
    const previous = map.get(mesh.entity_id);
    if (!previous) {
      map.set(mesh.entity_id, mesh);
      continue;
    }
    const offset = previous.vertices.length / 3;
    const vertices = new Float64Array(
      previous.vertices.length + mesh.vertices.length,
    );
    vertices.set(previous.vertices);
    vertices.set(mesh.vertices, previous.vertices.length);
    const faces = new Uint32Array(previous.faces.length + mesh.faces.length);
    faces.set(previous.faces);
    for (let i = 0; i < mesh.faces.length; i++)
      faces[previous.faces.length + i] = mesh.faces[i] + offset;
    map.set(mesh.entity_id, { ...previous, vertices, faces });
  }
  return map;
}
export function binaryEntity(
  ranges: { end: number; id: string }[],
  triangle: number,
) {
  if (!ranges.length || triangle < 0 || triangle >= ranges.at(-1)!.end)
    return undefined;
  let lo = 0,
    hi = ranges.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (triangle < ranges[mid].end) hi = mid;
    else lo = mid + 1;
  }
  return ranges[lo]?.id;
}
