# Windows check execution containment

The supported supervisor uses an unnamed Windows Job Object. It creates the
checker with `CREATE_SUSPENDED`, assigns and verifies membership in that job,
then resumes the primary thread. The job disallows both breakaway flags and
enables `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Only standard I/O handles are on
the explicit `STARTUPINFOEX` inheritance list; the job handle is not inherited.

A successful process outcome requires exit code zero **and zero active kernel
job members**. A sampled process tree is not completion authority. The kernel
process list supplies sampled RSS diagnostics; this is not a hard allocation
quota. Cancellation, a shared deadline, insufficient memory, accounting errors,
or a lingering descendant produce an incomplete control outcome. Termination
targets the owned job, never unrelated process IDs. Bounded shutdown and log
drainage may follow the work deadline. Undrained output is UNKNOWN and cannot
publish a checked candidate. Unsupported operating systems launch no checker.

The original Microsoft Store Python venv starts its real interpreter through
an App Execution Alias broker. Assigning that launcher to a job does not
contain the interpreter. The retained reproduction also shows why waiting for
the launcher and polling its descendants was insufficient. For an indirect
current Python executable, the supervisor now prepares a private bridge from
byte-identical copies of the loaded interpreter and its standard-library DLLs.
Its generated `pyvenv.cfg` uses the same standard library, and its `.pth` reads
the original venv packages. That startup file also restores the private `DLLs`
directory before loading those packages, including when a nested worker resets
`PYTHONPATH` to a fresh frozen application snapshot. Every recursive
`sys.executable` launch therefore
uses the direct copied interpreter. The active venv is unchanged. Private
`sys.prefix` differs; native package paths and frozen application imports remain
the original ones. The approximately 22 MB bridge is content-addressed and its
complete file inventory, source hashes, generated configuration and manifest
are revalidated before reuse. Already-direct portable Python needs no bridge.

This is lifecycle containment for ordinary `CreateProcess` descendants and a
locally trusted application/cache, not a hostile-code sandbox. Arbitrary
external broker services are outside the Job Object inheritance guarantee.
The supported Python launch path specifically avoids the observed broker.
Parent and child still apply the separate deferred-report/atomic-publication
fence; process completion by itself does not establish physical correctness.

Primary API contracts: [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[nested jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs),
[CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw),
[explicit startup attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
and the [CPython 3.12 venv launcher implementation](https://github.com/python/cpython/blob/3.12/PC/launcher.c).

Retained executable reproductions and observations live under
`evidence/release/process-tree-discovery-race/`. Earlier failing observations
remain immutable; later observations distinguish successful delayed completion
from termination and from unverified cleanup.
