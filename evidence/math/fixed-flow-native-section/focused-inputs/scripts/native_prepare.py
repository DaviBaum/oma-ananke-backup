"""Stage pinned native build inputs in an isolated workspace tree."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "evidence/dependencies/native-review"
DEST = ROOT / ".release/native-build"
EVIDENCE = ROOT / "evidence/dependencies/native-build"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".pending")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp.replace(path)


def download(name, url, expected_sha=None):
    path = DEST / "downloads" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    begin = time.perf_counter()
    metadata_path = EVIDENCE / "retrievals" / (name + ".json")
    if path.exists() and metadata_path.exists():
        record = json.loads(metadata_path.read_text())
        if sha(path) == record["sha256"] and (not expected_sha or record["sha256"] == expected_sha):
            return record
    request = urllib.request.Request(url, headers={"User-Agent":"OMA-pinned-native-build/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        temp = path.with_suffix(path.suffix + ".pending")
        with temp.open("wb") as stream:
            for chunk in iter(lambda:response.read(8*1024*1024), b""):
                stream.write(chunk)
        digest = sha(temp)
        if expected_sha and digest != expected_sha:
            raise ValueError(f"Publisher hash mismatch: {name}")
        if name.endswith((".gz", ".bz2")) and not tarfile.is_tarfile(temp):
            raise ValueError(f"Not a source tar archive: {name}")
        if name.endswith(".zip") and not zipfile.is_zipfile(temp):
            raise ValueError(f"Not a zip archive: {name}")
        temp.replace(path)
        record = {"file":str(path.relative_to(ROOT)), "url":url, "resolved_url":response.geturl(),
                  "sha256":digest, "bytes":path.stat().st_size, "publisher_sha256":expected_sha,
                  "retrieved_utc":datetime.now(timezone.utc).isoformat(), "seconds":time.perf_counter()-begin}
        json_write(metadata_path, record)
        print(json.dumps({"stage":"downloaded", **record}), flush=True)
        return record


def retained(name):
    rows = []
    for manifest in REVIEW.glob("retrievals-*.json"):
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if isinstance(value, list):
            rows.extend(r for r in value if isinstance(r, dict))
    matches = [r for r in rows if r.get("file") == name]
    if not matches:
        raise ValueError(f"No retained source provenance: {name}")
    original = REVIEW / name
    assert sha(original) == matches[0]["sha256"]
    dest = DEST / "downloads" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(original, dest)
    assert sha(dest) == matches[0]["sha256"]
    return {**matches[0], "file":str(dest.relative_to(ROOT)), "retained_original":str(original.relative_to(ROOT))}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    assert DEST.resolve().is_relative_to(ROOT.resolve())
    record = {"status":"PREPARING", "install_root":str(DEST), "active_runtime_modified":False,
              "ifcopenshell_commit":"1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2", "occt_version":"7.8.1",
              "compiler_jobs":4, "sources":[], "scope":"ISOLATED_CGAL_DISABLED_BUILD_INPUTS; NO_DISTRIBUTION_CLEARANCE"}
    try:
        for name in ["ifc-source.tar.gz", "occt-source-7.8.1.tar.gz", "ifc-step-parser-source.tar.gz", "ifc-mvd-source.tar.gz", "ifc-json-source.tar.gz"]:
            record["sources"].append(retained(name))
        jobs = [
            ("boost_1_86_0.tar.bz2", "https://archives.boost.io/release/1.86.0/source/boost_1_86_0.tar.bz2", "1bed88e40401b2cb7a1f76d4bab499e352fa4d0c5f31c0dbae64e24d34d7513b"),
            ("boost_1_86_0.publisher.json", "https://archives.boost.io/release/1.86.0/source/boost_1_86_0.tar.bz2.json", None),
            ("eigen-3.3.9.tar.gz", "https://gitlab.com/libeigen/eigen/-/archive/3.3.9/eigen-3.3.9.tar.gz", None),
            ("swig-4.2.1.tar.gz", "https://codeload.github.com/swig/swig/tar.gz/refs/tags/v4.2.1", None),
            ("swigwin-4.2.1.zip", "https://prdownloads.sourceforge.net/swig/swigwin-4.2.1.zip", None),
            ("swig-v4.2.1.tag.json", "https://api.github.com/repos/swig/swig/git/ref/tags/v4.2.1", None),
            ("eigen-3.3.9.tag.json", "https://gitlab.com/api/v4/projects/libeigen%2Feigen/repository/tags/3.3.9", None),
        ]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(download, *job) for job in jobs]
            failures = []
            for job, future in zip(jobs, futures):
                try:
                    record["sources"].append(future.result())
                except Exception as exc:
                    failures.append({"file":job[0],"url":job[1],"error":repr(exc)})
        record["retrieval_failures"] = failures
        record["status"] = "INPUTS_DOWNLOADED" if not failures else "PARTIAL_INPUTS"
    finally:
        json_write(EVIDENCE / "inputs.json", record)
    print(json.dumps({"status":record["status"],"sources":len(record["sources"]),"failures":record.get("retrieval_failures",[])}),flush=True)


if __name__ == "__main__":
    main()
