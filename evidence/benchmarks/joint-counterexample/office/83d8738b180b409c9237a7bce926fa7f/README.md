# Office fresh-counterexample workflow and export

The pinned `fc2eda1a64dc502bf4f3339cdca7d4d70286573bb90f17d4feb7113e07972f54`
backend completed all four assignments, accepted its selected checked candidate
at revision 1, and independently rechecked the exported IFC. Total workflow:
244.656 s; four-assignment worker: 193.187 s. All nine export release bindings
are true. Original project and source bytes remain unchanged.

| Assignment | Disposition | Source pairs performed | Cross-route check | Check/selection interval |
|---|---|---:|---|---:|
| 0:0 / 0:0 / 0:0 | REJECTED | 2,409 | Complete: FAIL | 57.094 s |
| 0:0 / 0:0 / 1:0 | REJECTED | 0 | One fresh failure; full denominator NOT_RUN | 6.238 s |
| 0:0 / 1:0 / 0:0 | CHECKED | 2,409 | All 3 pairs: PASS | 57.589 s |
| 0:0 / 1:0 / 1:0 | CHECKED | 2,409 | All 3 pairs: PASS | 57.185 s |

The second assignment generated new IFC GUIDs. Its supervised native child
copied and verified its parser input bytes, then freshly found one current
positive-volume intersection in 1.750 s. It reused no old verdict. All remaining
physical checks and objective authority are explicitly absent in its early
report. The entire failed-assignment check/selection interval was 6.238 s,
compared with 54.002 s in the frozen baseline.

The same frozen specification root
`e9f3766b2066f80510f11b0f48a2ec2844a03689061780d65881c4d4a4dd2d2e`
produced the same REJECTED, REJECTED, CHECKED, CHECKED sequence in both attempts.
Both checked layouts retain native length 3.600000000000005 m and zero fittings.
`comparison.json` records a 16.6003% reduction in observed worker time, excluding
acceptance/export from both sides. These are single local observations; other
tests can contend for resources. There is no general speedup or optimality claim.

This campaign explicitly adds a hypothetical third parallel service with two
alternatives to the retained original two-demand mission. It does not claim to
be the unchanged original benchmark or a whole-building engineering solution.

Selected candidate: `0d8f6fc6b0564461b236c2c4c1d735e4`.
Export: `c2f045f52cd0427ba65a575494b331e1`.
Exported IFC SHA:
`229093e0d37ed9efa9fe0668c60a21ac94244a250a2b2c4eabeaaa3df6c4194d`.
Fresh export report:
`6f4f25a5ae87fa378fe218588e25ac688b1cb555f25ced30bb77966a0a0b441c`.
That complete report covers 2,409 original-source pairs plus all three
cross-route pairs and passes in its separately supervised 45.547 s full check.

The subsequent `f39800f5...` source adds only a malformed-child-witness type
guard; this workflow remains evidence for its actual pinned `fc2eda1a...` build.
The final-source regression suite is retained separately.
