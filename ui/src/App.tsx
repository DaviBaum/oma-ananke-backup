import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { projectView } from "./viewState";
import LocalFiles from "./LocalFiles";
import { uploadLocalFiles, type UploadStatus } from "./uploads";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Box,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Code2,
  Database,
  Eye,
  EyeOff,
  FileBox,
  FileCheck2,
  FolderOpen,
  Gauge,
  GitBranch,
  History,
  Info,
  Layers3,
  ListFilter,
  LoaderCircle,
  Maximize2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  StepForward,
  Terminal,
  TriangleAlert,
  Undo2,
  Unplug,
  X,
  Zap,
} from "lucide-react";
import Viewport, { disciplineColor } from "./Viewport";
import MissionFields from "./MissionFields";
import { buildMission, emptyMission } from "./mission";
import JointMissionFields from "./JointMissionFields";
import SharedNetworkFields from "./SharedNetworkFields";
import NetworkDiagram from "./NetworkDiagram";
import NetworkLineage from "./NetworkLineage";
import {
  prepareNetworkRevision,
  buildNetworkRevision,
  networkRevisionIsCurrent,
  type NetworkRevisionSeed,
} from "./networkRevision";
import { parseSharedNetwork } from "./sharedNetwork";
import { buildJointMission, newJointMission } from "./jointMission";
import { applicabilityReason, currentPassingCheck } from "./checkApplicability";
import { isServiceElement } from "./semantics";
import { scopeEvidence } from "./evidenceScope";
import type { MeshProgress } from "./meshStream";
import { recordTiming, observeControls, timingEvidence } from "./telemetry";
import { ArtifactLinks, SourceAudits, checkIssue } from "./Evidence";
import EvidenceReview, { type EvidenceTarget } from "./EvidenceReview";
import ValidationAdvisories from "./ValidationAdvisories";
import {
  request,
  api,
  mergeEvents,
  eventCursor,
  normalizeSnapshot,
  type StateSelection,
} from "./api";
import type {
  Candidate,
  EngineEvent,
  Geometry,
  Health,
  Issue,
  Project,
  Run,
  RunRequest,
  Snapshot,
  Status,
} from "./types";

const statusClass = (value?: string) => {
  const s = value?.toUpperCase() ?? "UNKNOWN";
  return /^(PASS|CHECKED|ACCEPTED|COMPLETED|OK|AVAILABLE)$/.test(s)
    ? "good"
    : /FAIL|REJECT|ERROR|CRASH/.test(s)
      ? "bad"
      : /RUNNING|CHECKING|QUEUED/.test(s)
        ? "live"
        : /BLOCK|UNKNOWN|STALE|MISSING|CANCEL/.test(s)
          ? "warn"
          : "neutral";
};
function Badge({ status }: { status?: Status }) {
  return (
    <span className={`badge ${statusClass(status)}`}>
      <i />
      {status ?? "UNKNOWN"}
    </span>
  );
}
const readable = (s: unknown): string =>
  typeof s === "string" ? s : (JSON.stringify(s, null, 2) ?? "—");
const date = (s?: string) =>
  s
    ? new Date(s).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
const short = (s?: string) => (s ? `${s.slice(0, 10)}…` : "—");
const bytes = (n?: number) =>
  n === undefined ? "Not reported" : `${(n / 1024 ** 3).toFixed(1)} GB`;
