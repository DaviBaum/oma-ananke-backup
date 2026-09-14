# Native dependency provenance — 14 September 2026

**Public redistribution is NOT READY.** The local personal offline preview remains usable. This review changes no application license and performs no publication or runtime replacement. Its machine-readable decision is `native-distribution-review.json`.

The retained record covers the exact installed Windows/Python 3.12 IfcOpenShell 0.8.5 and cadquery-ocp 8.0.1.0.0 binaries, their pinned core sources, and all 72 DLLs bundled inside the OCP wheel. It does not clear all the other runtime packages in the application SBOM.

## What is now retained

- IfcOpenShell core source at `1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2`, its GPL/LGPL notices, Windows build recipe and patches, and source submodules that ship with the Python or SVG components.
- OCP binding source at `b0495a71d10168b96cef8043ac39020a3fa45372`, the complete generated Windows C++ binding/stub release (verified against the publisher's SHA-256), and wheel/proxy build source at `9d9bbaa37f088667c902c6e41ca0d2d4707cba83`.
- OCCT 8.0.1 source at `b8f597c677811d1f9f4d8a97f5ae2825c0353a42`, the applied wheel-build patch, LGPL 2.1 text and OCCT header exception. The 48 `TK*.dll` resources identify 8.0.1. IFC separately embeds OCCT 7.8.1; its source and Windows patch are retained too.
- Exact conda-forge package archives, SHA-256-verified package records, source recipes, recipe patches, and notices for all 24 other OCP DLLs. Every installed DLL's complete `.text` section matches a retained package DLL; many additional sections match too. This is machine-code correspondence, not a claim of whole-file identity: wheel relocation changes DLL import metadata.
- All 19 unique downloads referenced by those selected transitive source recipes, including the original Microsoft runtime installer, match the recipe's SHA-256. The executable is retained as provenance and was **not executed**. FreeImage and FreeType had no packaged notice files, so their notices were recovered from the exact source archives. `recovered-missing-source-notices.json` records that repair.
- `THIRD_PARTY_NOTICES.txt` collects 140 distinct retained notice texts, including optional source-component notices. Original paths and hashes accompany each text. `native-source-inventory.json` maps every selected transitive package to the relevant texts and build recipe.

The precise transitive versions are FreeImage 3.18.0, FreeType 2.12.1, Imath 3.2.3, OpenEXR/Iex/IlmThread 3.4.15, Little CMS 2.19.1, Lerc 4.2.0, libdeflate 1.25, libjpeg-turbo 3.2.0, xz/liblzma 5.8.3, libpng 1.6.58, LibRaw 0.22.2, libtiff 4.7.2, libwebp 1.6.0, zlib 1.3.2, OpenJPEG 2.5.4, OpenJPH 0.31.0, zstd 1.5.7, and MSVC CRT/OpenMP 14.51.36247. Little CMS's PE resource says 2.19.0, but the package code and original DLL hash identify the 2.19.1 package; the raw resource is preserved rather than silently corrected.

This software makes use of facilities provided by Open CASCADE Technology. Portions of this software are copyright © 2022 The FreeType Project (www.freetype.org). All rights reserved. These acknowledgements convey no endorsement and do not replace the accompanying licenses.

## Remaining distribution gates

1. **The installed IFC binary is not adequately described by LGPL-only metadata.** Its embedded build diagnostics identify CGAL Nef and polygon processing code. The pinned `Nef_polyhedron_3.h` explicitly identifies GPL-3.0-or-later or a commercial license. `ifc-binary-embedded-provenance.json`, `ifc-native-imports.json`, and the retained header establish this independently of PyPI's classifier. No commercial CGAL entitlement or application licensing decision has been inferred. A source archive and notice collection alone do not resolve this issue.
2. **The original IFC dependency build is not fully reproducible from retained public evidence.** Its Windows workflow restores a mutable `IfcOpenShell/build-outputs` dependency cache through a secret; MPIR is fetched without a revision. The current MPIR head is retained as a candidate source, explicitly not proven corresponding source. Boost 1.86.0 and Eigen 3.3.9 have source links/notices but their full archives are not retained. HDF5, MPFR, RocksDB, OpenCOLLADA/PCRE/libxml2 and other recipe dependencies are separately inventoried. A controlled rebuild with fixed source inputs is the practical way to close correspondence.
3. **Microsoft runtime redistribution authority remains unproven.** Exact 14.51.36247 binaries and the original runtime-use terms are retained, including the authoritative packaged DOCX. The packaged convenience TXT contains older terms and is not treated as authoritative. The [VS2026 redistribution list](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution) grants distribution of listed unmodified files subject to the corresponding licensed development product. The locally observed toolchain is VS2022 Build Tools, and this audit does not infer rights for the newer VS2026 runtime. Preserve the original license DOCX and obtain a valid applicable distribution route, or rebuild with an appropriately licensed toolchain/runtime.
4. This audit does not clear VTK, Python, CUDA, every other wheel, datasets, signing, installer, or application license decisions. Preserve the parent release gates.

## Practical CGAL-disabled IFC build path

The pinned CMake source **supports this configuration**. `cmake/CMakeLists.txt:99` exposes `WITH_CGAL`; lines 336–338 only locate/link CGAL when it is enabled; lines 680–682 only build `svgfill` for Python when CGAL is enabled. `src/ifcwrap/CMakeLists.txt:70` likewise only links `svgfill` with CGAL. This is source inspection, not a successful configuration/build claim.

Do **not** use `MINIMAL_BUILD=ON` for our Python engine: that option forcibly disables `BUILD_IFCPYTHON` (lines 129–140). Keep it off and select dependencies explicitly:

```text
-DMINIMAL_BUILD=OFF
-DBUILD_IFCPYTHON=ON -DBUILD_IFCGEOM=ON
-DWITH_OPENCASCADE=ON -DWITH_CGAL=OFF
-DBUILD_CONVERT=OFF -DBUILD_GEOMSERVER=OFF -DBUILD_EXAMPLES=OFF
-DCOLLADA_SUPPORT=OFF -DGLTF_SUPPORT=OFF -DHDF5_SUPPORT=OFF
-DIFCXML_SUPPORT=OFF -DWITH_PROJ=OFF -DWITH_ROCKSDB=OFF -DWITH_ZSTD=OFF
-DBUILD_QTVIEWER=OFF -DBUILD_ONLY_COMMON_SCHEMAS=OFF
-DVERSION_OVERRIDE=ON -DADD_COMMIT_SHA=ON
```

That proposed product variant supports STEP IFC input and Open CASCADE geometry; it intentionally omits IFC XML, HDF5, COLLADA, SVG/CGAL and RocksDB facilities. The engine's current STEP-based import, authoring and native Open CASCADE verification must all be revalidated against the resulting binary before replacing anything. This configuration is a candidate for LGPL/permissive-only dependency closure, not a final legal conclusion.

`lgpl-build-prerequisites.json` records the actual local inventory: VS2022 Build Tools 17.10.5 with x64 MSVC 14.40.33807, Windows SDKs through 10.0.22621.0, CMake 4.4.0, Ninja 1.11.1, and Python 3.12 headers/import library are present. Activate the x64 developer environment through the observed `vcvars64.bat`. SWIG is not on PATH and no complete local OCCT SDK was found. The OCP wheel supplies runtime DLLs, not a sufficient OCCT developer SDK.

Before any build, provision and pin a matching OCCT 7.8.1 SDK (source plus retained IFC patch), Boost 1.86.0, Eigen 3.3.9 and SWIG 4.2.1 with notices. Prefer an isolated SDK/output tree and explicit Python header/library/install destinations; do not point installation at the running `.venv`. The source recipe already compensates for old OCCT's CMake compatibility with `CMAKE_POLICY_VERSION_MINIMUM=3.5`; preserve and verify those adjustments under local CMake 4.4. Retain configuration, compiler, SDK, source hashes and generated wrapper sources. Then verify geometry behavior, candidate checks, IFC export/reimport and the complete regression suite under the new executable fingerprint. No large rebuild, configure step or installation was started during this audit.

## Reproduce the evidence checks

From the repository root, `.venv/Scripts/python.exe evidence/dependencies/finalize_native_inventory.py` rechecks retained download hashes and the notice/source mapping, then regenerates the manifest and notice collection. `native_probe.py` and `conda_notices.py` contain the read-only metadata/version and archive/PE-section probes. Network retrievals are pinned and recorded under `retrievals-*.json`; a current package listing is not itself a claim that a latest build was selected.
