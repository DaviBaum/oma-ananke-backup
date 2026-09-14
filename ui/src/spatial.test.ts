import { describe, it, expect } from "vitest";
import * as THREE from "three";
import {
  rebasePositions,
  frameBox,
  binaryEntity,
  isValidMesh,
  indexEntityMeshes,
} from "./spatial";
describe("spatial presentation boundary", () => {
  it("picks every materialized part of a route without mutating original geometry", () => {
    const a = {
        entity_id: "route",
        vertices: [0, 0, 0, 1, 0, 0, 0, 1, 0],
        faces: [0, 1, 2],
      },
      b = {
        entity_id: "route",
        vertices: [0, 0, 2, 1, 0, 2, 0, 1, 2],
        faces: [0, 1, 2],
      };
    const indexed = indexEntityMeshes([a, b]);
    expect(Array.from(indexed.get("route")!.faces)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(a.faces).toEqual([0, 1, 2]);
    expect(a.vertices).toHaveLength(9);
  });
  it("preserves federation offsets near large world coordinates", () => {
    const origin: [number, number, number] = [700000, 4500000, 250];
    const a = rebasePositions([700003, 4500004, 253], origin),
      b = rebasePositions([700013, 4500014, 259], origin);
    expect([...a]).toEqual([3, 4, 3]);
    expect([...b]).toEqual([13, 14, 9]);
    expect(b[0] - a[0]).toBe(10);
  });
  it("maps merged triangle picks to distinct entity IDs at boundaries", () => {
    const ranges = [
      { end: 12, id: "a" },
      { end: 24, id: "b" },
      { end: 90, id: "c" },
    ];
    expect(binaryEntity(ranges, 11)).toBe("a");
    expect(binaryEntity(ranges, 12)).toBe("b");
    expect(binaryEntity(ranges, 24)).toBe("c");
    expect(binaryEntity(ranges, 90)).toBeUndefined();
  });
  it("frames a wide building more efficiently on a wide viewport", () => {
    const box = new THREE.Box3(
        new THREE.Vector3(-50, -5, 0),
        new THREE.Vector3(50, 5, 10),
      ),
      dir = new THREE.Vector3(0, -1, 0.3).normalize();
    expect(frameBox(box, dir, 3).distance).toBeLessThan(
      frameBox(box, dir, 1).distance,
    );
  });
  it("rejects invalid mesh topology rather than rendering corrupt triangles", () => {
    expect(
      isValidMesh({
        entity_id: "a",
        vertices: [0, 0, 0, 1, 0, 0, 0, 1, 0],
        faces: [0, 1, 2],
      }),
    ).toBe(true);
    expect(
      isValidMesh({ entity_id: "a", vertices: [0, 0, 0], faces: [0, 1, 2] }),
    ).toBe(false);
  });
});
