"""Record per-project declared licensing and provenance without bundling models."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.ifc.audit import atomic_json


def main():
    base = ROOT / "data/ifc-bench"
    records = []
    for folder in sorted((base / "projects").iterdir()):
        license_path, card_path = folder / "license.txt", folder / "model_card.md"
        text = license_path.read_text(encoding="utf-8") if license_path.exists() else ""
        if "MIT License" in text:
            identifier, obligations = "MIT", ["retain copyright and permission notice"]
        elif "Attribution 3.0" in text:
            identifier, obligations = "CC-BY-3.0", ["attribution", "license link", "indicate modifications", "no implied endorsement"]
        elif "Attribution 4.0" in text:
            identifier, obligations = "CC-BY-4.0", ["attribution", "license link", "indicate modifications", "no implied endorsement"]
        elif "GNU General Public License" in text:
            identifier, obligations = "GPL-3.0-or-later-declared", ["retain source license", "model-specific interpretation requires review before redistribution"]
        else:
            identifier, obligations = "UNRESOLVED", ["no redistribution until terms established"]
        issues = []
        if "unspecified" in text or "original owners" in text:
            issues.append("Attribution holder not sufficiently identified in local license")
        if folder.name == "wbdg_office" and "Medical-Dental" in text:
            issues.append("License names Medical-Dental source although folder/card names WBDG Office; provenance mismatch retained")
        records.append({"project": folder.name, "license_path": str(license_path.relative_to(ROOT)),
                        "model_card_path": str(card_path.relative_to(ROOT)), "declared_license": identifier,
                        "license_sha256": hashlib.sha256(text.encode()).hexdigest(), "license_text": text,
                        "model_card": card_path.read_text(encoding="utf-8") if card_path.exists() else None,
                        "declared_obligations": obligations, "provenance_issues": issues,
                        "local_test_disposition": "ACQUIRED_FOR_LOCAL_TESTING", "commercial_demo": "NOT_DISTRIBUTED_OR_PUBLISHED",
                        "modified_model_redistribution": "DISABLED_BY_DEFAULT", "application_distribution": "SOURCE_ASSETS_EXCLUDED",
                        "acquisition_policy": "Download-on-demand at immutable revision; model license is independent of engine code license"})
    atomic_json(ROOT / "evidence/ifc/data-license-register.json", {"projects": records, "count": len(records),
                "interpretation": "Records local declared terms; unresolved attribution issues remain explicit. No model assets included in application."})
    print(json.dumps({"projects": len(records), "provenance_issues": [r["project"] for r in records if r["provenance_issues"]]}))


if __name__ == "__main__":
    main()