function Empty({
  icon: Icon = Info,
  title,
  children,
}: {
  icon?: typeof Info;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="panel-empty">
      <Icon size={27} strokeWidth={1.3} />
      <strong>{title}</strong>
      <p>{children}</p>
    </div>
  );
}
function KeyValue({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: unknown;
  mono?: boolean;
}) {
  return (
    <div className="key-value">
      <span>{label}</span>
      <strong className={mono ? "mono" : ""} title={readable(value)}>
        {value === undefined || value === null || value === ""
          ? "Not supplied"
          : readable(value)}
      </strong>
    </div>
  );
}
function Modal({
  title,
  kicker,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  kicker: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeRef.current();
      if (e.key === "Tab") {
        const nodes = Array.from(
          ref.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary,a[href],[tabindex="0"]',
          ) ?? [],
        );
        if (nodes.length && e.shiftKey && document.activeElement === nodes[0]) {
          e.preventDefault();
          nodes.at(-1)?.focus();
        } else if (
          nodes.length &&
          !e.shiftKey &&
          document.activeElement === nodes.at(-1)
        ) {
          e.preventDefault();
          nodes[0].focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal ${wide ? "wide" : ""}`}
      >
        <div className="modal-head">
          <div>
            <p className="eyebrow">{kicker}</p>
            <h2>{title}</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={19} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null),
    [projects, setProjects] = useState<Project[]>([]),
    [projectId, setProjectId] = useState<string | null>(
      localStorage.getItem("oma.project"),
    ),
    [headSnapshot, setSnapshot] = useState<Snapshot | null>(null),
    [headGeometry, setGeometry] = useState<Geometry | null>(null),
    [events, setEvents] = useState<EngineEvent[]>([]),
    [connected, setConnected] = useState(false),
    [syncError, setSyncError] = useState<string | null>(null),
    [geometryError, setGeometryError] = useState<string | null>(null),
    [loadingGeometry, setLoadingGeometry] = useState(false),
    [busy, setBusy] = useState<string | null>(null),
    [error, setError] = useState<string | null>(null),
    [notice, setNotice] = useState<string | null>(null);
  const [stateSelection, setStateSelection] = useState<StateSelection | null>(
      null,
    ),
    [viewSnapshot, setViewSnapshot] = useState<Snapshot | null>(null),
    [viewGeometry, setViewGeometry] = useState<Geometry | null>(null),
    [loadingView, setLoadingView] = useState(false),
    [viewError, setViewError] = useState<string | null>(null);
  const { snapshot, geometry } = projectView(
    projectId,
    stateSelection ? viewSnapshot : headSnapshot,
    stateSelection ? viewGeometry : headGeometry,
  );
  const [nav, setNav] = useState("model"),
    [rightTab, setRightTab] = useState("overview"),
    [bottomTab, setBottomTab] = useState("activity"),
    [search, setSearch] = useState(""),
    [storey, setStorey] = useState(""),
    [system, setSystem] = useState(""),
    [servicesOnly, setServicesOnly] = useState(false),
    [selected, setSelected] = useState<string | null>(null),
    [hiddenDisciplines, setHiddenDisciplines] = useState<Set<string>>(
      new Set(),
    ),
    [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set()),
    [isolated, setIsolated] = useState<string | null>(null),
    [selectedIssue, setSelectedIssue] = useState<Issue | null>(null),
    [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(
      null,
    ),
    [entityLimit, setEntityLimit] = useState(100),
    [eventSearch, setEventSearch] = useState(""),
    [eventFilter, setEventFilter] = useState("all"),
    [checkFilter, setCheckFilter] = useState("issues"),
    [checkLimit, setCheckLimit] = useState(60),
    [bottomExpanded, setBottomExpanded] = useState(false);
  const [modal, setModal] = useState<
      "import" | "run" | "export" | "record" | "help" | null
    >(null),
    [record, setRecord] = useState<unknown>(null),
    [importPaths, setImportPaths] = useState(""),
    [importName, setImportName] = useState(""),
    [importFiles, setImportFiles] = useState<File[]>([]),
    [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null),
    [operation, setOperation] = useState<RunRequest["operation"]>("check"),
    [scope, setScope] = useState("all"),
    [budget, setBudget] = useState(30),
    [missionForm, setMissionForm] = useState(emptyMission),
    [missionMode, setMissionMode] = useState<"single" | "joint" | "network">(
      "single",
    ),
    [jointMission, setJointMission] = useState(newJointMission),
    [sharedNetwork, setSharedNetwork] = useState(""),
    [networkRevision, setNetworkRevision] =
      useState<NetworkRevisionSeed | null>(null),
    [revisionAlternatives, setRevisionAlternatives] = useState(""),
    [draft, setDraft] = useState(true);
  const [evidenceTarget, setEvidenceTarget] = useState<EvidenceTarget | null>(
    null,
  );
  const recordJSON = useMemo(
    () => JSON.stringify(record, null, 2) ?? "null",
    [record],
  );
  const cursor = useRef(0),
    uploadAbort = useRef<AbortController | null>(null),
    generation = useRef(0),
    refreshRef = useRef<() => Promise<void>>(async () => {}),
    stateRoot = useRef("");
  useEffect(() => {
    if (headSnapshot) observeControls(headSnapshot.runs);
  }, [headSnapshot]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 8000);
    return () => clearTimeout(timer);
  }, [notice]);
  const [meshProgress, setMeshProgress] = useState<MeshProgress | null>(null),
    [viewMeshProgress, setViewMeshProgress] = useState<MeshProgress | null>(
      null,
    );
  const closeModal = useCallback(() => {
    uploadAbort.current?.abort(
      new DOMException(
        "File transfer cancelled. Received files remain local and can be reused on retry.",
        "AbortError",
      ),
    );
    setModal(null);
  }, []);
  const refreshProjects = useCallback(async () => {
    const list = await api.projects();
    setProjects(list);
    return list;
  }, []);
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [h, list] = await Promise.all([api.health(), api.projects()]);
        if (!mounted) return;
        setHealth(h);
        setProjects(list);
        setConnected(true);
        setSyncError(null);
        setProjectId((current) =>
          current && list.some((p) => p.id === current)
            ? current
            : (list[0]?.id ?? null),
        );
      } catch (e) {
        if (mounted) {
          setConnected(false);
          setSyncError((e as Error).message);
        }
      }
    };
    void load();
    const timer = setInterval(async () => {
      try {
        const h = await api.health();
        const projectList = await api.projects();
        if (mounted) {
          setHealth(h);
          setProjects(projectList);
          setConnected(true);
        }
      } catch (e) {
        if (mounted) {
          setConnected(false);
          setSyncError((e as Error).message);
        }
      }
    }, 10000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    const gen = ++generation.current;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined,
      disposed = false,
      polling = false;
    cursor.current = 0;
    stateRoot.current = "";
    setEvents([]);
    setSnapshot(null);
    setGeometry(null);
    setStateSelection(null);
    setSelected(null);
    setSelectedIssue(null);
    setSelectedCandidate(null);
    setHiddenDisciplines(new Set());
    setHiddenIds(new Set());
    setIsolated(null);
    setStorey("");
    setSystem("");
    setServicesOnly(false);
    setGeometryError(null);
    setMeshProgress(null);
    if (!projectId) {
      setLoadingGeometry(false);
      refreshRef.current = async () => {};
      return;
    }
    setLoadingGeometry(true);
    localStorage.setItem("oma.project", projectId);
    const current = () => !disposed && gen === generation.current;
    let ticks = 0;
    let observedRevision = -1;
    let observedSequence = -1;
    const refresh = async () => {
      const data = normalizeSnapshot(
        await api.snapshot(projectId, abort.signal),
      );
      if (!current()) return;
      if (data.project.revision < observedRevision) return;
      if (
        data.project.revision === observedRevision &&
        (data.events_seq ?? 0) < observedSequence
      )
        return;
      observedRevision = data.project.revision;
      observedSequence = Math.max(observedSequence, data.events_seq ?? 0);
      setSnapshot((previous) => {
        if (previous && previous.project.revision > data.project.revision)
          return previous;
        return previous?.project.state_root === data.project.state_root
          ? { ...data, entities: previous.entities, sources: previous.sources }
          : data;
      });
      setSelectedCandidate((previous) =>
        previous
          ? (data.candidates.find((c) => c.id === previous.id) ?? previous)
          : null,
      );
      if (stateRoot.current !== data.project.state_root) {
        stateRoot.current = data.project.state_root;
        setLoadingGeometry(true);
        setMeshProgress(null);
        setGeometryError(null);
        void (async () => {
          try {
            const mesh = await api.geometry(
              projectId,
              abort.signal,
              {
                revision: data.project.revision,
              },
              (progress) => {
                if (current() && stateRoot.current === data.project.state_root)
                  setMeshProgress(progress);
              },
            );
            if (current() && stateRoot.current === data.project.state_root) {
              if (mesh.state_root !== data.project.state_root)
                throw new Error(
                  "Geometry state root does not match the requested snapshot. Resynchronizing.",
                );
              setGeometry(mesh);
              setLoadingGeometry(false);
            }
          } catch (e) {
            if (current() && stateRoot.current === data.project.state_root) {
              setGeometryError((e as Error).message);
              setLoadingGeometry(false);
              stateRoot.current = "";
            }
          }
        })();
      }
    };
    refreshRef.current = refresh;
    let streamOpen = false,
      queue: EngineEvent[] = [],
      flushTimer: ReturnType<typeof setTimeout> | undefined,
      snapshotTimer: ReturnType<typeof setTimeout> | undefined;
    const stream = new EventSource(
      `/api/projects/${encodeURIComponent(projectId)}/stream?after=0`,
    );
    let disconnectedAt: number | undefined;
    const streamStarted = performance.now();
    stream.onopen = () => {
      if (current()) {
        const reconnected = disconnectedAt !== undefined;
        streamOpen = true;
        recordTiming(
          disconnectedAt === undefined
            ? "event_stream_connected"
            : "event_stream_reconnected",
          {
            project_id: projectId,
            elapsed_ms: performance.now() - (disconnectedAt ?? streamStarted),
            cursor: cursor.current,
          },
        );
        disconnectedAt = undefined;
        if (reconnected)
          void refresh().catch((error) => {
            if (current()) setSyncError((error as Error).message);
          });
      }
    };
    stream.onerror = () => {
      streamOpen = false;
      if (disconnectedAt === undefined) {
        disconnectedAt = performance.now();
        recordTiming("event_stream_disconnected", {
          project_id: projectId,
          cursor: cursor.current,
        });
      }
    };
    stream.onmessage = (message) => {
      if (!current()) return;
      try {
        const event = JSON.parse(message.data) as EngineEvent;
        if (
          event.project_id !== projectId ||
          !Number.isSafeInteger(event.seq) ||
          event.seq <= cursor.current
        )
          return;
        queue.push(event);
        if (!flushTimer)
          flushTimer = setTimeout(() => {
            flushTimer = undefined;
            if (!current()) return;
            const batch = queue;
            queue = [];
            setEvents((previous) => mergeEvents(previous, batch, projectId));
            cursor.current = eventCursor(batch, cursor.current);
            if (!snapshotTimer)
              snapshotTimer = setTimeout(() => {
                snapshotTimer = undefined;
                void refresh().catch((e) => {
                  if (current()) setSyncError((e as Error).message);
                });
              }, 750);
          }, 250);
      } catch {
        setSyncError(
          "An unreadable live event was received. Durable polling will resynchronize.",
        );
      }
    };
    const poll = async () => {
      if (!current() || polling) return;
      polling = true;
      let backlog = false;
      try {
        const incoming = await api.events(projectId, cursor.current);
        if (!current()) return;
        const valid = incoming.filter(
          (e) => e.project_id === projectId && e.seq > cursor.current,
        );
        if (valid.length) {
          setEvents((previous) => mergeEvents(previous, valid, projectId));
          cursor.current = eventCursor(valid, cursor.current);
          await refresh();
        } else if (++ticks % 24 === 0) {
          await refresh();
        }
        backlog = incoming.length >= 500;
        setConnected(true);
        setSyncError(null);
      } catch (e) {
        if (current()) {
          setConnected(false);
          setSyncError((e as Error).message);
        }
      } finally {
        polling = false;
        if (current())
          timer = setTimeout(poll, backlog ? 100 : streamOpen ? 5000 : 1500);
      }
    };
    void refresh()
      .then(poll)
      .catch((e) => {
        if (current()) {
          setError((e as Error).message);
          setLoadingGeometry(false);
          timer = setTimeout(poll, 2000);
        }
      });
    return () => {
      disposed = true;
      abort.abort();
      stream.close();
      if (flushTimer) clearTimeout(flushTimer);
      if (snapshotTimer) clearTimeout(snapshotTimer);
      if (timer) clearTimeout(timer);
    };
  }, [projectId]);
  useEffect(() => {
    setViewSnapshot(null);
    setViewGeometry(null);
    setViewError(null);
    setViewMeshProgress(null);
    if (!stateSelection || !projectId) {
      setLoadingView(false);
      return;
    }
    const abort = new AbortController();
    let live = true;
    setLoadingView(true);
    void (async () => {
      try {
        const data = normalizeSnapshot(
          await api.snapshot(projectId, abort.signal, stateSelection),
        );
        if (!live) return;
        setViewSnapshot(data);
        const mesh = await api.geometry(
          projectId,
          abort.signal,
          stateSelection,
          (progress) => {
            if (live) setViewMeshProgress(progress);
          },
        );
        if (live) {
          if (mesh.state_root !== data.project.state_root)
            throw new Error(
              "Geometry state root does not match this immutable replay snapshot.",
            );
          setViewGeometry(mesh);
          setLoadingView(false);
        }
      } catch (e) {
        if (live) {
          setLoadingView(false);
          setViewError((e as Error).message);
        }
      }
    })();
    return () => {
      live = false;
      abort.abort();
    };
  }, [stateSelection, projectId]);
  const perform = async (
    label: string,
    fn: () => Promise<unknown>,
    success?: string,
  ) => {
    if (busy) return;
    setBusy(label);
    setError(null);
    try {
      const result = await fn();
      await refreshRef.current();
      if (success) setNotice(success);
      return result;
    } catch (e) {
      setError((e as Error).message);
      return undefined;
    } finally {
      setBusy(null);
    }
  };
  const entities = snapshot?.entities ?? [];
  const disciplines = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of entities) {
      const d = e.discipline ?? "unknown";
      map.set(d, (map.get(d) ?? 0) + 1);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [entities]);
  const storeys = useMemo(
      () =>
        [
          ...new Set(entities.map((e) => e.storey).filter(Boolean)),
        ].sort() as string[],
      [entities],
    ),
    systems = useMemo(
      () =>
        [
          ...new Set(
            entities
              .flatMap((e) => e.system_ids ?? (e.system ? [e.system] : []))
              .filter(Boolean),
          ),
        ].sort() as string[],
      [entities],
    );
  const visibleIds = useMemo(
    () =>
      new Set(
        entities
          .filter(
            (e) =>
              !hiddenDisciplines.has(e.discipline ?? "unknown") &&
              !hiddenIds.has(e.id) &&
              (!servicesOnly || isServiceElement(e)) &&
              (!isolated || e.id === isolated) &&
              (!storey || e.storey === storey) &&
              (!system ||
                (e.system_ids ?? (e.system ? [e.system] : [])).includes(
                  system,
                )),
          )
          .map((e) => e.id),
      ),
    [
      entities,
      hiddenDisciplines,
      hiddenIds,
      isolated,
      storey,
      system,
      servicesOnly,
    ],
  );
  const searchResults = useMemo(() => {
    const q = search.toLowerCase();
    return entities.filter(
      (e) =>
        (!q ||
          [e.id, e.name, e.ifc_type, e.guid, e.step_id, e.system].some((v) =>
            String(v ?? "")
              .toLowerCase()
              .includes(q),
          )) &&
        (!storey || e.storey === storey) &&
        (!system ||
          (e.system_ids ?? (e.system ? [e.system] : [])).includes(system)),
    );
  }, [entities, search, storey, system]);
  const orderedRuns = [...(headSnapshot?.runs ?? [])].sort((a, b) =>
    (b.created_at ?? "").localeCompare(a.created_at ?? ""),
  );
  const selectedEntity = entities.find((e) => e.id === selected),
    activeRun = orderedRuns.find((r) =>
      /RUNNING|PAUSED|QUEUED|CHECKING|CANCELLING|PAUSING/.test(
        r.status.toUpperCase(),
      ),
    ),
    latestRun = activeRun ?? orderedRuns[0],
    candidates = headSnapshot?.candidates ?? [],
    issues = scopeEvidence(
      headSnapshot?.issues ?? [],
      candidates,
      snapshot?.project.state_root,
      stateSelection?.candidate_id,
    );
  const checks = scopeEvidence(
      headSnapshot?.checks ?? [],
      candidates,
      snapshot?.project.state_root,
      stateSelection?.candidate_id,
    ),
    displayChecks =
      checkFilter === "issues"
        ? issues
        : checks
            .filter((c) => checkFilter === "all" || c.status === checkFilter)
            .map(checkIssue);
  const selectedCurrentCandidate = selectedCandidate
    ? candidates.find((candidate) => candidate.id === selectedCandidate.id)
    : undefined;
  const exportCandidate =
    selectedCurrentCandidate ??
    (!selectedCandidate
      ? candidates.find(
          (candidate) =>
            candidate.state_root === snapshot?.project.state_root &&
            /^(CHECKED|ACCEPTED)$/.test(candidate.status),
        )
      : undefined);
  const failures = issues.filter((i) =>
      /FAIL|REJECT/.test(i.status.toUpperCase()),
    ),
    unknowns = issues.filter((i) =>
      /UNKNOWN|BLOCK|STALE/.test(i.status.toUpperCase()),
    );
  const shownEvents = useMemo(
    () =>
      events
        .filter(
          (e) =>
            (eventFilter === "all" || statusClass(e.status) === eventFilter) &&
            (!eventSearch ||
              `${e.seq} ${e.stage} ${e.status} ${e.message} ${e.candidate_id}`
                .toLowerCase()
                .includes(eventSearch.toLowerCase())),
        )
        .slice()
        .reverse(),
    [events, eventSearch, eventFilter],
  );
  const selectEntity = (id: string | null) => {
    setSelected(id);
    if (id) setRightTab("properties");
  };
  const viewCandidate = (candidate: Candidate) => {
    setSelectedCandidate(candidate);
    setSelectedIssue(null);
    setStateSelection({ candidate_id: candidate.id });
  };
  const returnToHead = () => {
    setStateSelection(null);
    setSelectedCandidate(null);
    setSelectedIssue(null);
  };
  const inspectIssue = (issue: Issue) => {
    setSelectedIssue(issue);
    setSelected(issue.participants[0] ?? null);
    setIsolated(null);
    setStorey("");
    setSystem("");
    setServicesOnly(false);
    setHiddenIds(
      (previous) =>
        new Set([...previous].filter((id) => !issue.participants.includes(id))),
    );
    setHiddenDisciplines(
      (previous) =>
        new Set(
          [...previous].filter(
            (d) =>
              !entities.some(
                (e) => issue.participants.includes(e.id) && e.discipline === d,
              ),
          ),
        ),
    );
    setRightTab("issues");
  };
  const toggleDiscipline = (discipline: string) =>
    setHiddenDisciplines((previous) => {
      const next = new Set(previous);
      if (next.has(discipline)) next.delete(discipline);
      else next.add(discipline);
      return next;
    });
  const inspectRecord = (value: unknown) => {
    setRecord(value);
    setModal("record");
  };
  const doImport = async () => {
    const paths = importPaths
      .split(/\r?\n/)
      .map((p) => p.trim().replace(/^"|"$/g, ""))
      .filter(Boolean);
    if (!paths.length && !importFiles.length) {
      setError("Choose local IFC files or enter absolute IFC paths.");
      return;
    }
    const controller = new AbortController();
    uploadAbort.current = controller;
    const result = await perform("Importing IFC models", async () => {
      const receipts = await uploadLocalFiles(
        importFiles,
        controller.signal,
        setUploadStatus,
      );
      controller.signal.throwIfAborted();
      setUploadStatus({
        phase: "IMPORTING",
        completed: receipts.length,
        total: importFiles.length,
      });
      uploadAbort.current = null;
      return api.import(
        [...new Set([...receipts.map((receipt) => receipt.path), ...paths])],
        importName.trim() || "Untitled federation",
      );
    });
    uploadAbort.current = null;
    setUploadStatus(null);
    if (result) {
      const p =
        "project" in (result as object)
          ? (result as { project: Project }).project
          : (result as Project);
      await refreshProjects();
      setProjectId(p.id);
      setModal(null);
      setImportPaths("");
      setImportFiles([]);
      setNotice(
        "IFC import recorded. Inspect geometry coverage and baseline evidence before making changes.",
      );
    }
  };
  const doRun = async () => {
    if (!projectId) return;
    try {
      if (
        stateSelection ||
        (networkRevision &&
          !networkRevisionIsCurrent(
            networkRevision,
            headSnapshot,
            !!stateSelection,
          ))
      )
        throw new Error(
          "Return to the current accepted head and prepare this revision again.",
        );
      const mission =
        operation === "check"
          ? undefined
          : missionMode === "network"
            ? networkRevision
              ? buildNetworkRevision(networkRevision, revisionAlternatives)
                  .mission
              : parseSharedNetwork(sharedNetwork).mission
            : missionMode === "joint"
              ? buildJointMission(jointMission)
              : buildMission(missionForm);
      const result = await perform("Starting run", () =>
        api.start(projectId, {
          operation,
          scope:
            scope === "selected" && selected
              ? [selected]
              : scope === "visible"
                ? [...visibleIds]
                : undefined,
          mission,
          budget_seconds: budget,
          seed: 0,
        }),
      );
      if (result) {
        setModal(null);
        setBottomTab("activity");
        setNav("runs");
        setNotice(
          "Run submitted. Status and controls follow durable worker events.",
        );
      }
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const showRun = () => {
    setNetworkRevision(null);
    setOperation("check");
    setModal("run");
  };
  const reviseNetwork = () => {
    if (!headSnapshot || stateSelection) return;
    try {
      const seed = prepareNetworkRevision(headSnapshot);
      setNetworkRevision(seed);
      setRevisionAlternatives(JSON.stringify(seed.alternatives, null, 2));
      setMissionMode("network");
      setOperation("optimize");
      setScope("all");
      setModal("run");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const revisionOffer = useMemo(() => {
    if (!snapshot?.networks?.length) return null;
    try {
      return {
        network: prepareNetworkRevision(snapshot).network,
        reason: null,
      };
    } catch (e) {
      return { network: null, reason: (e as Error).message };
    }
  }, [snapshot]);
  const revisionStale =
    !!networkRevision &&
    !networkRevisionIsCurrent(networkRevision, headSnapshot, !!stateSelection);
  const exportModel = async () => {
    if (!projectId) return;
    if (!draft && !currentPassingCheck(exportCandidate)) {
      setError(applicabilityReason(exportCandidate));
      return;
    }
    const result = await perform("Exporting IFC and evidence", () =>
      api.export(projectId, selectedCandidate?.id, draft),
    );
    if (result) {
      setRecord(result);
      setModal("record");
      setNotice(
        draft
          ? "Draft export completed. Inspect the export report for its evidence status."
          : "Export completed. Inspect the fresh-process recheck report.",
      );
    }
  };
  const capabilityLabel = health?.capabilities?.find((c) =>
    c.id.toLowerCase().includes("ananke"),
  );
  return (
    <div className="app-shell">
      <header className="topbar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setNav("model");
          }}
          aria-label="OMA and ANANKE workbench"
        >
          <svg viewBox="0 0 35 35" aria-hidden="true">
            <path
              d="M4 28 17.5 5 31 28H4Z M12 22 17.5 12 23 22H12Z"
              fillRule="evenodd"
            />
            <path d="M13 28h9" />
          </svg>
          <strong>
            OMA<span> + </span>ANANKE
          </strong>
        </a>
        <div className="topbar-divider" />
        <span className="product-label">ENGINEERING WORKBENCH</span>
        <div className="topbar-right">
          <span className={`connection ${connected ? "online" : "offline"}`}>
            <i />
            {connected ? "Local engine connected" : "Engine disconnected"}
          </span>
          <span className="version">
            {health?.version ? `v${health.version}` : "LOCAL"}
          </span>
          <button
            className="top-icon"
            title="Workbench help"
            aria-label="Workbench help"
            onClick={() => setModal("help")}
          >
            <CircleHelp size={18} />
          </button>
          <span className="avatar" title="Local workspace">
            <Box size={14} />
          </span>
        </div>
      </header>
      <nav className="rail" aria-label="Workspace navigation">
        {[
          { id: "model", icon: Box, label: "Model workspace" },
          { id: "runs", icon: Zap, label: "Run workspace" },
          {
            id: "verification",
            icon: ShieldCheck,
            label: "Verification evidence",
          },
          {
            id: "alternatives",
            icon: GitBranch,
            label: "Candidate alternatives",
          },
          { id: "history", icon: History, label: "Revision history" },
        ].map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            title={label}
            aria-label={label}
            className={nav === id ? "active" : ""}
            onClick={() => {
              setNav(id);
              if (id === "verification") setRightTab("issues");
              if (id === "alternatives") setBottomTab("candidates");
              if (id === "history") setBottomTab("history");
              if (id === "runs") setBottomTab("activity");
            }}
          >
            <Icon size={21} strokeWidth={1.7} />
            <span>{label.split(" ")[0]}</span>
          </button>
        ))}
        <div className="rail-spacer" />
        <button
          title="Hardware and capabilities"
          aria-label="Hardware and capabilities"
          className={nav === "diagnostics" ? "active" : ""}
          onClick={() => {
            setNav("diagnostics");
            setRightTab("diagnostics");
          }}
        >
          <Gauge size={21} strokeWidth={1.7} />
          <span>System</span>
        </button>
      </nav>
      <aside className="model-sidebar">
        <div className="sidebar-project">
          <p className="eyebrow">PROJECT EXPLORER</p>
          <div className="project-select">
            <FolderOpen size={19} />
            <select
              aria-label="Select project"
              value={projectId ?? ""}
              onChange={(e) => {
                recordTiming("project_view_requested", {
                  project_id: e.target.value,
                  previous_project_id: projectId,
                });
                setProjectId(e.target.value || null);
              }}
            >
              <option value="" disabled>
                Select a project
              </option>
              {projects.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <ChevronDown size={14} />
          </div>
          <div className="project-meta">
            <span>
              {snapshot
                ? `${snapshot.sources.length} source models`
                : "Your local IFC workspace"}
            </span>
            {snapshot && <span>r{snapshot.project.revision}</span>}
          </div>
        </div>
        <div className="sidebar-search">
          <Search size={15} />
          <input
            aria-label="Search model entities"
            placeholder="Search objects, GUIDs, systems…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setEntityLimit(100);
            }}
          />
          <kbd>/</kbd>
        </div>
        <div className="explorer-scroll">
          <div className="section-label">
            <span>FEDERATION</span>
            <button
              className="icon-button"
              title="Import source models"
              aria-label="Import source models"
              onClick={() => setModal("import")}
            >
              <Plus size={15} />
            </button>
          </div>
          {disciplines.length ? (
            disciplines.map(([discipline, count]) => (
              <div
                className={`discipline-row ${hiddenDisciplines.has(discipline) ? "muted" : ""}`}
                key={discipline}
              >
                <button
                  className="discipline-name"
                  onClick={() => toggleDiscipline(discipline)}
                >
                  <ChevronDown size={12} />
                  <span
                    className="discipline-square"
                    style={{ background: disciplineColor(discipline) }}
                  />
                  <span>{discipline.replaceAll("_", " ")}</span>
                  <small>{count.toLocaleString()}</small>
                </button>
                <button
                  className="icon-button visibility"
                  aria-label={`${hiddenDisciplines.has(discipline) ? "Show" : "Hide"} ${discipline}`}
                  onClick={() => toggleDiscipline(discipline)}
                >
                  {hiddenDisciplines.has(discipline) ? (
                    <EyeOff size={14} />
                  ) : (
                    <Eye size={14} />
                  )}
                </button>
              </div>
            ))
          ) : (
            <div className="tree-empty">
              <Layers3 size={22} strokeWidth={1} />
              <p>
                One coordinate space.
                <br />
                Every discipline in context.
              </p>
            </div>
          )}
          {!!storeys.length && (
            <div className="tree-filter">
              <label htmlFor="storey">Storey</label>
              <select
                id="storey"
                value={storey}
                onChange={(e) => setStorey(e.target.value)}
              >
                <option value="">All storeys</option>
                {storeys.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
          )}
          {!!systems.length && (
            <div className="tree-filter">
              <label htmlFor="system">System</label>
              <select
                id="system"
                value={system}
                onChange={(e) => setSystem(e.target.value)}
              >
                <option value="">All systems</option>
                {systems.map((s) => (
                  <option
                    key={s}
                    value={s}
                  >{`${String(snapshot?.sources.find((source) => source.id === s.split(":")[0])?.name ?? s.split(":")[0].slice(0, 8))} \u00b7 #${s.split(":").at(-1)}`}</option>
                ))}
              </select>
            </div>
          )}
          {(hiddenDisciplines.size > 0 ||
            hiddenIds.size > 0 ||
            isolated ||
            storey ||
            system ||
            servicesOnly) && (
            <button
              className="reset-visibility"
              onClick={() => {
                setHiddenDisciplines(new Set());
                setHiddenIds(new Set());
                setIsolated(null);
                setStorey("");
                setSystem("");
                setServicesOnly(false);
              }}
            >
              <Eye size={13} />
              Show all objects
            </button>
          )}
          <div className="section-label object-heading">
            <span>OBJECTS</span>
            <span>{searchResults.length.toLocaleString()}</span>
          </div>
          {searchResults.slice(0, entityLimit).map((e) => (
            <button
              key={e.id}
              className={`entity-row ${selected === e.id ? "selected" : ""} ${visibleIds.has(e.id) ? "" : "muted"}`}
              onClick={() => selectEntity(e.id)}
            >
              <Box size={14} strokeWidth={1.4} />
              <span>
                <strong>{e.name || e.ifc_type || e.id}</strong>
                <small>
                  {e.ifc_type ?? "IFC entity"} <i>·</i>{" "}
                  {e.step_id ? `#${e.step_id}` : short(e.id)}
                </small>
              </span>
              <ChevronRight size={12} />
            </button>
          ))}
          {searchResults.length > entityLimit && (
            <button
              className="load-more"
              onClick={() => setEntityLimit((n) => n + 100)}
            >
              Show next {Math.min(100, searchResults.length - entityLimit)}{" "}
              objects
            </button>
          )}
          {!searchResults.length && !!entities.length && (
            <p className="no-results">No matching objects.</p>
          )}
        </div>
        <button className="import-sidebar" onClick={() => setModal("import")}>
          <Plus size={16} />
          <span>Import IFC federation</span>
          <span className="keycap">IFC</span>
        </button>
        <div className="sidebar-footer">
          <Database size={12} />
          Local storage · immutable originals
        </div>
      </aside>
      <main className="main-workspace">
        <div className="workspace-heading">
          <div>
            <div className="breadcrumb">
              Workspace <ChevronRight size={12} />{" "}
              {snapshot?.project.name ?? "Getting started"}
            </div>
            <h2>
              {snapshot?.project.name ?? "Your next better building."}
              {snapshot && <Badge status={snapshot.project.status} />}
            </h2>
          </div>
          <div className="workspace-actions">
            <button
              className="secondary"
              disabled={
                !projectId ||
                !snapshot ||
                !!busy ||
                !!stateSelection?.revision ||
                stateSelection?.revision === 0
              }
              onClick={() => setModal("export")}
            >
              <ArrowDownToLine size={15} />
              Export
            </button>
            <button
              className="primary"
              disabled={
                !projectId ||
                !snapshot ||
                !connected ||
                !!busy ||
                !!stateSelection
              }
              onClick={showRun}
            >
              <Play size={14} fill="currentColor" />
              New run
              <ChevronDown size={13} />
            </button>
          </div>
        </div>
        {(!connected || syncError) && (
          <div className="connection-banner">
            <Unplug size={15} />
            <span>
              {syncError ??
                "The local engine is unavailable. Start the OMA service to load projects."}
            </span>
            <button
              onClick={() => {
                void perform("Reconnecting", async () => {
                  setHealth(await api.health());
                  setConnected(true);
                  setSyncError(null);
                  await refreshProjects();
                });
              }}
            >
              <RefreshCw size={13} />
              Reconnect
            </button>
          </div>
        )}
        {stateSelection && (
          <div className="replay-banner">
            <History size={15} />
            <span>
              {stateSelection.candidate_id
                ? `Inspecting candidate ${short(stateSelection.candidate_id)}`
                : `Replaying revision ${stateSelection.revision}`}{" "}
              <strong>Read-only view</strong> · current head r
              {headSnapshot?.project.revision ?? "—"}
            </span>
            <button onClick={returnToHead}>
              <ArrowRight size={13} />
              Return to current state
            </button>
          </div>
        )}
        <div
          className={`spatial-workspace ${bottomExpanded ? "timeline-expanded" : ""}`}
        >
          <Viewport
            geometry={geometry}
            entities={entities}
            visibleIds={visibleIds}
            selected={selected}
            issue={selectedIssue}
            candidate={selectedCurrentCandidate ?? selectedCandidate}
            onSelect={selectEntity}
            onImport={() => setModal("import")}
            loading={stateSelection ? loadingView : loadingGeometry}
            importStatus={
              !stateSelection && activeRun?.operation === "import"
                ? activeRun.status
                : null
            }
            progress={stateSelection ? viewMeshProgress : meshProgress}
            error={stateSelection ? viewError : geometryError}
            projectId={projectId}
            servicesOnly={servicesOnly}
            onToggleServices={() => setServicesOnly((value) => !value)}
          />
          <aside className="inspector">
            <div className="inspector-tabs">
              {[
                { id: "overview", label: "Overview" },
                { id: "properties", label: "Object" },
                { id: "issues", label: "Checks" },
              ].map((t) => (
                <button
                  key={t.id}
                  className={rightTab === t.id ? "active" : ""}
                  onClick={() => setRightTab(t.id)}
                >
                  {t.label}
                  {t.id === "issues" && issues.length > 0 && (
                    <span>{issues.length}</span>
                  )}
                </button>
              ))}
              <button
                className={
                  rightTab === "diagnostics" ? "active icon-tab" : "icon-tab"
                }
                title="Diagnostics"
                aria-label="Diagnostics"
                onClick={() => setRightTab("diagnostics")}
              >
                <SlidersHorizontal size={15} />
              </button>
            </div>
            <div className="inspector-content">
              {rightTab === "overview" && (
                <>
                  <div className="inspector-title">
                    <span className="eyebrow">ENGINEERING STATE</span>
                    <h3>
                      {snapshot
                        ? "The complete picture."
                        : "A workspace built on evidence."}
                    </h3>
                    <p>
                      {snapshot
                        ? "A shared model, with explicit uncertainty and a traceable path to every decision."
                        : "Import a federation to establish its actual geometry, provenance, and baseline."}
                    </p>
                  </div>
                  <div className="stat-grid">
                    <div>
                      <span>Model objects</span>
                      <strong>
                        {snapshot ? entities.length.toLocaleString() : "—"}
                      </strong>
                      <small>Accounted in state</small>
                    </div>
                    <div>
                      <span>Renderable</span>
                      <strong>
                        {geometry
                          ? geometry.meshes.length.toLocaleString()
                          : "—"}
                      </strong>
                      <small>Geometry artifacts</small>
                    </div>
                    <div>
                      <span>Failed checks</span>
                      <strong className={failures.length ? "text-bad" : ""}>
                        {checks.length || issues.length ? failures.length : "—"}
                      </strong>
                      <small>
                        {checks.length || issues.length
                          ? "Recorded evidence"
                          : "Not yet checked"}
                      </small>
                    </div>
                    <div>
                      <span>Unresolved</span>
                      <strong className={unknowns.length ? "text-warn" : ""}>
                        {checks.length || issues.length ? unknowns.length : "—"}
                      </strong>
                      <small>
                        {checks.length || issues.length
                          ? "Unknown or blocked"
                          : "Not yet checked"}
                      </small>
                    </div>
                  </div>
                  <div className="inspector-section">
                    <div className="section-label">
                      <span>WORKFLOW</span>
                      <ArrowUpRight size={13} />
                    </div>
                    <div
                      className={`workflow-step ${snapshot?.sources.length ? "complete" : ""}`}
                    >
                      <span>
                        {snapshot?.sources.length ? <Check size={13} /> : 1}
                      </span>
                      <div>
                        <strong>Establish the baseline</strong>
                        <p>Import, audit, and account for every object.</p>
                      </div>
                    </div>
                    <div
                      className={`workflow-step ${checks.length ? "complete" : ""}`}
                    >
                      <span>{checks.length ? <Check size={13} /> : 2}</span>
                      <div>
                        <strong>Inspect the evidence</strong>
                        <p>Physical checks with scoped verdicts.</p>
                      </div>
                    </div>
                    <div
                      className={`workflow-step ${candidates.some((c) => c.check?.status === "PASS") ? "complete" : ""}`}
                    >
                      <span>
                        {candidates.some((c) => c.check?.status === "PASS") ? (
                          <Check size={13} />
                        ) : (
                          3
                        )}
                      </span>
                      <div>
                        <strong>Explore a checked change</strong>
                        <p>Compare alternatives before publication.</p>
                      </div>
                    </div>
                    <div
                      className={`workflow-step ${snapshot?.project.status === "ACCEPTED" ? "complete" : ""}`}
                    >
                      <span>4</span>
                      <div>
                        <strong>Publish with confidence</strong>
                        <p>Export, reopen, and independently recheck.</p>
                      </div>
                    </div>
                  </div>
                  {!!snapshot?.sources.length && (
                    <SourceAudits
                      sources={snapshot.sources}
                      onOpen={inspectRecord}
                    />
                  )}{" "}
                  {revisionOffer && (
                    <div className="network-revision-card">
                      <div className="section-label">
                        <span>SHARED NETWORK</span>
                        <GitBranch size={15} />
                      </div>
                      <strong>{snapshot?.networks?.[0]?.id}</strong>
                      <p>
                        Revise the physical layout while preserving every
                        accepted service requirement.
                      </p>
                      <button
                        className="secondary"
                        onClick={reviseNetwork}
                        disabled={
                          !revisionOffer.network ||
                          !!stateSelection ||
                          !!busy ||
                          !connected
                        }
                      >
                        <GitBranch size={14} /> Revise this network
                      </button>
                      {(revisionOffer.reason || stateSelection) && (
                        <p className="muted">
                          {stateSelection
                            ? "Return to the current accepted head to revise its network."
                            : revisionOffer.reason}
                        </p>
                      )}
                      {snapshot?.networks?.map((network) => (
                        <NetworkLineage
                          key={network.id}
                          network={network}
                          onInspect={inspectRecord}
                        />
                      ))}
                    </div>
                  )}
                  {!!snapshot?.missing_inputs.length && (
                    <div className="missing-card">
                      <TriangleAlert size={16} />
                      <div>
                        <strong>Missing engineering inputs</strong>
                        {snapshot.missing_inputs.map((item, i) => {
                          const record =
                            item && typeof item === "object"
                              ? (item as Record<string, unknown>)
                              : null;
                          return (
                            <div key={i}>
                              <p>
                                {record
                                  ? readable(
                                      record.reason ??
                                        record.message ??
                                        "Input requires review",
                                    )
                                  : readable(item)}
                              </p>
                              {record && (
                                <button
                                  className="text-button"
                                  onClick={() => inspectRecord(item)}
                                >
                                  {record.code === "FEDERATION_DATUM_REVIEW"
                                    ? "Inspect datum evidence"
                                    : "Inspect input evidence"}
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  <div className="trust-note">
                    <ShieldCheck size={19} />
                    <p>
                      A view is not a certificate.
                      <br />
                      <strong>
                        Verification applies only to its declared scope.
                      </strong>
                    </p>
                  </div>
                  {snapshot && (
                    <div className="state-footer">
                      <span>STATE ROOT</span>
                      <button
                        onClick={() => inspectRecord(snapshot.project)}
                        className="mono"
                      >
                        {short(snapshot.project.state_root)}
                        <Code2 size={12} />
                      </button>
                    </div>
                  )}
                  {snapshot && projectId && (
                    <button
                      className="secondary state-dependencies"
                      onClick={() =>
                        setEvidenceTarget({
                          projectId,
                          root: snapshot.project.state_root,
                          revision: snapshot.project.revision,
                          candidate:
                            selectedCurrentCandidate ??
                            selectedCandidate ??
                            undefined,
                          initialTab: "dependencies",
                        })
                      }
                    >
                      <GitBranch size={14} />
                      Inspect revision dependencies
                    </button>
                  )}
                </>
              )}
              {rightTab === "properties" &&
                (selectedEntity ? (
                  <>
                    <div className="object-title">
                      <span className="object-type">
                        <Box size={15} />
                        {selectedEntity.ifc_type ?? "IFC OBJECT"}
                      </span>
                      <h3>{selectedEntity.name ?? selectedEntity.id}</h3>
                      <Badge
                        status={selectedEntity.geometry_status ?? "UNKNOWN"}
                      />
                    </div>
                    <div className="object-actions">
                      <button
                        onClick={() =>
                          setIsolated(
                            isolated === selectedEntity.id
                              ? null
                              : selectedEntity.id,
                          )
                        }
                      >
                        <Maximize2 size={13} />
                        {isolated ? "Unisolate" : "Isolate"}
                      </button>
                      <button
                        onClick={() =>
                          setHiddenIds((p) => {
                            const next = new Set(p);
                            if (next.has(selectedEntity.id))
                              next.delete(selectedEntity.id);
                            else next.add(selectedEntity.id);
                            return next;
                          })
                        }
                      >
                        <EyeOff size={13} />
                        {hiddenIds.has(selectedEntity.id) ? "Show" : "Hide"}
                      </button>
                      <button
                        onClick={() => inspectRecord(selectedEntity)}
                        aria-label="View complete object record"
                      >
                        <Code2 size={14} />
                      </button>
                    </div>
                    <div className="property-section">
                      <div className="section-label">IDENTITY & PROVENANCE</div>
                      <KeyValue
                        label="Entity ID"
                        value={selectedEntity.id}
                        mono
                      />
                      <KeyValue
                        label="IFC GUID"
                        value={selectedEntity.guid}
                        mono
                      />
                      <KeyValue
                        label="STEP ID"
                        value={selectedEntity.step_id}
                      />
                      <KeyValue
                        label="Source model"
                        value={selectedEntity.source_file}
                      />
                      <KeyValue
                        label="Discipline"
                        value={selectedEntity.discipline}
                      />
                      <KeyValue label="Storey" value={selectedEntity.storey} />
                      <KeyValue label="System" value={selectedEntity.system} />
                      {typeof selectedEntity.network_id === "string" && (
                        <>
                          <KeyValue
                            label="Network"
                            value={selectedEntity.network_id}
                          />
                          <KeyValue
                            label="Physical component"
                            value={selectedEntity.component_id}
                          />
                          <KeyValue
                            label="Demand membership"
                            value={selectedEntity.demand_ids}
                          />
                        </>
                      )}
                    </div>
                    {selectedEntity.bounds && (
                      <div className="property-section">
                        <div className="section-label">
                          WORLD BOUNDS · METERS
                        </div>
                        <KeyValue
                          label="Minimum"
                          value={selectedEntity.bounds.min
                            .map((n) => n.toFixed(3))
                            .join(", ")}
                          mono
                        />
                        <KeyValue
                          label="Maximum"
                          value={selectedEntity.bounds.max
                            .map((n) => n.toFixed(3))
                            .join(", ")}
                          mono
                        />
                      </div>
                    )}
                    <div className="property-section">
                      <div className="section-label">COMPONENT PROPERTIES</div>
                      {Object.entries(selectedEntity.properties ?? {})
                        .length ? (
                        Object.entries(selectedEntity.properties ?? {}).map(
                          ([key, value]) => (
                            <KeyValue key={key} label={key} value={value} />
                          ),
                        )
                      ) : (
                        <p className="muted-copy">
                          No property record supplied for this object.
                        </p>
                      )}
                    </div>
                  </>
                ) : (
                  <Empty icon={Box} title="Select an object">
                    Pick a component in the model or search the explorer to
                    inspect its identity and engineering data.
                  </Empty>
                ))}
              {rightTab === "issues" && (
                <>
                  <div className="inspector-title">
                    <span className="eyebrow">INDEPENDENT EVIDENCE</span>
                    <h3>Know what holds.</h3>
                    <p>
                      Each verdict belongs to a rule, an actual test, and a
                      defined scope.
                    </p>
                  </div>
                  <div className="check-summary">
                    <span>
                      <i className="dot bad" />
                      {failures.length} failed
                    </span>
                    <span>
                      <i className="dot warn" />
                      {unknowns.length} unresolved
                    </span>
                    <button
                      title="View full verification records"
                      aria-label="View full verification records"
                      onClick={() => inspectRecord(issues)}
                    >
                      <Code2 size={14} />
                    </button>
                  </div>
                  {selectedIssue && (
                    <div className="witness-detail">
                      <div className="section-label">SELECTED WITNESS</div>
                      <KeyValue
                        label="Rule"
                        value={selectedIssue.rule
                          .split(":")[0]
                          .replaceAll("_", " ")}
                      />
                      <KeyValue
                        label="World point (m)"
                        value={selectedIssue.witness?.point
                          ?.map((v) => v.toFixed(4))
                          .join(", ")}
                      />
                      <KeyValue label="Scope" value={selectedIssue.scope} />
                      <button
                        className="secondary full"
                        onClick={() => inspectRecord(selectedIssue)}
                      >
                        <Code2 size={14} />
                        Open complete evidence
                      </button>
                    </div>
                  )}
                  <div className="check-filter">
                    <label htmlFor="check-filter">View evidence</label>
                    <select
                      id="check-filter"
                      value={checkFilter}
                      onChange={(e) => setCheckFilter(e.target.value)}
                    >
                      <option value="issues">
                        Failed & unresolved ({issues.length})
                      </option>
                      <option value="all">All checks ({checks.length})</option>
                      <option value="PASS">
                        Passed (
                        {checks.filter((c) => c.status === "PASS").length})
                      </option>
                      <option value="NOT_APPLICABLE">Not applicable</option>
                    </select>
                  </div>
                  {displayChecks.length ? (
                    displayChecks.slice(0, checkLimit).map((issue) => (
                      <button
                        className={`issue-card ${selectedIssue?.id === issue.id ? "selected" : ""}`}
                        key={issue.id}
                        onClick={() => inspectIssue(issue)}
                      >
                        <div>
                          <Badge status={issue.status} />
                          <ArrowUpRight size={14} />
                        </div>
                        <strong title={issue.rule}>
                          {issue.rule.split(":")[0].replaceAll("_", " ")}
                        </strong>
                        <p>{issue.message}</p>
                        {issue.witness?.margin_m !== undefined && (
                          <span className="issue-measure">
                            Measured margin{" "}
                            <b>
                              {(issue.witness.margin_m * 1000).toFixed(2)} mm
                            </b>
                          </span>
                        )}
                        <span className="issue-ids">
                          {issue.participants.length} participating objects{" "}
                          <ChevronRight size={12} />
                        </span>
                      </button>
                    ))
                  ) : (
                    <Empty
                      icon={ShieldCheck}
                      title={
                        checks.length
                          ? "No matching checks"
                          : "No checks recorded"
                      }
                    >
                      {checks.length
                        ? "Select a different evidence filter to inspect other recorded verdicts."
                        : "Start a baseline check. An empty issue list does not establish a verified model."}
                    </Empty>
                  )}
                  {displayChecks.length > checkLimit && (
                    <button
                      className="load-more"
                      onClick={() => setCheckLimit((n) => n + 60)}
                    >
                      Show next{" "}
                      {Math.min(60, displayChecks.length - checkLimit)} checks ·{" "}
                      {displayChecks.length.toLocaleString()} total
                    </button>
                  )}
                </>
              )}
              {rightTab === "diagnostics" && (
                <>
                  <div className="inspector-title">
                    <span className="eyebrow">LOCAL WORKSTATION</span>
                    <h3>Compute, accounted for.</h3>
                    <p>
                      Hardware observations from the service. Unreported metrics
                      remain unknown.
                    </p>
                  </div>
                  <button
                    className="secondary full"
                    onClick={() => inspectRecord(timingEvidence())}
                  >
                    <Activity size={14} /> Browser timing evidence
                  </button>
                  <div className="hardware-card">
                    <span>
                      <Gauge size={16} />
                      PROCESSOR
                    </span>
                    <h4>
                      {typeof health?.hardware?.cpu === "string"
                        ? health.hardware.cpu
                        : readable(health?.hardware?.cpu ?? "Not reported")}
                    </h4>
                    <Meter
                      label="CPU utilization"
                      value={health?.hardware?.cpu_percent}
                    />
                    <KeyValue
                      label="System memory"
                      value={bytes(health?.hardware?.ram_total_bytes)}
                    />
                    <KeyValue
                      label="Available memory"
                      value={bytes(health?.hardware?.ram_available_bytes)}
                    />
                  </div>
                  <div className="hardware-card">
                    <span>
                      <Zap size={16} />
                      GRAPHICS
                    </span>
                    <h4>{health?.hardware?.gpu?.name ?? "GPU not reported"}</h4>
                    <Meter
                      label="GPU utilization"
                      value={health?.hardware?.gpu?.utilization_percent}
                    />
                    <KeyValue
                      label="VRAM total"
                      value={bytes(health?.hardware?.gpu?.memory_total_bytes)}
                    />
                    <KeyValue
                      label="VRAM used"
                      value={bytes(health?.hardware?.gpu?.memory_used_bytes)}
                    />
                    <KeyValue
                      label="Driver"
                      value={health?.hardware?.gpu?.driver}
                    />
                  </div>
                  <div className="property-section">
                    <div className="section-label">CAPABILITY GATES</div>
                    {health?.capabilities?.length ? (
                      health.capabilities.map((c) => (
                        <div className="capability" key={c.id}>
                          <div>
                            <strong>{c.label ?? c.id}</strong>
                            <Badge status={c.status} />
                          </div>
                          <p>
                            {c.reason ?? "No additional rationale reported."}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="muted-copy">
                        Capability register not yet supplied by the engine.
                      </p>
                    )}
                    <button
                      className="secondary full"
                      onClick={() => inspectRecord(health)}
                    >
                      <Code2 size={14} />
                      Complete diagnostic record
                    </button>
                  </div>
                </>
              )}
            </div>
          </aside>
          <section className="timeline">
            <div className="timeline-head">
              <div className="timeline-tabs">
                <button
                  className={bottomTab === "activity" ? "active" : ""}
                  onClick={() => setBottomTab("activity")}
                >
                  <Activity size={14} />
                  Live activity<span>{events.length}</span>
                </button>
                <button
                  className={bottomTab === "candidates" ? "active" : ""}
                  onClick={() => setBottomTab("candidates")}
                >
                  <GitBranch size={14} />
                  Alternatives<span>{candidates.length}</span>
                </button>
                <button
                  className={bottomTab === "history" ? "active" : ""}
                  onClick={() => setBottomTab("history")}
                >
                  <History size={14} />
                  History<span>{headSnapshot?.history.length ?? 0}</span>
                </button>
              </div>
              <div className="timeline-tools">
                {latestRun && <Badge status={latestRun.status} />}
                <button
                  className="icon-button"
                  title={bottomExpanded ? "Reduce timeline" : "Expand timeline"}
                  aria-label="Toggle expanded timeline"
                  onClick={() => setBottomExpanded(!bottomExpanded)}
                >
                  <Maximize2 size={14} />
                </button>
              </div>
            </div>
            {bottomTab === "activity" && (
              <>
                <div className="run-toolbar">
                  <div className="run-label">
                    <span
                      className={`run-pulse ${activeRun ? "active" : ""}`}
                    />
                    <strong>
                      {latestRun
                        ? (latestRun.stage ??
                          latestRun.operation ??
                          "Engine run")
                        : "Ready when you are"}
                    </strong>
                    <span>
                      {latestRun
                        ? short(latestRun.id)
                        : headSnapshot
                          ? "No computation is running"
                          : "Run state has not loaded"}
                    </span>
                  </div>
                  {activeRun && (
                    <RunControls
                      run={activeRun}
                      busy={!!busy}
                      onControl={(action) => {
                        void perform(`${action} requested`, () =>
                          api.control(activeRun.id, action),
                        );
                      }}
                    />
                  )}
                  <div className="event-filter">
                    <Search size={12} />
                    <input
                      aria-label="Filter durable events"
                      placeholder="Filter events"
                      value={eventSearch}
                      onChange={(e) => setEventSearch(e.target.value)}
                    />
                    <select
                      aria-label="Filter event status"
                      value={eventFilter}
                      onChange={(e) => setEventFilter(e.target.value)}
                    >
                      <option value="all">All states</option>
                      <option value="bad">Failures</option>
                      <option value="warn">Unresolved</option>
                      <option value="good">Completed</option>
                      <option value="live">Running</option>
                    </select>
                  </div>
                </div>
                <div className="event-list">
                  {shownEvents.length ? (
                    shownEvents.slice(0, 250).map((event) => (
                      <button
                        className="event-row"
                        key={event.seq}
                        onClick={() => inspectRecord(event)}
                      >
                        <span className="event-seq">
                          {String(event.seq).padStart(4, "0")}
                        </span>
                        <span className="event-time">
                          {date(event.timestamp)}
                        </span>
                        <span
                          className={`event-dot ${statusClass(event.status)}`}
                        />
                        <span className="event-stage">
                          {event.stage.replaceAll("_", " ")}
                        </span>
                        <span className="event-message">
                          {event.message ??
                            `${event.status}${event.candidate_id ? ` · Candidate ${short(event.candidate_id)}` : ""}`}
                        </span>
                        <Badge status={event.status} />
                        <Code2 size={13} />
                      </button>
                    ))
                  ) : (
                    <div className="timeline-empty">
                      <Terminal size={18} />
                      <span>
                        {events.length
                          ? "No events match the filter."
                          : "Your computation, as it happens."}
                      </span>
                      <p>
                        {events.length
                          ? "Change the event or status filter."
                          : "Every run produces durable, inspectable records here."}
                      </p>
                    </div>
                  )}
                </div>
                <div className="timeline-foot">
                  <span>
                    <i className={`dot ${connected ? "good" : "warn"}`} />
                    {connected ? "Synchronized" : "Disconnected"} · sequence{" "}
                    {cursor.current.toLocaleString()}
                  </span>
                  <span>
                    Retained view: {events.length.toLocaleString()} / 2,000
                    events · complete history on disk
                  </span>
                </div>
              </>
            )}
            {bottomTab === "candidates" && (
              <div className="candidate-list">
                {candidates.length ? (
                  candidates.map((candidate, i) => (
                    <div
                      key={candidate.id}
                      className={`candidate-card ${selectedCandidate?.id === candidate.id ? "selected" : ""}`}
                    >
                      <button
                        className="candidate-main"
                        onClick={() => viewCandidate(candidate)}
                      >
                        <span className="candidate-number">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span>
                          <strong>Candidate {short(candidate.id)}</strong>
                          <small>
                            {candidate.changed_ids.length} changed IDs ·{" "}
                            {candidate.routes.length} routes
                            {!!candidate.networks?.length &&
                              ` · ${candidate.networks.length} shared network${candidate.networks.length === 1 ? "" : "s"}`}{" "}
                            · {date(candidate.created_at)}
                          </small>
                        </span>
                        <Badge status={candidate.status} />
                        <div className="objective-values">
                          {Object.entries(candidate.objective ?? {})
                            .slice(0, 3)
                            .map(([key, value]) => (
                              <span key={key}>
                                <small>{key.replaceAll("_", " ")}</small>
                                <strong>
                                  {typeof value === "number"
                                    ? value.toLocaleString(undefined, {
                                        maximumFractionDigits: 3,
                                      })
                                    : readable(value)}
                                </strong>
                              </span>
                            ))}
                        </div>
                        <ChevronRight size={15} />
                      </button>
                      <div
                        className={`candidate-applicability ${candidate.check?.applicability === "CURRENT" && !candidate.validation_advisories?.length ? "current" : "stale"}`}
                      >
                        <span>{applicabilityReason(candidate)}</span>
                        {candidate.check?.checker_version && (
                          <small
                            title={`Checked: ${candidate.check.checker_version}; current: ${candidate.check.current_checker_version ?? "not reported"}`}
                          >
                            Checked with …
                            {candidate.check.checker_version.slice(-12)} ·
                            current{" "}
                            {candidate.check.current_checker_version
                              ? `…${candidate.check.current_checker_version.slice(-12)}`
                              : "not reported"}
                          </small>
                        )}
                      </div>
                      <ValidationAdvisories
                        advisories={candidate.validation_advisories}
                        compact
                      />
                      {selectedCandidate?.id === candidate.id &&
                        candidate.networks?.map((network) => (
                          <details
                            className="candidate-network"
                            key={network.id}
                            open
                          >
                            <summary>
                              <GitBranch size={14} />
                              {network.network_spec.network_id} ·{" "}
                              {network.component_ids.length} unique components ·{" "}
                              {network.demand_ids.length} demands
                            </summary>
                            <NetworkLineage
                              network={network}
                              onInspect={inspectRecord}
                            />
                            <NetworkDiagram
                              spec={network.network_spec}
                              selected={
                                selected?.startsWith(`${network.id}:`)
                                  ? selected.slice(network.id.length + 1)
                                  : null
                              }
                              onSelect={(component) =>
                                selectEntity(`${network.id}:${component}`)
                              }
                            />
                          </details>
                        ))}
                      {selectedCandidate?.id === candidate.id &&
                        candidate.routes.length > 0 && (
                          <div
                            className="candidate-route-list"
                            aria-label="Candidate route membership"
                          >
                            {candidate.routes.map((route, i) => (
                              <button
                                key={route.id ?? i}
                                disabled={!route.id}
                                onClick={() =>
                                  route.id && selectEntity(route.id)
                                }
                                title={route.id}
                              >
                                <GitBranch size={12} />
                                {typeof route.request_demand_id === "string"
                                  ? route.request_demand_id
                                  : Array.isArray(route.demand_ids)
                                    ? route.demand_ids.join(", ")
                                    : `Route ${i + 1}`}{" "}
                                ·{" "}
                                {String(
                                  route.service ?? "physical route",
                                ).replaceAll("_", " ")}
                              </button>
                            ))}
                          </div>
                        )}
                      <div className="candidate-bottom">
                        <span>
                          <ShieldCheck size={13} />
                          {candidate.check?.reason ??
                            `Checker: ${candidate.check?.status ?? "not reported"}`}
                        </span>
                        <button
                          onClick={() =>
                            projectId &&
                            setEvidenceTarget({
                              projectId,
                              root: candidate.state_root,
                              candidate,
                            })
                          }
                        >
                          <Code2 size={13} />
                          Evidence
                        </button>
                        <button
                          disabled={
                            !!busy ||
                            !connected ||
                            !!activeRun ||
                            stateSelection?.revision !== undefined
                          }
                          onClick={() => {
                            if (projectId)
                              void perform(
                                "Rechecking original candidate mission",
                                () => api.recheck(projectId, candidate.id),
                                "Recheck submitted with the original mission. Follow its durable run events.",
                              ).then((run) => {
                                if (run) {
                                  setBottomTab("activity");
                                  setNav("runs");
                                }
                              });
                          }}
                          title="Reopen candidate geometry and run the current independent checker against its original mission."
                        >
                          <RefreshCw size={13} />
                          Recheck
                        </button>
                        <button
                          className="accept-button"
                          disabled={
                            !currentPassingCheck(candidate) ||
                            !!busy ||
                            candidate.status === "ACCEPTED" ||
                            stateSelection?.revision !== undefined
                          }
                          onClick={() => {
                            if (projectId && headSnapshot)
                              void perform(
                                "Accepting checked candidate",
                                () =>
                                  api.accept(
                                    projectId,
                                    candidate.id,
                                    headSnapshot.project.revision,
                                  ),
                                "Checked candidate published as a new project revision.",
                              );
                          }}
                        >
                          <CheckCheck size={13} />
                          {candidate.status === "ACCEPTED"
                            ? "Accepted"
                            : "Accept checked"}
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="timeline-empty">
                    <GitBranch size={22} />
                    <span>Alternatives with a reason to exist.</span>
                    <p>
                      Candidate geometry, objective values, and checker verdicts
                      appear after a real run.
                    </p>
                  </div>
                )}
              </div>
            )}
            {bottomTab === "history" && (
              <div className="history-list">
                {headSnapshot?.history.length ? (
                  headSnapshot.history
                    .slice()
                    .reverse()
                    .map((revision) => (
                      <div className="history-row" key={revision.revision}>
                        <div className="revision-marker">
                          r{revision.revision}
                        </div>
                        <div>
                          <strong>
                            {revision.message ?? `${revision.status} revision`}
                          </strong>
                          <small>
                            {date(revision.created_at ?? revision.timestamp)} ·
                            root {short(revision.state_root)}
                          </small>
                        </div>
                        <Badge status={revision.status} />
                        <button
                          className="secondary"
                          onClick={() => {
                            setSelectedCandidate(null);
                            setSelectedIssue(null);
                            setStateSelection({ revision: revision.revision });
                          }}
                        >
                          <Play size={12} />
                          Replay
                        </button>
                        <button
                          className="secondary"
                          onClick={() => inspectRecord(revision)}
                        >
                          <Code2 size={13} />
                          Record
                        </button>
                        <button
                          className="secondary"
                          onClick={() =>
                            projectId &&
                            setEvidenceTarget({
                              projectId,
                              root: revision.state_root,
                              revision: revision.revision,
                              initialTab: "dependencies",
                            })
                          }
                        >
                          <GitBranch size={13} />
                          Dependencies
                        </button>
                        <button
                          className="secondary"
                          disabled={
                            revision.revision ===
                              headSnapshot?.project.revision || !!busy
                          }
                          onClick={() => {
                            if (projectId && headSnapshot)
                              void perform(
                                "Reverting project revision",
                                () =>
                                  api.revert(
                                    projectId,
                                    revision.revision,
                                    headSnapshot.project.revision,
                                  ),
                                "Revert published. Original revisions remain in the durable history.",
                              );
                          }}
                        >
                          <Undo2 size={13} />
                          Revert
                        </button>
                      </div>
                    ))
                ) : (
                  <div className="timeline-empty">
                    <History size={22} />
                    <span>A history you can return to.</span>
                    <p>
                      Immutable revisions and transactional changes appear here.
                    </p>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </main>
      <footer className="statusbar">
        <span>
          <ShieldCheck size={12} />
          Evidence before acceptance
        </span>
        <div>
          <span>
            {capabilityLabel
              ? `ANANKE · ${capabilityLabel.status}`
              : "ANANKE · capability status pending"}
          </span>
          <span>SI units · shared world coordinates</span>
          <span>{connected ? "LOCAL" : "OFFLINE"}</span>
        </div>
      </footer>
      {error && (
        <div className="toast error" role="alert">
          <TriangleAlert size={18} />
          <div>
            <strong>Action needs attention</strong>
            <p>{error}</p>
          </div>
          <button aria-label="Dismiss error" onClick={() => setError(null)}>
            <X size={16} />
          </button>
        </div>
      )}
      {notice && !error && (
        <div className="toast" role="status">
          <Info size={18} />
          <div>
            <p>{notice}</p>
          </div>
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {busy && (
        <div className="busy-indicator" role="status">
          <LoaderCircle size={15} className="spin" />
          {busy}
        </div>
      )}
      {evidenceTarget && (
        <Modal
          title="Evidence and dependencies"
          kicker="RECORDED ENGINEERING CONTEXT"
          wide
          onClose={() => setEvidenceTarget(null)}
        >
          <EvidenceReview target={evidenceTarget} />
        </Modal>
      )}
      {modal === "import" && (
        <Modal
          title="Bring your building together."
          kicker="IMPORT IFC FEDERATION"
          onClose={closeModal}
        >
          <div className="import-illustration">
            <FileBox size={28} strokeWidth={1} />
            <span />
            <Layers3 size={37} strokeWidth={1} />
            <span />
            <Box size={28} strokeWidth={1} />
          </div>
          <p className="modal-description">
            Import one or more local IFC files in their shared world
            coordinates. The engine audits each source and preserves the
            originals.
          </p>
          <label className="field">
            Project name
            <input
              placeholder="e.g. Digital Hub · coordination"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
            />
          </label>
          <LocalFiles
            files={importFiles}
            onChange={setImportFiles}
            onError={setError}
            disabled={!!busy}
          />
          <details className="import-paths" open={!!importPaths}>
            <summary>Use existing absolute IFC paths</summary>
            <label className="field">
              Absolute IFC paths <span>One file per line</span>
              <textarea
                rows={5}
                spellCheck={false}
                placeholder={
                  "C:\\Models\\architecture.ifc\nC:\\Models\\ventilation.ifc"
                }
                value={importPaths}
                onChange={(e) => setImportPaths(e.target.value)}
              />
            </label>
          </details>
          {uploadStatus && (
            <div className="upload-status" role="status">
              <LoaderCircle size={15} className="spin" />
              <span>
                {uploadStatus.phase === "IMPORTING"
                  ? "Recording import and queuing the actual IFC audit…"
                  : uploadStatus.phase === "UPLOADING"
                    ? `Transferring ${uploadStatus.filename} to the local engine · ${uploadStatus.completed}/${uploadStatus.total} files received`
                    : `${uploadStatus.completed}/${uploadStatus.total} files received and hashed`}
              </span>
              {uploadStatus.phase !== "IMPORTING" && (
                <button
                  onClick={() =>
                    uploadAbort.current?.abort(
                      new DOMException(
                        "File transfer cancelled. Received files remain local and can be reused on retry.",
                        "AbortError",
                      ),
                    )
                  }
                >
                  Cancel transfer
                </button>
              )}
            </div>
          )}
          <div className="inline-note">
            <Info size={15} />
            Files stay on this workstation. Federation alignment is audited,
            never manufactured by centering files.
          </div>
          <div className="modal-actions">
            <button
              className="secondary"
              disabled={!!busy}
              onClick={closeModal}
            >
              Cancel
            </button>
            <button
              className="primary"
              disabled={
                !!busy ||
                (!importPaths.trim() && !importFiles.length) ||
                !connected
              }
              onClick={() => void doImport()}
            >
              {busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Plus size={16} />
              )}
              Import and audit
            </button>
          </div>
        </Modal>
      )}
      {modal === "run" && (
        <Modal
          title={
            networkRevision
              ? "Revise the accepted network."
              : "A new engineering run."
          }
          kicker="EXPLICIT SCOPE · RECORDED EVIDENCE"
          onClose={closeModal}
        >
          {!networkRevision && (
            <div className="operation-choices">
              {[
                {
                  id: "check",
                  icon: ShieldCheck,
                  name: "Baseline check",
                  desc: "Inspect the current engineering state.",
                },
                {
                  id: "route",
                  icon: GitBranch,
                  name: "Physical route",
                  desc: "Route an explicit scenario through the model.",
                },
                {
                  id: "optimize",
                  icon: Zap,
                  name: "Optimize",
                  desc: "Explore candidates within the declared scope.",
                },
              ].map(({ id, icon: Icon, name, desc }) => (
                <button
                  key={id}
                  className={operation === id ? "selected" : ""}
                  onClick={() => setOperation(id as RunRequest["operation"])}
                >
                  <Icon size={19} />
                  <span>
                    <strong>{name}</strong>
                    <small>{desc}</small>
                  </span>
                  {operation === id && <Check size={16} />}
                </button>
              ))}
            </div>
          )}
          <div className="form-grid">
            <label className="field">
              Scope
              <select
                value={scope}
                disabled={!!networkRevision}
                onChange={(e) => setScope(e.target.value)}
              >
                <option value="all">Entire federation</option>
                <option value="visible">
                  Visible objects ({visibleIds.size})
                </option>
                <option value="selected" disabled={!selected}>
                  Selected object
                </option>
              </select>
            </label>
            <label className="field">
              Search budget (seconds)
              <input
                type="number"
                min="1"
                max="3600"
                value={budget}
                onChange={(e) =>
                  setBudget(Math.max(1, Math.min(3600, +e.target.value)))
                }
              />
            </label>
          </div>
          {operation !== "check" && (
            <>
              {!networkRevision && (
                <div
                  className="mission-mode"
                  role="group"
                  aria-label="Route mission structure"
                >
                  <button
                    className={missionMode === "single" ? "selected" : ""}
                    onClick={() => setMissionMode("single")}
                  >
                    Single route
                  </button>
                  <button
                    className={missionMode === "joint" ? "selected" : ""}
                    onClick={() => setMissionMode("joint")}
                  >
                    Simultaneous demands
                  </button>
                  <button
                    className={missionMode === "network" ? "selected" : ""}
                    onClick={() => setMissionMode("network")}
                  >
                    Shared network
                  </button>
                </div>
              )}
              {missionMode === "network" ? (
                <SharedNetworkFields
                  value={networkRevision ? revisionAlternatives : sharedNetwork}
                  onChange={
                    networkRevision ? setRevisionAlternatives : setSharedNetwork
                  }
                  revision={networkRevision}
                  revisionStale={revisionStale}
                  baselineBlocked={!!snapshot?.constraints.length}
                />
              ) : missionMode === "joint" ? (
                <JointMissionFields
                  value={jointMission}
                  onChange={setJointMission}
                />
              ) : (
                <MissionFields value={missionForm} onChange={setMissionForm} />
              )}
            </>
          )}
          <div className="inline-note">
            <ShieldCheck size={16} />
            Only executable capabilities run. Missing inputs and unsupported
            scope produce explicit blocked records.
          </div>
          <div className="modal-actions">
            <button className="secondary" onClick={closeModal}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={
                !!busy ||
                !connected ||
                !!stateSelection ||
                revisionStale ||
                (operation !== "check" &&
                  missionMode === "network" &&
                  !!snapshot?.constraints.length &&
                  !networkRevision)
              }
              onClick={() => void doRun()}
            >
              <Play size={14} />
              {networkRevision ? "Check replacement alternatives" : "Start run"}
            </button>
          </div>
        </Modal>
      )}
      {modal === "export" && (
        <Modal
          title="Export the state. Keep the proof."
          kicker="IFC + VERIFICATION EVIDENCE"
          onClose={closeModal}
        >
          <p className="modal-description">
            The engine writes edited IFC and an export manifest, then reports
            fresh-process reopening and the declared checks. Review the report
            for unsupported round-trip losses.
          </p>
          <div className="export-state">
            <FileCheck2 size={28} />
            <div>
              <strong>{snapshot?.project.name}</strong>
              <span>
                Revision {snapshot?.project.revision}{" "}
                {selectedCandidate
                  ? `· candidate ${short(selectedCandidate.id)}`
                  : ""}
              </span>
            </div>
            <Badge
              status={selectedCandidate?.status ?? snapshot?.project.status}
            />
          </div>
          <ValidationAdvisories
            advisories={exportCandidate?.validation_advisories}
          />
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={draft}
              onChange={(e) => setDraft(e.target.checked)}
            />
            <span>
              <strong>Export as a clearly labeled draft</strong>
              <small>
                Required when verification is missing, failed, stale, or outside
                scope.
              </small>
            </span>
          </label>
          <div className="inline-note">
            <Info size={15} />
            {applicabilityReason(exportCandidate)} The server independently
            enforces release predicates.
          </div>
          <div className="modal-actions">
            <button className="secondary" onClick={closeModal}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={
                !!busy ||
                !connected ||
                (!draft && !currentPassingCheck(exportCandidate))
              }
              onClick={() => void exportModel()}
            >
              <ArrowDownToLine size={15} />
              {draft ? "Export draft" : "Export checked release"}
            </button>
          </div>
        </Modal>
      )}
      {modal === "record" && (
        <Modal
          title="The complete record."
          kicker="DURABLE ENGINEERING EVIDENCE"
          onClose={closeModal}
          wide
        >
          <ArtifactLinks
            record={record}
            onOpen={(root) => {
              void perform("Loading evidence artifact", async () => {
                const value = await request(
                  `/artifacts/${encodeURIComponent(root)}`,
                );
                setRecord(value);
              });
            }}
          />
          <pre className="record-json">
            {recordJSON.slice(0, 200000)}
            {recordJSON.length > 200000
              ? "\n\n[Preview bounded to 200,000 characters. Save JSON to inspect the complete record.]"
              : ""}
          </pre>
          <div className="modal-actions">
            <button
              className="secondary"
              onClick={() => {
                const blob = new Blob([recordJSON], {
                    type: "application/json",
                  }),
                  url = URL.createObjectURL(blob),
                  anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "oma-evidence.json";
                anchor.click();
                URL.revokeObjectURL(url);
              }}
            >
              <ArrowDownToLine size={14} />
              Save JSON
            </button>
            <button className="primary" onClick={closeModal}>
              Done
            </button>
          </div>
        </Modal>
      )}
      {modal === "help" && (
        <Modal
          title="Every decision, inspectable."
          kicker="WORKBENCH GUIDE"
          onClose={closeModal}
        >
          <div className="help-list">
            <div>
              <Box size={20} />
              <span>
                <strong>Navigate the actual model</strong>
                <p>
                  Drag to orbit, right drag to pan, and scroll to zoom. F fits
                  the model. Pick an object for semantic properties; isolate it
                  in the inspector.
                </p>
              </span>
            </div>
            <div>
              <ScanIcon />
              <span>
                <strong>Look inside</strong>
                <p>
                  Plan and section use orthographic cameras. The clipping tool
                  cuts by world Z elevation. X-ray exposes systems through
                  surrounding geometry.
                </p>
              </span>
            </div>
            <div>
              <ShieldCheck size={20} />
              <span>
                <strong>Inspect the check, not just the color</strong>
                <p>
                  Open a check to see participating objects and its witness.
                  Select any event or candidate evidence to read and save the
                  underlying record.
                </p>
              </span>
            </div>
            <div>
              <History size={20} />
              <span>
                <strong>Work with actual state</strong>
                <p>
                  Pause and cancel request worker transitions. Accepted
                  revisions remain immutable, and a revert creates a new
                  transaction. The viewer never certifies geometry.
                </p>
              </span>
            </div>
          </div>
          <div className="modal-actions">
            <button className="primary" onClick={closeModal}>
              Back to the workbench
              <ArrowRight size={15} />
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
function Meter({ label, value }: { label: string; value?: number }) {
  return (
    <div className="meter">
      <div>
        <span>{label}</span>
        <strong>
          {value === undefined ? "Not reported" : `${value.toFixed(1)}%`}
        </strong>
      </div>
      <div className="meter-track">
        {value !== undefined && (
          <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
        )}
      </div>
    </div>
  );
}
function RunControls({
  run,
  busy,
  onControl,
}: {
  run: Run;
  busy: boolean;
  onControl: (action: string) => void;
}) {
  const paused = run.status.toUpperCase() === "PAUSED",
    pauseRequested = run.desired_action === "pause" && !paused,
    cancelRequested =
      run.desired_action === "cancel" ||
      run.status.toUpperCase() === "CANCELLING";
  return (
    <div className="run-controls">
      {(pauseRequested || cancelRequested) && (
        <span className="control-pending" role="status">
          {cancelRequested ? "Cancel requested" : "Pause requested"}
          <small>Waiting for worker checkpoint</small>
        </span>
      )}
      <button
        disabled={busy || cancelRequested}
        onClick={() => onControl(paused || pauseRequested ? "resume" : "pause")}
      >
        {paused || pauseRequested ? <Play size={12} /> : <Pause size={12} />}{" "}
        {paused || pauseRequested ? "Resume" : "Pause"}
      </button>
      <button
        disabled={busy || !paused || cancelRequested}
        onClick={() => onControl("step")}
        title="Execute one bounded worker step"
      >
        <StepForward size={13} /> Step
      </button>
      <button
        disabled={busy || cancelRequested}
        onClick={() => onControl("cancel")}
      >
        <Square size={11} /> Cancel
      </button>
    </div>
  );
}

function ScanIcon() {
  return <ListFilter size={20} />;
}
