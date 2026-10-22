import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const SYSTEM_COLORS = {
  hvac: "#347e73",
  plumbing: "#547b9b",
  electrical: "#b58b4b",
  fire: "#b5695f",
};
const FLOOR_HEIGHT = 2.65;
const FOOTPRINT = [
  { x: 0, z: -6.8, width: 28, depth: 6.8 },
  { x: 0, z: 6.8, width: 28, depth: 6.8 },
  { x: 0, z: 0, width: 7.8, depth: 6.8 },
];

/** An illustrative engineering model, independent of imported IFC geometry. */
export default function BuildingViewer({
  visibleSystems = ["hvac", "plumbing", "electrical", "fire"],
  level = "all",
  exploded = false,
  rotation = false,
  resetKey = 0,
  compare = false,
}) {
  const host = useRef(null);
  const sceneRef = useRef(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const element = host.current;
    if (!element) return undefined;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "low-power",
      });
    } catch {
      setUnavailable(true);
      return undefined;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute(
      "aria-label",
      "Illustrative five-level hospital with mechanical, plumbing, electrical and fire service routes. Drag or use arrow keys to orbit; scroll or press plus and minus to zoom.",
    );
    renderer.domElement.setAttribute("tabindex", "0");
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.touchAction = "none";
    element.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-25, 25, 22, -22, 0.1, 250);
    const defaultPosition = new THREE.Vector3(42, 31, 38);
    const defaultTarget = new THREE.Vector3(0, 6, 0);
    camera.position.copy(defaultPosition);
    camera.lookAt(defaultTarget);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(defaultTarget);
    controls.enableDamping = false;
    controls.enablePan = false;
    controls.minZoom = 0.62;
    controls.maxZoom = 2.4;
    controls.minPolarAngle = 0.22;
    controls.maxPolarAngle = Math.PI / 2.14;
    controls.autoRotateSpeed = 0.36;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.65;

    scene.add(new THREE.HemisphereLight("#fffdf8", "#c9c4b7", 2.5));
    const sun = new THREE.DirectionalLight("#fff9ef", 2.2);
    sun.position.set(-15, 40, 22);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.left = -27;
    sun.shadow.camera.right = 27;
    sun.shadow.camera.top = 28;
    sun.shadow.camera.bottom = -22;
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far = 95;
    sun.shadow.normalBias = 0.055;
    sun.shadow.bias = -0.0002;
    scene.add(sun);
    const fill = new THREE.DirectionalLight("#e7edf0", 0.8);
    fill.position.set(25, 12, -18);
    scene.add(fill);

    const geometries = new Set();
    const materials = new Set();
    function material(color, opacity = 1, extra = {}) {
      const value = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.83,
        metalness: 0.03,
        transparent: opacity < 1,
        opacity,
        depthWrite: opacity >= 1,
        ...extra,
      });
      materials.add(value);
      return value;
    }
    const slabMaterial = material("#e6e3d9", 0.7);
    const groundSlabMaterial = material("#d4d0c4");
    const columnMaterial = material("#b9b9ad", 0.6);
    const wallMaterial = material("#d8d8cf", 0.14, { side: THREE.DoubleSide });
    const roomMaterial = material("#c7c9bd", 0.22);
    const plantMaterial = material("#b1b9b1");
    const plantDetailMaterial = material("#7c8c82");
    const serviceMaterials = Object.fromEntries(
      Object.entries(SYSTEM_COLORS).map(([key, color]) => [
        key,
        material(color),
      ]),
    );
    const outlineMaterial = new THREE.LineBasicMaterial({
      color: "#8c9488",
      transparent: true,
      opacity: 0.22,
    });
    materials.add(outlineMaterial);
    const unitBox = new THREE.BoxGeometry(1, 1, 1);
    const unitBoxEdges = new THREE.EdgesGeometry(unitBox);
    geometries.add(unitBox);
    geometries.add(unitBoxEdges);

    function box(parent, width, height, depth, x, y, z, mat, outlined = false) {
      const mesh = new THREE.Mesh(unitBox, mat);
      mesh.scale.set(width, height, depth);
      mesh.position.set(x, y, z);
      mesh.castShadow = mat.opacity === 1;
      mesh.receiveShadow = true;
      parent.add(mesh);
      if (outlined) {
        const line = new THREE.LineSegments(unitBoxEdges, outlineMaterial);
        line.scale.copy(mesh.scale);
        line.position.copy(mesh.position);
        parent.add(line);
      }
      return mesh;
    }

    const unitPipe = new THREE.CylinderGeometry(1, 1, 1, 8, 1);
    geometries.add(unitPipe);
    const verticalAxis = new THREE.Vector3(0, 1, 0);
    function pipe(parent, a, b, radius, mat, rectangular = false) {
      const start = new THREE.Vector3(...a);
      const end = new THREE.Vector3(...b);
      const difference = end.clone().sub(start);
      const distance = difference.length();
      if (distance < 0.001) return;
      let mesh;
      if (rectangular) {
        mesh = new THREE.Mesh(unitBox, mat);
        mesh.scale.set(radius * 2, distance, radius * 1.45);
      } else {
        mesh = new THREE.Mesh(unitPipe, mat);
        mesh.scale.set(radius, distance, radius);
      }
      mesh.position.copy(start.add(end).multiplyScalar(0.5));
      mesh.quaternion.setFromUnitVectors(verticalAxis, difference.normalize());
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      parent.add(mesh);
    }
    function route(parent, points, radius, mat, rectangular = false) {
      for (let i = 1; i < points.length; i += 1)
        pipe(parent, points[i - 1], points[i], radius, mat, rectangular);
    }

    const building = new THREE.Group();
    scene.add(building);
    const floors = [];
    for (let floorIndex = 0; floorIndex < 5; floorIndex += 1) {
      const floor = new THREE.Group();
      floor.position.y = floorIndex * FLOOR_HEIGHT;
      building.add(floor);
      const architecture = new THREE.Group();
      floor.add(architecture);
      FOOTPRINT.forEach(({ x, z, width, depth }) => {
        box(
          architecture,
          width,
          0.15,
          depth,
          x,
          0,
          z,
          floorIndex === 0 ? groundSlabMaterial : slabMaterial,
          true,
        );
      });

      // Exposed structure and sparse room divisions keep the services readable.
      for (const z of [-9.8, -3.65, 3.65, 9.8]) {
        for (const x of [-13.5, -6.75, 0, 6.75, 13.5]) {
          box(architecture, 0.16, 2.5, 0.16, x, 1.3, z, columnMaterial);
        }
      }
      for (const side of [-1, 1]) {
        box(architecture, 27.5, 1.3, 0.035, 0, 0.8, side * 9.99, wallMaterial);
        for (const x of [-10.2, -6.8, -3.4, 3.4, 6.8, 10.2]) {
          box(architecture, 0.035, 0.8, 2.1, x, 0.47, side * 8.8, roomMaterial);
        }
      }
      // A lift/service core and fine stair landings add architectural scale.
      box(architecture, 1.9, 2.5, 1.8, -2.6, 1.3, -1.85, roomMaterial, true);
      box(architecture, 1.9, 2.5, 1.8, 2.6, 1.3, 1.85, roomMaterial, true);
      for (let step = 0; step < 7; step += 1) {
        box(
          architecture,
          1.5,
          0.055,
          0.28,
          -2.6,
          0.2 + step * 0.18,
          0.5 + step * 0.22,
          columnMaterial,
        );
      }

      const systems = {};
      for (const key of Object.keys(SYSTEM_COLORS)) {
        systems[key] = new THREE.Group();
        floor.add(systems[key]);
      }
      const hvac = systems.hvac;
      const plumbing = systems.plumbing;
      const electrical = systems.electrical;
      const fire = systems.fire;

      for (const side of [-1, 1]) {
        const z = side * 6.15;
        route(
          hvac,
          [
            [-12.5, 2.02, z],
            [12.5, 2.02, z],
          ],
          0.19,
          serviceMaterials.hvac,
          true,
        );
        for (const x of [-10.5, -7, -3.5, 3.5, 7, 10.5]) {
          const endZ = side * 9.15;
          route(
            hvac,
            [
              [x, 2.02, z],
              [x, 2.02, endZ],
            ],
            0.105,
            serviceMaterials.hvac,
            true,
          );
          box(hvac, 0.48, 0.075, 0.48, x, 1.93, endZ, serviceMaterials.hvac);
        }
        const waterZ = side * 7.04;
        route(
          plumbing,
          [
            [-12.4, 1.72, waterZ],
            [12.4, 1.72, waterZ],
          ],
          0.068,
          serviceMaterials.plumbing,
        );
        for (const x of [-11.5, -8, -4.5, 4.5, 8, 11.5]) {
          route(
            plumbing,
            [
              [x, 1.72, waterZ],
              [x, 1.72, side * 9.35],
              [x, 0.8, side * 9.35],
            ],
            0.046,
            serviceMaterials.plumbing,
          );
        }
        const fireZ = side * 5.45;
        route(
          fire,
          [
            [-12.7, 2.2, fireZ],
            [12.7, 2.2, fireZ],
          ],
          0.057,
          serviceMaterials.fire,
        );
        for (const x of [-11, -7.3, -3.7, 0, 3.7, 7.3, 11]) {
          route(
            fire,
            [
              [x, 2.2, fireZ],
              [x, 2.2, side * 4.25],
            ],
            0.035,
            serviceMaterials.fire,
          );
          box(
            fire,
            0.17,
            0.07,
            0.17,
            x,
            2.12,
            side * 4.25,
            serviceMaterials.fire,
          );
        }
        const cableZ = side * 7.65;
        route(
          electrical,
          [
            [-12.4, 1.89, cableZ],
            [12.4, 1.89, cableZ],
          ],
          0.073,
          serviceMaterials.electrical,
          true,
        );
        for (const x of [-9, -4.5, 4.5, 9]) {
          route(
            electrical,
            [
              [x, 1.89, cableZ],
              [x, 1.89, side * 8.9],
            ],
            0.04,
            serviceMaterials.electrical,
            true,
          );
          box(
            electrical,
            0.4,
            0.25,
            0.13,
            x,
            1.62,
            side * 8.9,
            serviceMaterials.electrical,
          );
        }
      }

      // Central connections are illustrative only and never change with results.
      for (const [key, offset, height, radius, rectangular] of [
        ["hvac", -0.85, 2.02, 0.19, true],
        ["plumbing", 0.15, 1.72, 0.068, false],
        ["electrical", 0.85, 1.89, 0.073, true],
        ["fire", 1.5, 2.2, 0.057, false],
      ]) {
        const reach =
          key === "hvac"
            ? 6.15
            : key === "plumbing"
              ? 7.04
              : key === "electrical"
                ? 7.65
                : 5.45;
        route(
          systems[key],
          [
            [offset, height, -reach],
            [offset, height, reach],
          ],
          radius,
          serviceMaterials[key],
          rectangular,
        );
      }

      // Vertical risers live within each level, so floor isolation stays legible.
      [
        ["hvac", -2.9, -2.55, 0.23],
        ["plumbing", -2.1, -2.55, 0.11],
        ["electrical", 2.2, 2.55, 0.13],
        ["fire", 2.9, 2.55, 0.085],
      ].forEach(([key, x, z, radius]) => {
        pipe(
          systems[key],
          [x, 0.15, z],
          [x, 2.55, z],
          radius,
          serviceMaterials[key],
          key === "hvac" || key === "electrical",
        );
      });
      floors.push({ group: floor, systems, architecture });
    }

    // Compact rooftop plant, scaled to the model rather than pictorial icons.
    const roofPlant = new THREE.Group();
    floors[4].group.add(roofPlant);
    for (const x of [-9.7, -6.1]) {
      box(roofPlant, 2.45, 0.8, 1.65, x, 2.85, -8.25, plantMaterial, true);
      box(roofPlant, 1.9, 0.12, 1.3, x, 3.31, -8.25, plantDetailMaterial);
      for (let i = 0; i < 6; i += 1) {
        box(
          roofPlant,
          0.06,
          0.03,
          1.13,
          x - 0.7 + i * 0.28,
          3.39,
          -8.25,
          plantMaterial,
        );
      }
    }

    // Batch repeated primitives per floor and service. This keeps interaction
    // responsive on ordinary laptops without sacrificing geometry detail.
    const instancedMeshes = [];
    function instancePrimitives(parent) {
      const batches = new Map();
      for (const child of [...parent.children]) {
        if (child.isGroup) instancePrimitives(child);
        if (!child.isMesh) continue;
        const key = `${child.geometry.uuid}:${child.material.uuid}`;
        if (!batches.has(key)) batches.set(key, []);
        batches.get(key).push(child);
      }
      for (const batch of batches.values()) {
        if (batch.length < 3) continue;
        const merged = new THREE.InstancedMesh(
          batch[0].geometry,
          batch[0].material,
          batch.length,
        );
        merged.castShadow = batch[0].castShadow;
        merged.receiveShadow = batch[0].receiveShadow;
        batch.forEach((mesh, index) => {
          mesh.updateMatrix();
          merged.setMatrixAt(index, mesh.matrix);
          parent.remove(mesh);
        });
        merged.instanceMatrix.needsUpdate = true;
        merged.computeBoundingSphere();
        parent.add(merged);
        instancedMeshes.push(merged);
      }
    }
    instancePrimitives(building);

    // A restrained site datum anchors the axonometric model.
    const site = new THREE.Group();
    scene.add(site);
    // A neutral shadow receiver lets the page's paper color show through.
    const shadowGeometry = new THREE.PlaneGeometry(90, 80);
    const shadowMaterial = new THREE.ShadowMaterial({
      color: "#5f655d",
      opacity: 0.13,
      depthWrite: false,
    });
    geometries.add(shadowGeometry);
    materials.add(shadowMaterial);
    const shadowPlane = new THREE.Mesh(shadowGeometry, shadowMaterial);
    shadowPlane.rotation.x = -Math.PI / 2;
    shadowPlane.position.y = -0.31;
    shadowPlane.receiveShadow = true;
    site.add(shadowPlane);
    const gridMaterial = new THREE.LineBasicMaterial({
      color: "#aaa89b",
      transparent: true,
      opacity: 0.08,
    });
    materials.add(gridMaterial);
    for (let x = -24; x <= 24; x += 4) {
      const geometry = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, -0.28, -20),
        new THREE.Vector3(x, -0.28, 20),
      ]);
      geometries.add(geometry);
      site.add(new THREE.Line(geometry, gridMaterial));
    }
    for (let z = -20; z <= 20; z += 4) {
      const geometry = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-24, -0.28, z),
        new THREE.Vector3(24, -0.28, z),
      ]);
      geometries.add(geometry);
      site.add(new THREE.Line(geometry, gridMaterial));
    }

    let frame = 0;
    let disposed = false;
    let inView = true;
    let lastTime = 0;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    function render(time = 0) {
      frame = 0;
      if (disposed || !inView || document.hidden) return;
      const delta = Math.min(Math.max((time - lastTime) / 1000, 0), 0.05);
      lastTime = time;
      controls.update(delta);
      renderer.render(scene, camera);
      if (controls.autoRotate) invalidate();
    }
    function invalidate() {
      if (!disposed && !frame && inView && !document.hidden)
        frame = requestAnimationFrame(render);
    }
    controls.addEventListener("change", invalidate);
    const resizeObserver = new ResizeObserver(() => {
      const width = Math.max(element.clientWidth, 1);
      const height = Math.max(element.clientHeight, 1);
      const aspect = width / height;
      const halfHeight = Math.max(17.5, 23 / aspect);
      camera.left = -halfHeight * aspect;
      camera.right = halfHeight * aspect;
      camera.top = halfHeight;
      camera.bottom = -halfHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      invalidate();
    });
    resizeObserver.observe(element);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      if (inView) invalidate();
    });
    intersectionObserver.observe(element);
    const onVisibility = () => invalidate();
    document.addEventListener("visibilitychange", onVisibility);

    const state = {
      floors,
      shellMaterials: { slabMaterial, columnMaterial, wallMaterial },
      invalidate,
      controls,
      reducedMotion,
      requestedRotation: false,
      reset() {
        camera.position.copy(defaultPosition);
        camera.zoom = 1;
        camera.updateProjectionMatrix();
        controls.target.copy(defaultTarget);
        controls.update();
        invalidate();
      },
    };
    sceneRef.current = state;
    const onMotion = () => {
      controls.autoRotate = state.requestedRotation && !reducedMotion.matches;
      invalidate();
    };
    reducedMotion.addEventListener("change", onMotion);
    const onContextLost = (event) => {
      event.preventDefault();
      setUnavailable(true);
    };
    const onContextRestored = () => {
      setUnavailable(false);
      invalidate();
    };
    const onKeyDown = (event) => {
      if (
        ![
          "ArrowLeft",
          "ArrowRight",
          "ArrowUp",
          "ArrowDown",
          "+",
          "=",
          "-",
          "r",
          "R",
        ].includes(event.key)
      )
        return;
      event.preventDefault();
      if (event.key === "r" || event.key === "R") {
        state.reset();
        return;
      }
      if (event.key === "+" || event.key === "=" || event.key === "-") {
        camera.zoom = THREE.MathUtils.clamp(
          camera.zoom * (event.key === "-" ? 0.9 : 1.1),
          controls.minZoom,
          controls.maxZoom,
        );
        camera.updateProjectionMatrix();
      } else {
        const spherical = new THREE.Spherical().setFromVector3(
          camera.position.clone().sub(controls.target),
        );
        if (event.key === "ArrowLeft") spherical.theta -= 0.12;
        if (event.key === "ArrowRight") spherical.theta += 0.12;
        if (event.key === "ArrowUp") spherical.phi -= 0.08;
        if (event.key === "ArrowDown") spherical.phi += 0.08;
        spherical.phi = THREE.MathUtils.clamp(
          spherical.phi,
          controls.minPolarAngle,
          controls.maxPolarAngle,
        );
        camera.position.setFromSpherical(spherical).add(controls.target);
      }
      controls.update();
      invalidate();
    };
    renderer.domElement.addEventListener("webglcontextlost", onContextLost);
    renderer.domElement.addEventListener(
      "webglcontextrestored",
      onContextRestored,
    );
    renderer.domElement.addEventListener("keydown", onKeyDown);
    invalidate();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      sceneRef.current = null;
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      reducedMotion.removeEventListener("change", onMotion);
      controls.removeEventListener("change", invalidate);
      renderer.domElement.removeEventListener(
        "webglcontextlost",
        onContextLost,
      );
      renderer.domElement.removeEventListener(
        "webglcontextrestored",
        onContextRestored,
      );
      renderer.domElement.removeEventListener("keydown", onKeyDown);
      controls.dispose();
      instancedMeshes.forEach((mesh) => mesh.dispose());
      geometries.forEach((geometry) => geometry.dispose());
      materials.forEach((mat) => mat.dispose());
      sun.shadow.map?.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === element)
        element.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    const state = sceneRef.current;
    if (!state) return;
    const selected = new Set(visibleSystems);
    const isolated = level !== "all";
    state.floors.forEach((floor, index) => {
      floor.group.visible = !isolated || index === Number(level);
      floor.group.position.y = isolated
        ? 5.1
        : index * (FLOOR_HEIGHT + (exploded ? 1.35 : 0));
      Object.entries(floor.systems).forEach(([key, group]) => {
        group.visible = selected.has(key);
      });
    });
    state.shellMaterials.slabMaterial.opacity = compare ? 0.28 : 0.7;
    state.shellMaterials.columnMaterial.opacity = compare ? 0.25 : 0.6;
    state.shellMaterials.wallMaterial.opacity = compare ? 0.055 : 0.14;
    state.requestedRotation = rotation;
    state.controls.autoRotate = rotation && !state.reducedMotion.matches;
    state.invalidate();
  }, [visibleSystems, level, exploded, rotation, compare]);

  useEffect(() => {
    sceneRef.current?.reset();
  }, [resetKey]);

  return (
    <div
      ref={host}
      className="building-viewer"
      style={{
        width: "100%",
        height: "100%",
        minHeight: 250,
        position: "relative",
      }}
    >
      {unavailable && (
        <div
          role="status"
          style={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeContent: "center",
            textAlign: "center",
            padding: 32,
            background: "#f5f2e9",
            color: "#656c61",
            zIndex: 1,
          }}
        >
          <svg
            width="160"
            height="118"
            viewBox="0 0 160 118"
            fill="none"
            aria-hidden="true"
            style={{ margin: "0 auto 18px" }}
          >
            {[0, 1, 2, 3, 4].map((floor) => (
              <path
                key={floor}
                d={`M20 ${62 - floor * 11} 80 ${32 - floor * 11} 140 ${62 - floor * 11} 80 ${92 - floor * 11}Z`}
                stroke="#8b9a8c"
                fill="#e4e5d9"
                fillOpacity=".5"
                transform="translate(0 24)"
              />
            ))}
          </svg>
          <span style={{ fontSize: 14, fontWeight: 500 }}>
            Building model preview
          </span>
          <span
            style={{
              maxWidth: 270,
              marginTop: 7,
              fontSize: 12,
              lineHeight: 1.6,
            }}
          >
            The interactive 3D view needs a browser with WebGL enabled. Project
            quantities and controls remain available.
          </span>
        </div>
      )}
    </div>
  );
}
