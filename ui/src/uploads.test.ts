import { afterEach, expect, test, vi } from "vitest";
import { uploadLocalFiles } from "./uploads";
afterEach(() => vi.restoreAllMocks());
const receipt = (file: File) => ({
  path: `C:\\immutable\\${file.name}`,
  name: file.name,
  sha256: "a".repeat(64),
  size_bytes: file.size,
  status: "UPLOADED",
  engineering_checks: "NOT_RUN",
});

test("uncertain transfers retry with one key and retain confirmed receipts", async () => {
  const file = new File(["ISO-10303-21;"], "model.ifc"),
    signal = new AbortController().signal;
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockRejectedValueOnce(new Error("connection lost"))
    .mockResolvedValueOnce(new Response(JSON.stringify(receipt(file))));
  await expect(uploadLocalFiles([file], signal, () => {})).rejects.toThrow(
    "connection lost",
  );
  const statuses: unknown[] = [];
  expect(
    await uploadLocalFiles([file], signal, (status) => statuses.push(status)),
  ).toEqual([receipt(file)]);
  expect(fetchMock.mock.calls[0][0]).toBe(fetchMock.mock.calls[1][0]);
  expect(fetchMock.mock.calls[1][1]?.body).toBe(file);
  expect(statuses).toMatchObject([
    { phase: "UPLOADING", completed: 0 },
    { phase: "RECEIVED", completed: 1 },
  ]);
  await uploadLocalFiles([file], signal, () => {});
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
test("a received byte-count mismatch cannot start an import", async () => {
  const file = new File(["IFC"], "bad.ifc");
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ ...receipt(file), size_bytes: 0 })),
  );
  await expect(
    uploadLocalFiles([file], new AbortController().signal, () => {}),
  ).rejects.toThrow("inconsistent upload receipt");
});
test("an already cancelled selection sends no file bytes", async () => {
  const controller = new AbortController();
  controller.abort();
  const fetchMock = vi.spyOn(globalThis, "fetch");
  await expect(
    uploadLocalFiles(
      [new File(["IFC"], "cancel.ifc")],
      controller.signal,
      () => {},
    ),
  ).rejects.toMatchObject({ name: "AbortError" });
  expect(fetchMock).not.toHaveBeenCalled();
});
test("a missing upload endpoint explains the local service requirement", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("Not Found", { status: 404 }),
  );
  await expect(
    uploadLocalFiles(
      [new File(["IFC"], "sample.ifc")],
      new AbortController().signal,
      () => {},
    ),
  ).rejects.toThrow("updated local engine");
});
