import { describe, expect, it } from "vitest";
import { readMeshStream } from "./meshStream";
const header = {
  type: "header",
  project_id: "p",
  state_root: "root",
  units: "m",
  coordinate_system: "world",
  mesh_count: 1,
};
const mesh = {
  type: "mesh",
  entity_id: "physical",
  vertices: [700003, 4500004, 253, 700004, 4500004, 253, 700003, 4500005, 253],
  faces: [0, 1, 2],
};
function streamed(records: unknown[], chunkSize = 7) {
  const bytes = new TextEncoder().encode(
    records.map((r) => JSON.stringify(r)).join("\n"),
  );
  return new Response(
    new ReadableStream({
      start(controller) {
        for (let i = 0; i < bytes.length; i += chunkSize)
          controller.enqueue(bytes.slice(i, i + chunkSize));
        controller.close();
      },
    }),
  );
}
describe("complete immutable geometry stream", () => {
  it("preserves world precision and topology across arbitrary network chunks", async () => {
    const result = await readMeshStream(
      streamed([
        header,
        mesh,
        { type: "complete", mesh_count: 1, state_root: "root" },
      ]),
    );
    expect(result.state_root).toBe("root");
    expect(result.meshes[0].vertices).toBeInstanceOf(Float64Array);
    expect(result.meshes[0].faces).toBeInstanceOf(Uint32Array);
    expect(Array.from(result.meshes[0].vertices)).toEqual(mesh.vertices);
  });
  it("never publishes a partially disconnected stream", async () => {
    await expect(readMeshStream(streamed([header, mesh]))).rejects.toThrow(
      "completion record",
    );
  });
  it("rejects a mismatched root and corrupted mesh indices", async () => {
    await expect(
      readMeshStream(
        streamed([
          header,
          mesh,
          { type: "complete", mesh_count: 1, state_root: "different" },
        ]),
      ),
    ).rejects.toThrow("state root");
    await expect(
      readMeshStream(
        streamed([
          header,
          { ...mesh, faces: [0, 1, 9] },
          { type: "complete", mesh_count: 1 },
        ]),
      ),
    ).rejects.toThrow("Invalid mesh");
  });
});
