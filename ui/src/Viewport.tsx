import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { candidateEntityIds } from "./candidateGeometry";
import {
  Box,
  Maximize,
  ScanLine,
  Layers2,
  Focus,
  Compass,
  Eye,
  ArrowUp,
  Minus,
  Plus,
  Gauge,
  Download,
  BoxSelect,
  X,
} from "lucide-react";
import {
  frameBox,
  rebasePositions,
  isValidMesh,
  indexEntityMeshes,
} from "./spatial";
import type {
  Geometry,
  Entity,
  Issue,
  Candidate,
  Vec3,
  MeshData,
  Bounds,
} from "./types";

export const disciplineColors: Record<string, string> = {
  arc: "#a3afa5",
  str: "#96a5b5",
  architecture: "#b4beb9",
  architectural: "#b4beb9",
  structure: "#a8b5c1",
  structural: "#a8b5c1",
  mechanical: "#dcb271",
  ventilation: "#dcb271",
  plumbing: "#72b7c0",
  electrical: "#b59ecf",
  heating: "#e19178",
  fire: "#db7c79",
  unknown: "#bac3bf",
};
export const disciplineColor = (s: string) =>
  disciplineColors[s.toLowerCase()] ?? "#96b7ac";
import {
  percentile,
  downloadJson,
  type NavigationBenchmark,
} from "./benchmark";

