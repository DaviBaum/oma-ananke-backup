The historical audit's “62,930 original STEP records compare identically” means equality of each original entity's IfcOpenShell canonical string after parsing. It did not compare original record text bytes. Its unchanged implementation shows that comparison explicitly.

A separate read-only audit of the same original and saved export confirms all 62,930 parsed entity strings match, while 14,650 original raw strings are reformatted and 48,280 remain text-identical. Examples include decimal formatting changes. Original IFC file bytes and saved export hashes remain unchanged. No native check, optimization or acceptance was rerun.

See `step-text-scope-audit.json` and `evidence/release/audit_historical_step_text.py`. The earlier receipts remain unchanged; no exact decimal-token preservation or equivalence under other parsers is claimed.
