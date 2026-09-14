import { expect, test } from "vitest";
import { projectView } from "./viewState";
import type { Geometry, Snapshot } from "./types";

const snapshot = { project: { id: "large", state_root: "root-a" } } as Snapshot;
const geometry = {
  project_id: "large",
  state_root: "root-a",
  meshes: [],
} as unknown as Geometry;

test("a project switch cannot rebuild the previous project's geometry", () => {
  expect(projectView("next", snapshot, geometry)).toEqual({
    snapshot: null,
    geometry: null,
  });
});

test("a new state cannot display old geometry while its stream loads", () => {
  expect(
    projectView("large", snapshot, { ...geometry, state_root: "root-old" }),
  ).toEqual({ snapshot, geometry: null });
});

test("a foreign project label cannot bypass identity validation with a matching root", () => {
  const copied = { ...snapshot, project: { ...snapshot.project, id: "copy" } };
  expect(projectView("copy", copied, geometry)).toEqual({
    snapshot: copied,
    geometry: null,
  });
});
