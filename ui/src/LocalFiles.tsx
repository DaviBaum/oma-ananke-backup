import { useState } from "react";
import { FileBox, FolderOpen, X } from "lucide-react";

export default function LocalFiles({
  files,
  onChange,
  onError,
  disabled,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  onError: (message: string) => void;
  disabled: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  const add = (incoming: File[]) => {
    if (disabled || !incoming.length) return;
    const invalid = incoming.filter(
      (file) => !/\.ifc$/i.test(file.name) || !file.size,
    );
    if (invalid.length) {
      onError(
        `Choose nonempty .ifc files. Unaccepted selection: ${invalid.map((file) => file.name).join(", ")}`,
      );
      return;
    }
    onChange([...files, ...incoming]);
  };
  return (
    <div className="local-file-picker">
      <label
        className={`local-file-drop ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          add(Array.from(event.dataTransfer.files));
        }}
      >
        <input
          aria-label="Choose local IFC files"
          type="file"
          accept=".ifc"
          multiple
          disabled={disabled}
          onChange={(event) => {
            add(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <FolderOpen size={28} strokeWidth={1.3} />
        <strong>Choose IFC files or drop them here</strong>
        <span>Multiple disciplines. One shared coordinate space.</span>
        <small>Transferred only to your local engine.</small>
      </label>
      {!!files.length && (
        <div className="selected-local-files" aria-label="Selected IFC files">
          {files.map((file, index) => (
            <div key={`${index}:${file.name}`}>
              <FileBox size={16} />
              <span>
                <strong>{file.name}</strong>
                <small>
                  {(file.size / 1048576).toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}{" "}
                  MiB
                </small>
              </span>
              <button
                aria-label={`Remove ${file.name}`}
                disabled={disabled}
                onClick={() => onChange(files.filter((_, i) => i !== index))}
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
