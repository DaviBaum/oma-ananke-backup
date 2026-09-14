"""Exact portable payload and frozen-test evidence checks shared by build/seal."""
from collections import Counter
from pathlib import Path
import json
import xml.etree.ElementTree as ET

from native_prepare import sha

PAYLOAD_DIRECTORIES = ("src", "runtime", "ui", "wheelhouse", "docs", "scripts")
PAYLOAD_FILES = ("OMA.cmd", "Start-OMA.ps1", "Install-OMA.ps1", "README.md", "requirements-runtime.lock")


def payload_files(package):
    package = Path(package).resolve()
    files = [package / name for name in PAYLOAD_FILES]
    for name in PAYLOAD_DIRECTORIES:
        directory = package / name
        assert directory.is_dir()
        for path in directory.rglob("*"):
            assert not path.is_symlink(), "Payload symlinks are not accepted"
            if path.is_file():
                files.append(path)
    return {path.relative_to(package).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
            for path in sorted(files)}


def verify_payload(package, portable):
    package = Path(package).resolve()
    manifest = package / "validated-payload.json"
    assert sha(manifest) == portable["validated_payload_manifest_sha256"]
    expected = json.loads(manifest.read_text())
    assert expected["checker_version"] == portable["identity"]["checker_version"]
    assert expected["source_checkpoint"] == portable["source_checkpoint"]
    source = {name.removeprefix("src/"): row["sha256"] for name, row in expected["files"].items()
              if name.startswith("src/") and name.endswith(".py")}
    assert source == portable["source_python_files"]
    extension = Path(portable["identity"]["extension"]).resolve()
    assert extension.is_relative_to(package)
    assert expected["files"][extension.relative_to(package).as_posix()]["sha256"] == portable["identity"]["extension_sha256"]
    assert expected["files"] == payload_files(package), "Portable payload changed after its validation boundary"
    return expected


def verify_suite_xml(path, nodes):
    assert len(nodes) == len(set(nodes))
    expected = []
    for node in nodes:
        pieces = node.split("::")
        assert pieces[0].endswith(".py") and len(pieces) >= 2
        classname = pieces[0][:-3].replace("/", ".").replace("\\", ".")
        if len(pieces) > 2:
            classname += "." + ".".join(pieces[1:-1])
        expected.append((classname, pieces[-1]))
    xml = ET.parse(path).getroot()
    cases = xml.findall(".//testcase")
    assert Counter((c.attrib.get("classname"), c.attrib["name"]) for c in cases) == Counter(expected)
    assert not xml.findall(".//failure") and not xml.findall(".//error")
    skipped = [{"classname": c.attrib.get("classname"), "name": c.attrib["name"],
                "reason": c.find("skipped").attrib.get("message")} for c in cases if c.find("skipped") is not None]
    allowed = {"test_private_bridge_corruption_is_not_reused[" + f + "]" for f in ("binary", "configuration", "extra_startup")}
    assert len(skipped) == 3 and {c["name"] for c in skipped} == allowed
    assert all(c["classname"] == "tests.test_windows_job_containment"
               and c["reason"] == "Current Python is a direct interpreter and needs no bridge" for c in skipped)
    return {"passed": len(cases) - 3, "failed": 0, "skipped": skipped}
