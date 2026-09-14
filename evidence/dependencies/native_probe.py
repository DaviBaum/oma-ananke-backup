"""Read-only native provenance probes; writes only this evidence directory."""
from pathlib import Path
import concurrent.futures, ctypes, hashlib, json, os, re, urllib.request

OUT = Path(__file__).parent / "native-review"
OUT.mkdir(exist_ok=True)
SITES = Path(__file__).resolve().parents[2] / ".venv/Lib/site-packages"

def fetch(item):
    name, url = item
    target = OUT / name
    try:
        if not target.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "OMA-native-source-inventory"})
            with urllib.request.urlopen(req, timeout=90) as response:
                target.write_bytes(response.read())
        raw = target.read_bytes()
        return {"file": name, "url": url, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    except Exception as exc:
        return {"file": name, "url": url, "error": str(exc)}

def metadata():
    tasks = [
        ("ocp-build-tags.json", "https://api.github.com/repos/CadQuery/ocp-build-system/tags?per_page=20"),
        ("ocp-tags.json", "https://api.github.com/repos/CadQuery/OCP/tags?per_page=15"),
        ("ifc-tree.json", "https://api.github.com/repos/IfcOpenShell/IfcOpenShell/git/trees/1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2?recursive=1"),
        ("occt-tag.json", "https://api.github.com/repos/Open-Cascade-SAS/OCCT/git/ref/tags/V8_0_1"),
        ("ifc-pypi.json", "https://pypi.org/pypi/ifcopenshell/0.8.5/json"),
        ("ocp-pypi.json", "https://pypi.org/pypi/cadquery-ocp/8.0.1.0.0/json"),
    ]
    results = list(concurrent.futures.ThreadPoolExecutor(6).map(fetch, tasks))
    (OUT / "retrievals-initial.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))

def versions():
    import OCP  # its generated loader establishes DLL search directories
    libs = SITES / "cadquery_ocp.libs"
    specs = {"FreeImage": ("FreeImage_GetVersion", ctypes.c_char_p), "liblzma": ("lzma_version_string", ctypes.c_char_p), "zstd": ("ZSTD_versionString", ctypes.c_char_p), "zlib": ("zlibVersion", ctypes.c_char_p), "libpng16": ("png_get_libpng_ver", ctypes.c_char_p), "openjp2": ("opj_version", ctypes.c_char_p), "libwebp": ("WebPGetDecoderVersion", ctypes.c_int), "libwebpmux": ("WebPGetMuxVersion", ctypes.c_int), "tiff": ("TIFFGetVersion", ctypes.c_char_p), "raw": ("libraw_version", ctypes.c_char_p)}
    result=[]
    for path in libs.glob("*.dll"):
        name=path.name.split("-")[0]
        row={"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
        if name in specs:
            function, restype = specs[name]
            try:
                module=ctypes.CDLL(str(path)); fn=getattr(module,function); fn.restype=restype
                fn.argtypes = [ctypes.c_void_p] if name == "libpng16" else []
                value=fn(None) if name == "libpng16" else fn()
                row["version_function"]=function
                row["version_result"]=value.decode() if isinstance(value,bytes) else value
            except Exception as exc: row["probe_error"]=str(exc)
        result.append(row)
    (OUT / "dll-probes.json").write_text(json.dumps(result, indent=2))
    print(json.dumps([r for r in result if "version_result" in r or "probe_error" in r], indent=2))

if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
