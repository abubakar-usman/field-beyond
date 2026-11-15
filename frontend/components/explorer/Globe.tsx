"use client";

// Illustrative 3D globe of the Moon or Mars. Colour texture only: it is not an elevation
// dataset. Pins are backend targets on this body; nothing here is drawn on an Earth map.
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import type { Planet, SurfacePoint } from "@/lib/planets";

const NO_LOCATIONS: SurfacePoint[] = [];

type Props = {
  planet: Planet;
  /** Backend targets on this body, shown as pins. */
  locations?: SurfacePoint[];
  preview?: boolean;
  selected?: SurfacePoint | null;
  onSelect?: (point: SurfacePoint) => void;
  zoom?: number;
  reset?: number;
  grid?: boolean;
};

function vector(point: SurfacePoint, radius = 1.008) {
  const lat = THREE.MathUtils.degToRad(point.lat);
  const lon = THREE.MathUtils.degToRad(point.lon);
  return new THREE.Vector3(
    Math.cos(lat) * Math.cos(lon),
    Math.sin(lat),
    -Math.cos(lat) * Math.sin(lon),
  ).multiplyScalar(radius);
}

export default function Globe({
  planet,
  locations = NO_LOCATIONS,
  preview = false,
  selected,
  onSelect,
  zoom = 0,
  reset = 0,
  grid = false,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const markers = useRef<(HTMLButtonElement | null)[]>([]);
  const selectionRef = useRef<HTMLDivElement>(null);
  const current = useRef({ selected, onSelect, locations });
  useEffect(() => {
    current.current = { selected, onSelect, locations };
  });
  const api = useRef<{
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    grid: THREE.LineSegments;
    focus: THREE.Vector3 | null;
  } | null>(null);
  const [retry, setRetry] = useState(0);
  // Status is keyed by the scene it describes, so a new scene starts as "loading"
  // without a synchronous setState in the effect.
  const sceneKey = `${planet.id}|${preview}|${retry}`;
  const [scene, setScene] = useState<{ key: string; status: "ready" | "error" } | null>(null);
  const status = scene?.key === sceneKey ? scene.status : "loading";

  useEffect(() => {
    const element = host.current!;
    let renderer: THREE.WebGLRenderer;
    let disposed = false;
    let frame = 0;
    const setStatus = (value: "ready" | "error") => setScene({ key: sceneKey, status: value });
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
      });
    } catch {
      setStatus("error");
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x000000, 0);
    element.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    camera.position.set(3.65, 0.4, 0.25);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.minDistance = 1.65;
    controls.maxDistance = 5.8;
    controls.autoRotate = preview && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    controls.autoRotateSpeed = planet.id === "moon" ? 0.55 : 0.4;
    controls.enableZoom = !preview;
    scene.add(new THREE.AmbientLight(0xffffff, 1.35));
    const sun = new THREE.DirectionalLight(0xfff5eb, 2.8);
    sun.position.set(3, 3, 4);
    scene.add(sun);
    const rim = new THREE.DirectionalLight(0xb4c9ed, 0.55);
    rim.position.set(-2, 1, -3);
    scene.add(rim);
    const geometry = new THREE.SphereGeometry(1, 96, 64);
    const material = new THREE.MeshStandardMaterial({
      roughness: 0.96,
      metalness: 0,
      color: 0xffffff,
    });
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);
    const gridVertices: number[] = [];
    const addLine = (a: SurfacePoint, b: SurfacePoint) => {
      gridVertices.push(...vector(a, 1.003).toArray(), ...vector(b, 1.003).toArray());
    };
    for (let lat = -75; lat <= 75; lat += 15) {
      for (let lon = -180; lon < 180; lon += 3) addLine({ lat, lon }, { lat, lon: lon + 3 });
    }
    for (let lon = -180; lon < 180; lon += 30) {
      for (let lat = -90; lat < 90; lat += 3) addLine({ lat, lon }, { lat: lat + 3, lon });
    }
    const gridGeometry = new THREE.BufferGeometry();
    gridGeometry.setAttribute("position", new THREE.Float32BufferAttribute(gridVertices, 3));
    const gridMaterial = new THREE.LineBasicMaterial({
      color: 0xc5eaaa,
      transparent: true,
      opacity: 0.13,
    });
    const gridMesh = new THREE.LineSegments(gridGeometry, gridMaterial);
    gridMesh.visible = false;
    scene.add(gridMesh);
    api.current = { camera, controls, grid: gridMesh, focus: null };
    const cancelFocus = () => {
      if (api.current) api.current.focus = null;
    };
    controls.addEventListener("start", cancelFocus);
    let texture: THREE.Texture | undefined;
    new THREE.TextureLoader().load(
      `/textures/${planet.id}.jpg`,
      (loaded) => {
        if (disposed) {
          loaded.dispose();
          return;
        }
        texture = loaded;
        loaded.colorSpace = THREE.SRGBColorSpace;
        loaded.anisotropy = renderer.capabilities.getMaxAnisotropy();
        material.map = loaded;
        material.bumpMap = loaded;
        material.bumpScale = planet.id === "moon" ? 0.025 : 0.018;
        material.needsUpdate = true;
        setStatus("ready");
      },
      undefined,
      () => {
        if (!disposed) setStatus("error");
      },
    );
    const resize = new ResizeObserver(() => {
      camera.aspect = element.clientWidth / Math.max(element.clientHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(element.clientWidth, element.clientHeight);
    });
    resize.observe(element);
    const raycaster = new THREE.Raycaster();
    const start = { x: 0, y: 0 };
    const down = (event: PointerEvent) => {
      start.x = event.clientX;
      start.y = event.clientY;
      if (api.current) api.current.focus = null;
    };
    const up = (event: PointerEvent) => {
      if (preview || Math.hypot(event.clientX - start.x, event.clientY - start.y) > 5) return;
      const bounds = renderer.domElement.getBoundingClientRect();
      raycaster.setFromCamera(
        new THREE.Vector2(
          ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
          (-(event.clientY - bounds.top) / bounds.height) * 2 + 1,
        ),
        camera,
      );
      const hit = raycaster.intersectObject(mesh)[0];
      if (hit?.uv)
        current.current.onSelect?.({ lat: hit.uv.y * 180 - 90, lon: hit.uv.x * 360 - 180 });
    };
    renderer.domElement.addEventListener("pointerdown", down);
    renderer.domElement.addEventListener("pointerup", up);
    const contextLost = (event: Event) => {
      event.preventDefault();
      setStatus("error");
    };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    const positionLabel = (point: SurfacePoint, node: HTMLElement | null) => {
      if (!node) return;
      const world = vector(point);
      const visible = world.dot(camera.position.clone().sub(world)) > 0;
      const screen = world.project(camera);
      node.style.left = `${(screen.x * 0.5 + 0.5) * element.clientWidth}px`;
      node.style.top = `${(-screen.y * 0.5 + 0.5) * element.clientHeight}px`;
      node.style.visibility = visible && screen.z < 1 ? "visible" : "hidden";
    };
    const animate = () => {
      frame = requestAnimationFrame(animate);
      if (api.current?.focus) {
        camera.position.lerp(api.current.focus, 0.07);
        if (camera.position.distanceTo(api.current.focus) < 0.005) api.current.focus = null;
      }
      controls.update();
      if (!preview) {
        current.current.locations.forEach((point, index) =>
          positionLabel(point, markers.current[index] ?? null),
        );
        if (current.current.selected) positionLabel(current.current.selected, selectionRef.current);
      }
      renderer.render(scene, camera);
    };
    animate();
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      controls.removeEventListener("start", cancelFocus);
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", down);
      renderer.domElement.removeEventListener("pointerup", up);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      geometry.dispose();
      material.dispose();
      texture?.dispose();
      gridGeometry.dispose();
      gridMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      api.current = null;
    };
  }, [planet.id, preview, retry, sceneKey]);

  useEffect(() => {
    if (selected && api.current)
      api.current.focus = vector(selected)
        .normalize()
        .multiplyScalar(Math.max(2.8, api.current.camera.position.length()));
  }, [selected, planet.id, retry]);
  useEffect(() => {
    if (!api.current || !zoom) return;
    api.current.focus = null;
    const position = api.current.camera.position;
    position.multiplyScalar(zoom > 0 ? 0.85 : 1.18);
    position.clampLength(1.65, 5.8);
  }, [zoom]);
  useEffect(() => {
    if (api.current && reset) api.current.focus = new THREE.Vector3(3.65, 0.4, 0.25);
  }, [reset]);
  useEffect(() => {
    if (api.current) api.current.grid.visible = grid;
  }, [grid, retry]);

  return (
    <div
      className={`globe ${preview ? "globe-preview" : ""}`}
      ref={host}
      aria-label={`Interactive 3D ${planet.name} globe`}
    >
      {status === "loading" && (
        <div className="globe-state" role="status">
          <LoaderCircle className="spin" size={22} />
          <span>Loading {planet.name.toLowerCase()} surface</span>
        </div>
      )}
      {status === "error" && (
        <div className="globe-state error" role="alert">
          <TriangleAlert size={24} />
          <span>Unable to render the globe</span>
          <small>Enable WebGL or try loading the surface again.</small>
          <button className="secondary" onClick={() => setRetry((value) => value + 1)}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}
      {!preview &&
        onSelect &&
        status === "ready" &&
        locations.map((point, index) => (
          <button
            key={point.targetId ?? point.name}
            ref={(node) => {
              markers.current[index] = node;
            }}
            className={`globe-pin ${selected?.targetId && selected.targetId === point.targetId ? "active" : ""}`}
            onClick={() => onSelect?.(point)}
            aria-label={`Select ${point.name}`}
          >
            <span className="pin-dot" />
            <span className="pin-name">{point.name}</span>
          </button>
        ))}
      {!preview && selected && status === "ready" && (
        <div className="surface-marker" ref={selectionRef}>
          <span />
          <i />
        </div>
      )}
    </div>
  );
}
