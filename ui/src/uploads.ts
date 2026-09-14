import { recordTiming } from "./telemetry";

export interface UploadReceipt {
  path: string;
  name: string;
  sha256: string;
  size_bytes: number;
  status: "UPLOADED";
  engineering_checks: "NOT_RUN";
}
export interface UploadStatus {
  phase: "UPLOADING" | "RECEIVED" | "IMPORTING";
  filename?: string;
  completed: number;
  total: number;
}
const uploads = new WeakMap<File, { key: string; receipt?: UploadReceipt }>();

export async function uploadLocalFiles(
  files: File[],
  signal: AbortSignal,
  onStatus: (status: UploadStatus) => void,
): Promise<UploadReceipt[]> {
  const receipts: UploadReceipt[] = [];
  for (const file of files) {
    signal.throwIfAborted();
    let stored = uploads.get(file);
    if (!stored) {
      stored = { key: crypto.randomUUID() };
      uploads.set(file, stored);
    }
    if (!stored.receipt) {
      onStatus({
        phase: "UPLOADING",
        filename: file.name,
        completed: receipts.length,
        total: files.length,
      });
      const started = performance.now();
      const params = new URLSearchParams({
        filename: file.name,
        idempotency_key: stored.key,
      });
      const response = await fetch(`/api/uploads?${params}`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
        signal,
      });
      if (response.status === 404)
        throw new Error(
          "File transfer needs the updated local engine. Restart the service, then retry, or use existing absolute IFC paths.",
        );
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : JSON.stringify(result.detail ?? result),
        );
      if (
        typeof result.path !== "string" ||
        typeof result.name !== "string" ||
        !/^[a-f0-9]{64}$/i.test(result.sha256 ?? "") ||
        result.size_bytes !== file.size ||
        result.status !== "UPLOADED" ||
        result.engineering_checks !== "NOT_RUN"
      )
        throw new Error(
          "The local engine returned an inconsistent upload receipt. Import has not started.",
        );
      stored.receipt = result as UploadReceipt;
      recordTiming("local_file_received", {
        filename: file.name,
        size_bytes: result.size_bytes,
        sha256: result.sha256,
        elapsed_ms: performance.now() - started,
      });
    }
    receipts.push(stored.receipt);
    onStatus({
      phase: "RECEIVED",
      filename: file.name,
      completed: receipts.length,
      total: files.length,
    });
  }
  signal.throwIfAborted();
  return receipts;
}
