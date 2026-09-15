# Export verification lifecycle

Single-route, simultaneous-route and shared-network exports use one configurable
budget for their preparation and fresh child checks. The Python API accepts
`export_project(..., budget_seconds=3600)` without changing its existing positional
arguments. The loopback export endpoint accepts `budget_seconds`, and the CLI
accepts `--budget-seconds`. The permitted range is 1–7200 seconds, finite only.

An export writes its draft manifest and original state before running checks.
Every round-trip and independent verifier uses the same immutable executable
snapshot. Child checks share the remaining deadline instead of receiving a new
budget each time. Native parsing is supervised outside its process: elapsed time,
aggregate memory of the observed child tree and a 2 GiB machine reserve are
checked at approximately 100 ms intervals. The tree memory limit is the smaller
of 48 GiB and 37.5% of system RAM. Deadline/resource failures stop the owned tree
and preserve an explicit `UNKNOWN_*` outcome. Process cleanup has its own bounded
waits; ordinary filesystem copying/hashing and final evidence persistence are
synchronous and can complete outside the deadline. This is not a hard real-time
operating-system guarantee.

After the top-level Windows Python launcher exits, already observed descendants
receive at most one second to finish shutdown, within the shared deadline and
continuing memory supervision. A persistent descendant prevents completion. This
avoids rejecting the brief native child teardown race without accepting an
abandoned checker process; real-process success and persistent-child tests cover
both outcomes.

Each child has a `checks/NNN-stage/check.json` record with the executable version,
command, process identity, elapsed time, peak observed tree memory, exit status
and any termination outcome. Each output stream retains at most 1 MiB. Full
observed byte counts and stream hashes identify truncation; output beyond that
limit is drained without retaining it. A child that writes a passing sidecar but
then times out cannot authorize an export. The observed sidecar status and the
effective process outcome remain separately recorded.

`CHECKED_LOCAL_SCOPE` requires a fresh passing report for the exact exported
candidate root, the frozen executable version, unchanged mission/rules/objective
and engineering scope, every original check plus the required exported-federation
correspondence checks, and matching current bytes for every exported IFC file.
No duplicate check identifiers are accepted. An incomplete or mismatched result
remains `DRAFT`, with the IFC copies, state, events, manifest and available check
logs retained. It is never upgraded to whole-building certification.

The regression suite injects real process timeouts and resource failures, checks
that an unrelated process survives descendant cleanup, and retains a real IFC
round-trip followed by a timed-out full verification. Native integration tests
cover ordinary routing, simultaneous routing, shared networks, network revisions
and an explicitly authorized host opening. This lifecycle changes no geometric
or mathematical checker rules.
