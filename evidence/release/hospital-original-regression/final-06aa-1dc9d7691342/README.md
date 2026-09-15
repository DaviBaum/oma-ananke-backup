# Closed Hospital-backend regression evidence

Original status: PASS. Source: `06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949`. Exact declared tests: 3317.

`result.json` is the unchanged original receipt. `retention-result.json` independently reconciles the exact source/test inventory and XML node multiset. `copy-map.json` maps original paths to portable relative retained files. Native temporary Stores were excluded. The six bounded generated test artifacts, when present, remain in their original snapshot-relative locations.

For reproduction, use the separately provided original Python/native dependency environment and repository original mathematical inputs as applicable, set PYTHONPATH to this `src` and OMA_SHARED_TREE_SOURCE to `src/oma/optimization/shared_tree_synthesis.py`, then run the frozen `snapshot/tests` with pytest `-o pythonpath=ABSOLUTE_RETAINED_SRC`. This evidence is not a self-contained interpreter package. No new tests or Hospital CAD checks were run while retaining it.

The local-tee comparison supplements retain their own failures, exact source identities and limited geometry scope. A Hospital campaign acceptance/export requires its separate current receipt; this full regression alone does not establish it.
