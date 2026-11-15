"use client";

// Three screens: choose a body, pick a target on its globe, then compare with Earth.
// Targets, regions, the registry and API health come from the FastAPI backend via /api.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Crosshair,
  Earth,
  Globe2,
  Layers3,
  LoaderCircle,
  LocateFixed,
  MapPin,
  Maximize2,
  Minus,
  MousePointer2,
  Move,
  Orbit,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import Globe from "./Globe";
import Comparison from "./Comparison";
import TargetProfile from "./TargetProfile";
import {
  coordinate,
  fmtKm,
  nearestTarget,
  planets,
  targetPoint,
  type PlanetId,
  type SurfacePoint,
} from "@/lib/planets";
import { api, type Health, type Region, type RegistryResponse, type Target } from "@/lib/api";
import { parseView, viewToUrl, type Screen, type ViewState } from "@/lib/urlState";

type Catalog = { targets: Target[]; regions: Region[]; registry: RegistryResponse | null };

const STEPS = ["Choose a world", "Pick a target", "Compare with Earth"] as const;
const PINNED_LIMIT = 12;

function customPoint(v: ViewState): SurfacePoint | null {
  return v.lat !== null && v.lon !== null ? { lat: v.lat, lon: v.lon } : null;
}

export default function Explorer({ initial }: { initial: ViewState }) {
  const [screen, setScreen] = useState<Screen>(initial.screen);
  const [planetId, setPlanetId] = useState<PlanetId>(initial.body);
  // A chosen point, or a target id from the URL waiting for the catalog to load.
  const [pointState, setPointState] = useState<SurfacePoint | null>(() => customPoint(initial));
  const [pendingTarget, setPendingTarget] = useState<string | null>(initial.target);
  const [topK, setTopK] = useState(initial.topK);
  const [pick, setPick] = useState<string | null>(initial.pick);
  const [zoom, setZoom] = useState(0);
  const [reset, setReset] = useState(0);
  const [grid, setGrid] = useState(false);
  const [help, setHelp] = useState(false);
  const [full, setFull] = useState(false);
  const [manual, setManual] = useState(false);
  const [coordError, setCoordError] = useState("");
  const [query, setQuery] = useState("");
  const [regionChoice, setRegionChoice] = useState<string | null>(initial.region);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [attempt, setAttempt] = useState(0);
  const planet = planets[planetId];

  useEffect(() => {
    let live = true;
    Promise.all([api.targets(), api.regions(), api.registry().catch(() => null)])
      .then(([targets, regions, registry]) => {
        if (!live) return;
        setCatalog({ targets, regions, registry });
        setCatalogError(null);
      })
      .catch((e: unknown) => {
        if (live) setCatalogError(e instanceof Error ? e.message : String(e));
      });
    api
      .health()
      .then((h) => live && setHealth(h))
      .catch(() => live && setHealth(null));
    return () => {
      live = false;
    };
  }, [attempt]);

  const retryCatalog = useCallback(() => setAttempt((n) => n + 1), []);

  // Mission guide: focus trap, Escape to close, scroll lock.
  useEffect(() => {
    if (!help) return;
    const previous = document.activeElement as HTMLElement | null;
    const buttons = document.querySelectorAll<HTMLButtonElement>(".guide-modal button");
    buttons[0]?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setHelp(false);
      if (event.key === "Tab") {
        if (event.shiftKey && document.activeElement === buttons[0]) {
          event.preventDefault();
          buttons[buttons.length - 1]?.focus();
        }
        if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) {
          event.preventDefault();
          buttons[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", keydown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", keydown);
      document.body.style.overflow = previousOverflow;
      previous?.focus();
    };
  }, [help]);

  const bodyTargets = useMemo(
    () => (catalog?.targets ?? []).filter((t) => t.body === planetId),
    [catalog, planetId],
  );
  const pendingMatch = pendingTarget ? bodyTargets.find((t) => t.id === pendingTarget) : null;
  const point: SurfacePoint | null =
    pointState ?? (pendingMatch ? targetPoint(pendingMatch) : null);

  function setPoint(p: SurfacePoint | null) {
    setPointState(p);
    setPendingTarget(null);
    setPick(null);
  }

  // Keep the URL in step with the view. A new screen adds a history entry (Back works);
  // other changes replace the current one.
  const view: ViewState = {
    screen,
    body: planetId,
    target: point?.targetId ?? (pointState ? null : pendingTarget),
    lat: point && !point.targetId ? point.lat : null,
    lon: point && !point.targetId ? point.lon : null,
    region: regionChoice,
    topK,
    pick,
  };
  const url = viewToUrl(view);
  const lastScreen = useRef(screen);
  useEffect(() => {
    const here = window.location.pathname + window.location.search;
    if (url !== here) {
      if (lastScreen.current !== screen) window.history.pushState(null, "", url);
      else window.history.replaceState(null, "", url);
    }
    lastScreen.current = screen;
  }, [url, screen]);

  useEffect(() => {
    const onPop = () => {
      const v = parseView(Object.fromEntries(new URLSearchParams(window.location.search)));
      lastScreen.current = v.screen;
      setScreen(v.screen);
      setPlanetId(v.body);
      setPointState(customPoint(v));
      setPendingTarget(v.target);
      setRegionChoice(v.region);
      setTopK(v.topK);
      setPick(v.pick);
      setFull(false);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  // Without a query: prepared sites and any target that has a profile. With one: IAU names too.
  const listed = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q)
      return bodyTargets
        .filter((t) => [t.name, t.id, t.feature_type ?? ""].join(" ").toLowerCase().includes(q))
        .slice(0, 40);
    return bodyTargets
      .filter((t) => t.origin !== "iau_gazetteer" || t.profile_status === "ready")
      .sort((a, b) => Number(b.profile_status === "ready") - Number(a.profile_status === "ready"));
  }, [bodyTargets, query]);
  const pins = useMemo(
    () =>
      bodyTargets
        .filter((t) => t.origin !== "iau_gazetteer" || t.profile_status === "ready")
        .slice(0, PINNED_LIMIT)
        .map(targetPoint),
    [bodyTargets],
  );

  const target = point?.targetId
    ? (bodyTargets.find((t) => t.id === point.targetId) ?? null)
    : null;
  const nearest = point && !point.targetId ? nearestTarget(point, bodyTargets, planet) : null;
  const regions = useMemo(() => catalog?.regions ?? [], [catalog]);
  // Default region: the first with features at the target's scale.
  const region = useMemo(() => {
    const chosen = regions.find((r) => r.id === regionChoice);
    if (chosen) return chosen;
    const scale = String(target?.comparison.scale_m ?? "");
    return regions.find((r) => r.scales[scale]?.status === "ready") ?? regions[0] ?? null;
  }, [regions, regionChoice, target]);
  const scaleStatus = target && region ? region.scales[String(target.comparison.scale_m)] : null;
  const blocker = !point
    ? "Select a target to continue"
    : !target
      ? "Only prepared targets can be scored. Use the nearest one below."
      : target.profile_status !== "ready"
        ? `No terrain profile yet. Run: pipeline target --target ${target.id}`
        : !region
          ? "No Earth region is loaded"
          : scaleStatus?.status === "not_ready"
            ? `No ${target.comparison.scale_m} m Earth features for ${region.name} yet`
            : null;

  function explore(id: PlanetId) {
    setPlanetId(id);
    setPoint(null);
    setZoom(0);
    setGrid(false);
    setQuery("");
    setScreen("explore");
    setManual(false);
  }
  const step = screen === "select" ? 0 : screen === "explore" ? 1 : 2;

  return (
    <div className={`app ${full ? "expanded-view" : ""}`}>
      <header className="site-header">
        <button
          className="brand"
          onClick={() => {
            setScreen("select");
            setFull(false);
          }}
          aria-label="Field Beyond home"
        >
          <span className="brand-symbol">
            <Orbit size={29} strokeWidth={1.35} />
          </span>
          <span>
            FIELD<span className="brand-light">BEYOND</span>
            <small>EARTH ANALOG EXPLORER</small>
          </span>
        </button>
        <nav className="workflow" aria-label="Exploration progress">
          {STEPS.map((label, i) => (
            <div key={label} className={`workflow-step ${i === step ? "current" : ""}`}>
              <span className="step-number">{i < step ? <Check size={11} /> : `0${i + 1}`}</span>
              <span>{label}</span>
              {i < 2 && <ChevronRight className="step-chevron" size={13} />}
            </div>
          ))}
        </nav>
        <div className="header-actions">
          <Link className="help-button" href="/about">
            <BookOpen size={16} />
            <span>Method &amp; credits</span>
          </Link>
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={16} />
            <span>Mission guide</span>
          </button>
        </div>
      </header>

      {screen === "select" ? (
        <main className="selection-page">
          <section className="intro">
            <div className="eyebrow">
              <span /> TERRAIN, MEASURED ACROSS WORLDS
            </div>
            <h1>
              Other worlds.<span> Familiar ground.</span>
            </h1>
            <p>
              Pick a place on the Moon or Mars. See which Earth terrain measures most like it.
              <br className="desktop-break" /> Slope, relief and roughness, compared window by
              window.
            </p>
          </section>
          <section className="planet-selection" aria-label="Choose a planet">
            {(["moon", "mars"] as PlanetId[]).map((id, index) => {
              const p = planets[id];
              const count = catalog?.targets.filter(
                (t) => t.body === id && t.profile_status === "ready",
              ).length;
              return (
                <article key={id} className={`planet-card planet-${id}`}>
                  <div className="planet-topline">
                    <span className="small-label">
                      0{index + 1} /{" "}
                      {id === "moon" ? "EARTH’S NATURAL SATELLITE" : "THE TERRESTRIAL PLANET"}
                    </span>
                    <span className={`planet-status ${id}`}>
                      <i /> {count === undefined ? "—" : count} SCORED TARGET
                      {count === 1 ? "" : "S"}
                    </span>
                  </div>
                  <div className="planet-stage">
                    <div className="orbital-ring ring-one" />
                    <div className="orbital-ring ring-two" />
                    <Globe planet={p} preview />
                    <span className="planet-annotation">
                      <span /> {p.distance}
                      <small>{p.distanceNote}</small>
                    </span>
                    <span className="stage-cross cross-one">+</span>
                    <span className="stage-cross cross-two">+</span>
                  </div>
                  <div className="planet-card-content">
                    <div className="planet-heading">
                      <div>
                        <span className="planet-subtitle">{p.subtitle}</span>
                        <h2>
                          {p.name}
                          <span>{id === "moon" ? "Luna" : "Sol IV"}</span>
                        </h2>
                      </div>
                      <button
                        className={`explore-arrow ${id === "moon" ? "accent" : ""}`}
                        onClick={() => explore(id)}
                        aria-label={`Explore ${p.name}`}
                      >
                        <ArrowRight size={24} strokeWidth={1.5} className="-rotate-45" />
                      </button>
                    </div>
                    <p>{p.description}</p>
                    <div className="planet-facts">
                      <div>
                        <span>DIAMETER</span>
                        <strong>
                          {p.diameter} <small>km</small>
                        </strong>
                      </div>
                      <div>
                        <span>SURFACE GRAVITY</span>
                        <strong>
                          {p.gravity} <small>m/s²</small>
                        </strong>
                      </div>
                      <button className="explore-text" onClick={() => explore(id)}>
                        Explore {p.name} <ArrowRight size={15} />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
          <section className="journey-strip">
            <div className="journey-title">
              <span className="mini-orbit">
                <Sparkles size={18} />
              </span>
              <div>
                <strong>Every match comes with its evidence.</strong>
                <span>Both values, the tolerance and the main mismatch, feature by feature.</span>
              </div>
            </div>
            <div className="journey-steps">
              <span>
                <Globe2 size={16} /> Choose a world
              </span>
              <ArrowRight size={13} />
              <span>
                <MapPin size={16} /> Pick a target
              </span>
              <ArrowRight size={13} />
              <span>
                <Earth size={16} /> Compare with Earth
              </span>
            </div>
          </section>
          <footer className="landing-footer">
            <ApiStatus health={health} error={catalogError} onRetry={retryCatalog} />
            <span>
              <i /> NASA Space Apps Challenge <span className="footer-separator">/</span> Project
              prototype
            </span>
            <a
              className="texture-credit"
              href="https://www.solarsystemscope.com/textures/"
              target="_blank"
              rel="noreferrer"
            >
              Textures: Solar System Scope · CC BY 4.0
            </a>
          </footer>
        </main>
      ) : screen === "explore" ? (
        <main className="explore-page">
          <div className="explore-topbar">
            <button
              className="text-button"
              onClick={() => {
                setScreen("select");
                setFull(false);
              }}
            >
              <ArrowLeft size={15} /> All worlds
            </button>
            <div className="planet-switch" aria-label="Select planet">
              {(["moon", "mars"] as PlanetId[]).map((id) => (
                <button
                  className={planetId === id ? "active" : ""}
                  key={id}
                  onClick={() => explore(id)}
                >
                  <span className={`tiny-planet ${id}`} />
                  {planets[id].name}
                </button>
              ))}
            </div>
            <span className="topbar-status">
              <i /> EXPLORATION MODE
            </span>
          </div>
          <div className="dashboard">
            <aside className="left-sidebar">
              <div className="eyebrow">
                <span /> {planet.subtitle}
              </div>
              <h1>
                {planet.name}
                <span>{planet.altName}</span>
              </h1>
              <p className="sidebar-intro">
                Pick a prepared target, or click the globe
                <br />
                and use the nearest one.
              </p>
              <div className="sidebar-divider" />
              <div className="section-title">
                <h2>Targets</h2>
                <span>{String(listed.length).padStart(2, "0")}</span>
              </div>
              <label className="target-search">
                <Search size={13} />
                <input
                  type="search"
                  value={query}
                  placeholder="Find an IAU name…"
                  aria-label="Find a target by IAU name"
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              {catalogError ? (
                <div className="inline-alert" role="alert">
                  <TriangleAlert size={14} />
                  <div>
                    <strong>The API is not reachable.</strong>
                    <p>{catalogError}</p>
                    <button className="text-button" onClick={retryCatalog}>
                      Retry <RotateCcw size={11} />
                    </button>
                  </div>
                </div>
              ) : !catalog ? (
                <p className="section-description">Loading targets…</p>
              ) : listed.length === 0 ? (
                <p className="section-description">
                  {query
                    ? "No target with that name."
                    : `No ${planet.name} targets are loaded. Run the pipeline (or seed-fake).`}
                </p>
              ) : (
                <div className="location-list">
                  {listed.map((t, i) => (
                    <button
                      key={t.id}
                      className={`location-item ${point?.targetId === t.id ? "selected" : ""}`}
                      onClick={() => {
                        setPoint(targetPoint(t));
                        setManual(false);
                      }}
                    >
                      <span className="location-number">{String(i + 1).padStart(2, "0")}</span>
                      <div>
                        <strong>{t.name}</strong>
                        <small>
                          {coordinate(t.comparison.center_lat)} ·{" "}
                          {coordinate(t.comparison.center_lon, false)}
                        </small>
                        <span className="tag-row">
                          <span className="mini-tag">{t.comparison.scale_m} m</span>
                          {t.origin === "iau_gazetteer" && <span className="mini-tag">IAU</span>}
                          {t.data_status === "synthetic" && (
                            <span className="mini-tag warn">synthetic</span>
                          )}
                          {t.profile_status !== "ready" && (
                            <span className="mini-tag dim">no profile</span>
                          )}
                        </span>
                      </div>
                      <ChevronRight size={14} />
                    </button>
                  ))}
                </div>
              )}
              <div className="custom-location-note">
                <Crosshair size={19} />
                <div>
                  <strong>Any point on the surface.</strong>
                  <p>Click the globe or enter coordinates. The nearest scored target is offered.</p>
                  <button
                    className="text-button"
                    onClick={() => {
                      setManual(!manual);
                      setCoordError("");
                    }}
                  >
                    Enter coordinates <ArrowRight size={12} />
                  </button>
                </div>
              </div>
              <div className="dataset-note">
                <Layers3 size={14} />
                <span>
                  Elevation source <strong>{planet.dataset}</strong>
                </span>
              </div>
            </aside>
            <section className="globe-workspace">
              <div className="workspace-topline">
                <span>
                  <span className="live-dot" /> 3D SURFACE EXPLORER
                </span>
                <span>{planet.name.toUpperCase()} / GLOBAL VIEW</span>
              </div>
              <div className="explore-orbit orbit-a" />
              <div className="explore-orbit orbit-b" />
              <Globe
                key={planetId}
                planet={planet}
                locations={pins}
                selected={point}
                onSelect={(p) => {
                  setPoint(p);
                  setManual(false);
                }}
                zoom={zoom}
                reset={reset}
                grid={grid}
              />
              <div className="globe-tools">
                <button
                  aria-label="Zoom in"
                  title="Zoom in"
                  onClick={() => setZoom((value) => Math.max(0, value) + 1)}
                >
                  <Plus size={18} />
                </button>
                <button
                  aria-label="Zoom out"
                  title="Zoom out"
                  onClick={() => setZoom((value) => Math.min(0, value) - 1)}
                >
                  <Minus size={18} />
                </button>
                <span />
                <button
                  aria-label="Reset globe view"
                  title="Reset view"
                  onClick={() => setReset((value) => value + 1)}
                >
                  <RotateCcw size={16} />
                </button>
                <button
                  className={grid ? "active" : ""}
                  aria-label="Toggle surface grid"
                  aria-pressed={grid}
                  title="Toggle surface grid"
                  onClick={() => setGrid(!grid)}
                >
                  <Globe2 size={17} />
                </button>
                <button
                  aria-label={full ? "Exit expanded view" : "Expand globe"}
                  title="Expand globe"
                  onClick={() => setFull(!full)}
                >
                  <Maximize2 size={16} />
                </button>
              </div>
              <div className="workspace-bottom">
                <div>
                  <span className="axis-label">N</span>
                  <span className="compass-line" />
                  <span>ILLUSTRATIVE TEXTURE · NOT ELEVATION</span>
                </div>
                <span>
                  <Move size={13} /> Drag to rotate <i /> Scroll to zoom <i /> Click to select
                </span>
              </div>
              <div className="selection-tip">
                <MousePointer2 size={13} />{" "}
                {point ? "Click another point to update your selection" : "Where will you begin?"}
              </div>
            </section>
            <aside className="right-sidebar">
              <div className="section-title">
                <h2>Your target</h2>
                <Crosshair size={17} />
              </div>
              <span className={`selection-status ${point ? "is-selected" : ""}`}>
                <i /> {point ? "SURFACE POINT SELECTED" : "AWAITING SELECTION"}
              </span>
              {point ? (
                <>
                  <div className="target-name">
                    <span className="target-type">
                      {point.targetId ? "PREPARED TARGET" : "CUSTOM COORDINATES"}
                    </span>
                    <h3>{point.name || "Custom point"}</h3>
                    <p>
                      {point.description ||
                        "Your own point. The search scores prepared targets only, so the nearest one is offered below."}
                    </p>
                  </div>
                  <div className="coordinate-box">
                    <div>
                      <span>LATITUDE</span>
                      <strong>{coordinate(point.lat)}</strong>
                    </div>
                    <div>
                      <span>LONGITUDE</span>
                      <strong>{coordinate(point.lon, false)}</strong>
                    </div>
                    <span className="coordinate-system">Planetocentric · East-positive</span>
                  </div>
                  {target?.profile_status === "ready" && <TargetProfile targetId={target.id} />}
                  {nearest && (
                    <div className="nearest-target">
                      <span>NEAREST SCORED TARGET</span>
                      <strong>{nearest.target.name}</strong>
                      <small>
                        {fmtKm(nearest.distanceM)} away on {planet.name} ({planet.radiusM / 1000} km
                        radius)
                      </small>
                      <button
                        className="secondary"
                        onClick={() => setPoint(targetPoint(nearest.target))}
                      >
                        Use {nearest.target.name} <Check size={13} />
                      </button>
                    </div>
                  )}
                  <button className="text-button clear-selection" onClick={() => setPoint(null)}>
                    <X size={12} /> Clear selection
                  </button>
                </>
              ) : (
                <div className="target-empty">
                  <div className="target-reticle">
                    <LocateFixed size={32} strokeWidth={1} />
                  </div>
                  <h3>Find your starting point.</h3>
                  <p>Select a target from the list or click anywhere on the globe.</p>
                  <div className="empty-coordinate">
                    <span>
                      LATITUDE <b>—</b>
                    </span>
                    <span>
                      LONGITUDE <b>—</b>
                    </span>
                  </div>
                </div>
              )}
              {manual && (
                <form
                  className="manual-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const form = new FormData(event.currentTarget);
                    const lat = Number(form.get("latitude"));
                    const lon = Number(form.get("longitude"));
                    if (
                      !Number.isFinite(lat) ||
                      !Number.isFinite(lon) ||
                      lat < -90 ||
                      lat > 90 ||
                      lon < -180 ||
                      lon > 180
                    ) {
                      setCoordError("Latitude: −90 to 90. Longitude: −180 to 180.");
                      return;
                    }
                    setPoint({ lat, lon });
                    setCoordError("");
                    setManual(false);
                  }}
                >
                  <label>
                    Latitude
                    <input
                      name="latitude"
                      aria-label="Latitude"
                      autoFocus
                      type="number"
                      step="any"
                      min="-90"
                      max="90"
                      placeholder="−90 to 90"
                      required
                    />
                  </label>
                  <label>
                    Longitude
                    <input
                      name="longitude"
                      aria-label="Longitude"
                      type="number"
                      step="any"
                      min="-180"
                      max="180"
                      placeholder="−180 to 180"
                      required
                    />
                  </label>
                  {coordError && <p role="alert">{coordError}</p>}
                  <button className="secondary" type="submit">
                    Set surface point <Check size={13} />
                  </button>
                </form>
              )}
              <div className="compare-section">
                <div className="compare-description">
                  <Earth size={19} />
                  <div>
                    <strong>Earth search region</strong>
                    <p>{region?.description ?? "Regions load from the API."}</p>
                  </div>
                </div>
                <select
                  className="region-select"
                  aria-label="Earth search region"
                  value={region?.id ?? ""}
                  onChange={(e) => {
                    setRegionChoice(e.target.value);
                    setPick(null);
                  }}
                  disabled={!regions.length}
                >
                  {regions.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.role})
                    </option>
                  ))}
                </select>
                <button
                  className="primary compare-button"
                  disabled={blocker !== null}
                  onClick={() => {
                    setScreen("compare");
                    setFull(false);
                  }}
                >
                  Compare with Earth <ArrowRight size={17} />
                </button>
                <span className="button-note">
                  {blocker ?? "Compares slope distribution, relief and roughness"}
                </span>
              </div>
              <div className="science-note">
                <span className="mini-dot" /> TERRAIN, NOT APPEARANCE
                <p>Matches use measured terrain features, not how a place looks in imagery.</p>
              </div>
            </aside>
          </div>
          <footer className="explore-footer">
            <span>
              <span className="live-dot" /> FIELD BEYOND <span className="muted">/</span> SURFACE
              EXPLORATION
            </span>
            <ApiStatus health={health} error={catalogError} onRetry={retryCatalog} />
          </footer>
        </main>
      ) : (
        <>
          {target && region && target.profile_status === "ready" ? (
            <Comparison
              planet={planet}
              target={target}
              region={region}
              regions={regions}
              onRegionChange={(id) => {
                setRegionChoice(id);
                setPick(null);
              }}
              topK={topK}
              onTopKChange={(k) => {
                setTopK(k);
                setPick(null);
              }}
              pick={pick}
              onPick={setPick}
              registry={catalog?.registry ?? null}
              onBack={() => setScreen("explore")}
            />
          ) : (
            // Opened from a link before the catalog loaded, or for a target that cannot be scored.
            <main className="comparison-page">
              <div className="empty-results" role={catalogError ? "alert" : "status"}>
                <div className="empty-icon">
                  {catalog || catalogError ? (
                    <TriangleAlert size={28} />
                  ) : (
                    <LoaderCircle className="spin" size={28} />
                  )}
                </div>
                <h3>
                  {catalogError
                    ? "The API is not reachable."
                    : !catalog
                      ? "Loading the search…"
                      : "This link does not point to a target that can be scored."}
                </h3>
                {(catalog || catalogError) && (
                  <button className="secondary retry" onClick={() => setScreen("explore")}>
                    <ArrowLeft size={13} /> Back to exploration
                  </button>
                )}
              </div>
            </main>
          )}
        </>
      )}

      {help && (
        <div className="modal-backdrop" onClick={() => setHelp(false)}>
          <section
            className="guide-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Mission guide"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="modal-close"
              onClick={() => setHelp(false)}
              aria-label="Close mission guide"
            >
              <X size={19} />
            </button>
            <span className="eyebrow">
              <Orbit size={16} /> HOW IT WORKS
            </span>
            <h2>
              Across worlds.
              <br />
              Through terrain.
            </h2>
            <p>
              Field Beyond looks for Earth places whose terrain measurements resemble a chosen
              target on the Moon or Mars.
            </p>
            <ol>
              <li>
                <Globe2 />
                <div>
                  <strong>Choose a world</strong>
                  <span>The Moon (60 m pixels) or Mars (200 m pixels).</span>
                </div>
              </li>
              <li>
                <Crosshair />
                <div>
                  <strong>Pick a target</strong>
                  <span>
                    Choose a prepared target, search IAU names, or click the globe and use the
                    nearest scored target.
                  </span>
                </div>
              </li>
              <li>
                <Earth />
                <div>
                  <strong>Compare with Earth</strong>
                  <span>
                    Slope distribution, relief and roughness are compared with 10 km Earth windows
                    in the chosen region.
                  </span>
                </div>
              </li>
            </ol>
            <div className="guide-disclaimer">
              Scores are configured similarity (terrain-v1), not probability. A place that is not in
              the checked registry is labelled &ldquo;not in checked records&rdquo;, not a
              discovery.
            </div>
            <button className="primary" onClick={() => setHelp(false)}>
              Let’s explore <ArrowRight size={16} />
            </button>
          </section>
        </div>
      )}
    </div>
  );
}

function ApiStatus({
  health,
  error,
  onRetry,
}: {
  health: Health | null;
  error: string | null;
  onRetry: () => void;
}) {
  if (error)
    return (
      <span className="api-status down">
        <i /> API not reachable ·{" "}
        <button className="text-button" onClick={onRetry}>
          retry
        </button>
      </span>
    );
  if (!health)
    return (
      <span className="api-status">
        <i /> Connecting to API…
      </span>
    );
  return (
    <span className={`api-status ${health.status === "ok" ? "up" : "down"}`}>
      <i /> API {health.status} · {health.store} store · code {health.code_version.slice(0, 7)} · 10
      km windows
    </span>
  );
}
