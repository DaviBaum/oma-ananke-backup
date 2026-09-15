# Office finite shared-tree generation: retained 4b0 campaign

The exact campaign is under `5f68a587a8654bd187768d03f913388d/`. Its canonical completion receipt is [completion-audits/7732ef7f654c4cecb392f3456048f6ec/result.json](5f68a587a8654bd187768d03f913388d/completion-audits/7732ef7f654c4cecb392f3456048f6ec/result.json).

Frozen source **4b0af802a0934f31a0fc0812a9d23afccb22b048e48f888604d7ff9c1603fbb0** generated four alternatives from explicit source/sink requirements, two finite tee sites, stubs and a detour plane. No complete input trees were supplied. All four alternatives passed native geometry and fixed-flow service checks. Normal selection chose the 5 m, one-tee, four-part network; the other alternatives each measured 5.892699081698725 m with three fittings. Selection, revision-1 acceptance and fresh IFC export/recheck completed in 117.938 s.

Selected and exported geometry each has four parts, nine ports, 803 original obstacles, 3,212 source pairs and six self pairs. Each other alternative has eight parts, 17 ports, 6,424 source pairs and 28 self pairs. All 62,930 canonical parsed original IFC entities are preserved. Original source bytes, mission, project head, run and candidate remained unchanged. Canonical parsed preservation is distinct from serializer text equality.

This is a newly declared hypothetical fixed-flow mission: two simultaneous 0.5 L/s demands and 100 Pa available static pressure per sink, with explicit ideal-bore and loss assumptions. It does not establish a pressure-driven operating point, a global geometric optimum, or improvement over older missions. The later **33a coupled analytic workflow is a separate checkpoint**, retained in [the independent evidence collection](../../math/shared-tree-native-independent/README.md).

The original reporting failures remain unchanged: a missing finite-verifier output limit, an incorrect baseline-root comparison, and a final cp1252/UTF-8 project-name comparison that incorrectly reported input mutation. The separate completion audit verifies unchanged bytes and database state with explicit UTF-8; no native rerun was used to reconcile that reporting failure.

The folder contains exact evidence, actual IFCs, reports and scripts, not a duplicated live Store. `public-mapping.json` links original paths to these copies and the shared frozen source dependencies. `files-index.json` and `handoff.json` bind this public collection. Verify both collections with the standard-library `evidence/math/shared-tree-native-independent/verify.py` script.