import type { MeshProgress } from "./meshStream";
import { recordTiming } from "./telemetry";
type ViewMode = "perspective" | "plan" | "section";
interface Props {
  geometry: Geometry | null;
  entities: Entity[];
  selected: string | null;
  visibleIds: Set<string>;
  issue: Issue | null;
  candidate: Candidate | null;
  onSelect: (id: string | null) => void;
  onImport: () => void;
  loading: boolean;
  progress?: MeshProgress | null;
  error: string | null;
  projectId: string | null;
  servicesOnly: boolean;
  onToggleServices: () => void;
}
type Range = { end: number; id: string };
interface SceneContext {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera | THREE.OrthographicCamera;
  controls: OrbitControls;
  model: THREE.Group;
  overlays: THREE.Group;
  selection: THREE.Group;
  grid: THREE.GridHelper;
  origin: THREE.Vector3;
  bounds: THREE.Box3;
  meshes: Map<string, MeshData>;
  pickIds: string[];
  fit: (target?: THREE.Box3) => void;
  redraw: () => void;
  dispose: () => void;
}
function disposeGroup(group: THREE.Group) {
  group.traverse((obj) => {
    if (obj instanceof THREE.Mesh || obj instanceof THREE.Line) {
      obj.geometry.dispose();
      for (const mat of Array.isArray(obj.material)
        ? obj.material
        : [obj.material])
        mat.dispose();
    }
  });
  group.clear();
}
function buildRenderable(data: MeshData, origin: THREE.Vector3) {
  const positions = rebasePositions(data.vertices, cOrigin(origin));
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setIndex(new THREE.BufferAttribute(Uint32Array.from(data.faces), 1));
  geo.computeVertexNormals();
  geo.computeBoundingSphere();
  return geo;
}
function cOrigin(origin: THREE.Vector3): Vec3 {
  return [origin.x, origin.y, origin.z];
}
function entityBounds(data: MeshData, origin: THREE.Vector3) {
  const box = new THREE.Box3();
  for (let i = 0; i < data.vertices.length; i += 3) {
    const x = data.vertices[i] - origin.x,
      y = data.vertices[i + 1] - origin.y,
      z = data.vertices[i + 2] - origin.z;
    box.min.x = Math.min(box.min.x, x);
    box.max.x = Math.max(box.max.x, x);
    box.min.y = Math.min(box.min.y, y);
    box.max.y = Math.max(box.max.y, y);
    box.min.z = Math.min(box.min.z, z);
    box.max.z = Math.max(box.max.z, z);
  }
  return box;
}
export default function Viewport(props: Props) {
  const host = useRef<HTMLDivElement>(null),
    ctx = useRef<SceneContext | null>(null),
    onSelect = useRef(props.onSelect);
  onSelect.current = props.onSelect;
  const [mode, setMode] = useState<ViewMode>("perspective"),
    [xray, setXray] = useState(false),
    [clip, setClip] = useState(false),
    [clipHeight, setClipHeight] = useState(65),
    [compare, setCompare] = useState(false),
    [split, setSplit] = useState(50),
    [envelopes, setEnvelopes] = useState(false),
    [webglError, setWebglError] = useState<string | null>(null),
    [stats, setStats] = useState({ triangles: 0, objects: 0 });
  const [sectionBox, setSectionBox] = useState<Bounds | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [geometryReady, setGeometryReady] = useState(0);
  const viewState = useRef({
    sectionBox,
    mode,
    xray,
    clip,
    clipHeight,
    compare,
    split,
    envelopes,
  });
  viewState.current = {
    sectionBox,
    mode,
    xray,
    clip,
    clipHeight,
    compare,
    split,
    envelopes,
  };
  const [benchmark, setBenchmark] = useState<NavigationBenchmark | null>(null);
  const [benchmarkPhase, setBenchmarkPhase] = useState<string | null>(null);
  const benchmarkRun = useRef<{
    start: number;
    last: number;
    intervals: number[];
    costs: number[];
    gpuCosts: number[];
    gpuDisjoint: boolean;
    position: THREE.Vector3;
    target: THREE.Vector3;
    offset: THREE.Vector3;
    phase: string;
    metadata: NavigationBenchmark;
  } | null>(null);
  const finishBenchmark = (reason?: string) => {
    const run = benchmarkRun.current,
      c = ctx.current;
    if (!run || !c) return;
    benchmarkRun.current = null;
    const elapsed = run.intervals.reduce((a, b) => a + b, 0);
    const fps = elapsed > 0 ? (run.intervals.length * 1000) / elapsed : 0;
    const result: NavigationBenchmark = {
      ...run.metadata,
      status: reason ? "CANCELLED" : "COMPLETED",
      reason,
      frames: run.intervals.length,
      elapsed_ms: elapsed,
      average_fps: fps,
      frame_interval_p50_ms: percentile(run.intervals, 0.5),
      frame_interval_p95_ms: percentile(run.intervals, 0.95),
      cpu_submission_p95_ms: percentile(run.costs, 0.95),
      gpu_timer_status: run.gpuDisjoint
        ? "DISJOINT"
        : run.metadata.gpu_timer_status === "UNAVAILABLE"
          ? "UNAVAILABLE"
          : run.gpuCosts.length
            ? "AVAILABLE"
            : "NO_SAMPLES",
      gpu_frame_p95_ms:
        run.gpuDisjoint || !run.gpuCosts.length
          ? undefined
          : percentile(run.gpuCosts, 0.95),
      gpu_samples: run.gpuCosts.length,
      frames_over_33_33ms: run.intervals.filter((n) => n > 1000 / 30).length,
      average_30fps_gate: reason
        ? "NOT_EVALUATED"
        : fps >= 30
          ? "PASS"
          : "FAIL",
    };
    c.camera.position.copy(run.position);
    c.controls.target.copy(run.target);
    c.controls.enabled = true;
    c.controls.update();
    c.redraw();
    setBenchmark(result);
    setBenchmarkPhase(null);
    try {
      localStorage.setItem("oma.navigation-benchmark", JSON.stringify(result));
    } catch {
      /* Download remains available. */
    }
  };
  const finishBenchmarkRef = useRef(finishBenchmark);
  finishBenchmarkRef.current = finishBenchmark;
  const startBenchmark = () => {
    const c = ctx.current;
    if (!c || !stats.objects || benchmarkRun.current || mode !== "perspective")
      return;
    c.fit();
    const gl = c.renderer.getContext(),
      debug = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = debug
      ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL))
      : String(gl.getParameter(gl.RENDERER));
    const vendor = debug
      ? String(gl.getParameter(debug.UNMASKED_VENDOR_WEBGL))
      : String(gl.getParameter(gl.VENDOR));
    c.controls.enabled = false;
    const metadata: NavigationBenchmark = {
      kind: "oma_navigation_benchmark_v1",
      created_at: new Date().toISOString(),
      status: "COMPLETED",
      project_id: props.projectId,
      state_root: props.geometry?.state_root,
      scene: {
        ...stats,
        draw_calls: c.renderer.info.render.calls,
        width: c.renderer.domElement.clientWidth,
        height: c.renderer.domElement.clientHeight,
        drawing_buffer_width: gl.drawingBufferWidth,
        drawing_buffer_height: gl.drawingBufferHeight,
        pixel_ratio: c.renderer.getPixelRatio(),
        clipped: clip || !!sectionBox,
        xray,
        comparison: compare,
      },
      renderer: { vendor, renderer, browser: navigator.userAgent },
      protocol: {
        warmup_ms: 2000,
        measurement_ms: 10000,
        path: "Fixed 360-degree Z-axis orbit about fitted visible bounds; constant radius/elevation. Actual scene rendered each animation frame.",
        frame_cost:
          "Frame intervals measure delivered RAF cadence during camera motion. CPU submission timing excludes asynchronous GPU completion. When available, EXT_disjoint_timer_query_webgl2 samples actual GPU render duration every tenth measured frame; disjoint queries are rejected.",
      },
      gpu_timer_status: gl.getExtension("EXT_disjoint_timer_query_webgl2")
        ? "NO_SAMPLES"
        : "UNAVAILABLE",
      frames: 0,
      elapsed_ms: 0,
      average_fps: 0,
      frame_interval_p50_ms: 0,
      frame_interval_p95_ms: 0,
      cpu_submission_p95_ms: 0,
      frames_over_33_33ms: 0,
      average_30fps_gate: "NOT_EVALUATED",
    };
    benchmarkRun.current = {
      start: performance.now(),
      last: 0,
      intervals: [],
      costs: [],
      gpuCosts: [],
      gpuDisjoint: false,
      position: c.camera.position.clone(),
      target: c.controls.target.clone(),
      offset: c.camera.position.clone().sub(c.controls.target),
      phase: "Warming up",
      metadata,
    };
    setBenchmark(null);
    setBenchmarkPhase("Warming up");
    c.redraw();
  };
  useEffect(() => {
    finishBenchmarkRef.current("View settings changed");
  }, [mode, xray, clip, clipHeight, compare, split, sectionBox]);
  useEffect(() => {
    ctx.current?.redraw();
  }, [sectionBox]);
  const fitSectionBox = () => {
    const c = ctx.current;
    if (!c) return;
    const mesh = props.selected ? c.meshes.get(props.selected) : undefined;
    const box = mesh
      ? entityBounds(mesh, c.origin).expandByScalar(0.5)
      : new THREE.Box3().setFromObject(c.model);
    if (box.isEmpty()) return;
    box.translate(c.origin);
    setSectionBox({
      min: box.min.toArray() as Vec3,
      max: box.max.toArray() as Vec3,
    });
  };
  const projectRef = useRef<string | null>(null);
  useEffect(() => {
    if (!host.current) return;
    const container = host.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: "high-performance",
      });
    } catch (error) {
      setWebglError(String(error));
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor("#edf1ed");
    renderer.localClippingEnabled = true;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    container.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      "Interactive 3D engineering viewport. Drag to orbit, right drag to pan, scroll to zoom.",
    );
    renderer.domElement.tabIndex = 0;
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0x718075, 1.7));
    const light = new THREE.DirectionalLight(0xfff8e8, 2);
    light.position.set(25, -40, 70);
    scene.add(light);
    const fill = new THREE.DirectionalLight(0xcfe1ee, 0.8);
    fill.position.set(-40, 20, 15);
    scene.add(fill);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100000);
    camera.up.set(0, 0, 1);
    camera.position.set(28, -36, 27);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.screenSpacePanning = true;
    controls.target.set(0, 0, 3);
    const model = new THREE.Group(),
      overlays = new THREE.Group(),
      selection = new THREE.Group();
    scene.add(model, overlays, selection);
    const sectionOutline = new THREE.Box3Helper(new THREE.Box3(), 0x638875);
    (sectionOutline.material as THREE.LineBasicMaterial).transparent = true;
    (sectionOutline.material as THREE.LineBasicMaterial).opacity = 0.55;
    sectionOutline.visible = false;
    scene.add(sectionOutline);
    const grid = new THREE.GridHelper(100, 50, 0xc5d1c8, 0xdbe2dc);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.05;
    scene.add(grid);
    const pickTarget = new THREE.WebGLRenderTarget(1, 1, {
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      depthBuffer: true,
    });
    pickTarget.texture.colorSpace = THREE.NoColorSpace;
    const pickMaterial = new THREE.MeshBasicMaterial({
      vertexColors: true,
      toneMapped: false,
      fog: false,
      blending: THREE.NoBlending,
      side: THREE.DoubleSide,
    });
    const pickPixel = new Uint8Array(4);
    const gpuGl = renderer.getContext() as WebGL2RenderingContext;
    const gpuTimer = gpuGl.getExtension("EXT_disjoint_timer_query_webgl2");
    const gpuQueries: {
      query: WebGLQuery;
      run: NonNullable<typeof benchmarkRun.current>;
    }[] = [];
    let pending = true,
      frame = 0;
    const context: SceneContext = {
      renderer,
      scene,
      camera,
      controls,
      model,
      overlays,
      selection,
      grid,
      origin: new THREE.Vector3(),
      bounds: new THREE.Box3(
        new THREE.Vector3(-10, -10, 0),
        new THREE.Vector3(10, 10, 10),
      ),
      meshes: new Map(),
      pickIds: [],
      fit(target) {
        const visibleBounds = new THREE.Box3().setFromObject(this.model);
        const box =
          target ?? (visibleBounds.isEmpty() ? this.bounds : visibleBounds);
        const center = box.getCenter(new THREE.Vector3()),
          size = box.getSize(new THREE.Vector3()),
          radius = Math.max(size.length() / 2, 1),
          direction = new THREE.Vector3(1, -1.4, 0.95).normalize();
        if (viewState.current.mode === "plan") direction.set(0, -0.00001, 1);
        if (viewState.current.mode === "section") direction.set(0, -1, 0.03);
        const framing = frameBox(
          box,
          direction,
          container.clientWidth / Math.max(container.clientHeight, 1),
        );
        this.controls.target.copy(center);
        this.camera.position
          .copy(center)
          .addScaledVector(direction, framing.distance);
        this.camera.near = Math.max(radius / 10000, 0.001);
        this.camera.far = radius * 100 + 1000;
        if (this.camera instanceof THREE.OrthographicCamera) {
          const aspect =
            container.clientWidth / Math.max(container.clientHeight, 1);
          this.camera.top = framing.halfHeight;
          this.camera.bottom = -framing.halfHeight;
          this.camera.left = -framing.halfHeight * aspect;
          this.camera.right = framing.halfHeight * aspect;
          this.camera.zoom = 1;
        }
        this.camera.updateProjectionMatrix();
        this.controls.update();
        pending = true;
      },
      redraw() {
        pending = true;
      },
      dispose() {
        cancelAnimationFrame(frame);
        resize.disconnect();
        controls.dispose();
        disposeGroup(model);
        disposeGroup(overlays);
        disposeGroup(selection);
        sectionOutline.geometry.dispose();
        (sectionOutline.material as THREE.Material).dispose();
        grid.geometry.dispose();
        (grid.material as THREE.Material).dispose();
        for (const pendingQuery of gpuQueries)
          gpuGl.deleteQuery(pendingQuery.query);
        pickTarget.dispose();
        pickMaterial.dispose();
        renderer.dispose();
        renderer.domElement.remove();
      },
    };
    ctx.current = context;
    controls.addEventListener("change", () => {
      pending = true;
    });
    const resize = new ResizeObserver(() => {
      const w = container.clientWidth,
        h = container.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      if (context.camera instanceof THREE.PerspectiveCamera)
        context.camera.aspect = w / h;
      else {
        const half = context.camera.top;
        context.camera.left = (-half * w) / h;
        context.camera.right = (half * w) / h;
      }
      context.camera.updateProjectionMatrix();
      pending = true;
    });
    resize.observe(container);
    const clock = () => {
      frame = requestAnimationFrame(clock);
      if (gpuTimer && gpuQueries.length) {
        const disjoint = !!gpuGl.getParameter(gpuTimer.GPU_DISJOINT_EXT);
        for (let i = gpuQueries.length - 1; i >= 0; i--) {
          const pendingQuery = gpuQueries[i];
          const available = gpuGl.getQueryParameter(
            pendingQuery.query,
            gpuGl.QUERY_RESULT_AVAILABLE,
          );
          if (disjoint) {
            pendingQuery.run.gpuDisjoint = true;
            pendingQuery.run.gpuCosts = [];
          }
          if (available || disjoint) {
            if (!disjoint)
              pendingQuery.run.gpuCosts.push(
                Number(
                  gpuGl.getQueryParameter(
                    pendingQuery.query,
                    gpuGl.QUERY_RESULT,
                  ),
                ) / 1e6,
              );
            gpuGl.deleteQuery(pendingQuery.query);
            gpuQueries.splice(i, 1);
          }
        }
      }
      const run = benchmarkRun.current,
        now = performance.now();
      let sample = false;
      if (run) {
        if (document.hidden)
          finishBenchmarkRef.current("Browser tab became hidden");
        else if (now - run.start >= 12000) finishBenchmarkRef.current();
        else {
          const elapsed = now - run.start,
            angle = (2 * Math.PI * Math.max(0, elapsed - 2000)) / 10000;
          context.camera.position
            .copy(run.offset)
            .applyAxisAngle(new THREE.Vector3(0, 0, 1), angle)
            .add(run.target);
          context.camera.lookAt(run.target);
          pending = true;
          if (elapsed >= 2000) {
            if (run.last) {
              run.intervals.push(now - run.last);
              sample = true;
            }
            run.last = now;
            if (run.phase !== "Measuring camera motion") {
              run.phase = "Measuring camera motion";
              setBenchmarkPhase(run.phase);
            }
          }
        }
      }
      context.controls.update();
      if (!pending) return;
      pending = false;
      const renderStart = performance.now();
      const gpuQuery =
        sample && run && gpuTimer && run.intervals.length % 10 === 0
          ? gpuGl.createQuery()
          : null;
      if (gpuQuery) gpuGl.beginQuery(gpuTimer!.TIME_ELAPSED_EXT, gpuQuery);
      const state = viewState.current;
      const z =
        context.bounds.min.z +
        ((context.bounds.max.z - context.bounds.min.z) * state.clipHeight) /
          100;
      renderer.clippingPlanes = state.clip
        ? [new THREE.Plane(new THREE.Vector3(0, 0, -1), z)]
        : [];
      sectionOutline.visible = !!state.sectionBox;
      if (state.sectionBox) {
        const low = new THREE.Vector3(...state.sectionBox.min).sub(
            context.origin,
          ),
          high = new THREE.Vector3(...state.sectionBox.max).sub(context.origin);
        sectionOutline.box.set(low, high);
        sectionOutline.updateMatrixWorld(true);
        renderer.clippingPlanes.push(
          new THREE.Plane(new THREE.Vector3(1, 0, 0), -low.x),
          new THREE.Plane(new THREE.Vector3(-1, 0, 0), high.x),
          new THREE.Plane(new THREE.Vector3(0, 1, 0), -low.y),
          new THREE.Plane(new THREE.Vector3(0, -1, 0), high.y),
          new THREE.Plane(new THREE.Vector3(0, 0, 1), -low.z),
          new THREE.Plane(new THREE.Vector3(0, 0, -1), high.z),
        );
      }
      renderer.setScissorTest(false);
      renderer.setViewport(0, 0, container.clientWidth, container.clientHeight);
      const candidateBatches = model.children.filter(
        (child) => child.userData.candidate,
      );
      if (
        state.compare &&
        (overlays.children.length || candidateBatches.length)
      ) {
        const width = container.clientWidth,
          height = container.clientHeight;
        renderer.setScissorTest(true);
        renderer.setScissor(0, 0, (width * state.split) / 100, height);
        overlays.visible = false;
        selection.visible = !selection.userData.candidate;
        candidateBatches.forEach((child) => {
          child.visible = false;
        });
        renderer.render(scene, context.camera);
        renderer.setScissor(
          (width * state.split) / 100,
          0,
          (width * (100 - state.split)) / 100,
          height,
        );
        overlays.visible = true;
        selection.visible = true;
        candidateBatches.forEach((child) => {
          child.visible = true;
        });
        renderer.render(scene, context.camera);
        renderer.setScissorTest(false);
      } else {
        overlays.visible = true;
        selection.visible = true;
        renderer.render(scene, context.camera);
      }
      if (gpuQuery && run) {
        gpuGl.endQuery(gpuTimer!.TIME_ELAPSED_EXT);
        gpuQueries.push({ query: gpuQuery, run });
      }
      if (sample && benchmarkRun.current)
        benchmarkRun.current.costs.push(performance.now() - renderStart);
    };
    clock();
    let downX = 0,
      downY = 0;
    renderer.domElement.addEventListener("pointerdown", (event) => {
      downX = event.clientX;
      downY = event.clientY;
    });
    renderer.domElement.addEventListener("pointerup", (event) => {
      if (
        event.button !== 0 ||
        Math.hypot(event.clientX - downX, event.clientY - downY) > 4
      )
        return;
      if (benchmarkRun.current) return;
      const started = performance.now(),
        rect = renderer.domElement.getBoundingClientRect();
      const x = event.clientX - rect.left,
        y = event.clientY - rect.top;
      const oldTarget = renderer.getRenderTarget(),
        oldColor = renderer.getClearColor(new THREE.Color()),
        oldAlpha = renderer.getClearAlpha();
      const oldOverride = scene.overrideMaterial,
        visibility = new Map<THREE.Object3D, boolean>();
      const beforeSide =
        viewState.current.compare &&
        x / rect.width < viewState.current.split / 100;
      try {
        for (const child of scene.children) {
          visibility.set(child, child.visible);
          child.visible = child === model;
        }
        for (const child of model.children)
          if (beforeSide && child.userData.candidate) {
            visibility.set(child, child.visible);
            child.visible = false;
          }
        scene.overrideMaterial = pickMaterial;
        context.camera.setViewOffset(rect.width, rect.height, x, y, 1, 1);
        renderer.setScissorTest(false);
        renderer.setRenderTarget(pickTarget);
        renderer.setViewport(0, 0, 1, 1);
        renderer.setClearColor(0, 0);
        renderer.render(scene, context.camera);
        renderer.readRenderTargetPixels(pickTarget, 0, 0, 1, 1, pickPixel);
        const index = pickPixel[0] + pickPixel[1] * 256 + pickPixel[2] * 65536;
        onSelect.current(context.pickIds[index] || null);
        recordTiming("semantic_pick", {
          elapsed_ms: performance.now() - started,
          entity_id: context.pickIds[index] || null,
          method:
            "single-pixel GPU identity pass on actual clipped mesh buffers",
        });
      } finally {
        context.camera.clearViewOffset();
        scene.overrideMaterial = oldOverride;
        for (const [child, visible] of visibility) child.visible = visible;
        renderer.setRenderTarget(oldTarget);
        renderer.setClearColor(oldColor, oldAlpha);
        renderer.setViewport(
          0,
          0,
          container.clientWidth,
          container.clientHeight,
        );
        pending = true;
      }
    });
    renderer.domElement.addEventListener("keydown", (event) => {
      if (event.key.toLowerCase() === "f") {
        event.preventDefault();
        context.fit();
      }
      if (event.key === "Escape") onSelect.current(null);
    });
    return () => {
      context.dispose();
      ctx.current = null;
    };
  }, []);
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    const bufferStarted = performance.now();
    let cancelled = false,
      committed = false,
      yieldedAt = performance.now();
    const prepared = new THREE.Group();
    const checkpoint = async (force = false) => {
      if (force || performance.now() - yieldedAt > 12) {
        await new Promise<void>((resolve) => setTimeout(resolve, 0));
        yieldedAt = performance.now();
      }
      if (cancelled)
        throw new DOMException("Geometry preparation cancelled", "AbortError");
    };
    if (benchmarkRun.current)
      finishBenchmarkRef.current("Scene geometry or visibility changed");
    else setBenchmark(null);
    setStats({ triangles: 0, objects: 0 });
    c.meshes.clear();
    c.pickIds = [""];
    disposeGroup(c.model);
    disposeGroup(c.selection);
    disposeGroup(c.overlays);
    c.redraw();
    setPreparing(!!props.geometry);
    void (async () => {
      await checkpoint(true);
      if (!props.geometry) {
        c.meshes.clear();
        setStats({ triangles: 0, objects: 0 });
        c.redraw();
        return;
      }
      if (
        props.geometry.units !== "m" ||
        (props.geometry.coordinate_system &&
          props.geometry.coordinate_system !== "world")
      ) {
        setWebglError(
          "Geometry must declare world coordinates in meters. Rendering is blocked until the coordinate audit is resolved.",
        );
        return;
      }
      const invalid: MeshData[] = [];
      for (const mesh of props.geometry.meshes) {
        if (!isValidMesh(mesh)) invalid.push(mesh);
        await checkpoint();
      }
      if (invalid.length) {
        setWebglError(
          `${invalid.length} mesh artifacts have invalid coordinates or topology. Rendering is blocked; inspect source artifacts.`,
        );
        return;
      }
      setWebglError(null);
      c.meshes = indexEntityMeshes(props.geometry.meshes);
      const rawBounds = new THREE.Box3();
      const zero = new THREE.Vector3();
      for (const m of props.geometry.meshes) {
        rawBounds.union(entityBounds(m, zero));
        await checkpoint();
      }
      if (rawBounds.isEmpty()) {
        setStats({ triangles: 0, objects: 0 });
        c.redraw();
        return;
      }
      const newProject = projectRef.current !== props.projectId;
      if (newProject) {
        setSectionBox(null);
        c.origin.copy(rawBounds.getCenter(new THREE.Vector3()));
      }
      c.bounds.copy(rawBounds).translate(c.origin.clone().negate());
      const entities = new Map(props.entities.map((e) => [e.id, e]));
      const groups = new Map<string, MeshData[]>();
      const proposedIds = candidateEntityIds(props.candidate);
      const objectIds = new Set<string>();
      const pickIndices = new Map<string, number>();
      let triangleCount = 0;
      for (const m of props.geometry.meshes) {
        await checkpoint();
        if (!props.visibleIds.has(m.entity_id) || !m.faces.length) continue;
        const discipline = String(
          entities.get(m.entity_id)?.discipline ?? m.discipline ?? "unknown",
        );
        const key = `${discipline}|${proposedIds.has(m.entity_id) ? "candidate" : "original"}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(m);
        triangleCount += m.faces.length / 3;
        objectIds.add(m.entity_id);
        if (!pickIndices.has(m.entity_id)) {
          pickIndices.set(m.entity_id, c.pickIds.length);
          c.pickIds.push(m.entity_id);
        }
      }
      for (const [key, items] of groups) {
        const [discipline, kind] = key.split("|");
        let chunk: MeshData[] = [],
          count = 0;
        const flush = () => {
          if (!chunk.length) return;
          const positions = new Float32Array(
              chunk.reduce((sum, m) => sum + m.vertices.length, 0),
            ),
            indices = new Uint32Array(
              chunk.reduce((sum, m) => sum + m.faces.length, 0),
            ),
            ranges: Range[] = [];
          const pickColors = new Uint8Array(positions.length);
          let positionOffset = 0,
            indexOffset = 0;
          for (const item of chunk) {
            const offset = positionOffset / 3;
            const identity = pickIndices.get(item.entity_id)!;
            for (
              let k = positionOffset;
              k < positionOffset + item.vertices.length;
              k += 3
            ) {
              pickColors[k] = identity & 255;
              pickColors[k + 1] = (identity >>> 8) & 255;
              pickColors[k + 2] = (identity >>> 16) & 255;
            }
            for (let k = 0; k < item.vertices.length; k += 3) {
              positions[positionOffset++] = item.vertices[k] - c.origin.x;
              positions[positionOffset++] = item.vertices[k + 1] - c.origin.y;
              positions[positionOffset++] = item.vertices[k + 2] - c.origin.z;
            }
            for (const face of item.faces)
              indices[indexOffset++] = face + offset;
            ranges.push({ end: indexOffset / 3, id: item.entity_id });
          }
          const geo = new THREE.BufferGeometry();
          geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
          geo.setIndex(new THREE.BufferAttribute(indices, 1));
          geo.setAttribute(
            "color",
            new THREE.BufferAttribute(pickColors, 3, true),
          );
          geo.computeVertexNormals();
          geo.computeBoundingSphere();
          const material = new THREE.MeshStandardMaterial({
            color:
              kind === "candidate" ? "#308d76" : disciplineColor(discipline),
            roughness: 0.78,
            metalness: 0.025,
            side: THREE.DoubleSide,
            transparent: xray,
            opacity: xray ? 0.2 : 1,
            depthWrite: !xray,
          });
          const mesh = new THREE.Mesh(geo, material);
          mesh.userData.ranges = ranges;
          mesh.userData.candidate = kind === "candidate";
          prepared.add(mesh);
          chunk = [];
          count = 0;
        };
        for (const item of items) {
          await checkpoint();
          chunk.push(item);
          count += item.vertices.length;
          if (count > 600000) flush();
        }
        flush();
        await checkpoint();
      }
      const size = c.bounds.getSize(new THREE.Vector3()),
        span = Math.max(size.x, size.y, 10);
      c.grid.scale.setScalar(span / 65);
      c.grid.position.set(
        c.bounds.getCenter(new THREE.Vector3()).x,
        c.bounds.getCenter(new THREE.Vector3()).y,
        c.bounds.min.z - 0.025,
      );
      if (newProject) {
        const buildingBox = new THREE.Box3();
        for (const [id, mesh] of c.meshes) {
          await checkpoint();
          const type = entities.get(id)?.ifc_type ?? "";
          if (
            /^Ifc(Wall|Slab|Column|Beam|Roof|Door|Window|Stair|CurtainWall|Member|Plate|Flow|Pipe|Duct)/.test(
              type,
            )
          )
            buildingBox.union(entityBounds(mesh, c.origin));
        }
        c.fit(buildingBox.isEmpty() ? undefined : buildingBox);
      }
      await checkpoint();
      c.model.add(...[...prepared.children]);
      projectRef.current = props.projectId;
      committed = true;
      setStats({ triangles: triangleCount, objects: objectIds.size });
      setGeometryReady((value) => value + 1);
      recordTiming("geometry_buffers_ready", {
        project_id: props.projectId,
        state_root: props.geometry.state_root,
        objects: objectIds.size,
        triangles: triangleCount,
        elapsed_ms: performance.now() - bufferStarted,
      });
      c.redraw();
    })()
      .catch((error: Error) => {
        if (!cancelled) setWebglError(error.message);
      })
      .finally(() => {
        disposeGroup(prepared);
        if (!cancelled) setPreparing(false);
      });
    return () => {
      cancelled = true;
      if (!committed && props.geometry)
        recordTiming("geometry_preparation_cancelled", {
          project_id: props.projectId,
          state_root: props.geometry.state_root,
          elapsed_ms: performance.now() - bufferStarted,
        });
      disposeGroup(prepared);
    };
  }, [
    props.geometry,
    props.entities,
    props.visibleIds,
    props.projectId,
    props.candidate?.id,
    xray,
  ]);
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    disposeGroup(c.selection);
    c.selection.userData.candidate =
      !!props.selected &&
      candidateEntityIds(props.candidate).has(props.selected);
    if (props.selected && !preparing) {
      const data = c.meshes.get(props.selected);
      if (data) {
        const geo = buildRenderable(data, c.origin);
        const mesh = new THREE.Mesh(
          geo,
          new THREE.MeshStandardMaterial({
            color: "#2f8d76",
            emissive: "#17664b",
            emissiveIntensity: 0.45,
            transparent: true,
            opacity: 0.75,
            side: THREE.DoubleSide,
            depthTest: false,
          }),
        );
        mesh.renderOrder = 10;
        c.selection.add(mesh);
        const edge = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo, 25),
          new THREE.LineBasicMaterial({ color: "#153d36", depthTest: false }),
        );
        edge.renderOrder = 11;
        c.selection.add(edge);
      }
    }
    c.redraw();
  }, [
    props.selected,
    props.geometry,
    props.candidate?.id,
    geometryReady,
    preparing,
  ]);
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    disposeGroup(c.overlays);
    if (preparing) {
      c.redraw();
      return;
    }
    if (props.issue?.witness?.point) {
      const position = new THREE.Vector3(...props.issue.witness.point).sub(
        c.origin,
      );
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.035, 20, 12),
        new THREE.MeshBasicMaterial({ color: "#df694d", depthTest: false }),
      );
      dot.position.copy(position);
      dot.renderOrder = 12;
      c.overlays.add(dot);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.12, 0.006, 8, 48),
        new THREE.MeshBasicMaterial({ color: "#b74931", depthTest: false }),
      );
      ring.position.copy(position);
      ring.renderOrder = 12;
      c.overlays.add(ring);
      if (props.issue.witness.other_point) {
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([
            position,
            new THREE.Vector3(...props.issue.witness.other_point).sub(c.origin),
          ]),
          new THREE.LineBasicMaterial({ color: "#c35839", depthTest: false }),
        );
        line.renderOrder = 12;
        c.overlays.add(line);
      }
      c.fit(
        new THREE.Box3(
          position.clone().addScalar(-1.5),
          position.clone().addScalar(1.5),
        ),
      );
    }
    for (const route of props.candidate?.routes ?? []) {
      const materialized = route.id && c.meshes.has(route.id);
      const points = route.points_m ?? route.points ?? route.centerline ?? [];
      const diameter = route.diameter_m ?? route.section?.diameter_m;
      const insulation = route.insulation_m ?? route.section?.insulation_m;
      const radius =
        route.radius_m ??
        route.radius ??
        route.section?.radius_m ??
        (diameter !== undefined && insulation !== undefined
          ? diameter / 2 + insulation
          : undefined);
      if (radius === undefined || radius <= 0) continue;
      for (let i = 1; i < points.length; i++) {
        const a = new THREE.Vector3(...points[i - 1]).sub(c.origin),
          b = new THREE.Vector3(...points[i]).sub(c.origin),
          direction = b.clone().sub(a),
          length = direction.length();
        if (length < 1e-9) continue;
        const geo = new THREE.CylinderGeometry(radius, radius, length, 12);
        const mat = new THREE.MeshStandardMaterial({
          color: "#278b75",
          roughness: 0.5,
          metalness: 0.15,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.copy(a).add(b).multiplyScalar(0.5);
        mesh.quaternion.setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          direction.normalize(),
        );
        if (!materialized) c.overlays.add(mesh);
        else {
          geo.dispose();
          mat.dispose();
        }
        if (envelopes && route.clearance_m) {
          const shell = new THREE.Mesh(
            new THREE.CylinderGeometry(
              radius + route.clearance_m,
              radius + route.clearance_m,
              length,
              12,
            ),
            new THREE.MeshBasicMaterial({
              color: "#359b88",
              opacity: 0.12,
              transparent: true,
              depthWrite: false,
              side: THREE.DoubleSide,
            }),
          );
          shell.position.copy(mesh.position);
          shell.quaternion.copy(mesh.quaternion);
          c.overlays.add(shell);
        }
      }
    }
    c.redraw();
  }, [
    props.issue,
    props.candidate,
    props.geometry,
    envelopes,
    geometryReady,
    preparing,
  ]);
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    const old = c.camera;
    if (mode === "perspective") {
      if (!(old instanceof THREE.PerspectiveCamera)) {
        c.camera = new THREE.PerspectiveCamera(
          38,
          Math.max(host.current!.clientWidth, 1) /
            Math.max(host.current!.clientHeight, 1),
          0.01,
          100000,
        );
        c.camera.up.set(0, 0, 1);
      }
    } else if (!(old instanceof THREE.OrthographicCamera)) {
      c.camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.01, 100000);
      c.camera.up.set(0, 0, 1);
    }
    if (old !== c.camera) {
      c.controls.object = c.camera;
    }
    c.controls.enableRotate = mode === "perspective";
    c.fit();
    c.redraw();
  }, [mode]);
  useEffect(() => {
    ctx.current?.redraw();
  }, [clip, clipHeight, compare, split]);
  const fitSelection = () => {
    const c = ctx.current;
    if (!c) return;
    const selected = props.selected ? c.meshes.get(props.selected) : undefined;
    if (selected) c.fit(entityBounds(selected, c.origin));
    else if (props.issue?.witness?.point) {
      const p = new THREE.Vector3(...props.issue.witness.point).sub(c.origin);
      c.fit(new THREE.Box3(p.clone().addScalar(-2), p.clone().addScalar(2)));
    } else c.fit();
  };
  return (
    <div className="viewport-wrap">
      <div className="viewport-canvas" ref={host} />
      <div className="viewport-top">
        <div className="segmented">
          {(["perspective", "plan", "section"] as ViewMode[]).map((v) => (
            <button
              key={v}
              className={mode === v ? "active" : ""}
              onClick={() => setMode(v)}
            >
              {v === "perspective" ? (
                <Box size={14} />
              ) : v === "plan" ? (
                <ArrowUp size={14} />
              ) : (
                <ScanLine size={14} />
              )}
              <span>
                {v === "perspective"
                  ? "3D model"
                  : v === "plan"
                    ? "Plan"
                    : "Section"}
              </span>
            </button>
          ))}
        </div>
        <div className="viewport-chips">
          {props.projectId && (
            <button
              className={`service-view ${props.servicesOnly ? "active" : ""}`}
              onClick={props.onToggleServices}
              title="Display only service element IFC types; this does not change engineering state"
            >
              <Layers2 size={13} />
              Service elements
            </button>
          )}
          <span className="light-chip">WORLD · m</span>
          {props.geometry?.truncated && (
            <span className="light-chip warning">PARTIAL GEOMETRY</span>
          )}
        </div>
      </div>
      <div className="viewport-toolrail">
        <button
          aria-label="Fit model (F)"
          title="Fit model (F)"
          onClick={() => ctx.current?.fit()}
        >
          <Maximize size={18} />
        </button>
        <button
          aria-label="Focus selection"
          title="Focus selection or witness"
          onClick={fitSelection}
        >
          <Focus size={18} />
        </button>
        <div className="tool-divider" />
        <button
          aria-label="Toggle x-ray"
          title="X-ray"
          className={xray ? "active" : ""}
          onClick={() => setXray(!xray)}
        >
          <Eye size={18} />
        </button>
        <button
          aria-label="Toggle horizontal clipping plane"
          title="Horizontal clipping plane"
          className={clip ? "active" : ""}
          onClick={() => setClip(!clip)}
        >
          <ScanLine size={18} />
        </button>
        <button
          aria-label="Toggle section box"
          title="Six-plane section box in world meters"
          className={sectionBox ? "active" : ""}
          onClick={() => (sectionBox ? setSectionBox(null) : fitSectionBox())}
        >
          <BoxSelect size={18} />
        </button>
        <button
          aria-label="Show route envelope guides"
          title="Parameterized straight-section clearance guides"
          className={envelopes ? "active" : ""}
          onClick={() => setEnvelopes(!envelopes)}
        >
          <Layers2 size={18} />
        </button>
        <div className="tool-divider" />
        <button
          aria-label="Zoom in"
          onClick={() => {
            const c = ctx.current;
            if (c) {
              if (c.camera instanceof THREE.OrthographicCamera)
                c.camera.zoom *= 1.2;
              else c.camera.position.lerp(c.controls.target, 0.2);
              c.camera.updateProjectionMatrix();
              c.redraw();
            }
          }}
        >
          <Plus size={18} />
        </button>
        <button
          aria-label="Zoom out"
          onClick={() => {
            const c = ctx.current;
            if (c) {
              if (c.camera instanceof THREE.OrthographicCamera)
                c.camera.zoom /= 1.2;
              else
                c.camera.position.add(
                  c.camera.position
                    .clone()
                    .sub(c.controls.target)
                    .multiplyScalar(0.2),
                );
              c.camera.updateProjectionMatrix();
              c.redraw();
            }
          }}
        >
          <Minus size={18} />
        </button>
      </div>
      {sectionBox && (
        <div className="section-box-control">
          <div>
            <strong>
              Section box <small>WORLD m</small>
            </strong>
            <button
              aria-label="Close section box"
              onClick={() => setSectionBox(null)}
            >
              <X size={12} />
            </button>
          </div>
          <div className="section-box-labels">
            <span>Axis</span>
            <span>Minimum</span>
            <span>Maximum</span>
          </div>
          {(["X", "Y", "Z"] as const).map((axis, index) => (
            <div className="section-box-row" key={axis}>
              <b>{axis}</b>
              {(["min", "max"] as const).map((edge) => (
                <input
                  key={edge}
                  aria-label={`Section box ${axis} ${edge}`}
                  type="number"
                  step="0.1"
                  value={Number(sectionBox[edge][index].toFixed(4))}
                  onChange={(event) => {
                    const value = event.target.valueAsNumber;
                    if (!Number.isFinite(value)) return;
                    if (
                      (edge === "min" && value >= sectionBox.max[index]) ||
                      (edge === "max" && value <= sectionBox.min[index])
                    )
                      return;
                    setSectionBox((previous) => {
                      if (!previous) return previous;
                      const next = {
                        min: [...previous.min] as Vec3,
                        max: [...previous.max] as Vec3,
                      };
                      next[edge][index] = value;
                      return next;
                    });
                  }}
                />
              ))}
            </div>
          ))}
          <button className="section-box-fit" onClick={fitSectionBox}>
            <Focus size={12} />
            {props.selected
              ? "Fit to selection + 0.5 m"
              : "Fit to visible model"}
          </button>
        </div>
      )}
      {clip && (
        <div className="clip-control">
          <ScanLine size={14} />
          <label htmlFor="clip-height">Section height</label>
          <input
            id="clip-height"
            type="range"
            min="0"
            max="100"
            value={clipHeight}
            onChange={(e) => setClipHeight(+e.target.value)}
          />
          <span>
            {ctx.current
              ? (
                  ctx.current.bounds.min.z +
                  ((ctx.current.bounds.max.z - ctx.current.bounds.min.z) *
                    clipHeight) /
                    100 +
                  ctx.current.origin.z
                ).toFixed(2)
              : "—"}{" "}
            m
          </span>
        </div>
      )}
      {props.candidate && candidateEntityIds(props.candidate).size > 0 && (
        <div className="compare-control">
          <button
            className={compare ? "active" : ""}
            onClick={() => setCompare(!compare)}
          >
            <Layers2 size={14} />
            Compare candidate geometry
          </button>
          <button
            onClick={() => {
              const c = ctx.current;
              if (!c) return;
              const box = new THREE.Box3();
              for (const id of candidateEntityIds(props.candidate)) {
                const data = c.meshes.get(id);
                if (data) box.union(entityBounds(data, c.origin));
              }
              for (const route of props.candidate?.routes ?? []) {
                const mesh = route.id ? c.meshes.get(route.id) : undefined;
                if (mesh) box.union(entityBounds(mesh, c.origin));
                else
                  for (const point of route.points_m ??
                    route.points ??
                    route.centerline ??
                    [])
                    box.expandByPoint(
                      new THREE.Vector3(...point).sub(c.origin),
                    );
              }
              if (!box.isEmpty()) c.fit(box.expandByScalar(0.2));
            }}
          >
            <Focus size={13} />
            Focus candidate
          </button>
          <span>{props.candidate.status}</span>
        </div>
      )}
      {compare &&
        props.candidate &&
        candidateEntityIds(props.candidate).size > 0 && (
          <>
            <div className="compare-line" style={{ left: `${split}%` }}>
              <span>↔</span>
            </div>
            <div className="compare-label before">
              {props.candidate.networks?.some(
                (network) => network.network_contract?.revision,
              )
                ? "Source context · previous network not loaded"
                : "Baseline context"}
            </div>
            <div className="compare-label after">Candidate geometry</div>
            <input
              className="compare-range"
              aria-label="Before and candidate comparison divider"
              type="range"
              min="5"
              max="95"
              value={split}
              onChange={(e) => setSplit(+e.target.value)}
            />
          </>
        )}
      {!props.projectId && !props.loading && (
        <div className="empty-viewport">
          <div className="empty-orbit">
            <span />
            <span />
            <Box size={40} strokeWidth={1} />
          </div>
          <p className="eyebrow">A CLEARER VIEW OF WHAT'S POSSIBLE</p>
          <h1>
            Engineering,
            <br />
            in full view.
          </h1>
          <p>
            Bring your building into one shared space.
            <br />
            Inspect the facts. Explore changes. Follow the evidence.
          </p>
          <button className="primary large" onClick={props.onImport}>
            <Plus size={17} />
            Import IFC models
          </button>
          <div className="empty-foot">
            LOCAL COMPUTATION <i /> ORIGINALS PRESERVED <i /> IFC NATIVE
          </div>
        </div>
      )}
      {(props.loading || preparing) && (
        <div className="viewport-loading">
          <span className="spinner" />
          <strong>
            {preparing ? "Preparing model geometry" : "Loading model geometry"}
          </strong>
          <span>
            {preparing
              ? "Building complete mesh buffers; project switching remains available"
              : props.progress
                ? `${props.progress.received_meshes.toLocaleString()} actual meshes received / ${(props.progress.received_bytes / 1048576).toFixed(1)} MiB decoded`
                : "Reading actual IFC mesh artifacts"}
          </span>
        </div>
      )}
      {(props.error || webglError) && (
        <div className="viewport-error">
          <strong>Geometry is unavailable</strong>
          <p>{props.error ?? webglError}</p>
        </div>
      )}
      {props.projectId &&
        !props.loading &&
        !props.geometry?.meshes.length &&
        !props.error && (
          <div className="viewport-loading">
            <Box size={30} />
            <strong>No renderable geometry</strong>
            <span>
              Inspect the input audit for unsupported or unresolved objects.
            </span>
          </div>
        )}
      {(!props.candidate || benchmarkPhase) && (
        <div className="navigation-benchmark">
          {benchmarkPhase ? (
            <div className="benchmark-progress" role="status">
              <span className="spinner" />
              {benchmarkPhase}
              <button
                onClick={() => finishBenchmark("Cancelled by user")}
                aria-label="Cancel navigation benchmark"
              >
                <X size={13} />
              </button>
            </div>
          ) : (
            <button
              disabled={
                !stats.objects || mode !== "perspective" || props.loading
              }
              onClick={startBenchmark}
              title="2-second warmup, then a measured 10-second orbit of this scene"
            >
              <Gauge size={13} /> Navigation benchmark
            </button>
          )}
          {benchmark && (
            <div
              className="benchmark-result"
              data-testid="navigation-benchmark-result"
            >
              <strong>
                {benchmark.status === "COMPLETED"
                  ? `${benchmark.average_fps.toFixed(1)} FPS`
                  : "Benchmark cancelled"}
              </strong>
              <span>
                {benchmark.scene.objects.toLocaleString()} objects {"\u00b7"}{" "}
                {benchmark.frame_interval_p95_ms.toFixed(1)} ms p95
              </span>
              {benchmark.gpu_frame_p95_ms !== undefined && (
                <span>
                  GPU p95 {benchmark.gpu_frame_p95_ms.toFixed(2)} ms (
                  {benchmark.gpu_samples} queries)
                </span>
              )}
              <span
                className={
                  benchmark.average_30fps_gate === "PASS"
                    ? "benchmark-pass"
                    : "benchmark-fail"
                }
              >
                30 FPS mean gate: {benchmark.average_30fps_gate}
              </span>
              <button
                onClick={() =>
                  downloadJson(
                    benchmark,
                    `oma-navigation-${props.projectId}.json`,
                  )
                }
              >
                <Download size={12} /> JSON evidence
              </button>
              <details>
                <summary>Measurement record</summary>
                <pre>{JSON.stringify(benchmark, null, 2)}</pre>
              </details>
            </div>
          )}
        </div>
      )}
      <div className="viewport-bottom">
        <span>
          <span className="legend-dot" />
          {stats.objects.toLocaleString()}{" "}
          {sectionBox || clip ? "enabled" : "visible"} objects <b>·</b>{" "}
          {stats.triangles.toLocaleString()} triangles
        </span>
        <span>
          Orbit <kbd>drag</kbd> Pan <kbd>right drag</kbd> Fit <kbd>F</kbd>
        </span>
      </div>
      <div className="north">
        <Compass size={29} strokeWidth={1} />
        <span>Z ↑</span>
      </div>
    </div>
  );
}
export type { Vec3 };
