import { TriangleAlert } from "lucide-react";
import type { ValidationAdvisory } from "./types";

export default function ValidationAdvisories({
  advisories,
  compact = false,
}: {
  advisories?: ValidationAdvisory[];
  compact?: boolean;
}) {
  if (!advisories?.length) return null;
  return (
    <div
      className="validation-advisories"
      role="note"
      aria-label="Known validation advisories"
    >
      {advisories.map((item) => (
        <article key={item.id}>
          <div className="validation-advisory-title">
            <TriangleAlert size={17} />
            <strong>
              {item.id} · {item.claim}
            </strong>
          </div>
          <strong className="validation-resolution">
            {item.status.replaceAll("_", " ")}
          </strong>
          <details open={!compact}>
            <summary>Advisory details and required correction</summary>
            <p>{item.reason}</p>
            <p>{item.resolution_contract}</p>
            <p>{item.scope}</p>
            <ul>
              {item.route_ids.map((id) => (
                <li key={id}>
                  <code>{id}</code>
                </li>
              ))}
            </ul>
            {/^https?:\/\//i.test(item.source) ? (
              <a href={item.source} target="_blank" rel="noreferrer">
                View the referenced source
              </a>
            ) : (
              <p>{item.source}</p>
            )}
          </details>
        </article>
      ))}
    </div>
  );
}
