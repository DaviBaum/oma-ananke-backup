# Exact reference-frame identity

The selected federation reference now has an exact identity self-map after all existing source/alignment prerequisites pass. Other sources retain their measured transforms; this is not tolerance-based snapping.

The actual Hospital ARC reference formerly produced diagonal 1.0000000000000002 and off-diagonal values around 1e-17. That missed the CAD identity fast path. Four retained authored native components required four transform/reinspection calls before the fix and zero afterward; afterward all four original in-memory native objects are preserved. The same fast path applies to reference-source obstacles, but this probe does not measure whole-model speed or certify those obstacles.

All 54 focused federation/native consumers passed. The separate actual semantic-only profile returned PASS over 1,346,650 original parsed records, four new components and nine ports. Profiling overhead is included: 58.59 seconds total, with 17.84 seconds in three IFC parses and substantial Python entity wrapping/comparison cost. This is a partial semantic observation, not a whole-Hospital feasibility report. Full architectural clearance remains pending, and all seven disciplines are not aligned or checked by this probe.

The contained probe completed in 80.734 seconds with zero remaining processes; peak sampled tree RSS was 3,004,866,560 bytes. Original input and candidate bytes, the fixed original CAD/semantics source, and both federation implementations remained unchanged. The initial wrapper's missing build-environment key failed before any child/native work and remains separately retained.
