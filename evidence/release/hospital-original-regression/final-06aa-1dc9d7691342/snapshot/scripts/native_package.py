"""Package the isolated native build as an explicitly identified candidate wheel."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import IFC_COMMIT, developer_environment, run


def main():
    installed = DEST / "python/ifcopenshell"
    extensions = list(installed.glob("*.pyd"))
    assert len(extensions) == 1, "Exactly one compiled Python extension is required"
    binary = extensions[0].read_bytes()
    assert binary[:2] == b"MZ"
    pe_offset = struct.unpack_from("<I", binary, 0x3C)[0]
    assert struct.unpack_from("<H",binary,pe_offset+4)[0] == 0x8664
    cache = (DEST / "build/ifc/CMakeCache.txt").read_text(encoding="utf-8")
    assert "WITH_CGAL:BOOL=OFF" in cache and "WITH_OPENCASCADE:BOOL=ON" in cache
    commands = json.loads((DEST / "build/ifc/compile_commands.json").read_text())
    assert commands and not any("/kernels/cgal/" in str(row["file"]).replace("\\","/").lower() for row in commands)
    assert not any("IFOPSH_WITH_CGAL" in row["command"] or "/svgfill/" in str(row["file"]).replace("\\","/").lower() for row in commands)
    env = developer_environment()
    dumpbin=shutil.which("dumpbin.exe",path=env["PATH"])
    assert dumpbin, "The isolated compiler SDK must expose dumpbin"
    pe_record = run("candidate-pe-dependencies",[dumpbin,"/DEPENDENTS",extensions[0]],env=env,budget=120)
    # Source identity alone cannot distinguish two compiler/configuration
    # outputs. Bind this local package version to the actual extension bytes.
    version = "0.8.5+oma.nocgal." + IFC_COMMIT[:7] + ".b" + sha(extensions[0])
    staging = DEST / "wheel-stage"
    staging.mkdir(parents=True,exist_ok=True)
    package = staging / "ifcopenshell"
    shutil.copytree(installed,package,dirs_exist_ok=True)
    initializer = package / "__init__.py"
    before = sha(initializer)
    text = initializer.read_text(encoding="utf-8")
    assert '__version__ = version = "0.0.0"' in text
    initializer.write_text(text.replace('__version__ = version = "0.0.0"',f'__version__ = version = "{version}"'),encoding="utf-8")
    variant = json.loads((EVIDENCE / "ifc-variant.json").read_text())
    variant["scope"] = "STEP IFC and OpenCASCADE geometry; CGAL geometry and SVG-fill, IFCXML, HDF5, COLLADA, glTF, PROJ, RocksDB and ZSTD disabled; ordinary SVG serialization is not excluded by WITH_CGAL=OFF"
    variant.update(package_version=version, native_extension_sha256=sha(extensions[0]),
        ifc_cmake_cache_sha256=sha(DEST / "build/ifc/CMakeCache.txt"),
        compile_commands_sha256=sha(DEST / "build/ifc/compile_commands.json"),
        native_extension_machine="AMD64",application_validation="NOT_RUN",public_redistribution="NOT_CLEARED",
        pe_dependency_record=str(pe_record / "record.json"),
        absent_original_cgal_diagnostics={marker:binary.count(marker.encode("ascii")) for marker in
            ("CGAL/Nef_3/", "CGAL\\Nef_3\\", "Nef_polyhedron_3", "CGAL::Nef")},
        cgal_build_evidence="WITH_CGAL=OFF; no CGAL kernel or SVG-fill compilation unit or enabling macro in actual compile commands. Binary diagnostic search is supplemental, not a license conclusion.",
        version_stamp={"path":"ifcopenshell/__init__.py","before_sha256":before,"after_sha256":sha(initializer),
                       "change":"Replace upstream release placeholder with explicit local candidate variant version"})
    json_write(package / "NATIVE_BUILD_VARIANT.json",variant)
    for source,label in [(DEST / "src/ifc/COPYING","IFCOPENSHELL_COPYING"),(DEST / "src/ifc/COPYING.LESSER","IFCOPENSHELL_COPYING.LESSER"),
            (DEST / "src/occt/LICENSE_LGPL_21.txt","OCCT_LICENSE_LGPL_21.txt"),(DEST / "src/occt/OCCT_LGPL_EXCEPTION.txt","OCCT_LGPL_EXCEPTION.txt"),
            (DEST / "src/boost/LICENSE_1_0.txt","BOOST_LICENSE_1_0.txt"),(DEST / "src/eigen/COPYING.MPL2","EIGEN_COPYING.MPL2")]:
        assert source.exists()
        notices = package / "native-notices"
        notices.mkdir(exist_ok=True)
        shutil.copyfile(source,notices / label)
    setup = '''from pathlib import Path
from setuptools import setup, find_packages
from setuptools.dist import Distribution
class NativeDistribution(Distribution):
    def has_ext_modules(self):
        return True
root = Path("ifcopenshell")
files = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
setup(name="ifcopenshell", version=VERSION, description="Isolated STEP/OpenCASCADE IfcOpenShell candidate; CGAL disabled",
      packages=find_packages(), package_data={"ifcopenshell":files}, distclass=NativeDistribution,
      python_requires=">=3.12,<3.13", install_requires=["shapely","numpy","isodate","python-dateutil","lark","typing-extensions"])
'''.replace("VERSION",repr(version))
    (staging / "setup.py").write_text(setup,encoding="utf-8")
    run("candidate-wheel",[sys.executable,"setup.py","bdist_wheel","--dist-dir",DEST / "wheels"],cwd=staging,env=developer_environment(),budget=600)
    wheels = list((DEST / "wheels").glob(f"ifcopenshell-{version}-cp312-cp312-win_amd64.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        record_name = next(name for name in archive.namelist() if name.endswith(".dist-info/RECORD"))
        checked = 0
        for name,digest,length in csv.reader(io.StringIO(archive.read(record_name).decode())):
            if not digest:
                assert name == record_name
                continue
            data=archive.read(name)
            actual="sha256="+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            assert digest == actual and int(length) == len(data)
            checked += 1
        descriptor=archive.read(next(name for name in archive.namelist() if name.endswith(".dist-info/WHEEL"))).decode()
        assert "Root-Is-Purelib: false" in descriptor and "Tag: cp312-cp312-win_amd64" in descriptor
    generated = [{"path":str(p),"sha256":sha(p),"bytes":p.stat().st_size}
                 for p in (DEST / "build/ifc").rglob("*PYTHON_wrap*.cxx")]
    assert generated, "Retain generated native binding sources"
    result = {"status":"CANDIDATE_WHEEL_PACKAGED_NOT_RELEASED","wheel":str(wheel),"sha256":sha(wheel),"bytes":wheel.stat().st_size,
        "version":version,"record_entries_verified":checked,"generated_wrapper_sources":generated,"variant":variant,
        "active_runtime_modified":False,"application_validation":"NOT_RUN"}
    json_write(EVIDENCE / "candidate-wheel.json",result)
    print(json.dumps({k:result[k] for k in ["status","wheel","sha256","bytes","record_entries_verified"]}),flush=True)


if __name__ == "__main__":
    main()
