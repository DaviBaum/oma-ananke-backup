# Managed native checker execution and publication

Ordinary routes, simultaneous route sets, shared networks, baseline checks,
historical rechecks and fresh export checks now use one deferred publication
protocol. A private PASS is evidence produced by a child, not a live candidate
verdict. The parent can publish it only after successful supervised completion
and current transactional admission. The mathematical and physical scopes of
the report remain unchanged.

`Store.begin_check_execution` gives one fresh identity authority over exactly
one candidate. Its immutable binding includes the candidate root and payload,
project, original run/request/baseline, optional recheck control run/request,
mission, rules, source manifest, executable and shared monotonic deadline.
Beginning a new check makes that candidate CHECKING and supersedes an older
running identity. Its preceding report remains retained for inspection.

The fresh interpreter uses `DeferredVerificationStore`. It reloads persisted
inputs, runs the normal independent checker and writes one invocation-bound
private receipt plus an immutable report blob. It cannot publish CHECKED.
Successful exit without the exact current receipt is incomplete. A timeout,
cancellation, resource limit, abnormal exit or stale receipt cannot grant a
physical verdict even if a private PASS exists.

After receipt validation and report-assurance construction, Store checks the
current execution, candidate, origin and control identities again inside the
same SQLite transaction that commits the report, candidate status and events.
A terminal, cancelled or paused control owner, expired deadline, changed
request/root/scope or superseding check blocks admission. Only the still-owning
identity may close an incomplete execution as UNKNOWN with no current report.
An older cleanup cannot erase a newer report. Other completed incumbents from
the run are preserved and remain eligible under their own current evidence.

Acceptance revalidates the current candidate, exact report, execution, scope
and executable inside the revision transaction, after expensive transition
derivation. Managed acceptance inserts an exact-report authorization row; the
revision insert consumes it in the same transaction. Revision, event and
idempotency response commit or roll back together.

Managed physical PASS publication and physical acceptance also freshly hash
every current source and materialized IFC, plus the protected baseline's source
and route/network materializations. Resolved paths with conflicting expected
hashes, missing bytes or changed file/handle identities block publication. The
sweep runs inside the transaction so relocation aliases remain consistent.
Its immutable byte-applicability artifact is retained in the publication event.
The report's geometry is not recomputed by this hash sweep, and it does not lock
out arbitrary filesystem writers. Native tests first moved an actual source
wall and enlarged an exported pipe into a collision after a genuine PASS; both
old acceptances succeeded. Both now reject, as does a mutation after real parent
assurance construction. Unchanged geometry still accepts.

SQLite triggers also enforce the managed boundary for older frozen APIs that
share the same database. Their old candidate UPDATE cannot publish a late or
superseded report, and their old revision INSERT lacks the transactional
exact-report authorization. Unmanaged historical candidates retain their
legacy behavior. Database backups retain the triggers. The initial trigger
bodies are immutable under their current names; any future tightening requires
an explicit versioned migration, not a silent `CREATE IF NOT EXISTS` edit.

The retained investigations include a real native late PASS that was previously
manually acceptable after caller timeout, actual nested Windows descendants,
native exports that finish their check before an abnormal process disposition,
and a synthetic acceptance interleaving that changes executable identity after
transition derivation. Both the initially failing evidence and corrected
regressions remain present. Analytic Store fixtures test transaction ordering;
they do not stand in for the separate native physical checks.

Relevant regression evidence includes:

- `evidence/release/managed-check-integration-corrected.xml`: 130 ordinary,
  joint, network, selection, export and interruption tests on `ecccd882...`.
- `evidence/release/managed-execution-database-fences.xml`: 45 Store and
  database compatibility/atomicity tests on `01efe4bc...`.
- `evidence/release/acceptance-build-freshness.xml`: two acceptance
  interleavings on `01efe4bc...`.
- `evidence/release/managed-owner-terminal-stop.xml`: three actual child
  private-PASS interruptions on `5636d709...`.
- `evidence/release/acceptance-input-freshness.xml`: four actual native input
  mutation/publication/acceptance checks on `dd5f0bfe...`.

The process-ownership review also reproduced a detached descendant missed by
periodic process-tree discovery. That finding is retained under
`evidence/release/process-tree-discovery-race/`. Checkers and EngineService
workers now launch suspended, enter a Windows Job Object before execution,
and require the kernel's active-process count to reach zero before successful
completion. Cancellation terminates the owned job. A separately hash-checked
interpreter bridge prevents Microsoft Store Python's launcher broker from
escaping that ownership; ordinary portable Python runs directly. Nested native
checker imports and actual service shutdown pass in the 17-test checkpoint
`evidence/release/windows-job-nested-startup-corrected.xml` on `f4fe04b0...`.
See `docs/windows-check-containment.md` for the exact ownership and resource
scope. This is process containment, not a hostile-code security sandbox.

Command-line verification also creates a fresh managed recheck owner instead
of writing a report through the historical run. Its 11-test native checkpoint
is `evidence/release/cli-managed-verify.xml` on `4396616c...`. Service thread
registration/start and shutdown are serialized; three startup/shutdown race
tests pass on `e3fde02b...` in `evidence/release/service-start-shutdown.xml`.

Shared deadlines prevent a late report from being admitted. Parent-side
assurance construction and SQLite lock acquisition may finish after that
deadline before admission rejects it; this protocol does not claim those
operations are preemptible or that cleanup takes zero time. Operating-system
containment also does not remove common-mode risks in the native CAD kernel.
