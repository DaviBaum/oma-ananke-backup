"""Independent recursive interpreter/import parity probe; no production edits.

Run with the intended immutable oma source PYTHONPATH. Three ordinary
sys.executable descendants stay alive together until the supervisor callback
releases them. Every process executes the real native dependency imports.
"""
from pathlib import Path
import importlib.metadata
import json
import os
import sys
import time
import uuid

from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json, sha256_file


CHILD = r'''
import ctypes, importlib.metadata, json, os, pathlib, subprocess, sys, time
import psutil, ifcopenshell, numpy, scipy, pydantic, oma
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
directory, depth = pathlib.Path(sys.argv[1]), int(sys.argv[2])
buffer = ctypes.create_unicode_buffer(32768)
ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer))
packages = ['ifcopenshell', 'cadquery-ocp', 'numpy', 'scipy', 'pydantic', 'psutil']
record = dict(pid=os.getpid(), created=psutil.Process().create_time(), depth=depth,
    executable=sys.executable, loaded_image=buffer.value,
    prefix=sys.prefix, base_prefix=sys.base_prefix, base_executable=sys._base_executable,
    path=sys.path, oma_path=list(oma.__path__),
    versions={name:importlib.metadata.version(name) for name in packages},
    actual_native_box_nonempty=not BRepPrimAPI_MakeBox(1.,2.,3.).Shape().IsNull(),
    actual_ifc_schema=ifcopenshell.file(schema='IFC4').schema)
(directory / ('process-'+str(depth)+'.json')).write_text(json.dumps(record),encoding='utf-8')
if depth:
    nested = subprocess.Popen([sys.executable, '-c', sys.argv[3], str(directory), str(depth-1), sys.argv[3]],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if nested.wait(timeout=15):
        raise RuntimeError('nested interpreter failed')
else:
    expiry = time.monotonic()+10
    while not (directory/'release').exists():
        if time.monotonic() >= expiry:
            raise RuntimeError('release was not received')
        time.sleep(.01)
'''


def main():
    directory = Path(__file__).resolve().parent/'bridge-attempts'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    version = checker_version()
    packages = ['ifcopenshell','cadquery-ocp','numpy','scipy','pydantic','psutil']
    expected = {name:importlib.metadata.version(name) for name in packages}
    first_ready = None
    def control():
        nonlocal first_ready
        if all((directory/f'process-{i}.json').exists() for i in range(3)):
            if first_ready is None:
                first_ready = time.monotonic()
            # Hold the three descendants together for several supervisor polls.
            if time.monotonic()-first_ready >= .35:
                (directory/'release').write_text('release all three ordinary descendants')
        return False
    result = supervise_check([sys.executable,'-c',CHILD,str(directory),'2',CHILD],
        environment={**os.environ,'OMA_EXECUTABLE_BUILD':version},directory=directory/'supervision',
        deadline=time.monotonic()+20,reserve_bytes=0,cancellation_requested=control)
    records = [json.loads((directory/f'process-{i}.json').read_text()) for i in range(3)
        if (directory/f'process-{i}.json').exists()]
    observed = {r['pid'] for r in result.get('containment',{}).get('observed_process_identities',[])}
    import oma
    checks = {
        'all_three_records':len(records)==3,
        'all_three_native_imports':len(records)==3 and all(r['actual_native_box_nonempty'] and r['actual_ifc_schema']=='IFC4' for r in records),
        'package_versions_equal':len(records)==3 and all(r['versions']==expected for r in records),
        'loaded_image_matches_recursive_executable':len(records)==3 and all(Path(r['executable']).resolve()==Path(r['loaded_image']).resolve() for r in records),
        'all_observed_in_owned_job':len(records)==3 and all(r['pid'] in observed for r in records),
        'frozen_oma_path_equal':len(records)==3 and all(r['oma_path']==list(oma.__path__) for r in records),
        'job_empty_at_completion':result['status']=='COMPLETED' and result['containment']['active_processes']==0,
    }
    summary = {'scope':'ACTUAL_RECURSIVE_PYTHON_AND_NATIVE_IMPORT_PARITY; NOT A SECURITY SANDBOX',
        'executable_version':version,'script_sha256':sha256_file(Path(__file__)),
        'checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL',
        'supervisor_status':result['status'],'elapsed_seconds':result['elapsed_seconds'],
        'attempt':str(directory),'parent_prefix':sys.prefix,'parent_executable':sys.executable,
        'expected_versions':expected,'records':records}
    atomic_json(directory/'observation.json',summary)
    atomic_json(Path(__file__).resolve().parent/'bridge-latest.json',summary)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
