# Independent committed-checkpoint audit

Commit: `633a6cdbcd75a24b0146f4d8228edef1bc0c4046`.

The standard-library audit resolves the immutable Git tree, reads blobs by their object IDs, verifies each Git blob object hash and compares SHA-256 values with the committed frozen manifests. All 114 application files, 305 test/support inputs and ten integrated documentation/example files match. These 429 files include the complete committed Python application inventory and all 138 committed Python test files. The original receipt's exact 3,275 test-node multiset also matches its retained JUnit report; no test was executed.

The audit checks 27 recovery/full-suite/Hospital entrypoints and their local Markdown targets inside the same commit. It verifies the committed backup and EDF release manifest bindings, not the current remote service or binary archive contents. No archive was downloaded or extracted. The EDF archive remains distinct from the live f73 source; the newer package status is outside this audit.

The Hospital federation alignment blocker and separate architectural timeout remain unresolved outcomes. All 42 scoped mathematics obligations and every original full-algorithm false flag remain unchanged. Exact stored bytes and retained successful test receipts do not establish complete mathematics, new native feasibility, complete dependency reproduction on another machine or a whole-building result.

Run `python audit.py` from this directory in a clone containing the pinned commit. It requires only Python and Git. `result.json`, `verified-files.json` and `verified-entrypoints.json` contain the complete comparison results. The script writes only those local audit files; it does not alter Git objects, source, tests or release indexes.
