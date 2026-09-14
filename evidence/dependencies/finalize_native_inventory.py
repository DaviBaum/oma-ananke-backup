"""Assemble the retained native evidence without claiming redistribution approval."""
from pathlib import Path
import datetime, hashlib, json, tarfile, zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'native-review'
records=json.loads((OUT/'dll-code-correspondence.json').read_text())
packages=json.loads((OUT/'native-source-inventory.json').read_text())
retrievals=[]
for f in sorted(OUT.glob('retrievals-*.json')):
    for row in json.loads(f.read_text()):
        if 'file' in row and (OUT/row['file']).is_file():
            raw=(OUT/row['file']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==row['sha256'], row['file']
        retrievals.append(row)
assert len(records)==24 and all(r['matches_by_exact_text_section'] for r in records)
for r in packages:
    assert r['notices'], r['package']
    assert all((OUT/f).exists() for f in r['notices'])

core=[
 {'name':'IfcOpenShell','version':'0.8.5','commit':'1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2','source':'ifc-source.tar.gz','license':'LGPL-3.0-or-later for core; distributed binary additionally includes CGAL GPL-3.0-or-later/commercial components','evidence':['ifc-binary-embedded-provenance.json','ifc-native-imports.json','cgal-Nef_polyhedron_3.h']},
 {'name':'OCP bindings','version':'8.0.1.0','wheel_version':'8.0.1.0.0','commit':'b0495a71d10168b96cef8043ac39020a3fa45372','source':'ocp-source.tar.gz','generated_windows_source':'OCP_src_stubs_Windows.zip','license':'Apache-2.0'},
 {'name':'OCP wheel build and proxy','version':'8.0.1.0.0','commit':'9d9bbaa37f088667c902c6e41ca0d2d4707cba83','source':'ocp-build-source.tar.gz','license':'Apache-2.0'},
 {'name':'Open CASCADE in OCP','version':'8.0.1','commit':'b8f597c677811d1f9f4d8a97f5ae2825c0353a42','source':'occt-source-8.0.1.tar.gz','license':'LGPL-2.1-only WITH OCCT-exception-1.0','patch':'ocp-build-files/patches/occt-8.0.1/switch-vtk-freetype-cmake-order.patch'},
 {'name':'Open CASCADE in IfcOpenShell','version':'7.8.1','source':'occt-source-7.8.1.tar.gz','license':'LGPL-2.1-only WITH OCCT-exception-1.0','patch':'ifc-build-files/win/patches/V7_8_1.patch','correspondence':'Pinned recipe plus embedded native build paths; independent rebuild not performed'},
 {'name':'CGAL in IfcOpenShell','version':'5.5.5','source':'cgal-source-5.5.5.tar.gz','license':'Per-header GPL-3.0-or-later OR commercial; some packages LGPL-3.0-or-later','correspondence':'Pinned Windows recipe and embedded Nef header paths; GPL header captured; private dependency cache has no retained binary build attestation'},
]
static=[
 {'name':'Boost','recipe_version':'1.86.0','source_url':'https://archives.boost.io/release/1.86.0/source/boost_1_86_0.tar.gz','notice':'ifc-boost-LICENSE','scope':'Embedded versioned build paths; full source archive not downloaded'},
 {'name':'Eigen','recipe_version':'3.3.9','source_url':'https://gitlab.com/libeigen/eigen/-/archive/3.3.9/eigen-3.3.9.tar.gz','notice':'ifc-eigen-LICENSE','scope':'Required by IfcGeom CMake; full source archive not downloaded'},
 {'name':'MPIR','recipe_version':None,'source':'mpir-candidate-source.tar.gz','candidate_commit':'365957bc3f3c49908d07ec942a7019844a16daea','scope':'Current head of unpinned upstream recipe; NOT proven corresponding binary source'},
 {'name':'MPFR','recipe_commit':'2ebbe10fd029a480cf6e8a64c493afa9f3654251','source':'mpfr-source.tar.gz'},
 {'name':'HDF5','recipe_version':'1.13.1','source':'ifc-hdf5-source.tar.gz','scope':'Embedded versioned build paths'},
 {'name':'nlohmann/json','recipe_version':'3.6.1','source':'ifc-json-source.tar.gz'},
 {'name':'RocksDB','recipe_version':'9.11.2','source':'ifc-rocksdb-source.tar.gz','scope':'Pinned recipe; embedded RocksDB paths do not independently prove version'},
 {'name':'PROJ','recipe_version':'9.4.1','source':'ifc-proj-source.tar.gz','scope':'Recipe dependency, actual linked contribution not established'},
 {'name':'OpenCOLLADA with bundled PCRE/libxml2','recipe_commit':'064a60b65c2c31b94f013820856bc84fb1937cc6','source':'ifc-opencollada-source.tar.gz','scope':'Pinned recipe; embedded PCRE diagnostics; component linkage needs original build manifest'},
 {'name':'zstd','recipe_version':'1.5.7','source':'upstream-v1.5.7.tar.gz','scope':'Recipe dependency; compression optional'},
 {'name':'svgpp','recipe_commit':'5f1870aa7b757718ff5f86bdfb55966fa4f217f9','source':'ifc-svgpp-source.tar.gz'},
 {'name':'python-mvdxml','recipe_commit':'83c12fa494b9d6a5a370d8525dc1f76aa5c89d8d','source':'ifc-mvd-source.tar.gz'},
 {'name':'step-file-parser','recipe_commit':'30317826f8f743860ecff9e183699296593e42cb','source':'ifc-step-parser-source.tar.gz'},
]
gates=[
 {'id':'IFC_CGAL_DISTRIBUTION_TERMS','status':'OPEN','reason':'The installed IfcOpenShell native binary contains GPL/commercial CGAL code. LGPL wheel metadata is insufficient. No app license was changed and no commercial license was inferred. A CGAL-disabled replacement must be built and revalidated before an LGPL/permissive-only claim.'},
 {'id':'IFC_CORRESPONDING_BUILD','status':'OPEN','reason':'Pinned source and recipes retained, but upstream Windows job restores a mutable private build-outputs dependency cache, and MPIR is unpinned. Exact original dependency build correspondence and relink/rebuild completeness have not been proven.'},
 {'id':'MICROSOFT_REDISTRIBUTION_AUTHORITY','status':'OPEN','reason':'Exact 14.51.36247 runtime binaries/package notices and original Microsoft redistributable retained. Its runtime-use license is not itself redistribution permission. VS2026 REDIST permits listed unmodified code subject to a valid corresponding Visual Studio license. Local installed Build Tools is VS2022; no entitlement to redistribute these VS2026 binaries was inferred.'},
 {'id':'OCP_NATIVE_NOTICES_AND_SOURCES','status':'INVENTORIED','reason':'All 48 OCCT DLLs carry 8.0.1 resources; all 24 other DLLs match retained package executable sections. Complete generated Windows binding sources, OCCT sources/patch, 19 unique package upstream downloads and each notice/recipe retained. Exact rebuilt binary equivalence has not been tested.'},
 {'id':'WHOLE_APPLICATION_RELEASE','status':'OUT_OF_SCOPE','reason':'This bounded audit does not close VTK, Python, CUDA, all other wheels, data licenses, signing, installer, or application license decisions. Existing SBOM/release gates remain authoritative.'},
]
manifest={'schema_version':1,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'public_redistribution_status':'NOT_READY','local_personal_offline_qa':'AVAILABLE; no public distribution performed','core':core,'ifc_static_and_submodules':static,'ocp_dll_count':72,'occt_dll_count':48,'other_dll_count':24,'other_dll_correspondence':records,'transitive_sources':packages,'downloads':retrievals,'gates':gates,'validation':'All retained retrieval SHA256 values checked; every transitive package download matched its published SHA256 and every extracted DLL matched info/paths.json. Machine code .text sections match installed DLLs, while delvewheel relocation changes import metadata. These comparisons do not assert whole-file identity.'}
(OUT/'native-distribution-review.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

notice_files=[OUT/'ifc-COPYING',OUT/'ifc-COPYING.LESSER',OUT/'ifc-boost-LICENSE',OUT/'ifc-eigen-LICENSE',OUT/'ocp-LICENSE']
for item in packages: notice_files += [OUT/f for f in item['notices'] if Path(f).suffix.lower() not in ['.docx','.rtf']]
for folder in (OUT/'source-notices').iterdir():
    notice_files += [f for f in folder.rglob('*') if f.is_file() and (f.name.lower().startswith(('license','copying','copyright','notice')) or f.name=='OCCT_LGPL_EXCEPTION.txt') and f.suffix.lower() not in ['.py','.h','.hpp','.hxx','.c','.cpp','.png','.svg']]
notice_files.append(OUT/'microsoft-runtime-license-from-docx.txt')
seen=set();parts=['OMA + ANANKE — NATIVE THIRD-PARTY NOTICE COLLECTION\n\nPublic redistribution is NOT cleared. Read native-distribution-review.json and README.md.\n\nThis software makes use of facilities provided by Open CASCADE Technology 7.8.1 and 8.0.1.\nIfcOpenShell, CGAL, OCP, the image/codec libraries, and Microsoft runtime components retain their respective licenses and authorship. No endorsement is implied.\n\nThese texts are preserved from the pinned sources and binary package records. Some source archives include notices for optional components; this collection does not claim every such component is used.\n']
for f in notice_files:
    raw=f.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha in seen:continue
    seen.add(sha)
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('latin-1')
    parts.append('\n'+'='*78+'\nSOURCE: '+str(f.relative_to(OUT))+'\nSHA256: '+sha+'\n'+'='*78+'\n'+text)
(OUT/'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(parts),encoding='utf-8')
print(json.dumps({'status':manifest['public_redistribution_status'],'dlls':72,'notice_texts':len(seen),'retrieval_records':len(retrievals),'inventory':'evidence/dependencies/native-review/native-distribution-review.json'}))
