"""Isolated pinned Windows IfcOpenShell build; never install into the live venv."""
import argparse
import difflib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
import zipfile

import psutil
from native_prepare import ROOT, REVIEW, DEST, EVIDENCE, sha, json_write

IFC_COMMIT = "1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2"
VCVARS = r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
SCRIPT_SHA256 = sha(Path(__file__))


def extract(name, label):
    archive = DEST / "downloads" / name
    target = DEST / "src" / label
    assert target.resolve().is_relative_to(DEST.resolve())
    marker = EVIDENCE / "extraction" / (label + ".json")
    digest = sha(archive)
    retrieval = EVIDENCE / "retrievals" / (name + ".json")
    if retrieval.exists():
        assert digest == json.loads(retrieval.read_text())["sha256"]
    else:
        retained = json.loads((EVIDENCE / "inputs.json").read_text())["sources"]
        assert any(Path(row["file"]).name == name and row["sha256"] == digest for row in retained)
    if marker.exists():
        previous = json.loads(marker.read_text())
        if previous["archive_sha256"] == digest and target.exists():
            return target
        raise ValueError("Existing extraction does not match pinned input")
    begin = time.perf_counter()
    files, notices, links = [], [], []
    target.mkdir(parents=True, exist_ok=True)
    def write(relative, data):
        parts = PurePosixPath(relative).parts
        if not parts or any(p in ("..", "") for p in parts):
            raise ValueError("Archive traversal rejected")
        destination = target.joinpath(*parts)
        assert destination.resolve().is_relative_to(target.resolve())
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        item = {"path":relative,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
        files.append(item)
        if destination.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
            notices.append(item)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zipped:
            for item in zipped.infolist():
                relative = "/".join(PurePosixPath(item.filename).parts[1:])
                if item.is_dir() or not relative:
                    continue
                write(relative, zipped.read(item))
    else:
        with tarfile.open(archive) as packed:
            for item in packed:
                relative = "/".join(PurePosixPath(item.name).parts[1:])
                if item.isdir() or not relative:
                    continue
                if item.issym():
                    link_destination = (target / relative).parent / item.linkname
                    assert link_destination.resolve().is_relative_to(target.resolve())
                    # Match a Windows Git checkout with core.symlinks=false.
                    # These three Bonsai template links are not compiled Python/CAD inputs.
                    write(relative, item.linkname.encode("utf-8"))
                    links.append({"path":relative,"target":item.linkname,"disposition":"WINDOWS_GIT_SYMLINK_AS_TEXT"})
                    continue
                if not item.isfile():
                    raise ValueError(f"Non-regular source archive item needs explicit review: {item.name}")
                write(relative, packed.extractfile(item).read())
    content_root = hashlib.sha256(json.dumps(sorted(files,key=lambda r:r["path"]),sort_keys=True).encode()).hexdigest()
    json_write(marker,{"archive":str(archive),"archive_sha256":digest,"destination":str(target),
        "file_count":len(files),"expanded_bytes":sum(f["bytes"] for f in files),"tree_root":content_root,
        "files":files,"notice_paths":notices,"symlink_dispositions":links,"seconds":time.perf_counter()-begin})
    print(json.dumps({"stage":"extracted","label":label,"files":len(files),"seconds":time.perf_counter()-begin}),flush=True)
    return target


def developer_environment():
    # Only this child receives the toolchain environment; no user/system PATH edits.
    batch = DEST / "activate-compiler.cmd"
    installer = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer"
    batch.write_text(f'@echo off\nset "PATH={installer};%PATH%"\ncall "{VCVARS}" >nul\nif errorlevel 1 exit /b 1\nset\n',encoding="ascii")
    output = subprocess.check_output(["cmd.exe","/d","/c",str(batch)],text=True,encoding="utf-8",errors="replace")
    env = os.environ.copy()
    for line in output.splitlines():
        if "=" in line and not line.startswith("="):
            key,value = line.split("=",1)
            env[key] = value
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = "4"
    env.pop("PYTHONPATH",None)
    env.pop("OMA_EXECUTABLE_BUILD",None)
    if not shutil.which("cl",path=env["PATH"]):
        raise RuntimeError("The isolated x64 compiler environment did not locate cl.exe")
    return env


def run(stage, command, *, cwd=None, env=None, budget=7200):
    """Record full command/output, bounded process-tree resources and cancellation."""
    folder = EVIDENCE / "commands" / (stage + "-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    begin = time.perf_counter()
    record = {"stage":stage,"command":[str(x) for x in command],"cwd":str(cwd or DEST),
              "orchestration_script_sha256":SCRIPT_SHA256,
              "started_utc":datetime.now(timezone.utc).isoformat(),"budget_seconds":budget,
              "compiler_jobs":4,"status":"RUNNING","peak_process_tree_rss_bytes":0,
              "cancel_file":str(DEST / "CANCEL_BUILD")}
    json_write(folder / "record.json",record)
    with (folder / "output.log").open("w",encoding="utf-8") as output:
        try:
            process = subprocess.Popen([str(x) for x in command],cwd=cwd or DEST,env=env,stdout=output,stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except OSError as error:
            record.update(status="FAILED_TO_START",error=repr(error),seconds=time.perf_counter()-begin)
            json_write(folder / "record.json",record)
            raise
        record["pid"] = process.pid
        last_print=0
        while process.poll() is None:
            elapsed=time.perf_counter()-begin
            children=[]
            try:
                parent=psutil.Process(process.pid)
                children=parent.children(recursive=True)
                rss=sum(p.memory_info().rss for p in [parent,*children] if p.is_running())
            except psutil.NoSuchProcess:
                rss=0
            record["peak_process_tree_rss_bytes"]=max(record["peak_process_tree_rss_bytes"],rss)
            if elapsed>budget or rss>48*1024**3 or (DEST / "CANCEL_BUILD").exists():
                for child in children:
                    try: child.kill()
                    except psutil.NoSuchProcess: pass
                process.kill()
                record["status"]="CANCELLED_OR_RESOURCE_LIMIT"
                break
            if elapsed-last_print>30:
                record["seconds"]=elapsed
                json_write(folder / "record.json",record)
                print(json.dumps({"stage":stage,"seconds":elapsed,"rss_bytes":rss,"log":str(folder / "output.log")}),flush=True)
                last_print=elapsed
            time.sleep(1)
        process.wait()
    record.update(exit_code=process.returncode,seconds=time.perf_counter()-begin,
                  log_sha256=sha(folder / "output.log"),status="PASS" if process.returncode==0 else record["status"] if record["status"]!="RUNNING" else "FAIL")
    json_write(folder / "record.json",record)
    print(json.dumps({"stage":stage,"status":record["status"],"seconds":record["seconds"],"record":str(folder / "record.json")}),flush=True)
    if process.returncode:
        print((folder / "output.log").read_text(encoding="utf-8",errors="replace")[-12000:],flush=True)
        raise RuntimeError(f"{stage} failed; exact configuration/output retained")
    return folder


def prepare(env):
    inputs=json.loads((EVIDENCE / "inputs.json").read_text())
    assert inputs["status"] == "INPUTS_DOWNLOADED"
    for item in inputs["sources"]:
        assert sha(ROOT / item["file"]) == item["sha256"]
    paths = {
        "ifc":extract("ifc-source.tar.gz","ifc"),
        "occt":extract("occt-source-7.8.1.tar.gz","occt"),
        "boost":extract("boost_1_86_0.tar.bz2","boost"),
        "eigen":extract("eigen-0fd6b4f71dd85b2009ee4d1aeb296e2c11fc9d68.tar.gz","eigen"),
        "swig_source":extract("swig-b592468f522cf7f4a0812493bfa07cbe60679d7c.tar.gz","swig-source"),
        "swig":extract("swigwin-4.2.1.zip","swigwin"),
    }
    for name,label,destination in [
        ("ifc-mvd-source.tar.gz","ifc-mvd","src/ifcopenshell-python/ifcopenshell/mvd"),
        ("ifc-step-parser-source.tar.gz","ifc-step-parser","src/ifcopenshell-python/ifcopenshell/simple_spf")]:
        source=extract(name,label)
        shutil.copytree(source,paths["ifc"] / destination,dirs_exist_ok=True)
    # The retained tarball matches this pinned upstream commit. Fetch its Git
    # identity so ADD_COMMIT_SHA cannot accidentally discover the parent OMA repo.
    if not (paths["ifc"] / ".git").exists():
        run("ifc-git-init",["git","init"],cwd=paths["ifc"],env=env,budget=120)
        run("ifc-git-pin",["git","fetch","--depth=1","https://github.com/IfcOpenShell/IfcOpenShell.git",IFC_COMMIT],cwd=paths["ifc"],env=env,budget=900)
        run("ifc-git-head",["git","update-ref","HEAD",IFC_COMMIT],cwd=paths["ifc"],env=env,budget=120)
        run("ifc-git-index",["git","read-tree",IFC_COMMIT],cwd=paths["ifc"],env=env,budget=120)
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=paths["ifc"],text=True).strip()==IFC_COMMIT
    patch_ifc_opaque_coordinates(paths["ifc"],env)
    patch=REVIEW / "ifc-build-files/win/patches/V7_8_1.patch"
    patch_marker=EVIDENCE / "occt-patch.json"
    if not patch_marker.exists():
        if not (paths["occt"] / ".git").exists():
            run("occt-git-init",["git","init"],cwd=paths["occt"],env=env,budget=120)
        assert Path(subprocess.check_output(["git","rev-parse","--show-toplevel"],cwd=paths["occt"],text=True).strip()).resolve()==paths["occt"].resolve()
        run("occt-patch-check",["git","apply","--check","--ignore-whitespace",str(patch)],cwd=paths["occt"],env=env,budget=120)
        run("occt-patch",["git","apply","--ignore-whitespace",str(patch)],cwd=paths["occt"],env=env,budget=120)
        assert "add_definitions(-DHAVE_NO_DLL)" in (paths["occt"] / "CMakeLists.txt").read_text()
        json_write(patch_marker,{"patch":str(patch),"sha256":sha(patch),"source":"OCCT 7.8.1 retained source",
            "modified_files":{name:sha(paths["occt"] / name) for name in ["CMakeLists.txt","adm/cmake/occt_defs_flags.cmake","adm/cmake/occt_toolkit.cmake","adm/cmake/cotire.cmake"]}})
    run("swig-version",[paths["swig"] / "swig.exe","-version"],env=env,budget=30)
    json_write(EVIDENCE / "prepared-paths.json",{k:str(v) for k,v in paths.items()})
    json_write(EVIDENCE / "toolchain.json",{"vcvars":VCVARS,"python_executable":sys.executable,"python_base_prefix":sys.base_prefix,
        "python_version":sys.version,"cmake_executable":shutil.which("cmake",path=env["PATH"]),"ninja_executable":shutil.which("ninja",path=env["PATH"]),
        "cl_executable":shutil.which("cl",path=env["PATH"]),"VCToolsVersion":env.get("VCToolsVersion"),
        "WindowsSDKVersion":env.get("WindowsSDKVersion"),"compiler_jobs":4,"active_runtime_modified":False})
    return paths


def patch_ifc_opaque_coordinates(source,env):
    """Expose generic coordinate templates independently of optional CGAL."""
    relative="src/ifcwrap/IfcGeomWrapper.i"
    path=source / relative
    marker=EVIDENCE / "ifc-opaque-coordinate-patch.json"
    if marker.exists():
        assert sha(path)==json.loads(marker.read_text())["after_sha256"]
        return
    extraction=json.loads((EVIDENCE / "extraction/ifc.json").read_text())
    original_sha=next(row["sha256"] for row in extraction["files"] if row["path"]==relative)
    assert sha(path)==original_sha
    original=path.read_bytes().decode("utf-8")
    newline="\r\n" if "\r\n" in original else "\n"
    declarations=newline.join(["%template(OpaqueCoordinate_3) IfcGeom::OpaqueCoordinate<3>;",
        "%template(OpaqueCoordinate_4) IfcGeom::OpaqueCoordinate<4>;",""])
    assert original.count(declarations)==1 and original.count("#ifdef IFOPSH_WITH_CGAL")==1
    modified=original.replace(declarations,"")
    modified=modified.replace("#ifdef IFOPSH_WITH_CGAL",declarations+newline+"#ifdef IFOPSH_WITH_CGAL")
    patch=EVIDENCE / "patches/ifc-opaque-coordinates-nocgal.patch"
    patch.parent.mkdir(exist_ok=True)
    patch.write_bytes("".join(difflib.unified_diff(original.splitlines(keepends=True),modified.splitlines(keepends=True),
        fromfile="a/"+relative,tofile="b/"+relative)).encode("utf-8"))
    run("ifc-opaque-patch-check",["git","apply","--check",patch],cwd=source,env=env,budget=120)
    run("ifc-opaque-patch",["git","apply",patch],cwd=source,env=env,budget=120)
    assert path.read_bytes().decode("utf-8")==modified
    json_write(marker,{"source_commit":IFC_COMMIT,"path":relative,"before_sha256":original_sha,"after_sha256":sha(path),
        "patch":str(patch),"patch_sha256":sha(patch),"change":"Move two generic OpaqueCoordinate SWIG template declarations outside optional CGAL guard",
        "reason":"Always-exposed native position/axis/plane_equation methods return these generic coordinates; CGAL-disabled wrapper otherwise fails MSVC C2248",
        "geometry_kernel_changed":False,"active_runtime_modified":False})


def build_occt(paths,env):
    build=DEST / "build/occt"; install=DEST / "sdk/occt"
    run("occt-configure",["cmake","-S",paths["occt"],"-B",build,"-G","Ninja","-DCMAKE_BUILD_TYPE=Release",
        f"-DINSTALL_DIR={install}",f"-DCMAKE_INSTALL_PREFIX={install}","-DBUILD_LIBRARY_TYPE=Static","-DCMAKE_DEBUG_POSTFIX=",
        "-DBUILD_MODULE_Draw=OFF","-DBUILD_RELEASE_DISABLE_EXCEPTIONS=OFF","-DUSE_XLIB=OFF","-DUSE_FREETYPE=OFF",
        "-DUSE_OPENGL=OFF","-DUSE_GLES2=OFF","-DUSE_TBB=OFF","-DUSE_VTK=OFF","-DBUILD_USE_PCH=ON",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5","-DMSVC_STATIC_RUNTIME=OFF"],env=env,budget=600)
    run("occt-compile",["cmake","--build",build,"--parallel","4"],env=env,budget=14400)
    run("occt-install",["cmake","--install",build],env=env,budget=1800)


def build_boost(paths,env):
    source=paths["boost"]
    env=env.copy()
    # Boost's engine scripts invoke sibling batch helpers by bare filename.
    # Keep the host's current-directory search restriction and add only this
    # hash-retained build-script directory to the isolated child PATH.
    env["PATH"]=str(source / "tools/build/src/engine")+os.pathsep+env["PATH"]
    if not (source / "b2.exe").exists():
        run("boost-bootstrap",["cmd.exe","/d","/c",str(source / "bootstrap.bat")],cwd=source,env=env,budget=600)
    run("boost-compile",[source / "b2.exe","-j4","toolset=msvc","address-model=64","variant=release","link=static",
        "runtime-link=shared","threading=multi","--with-system","--with-program_options","--with-regex","--with-thread",
        "--with-date_time","--with-iostreams","--with-filesystem","stage",f"--stagedir={DEST / 'sdk/boost'}"],cwd=source,env=env,budget=7200)


def build_ifc(paths,env):
    build=DEST / "build/ifc"; install=DEST / "sdk/ifc"
    occt_libs=list((DEST / "sdk/occt").rglob("TKernel.lib"))
    occt_headers=list((DEST / "sdk/occt").rglob("Standard_Version.hxx"))
    assert len(occt_libs)==len(occt_headers)==1
    flags={"MINIMAL_BUILD":"OFF","BUILD_IFCPYTHON":"ON","BUILD_IFCGEOM":"ON","WITH_OPENCASCADE":"ON","WITH_CGAL":"OFF",
        "BUILD_CONVERT":"OFF","BUILD_GEOMSERVER":"OFF","BUILD_EXAMPLES":"OFF","COLLADA_SUPPORT":"OFF","GLTF_SUPPORT":"OFF",
        "HDF5_SUPPORT":"OFF","IFCXML_SUPPORT":"OFF","WITH_PROJ":"OFF","WITH_ROCKSDB":"OFF","WITH_ZSTD":"OFF",
        "BUILD_QTVIEWER":"OFF","BUILD_ONLY_COMMON_SCHEMAS":"OFF","VERSION_OVERRIDE":"ON","ADD_COMMIT_SHA":"ON",
        "BUILD_SHARED_LIBS":"OFF","BUILD_DOCUMENTATION":"OFF","USE_MMAP":"OFF"}
    command=["cmake","-S",paths["ifc"] / "cmake","-B",build,"-G","Ninja","-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install}",f"-DPYTHON_MODULE_INSTALL_DIR={DEST / 'python'}",
        f"-DPYTHON_EXECUTABLE={sys.executable}",f"-DPYTHON_INCLUDE_DIR={Path(sys.base_prefix) / 'include'}",
        f"-DPYTHON_LIBRARY={Path(sys.base_prefix) / 'libs/python312.lib'}",f"-DSWIG_EXECUTABLE={paths['swig'] / 'swig.exe'}",
        f"-DBOOST_ROOT={paths['boost']}",f"-DBOOST_LIBRARYDIR={DEST / 'sdk/boost/lib'}",f"-DEIGEN_DIR={paths['eigen']}",
        # Use the installed SDK's imported targets. The upstream manual-path
        # fallback exposes one interface target but IfcGeom links TKernel
        # directly, losing its required include directory in that fallback.
        "-UOCC_INCLUDE_DIR","-UOCC_LIBRARY_DIR",f"-DOpenCASCADE_DIR={DEST / 'sdk/occt/cmake'}",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        *[f"-D{k}={v}" for k,v in flags.items()]]
    json_write(EVIDENCE / "ifc-variant.json",{"flags":flags,"source_commit":IFC_COMMIT,"compiler_jobs":4,
        "scope":"STEP IFC and OpenCASCADE geometry; CGAL geometry and SVG-fill, IFCXML, HDF5, COLLADA, glTF, PROJ, RocksDB and ZSTD intentionally disabled; ordinary SVG serialization is not excluded by WITH_CGAL=OFF",
        "runtime_replacement":"NOT_AUTHORIZED_BY_BUILD_SUCCESS; independent application validation required"})
    run("ifc-configure",command,env=env,budget=600)
    run("ifc-compile",["cmake","--build",build,"--parallel","4"],env=env,budget=21600)
    run("ifc-install",["cmake","--install",build],env=env,budget=1800)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["prepare","occt","boost","ifc","all"],default="prepare")
    args=parser.parse_args()
    env=developer_environment()
    paths=prepare(env)
    for stage,function in [("occt",build_occt),("boost",build_boost),("ifc",build_ifc)]:
        if args.stage in (stage,"all"):
            function(paths,env)
