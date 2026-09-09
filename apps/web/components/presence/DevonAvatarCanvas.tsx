"use client";

/**
 * The avatar stage: a react-three-fiber Canvas on a dark set matching the
 * command center, lit three-point, camera at head height.
 *
 * The rig inside is one of two things. With a modelUrl, GltfRig loads the
 * GLB through three's own GLTFLoader, finds every mesh that carries a
 * morphTargetDictionary, and each frame writes the sampled ARKit weights
 * into morphTargetInfluences with a lerp against the previous value. Without
 * one, PlaceholderHead is a procedural head built here in code (sphere head,
 * hinged jaw, hemisphere eyelids, torus lips, bar brows) driven by the same
 * weights, so the frame pipeline is demonstrable end to end without any
 * shipped likeness.
 *
 * Both rigs sample the shared FrameBuffer at the audio clock inside their
 * own useFrame, through useAvatarWeights. Only one rig is mounted at a time.
 *
 * UNVERIFIED: no real GLB has been loaded in this build, so the morph names
 * a given asset exposes, and the auto framing, are untested. The HUD shows
 * how many of the 52 names matched once a model loads.
 */

import { Component, Suspense, useCallback, useEffect, useMemo, useRef, type ReactNode } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import {
  DEFAULT_GRID,
  applyField,
  buildGridEdges,
  buildGridPlane,
  buildMotes,
  vertexCount,
  writeDepthColors,
} from "@/components/presence/face-mesh";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { lerpWeights, type FrameBuffer } from "@/lib/presence/frame-buffer";
import { ARKIT_BLENDSHAPES, type PresenceState, type Weights } from "@/lib/presence/protocol";

export type RenderTelemetry = {
  /** How far the oldest due frame trailed the clock before sampling. */
  behindMs: number;
  /** Age on the audio clock of the frame on the face. */
  faceAgeMs: number;
  fps: number;
  /** A streamed frame is driving the face right now. */
  frameShown: boolean;
};

export type RigInfo = {
  source: "placeholder" | "gltf";
  meshes: number;
  /** ARKit names found in at least one morph dictionary. */
  matched: number;
};

export type AvatarDriver = {
  buffer: FrameBuffer;
  /** Audio clock in ms on the frame timeline, or null when nothing plays. */
  audioClockMs: () => number | null;
  /** Remote audio RMS 0..1 for the energy fallback; 0 when unknown. */
  audioLevel: () => number;
  state: PresenceState;
  /** Per frame lerp factor 0..1 toward the sampled weights. */
  smoothing: number;
  onTelemetry?: (telemetry: RenderTelemetry) => void;
};

const STAGE_BACKGROUND = "#04070d";
/** Lag tolerated before FrameBuffer.compress starts shedding detail. */
const COMPRESS_WINDOW_MS = 250;
/** After this long without a frame, the energy fallback drives the jaw. */
const FRAME_FRESH_MS = 400;
const TELEMETRY_INTERVAL_S = 0.25;
const BLINK_SECONDS = 0.14;

function useLatest<T>(value: T) {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref;
}

/**
 * Sampling shared by both rigs. Returns a tick() for the rig's useFrame that
 * yields the raw sampled target and the smoothed weights for this frame.
 */
function useAvatarWeights(driver: AvatarDriver) {
  const driverRef = useLatest(driver);
  const targetRef = useRef<Weights>({});
  const smoothedRef = useRef<Weights>({});
  const shownAtRef = useRef<number | null>(null);
  const fpsRef = useRef(60);
  const telemetryAtRef = useRef(0);
  const blinkRef = useRef({ nextAt: 2.5, startedAt: -1 });

  return useCallback((elapsed: number, delta: number) => {
    const d = driverRef.current;
    if (delta > 0) fpsRef.current = fpsRef.current * 0.9 + (1 / delta) * 0.1;

    const clock = d.audioClockMs();
    let behindMs = 0;
    let faceAgeMs = 0;
    let frameShown = false;

    if (clock !== null) {
      const oldest = d.buffer.frames[0];
      behindMs = oldest !== undefined && oldest.at_ms <= clock ? clock - oldest.at_ms : 0;
      d.buffer.compress(behindMs, COMPRESS_WINDOW_MS);
      const frame = d.buffer.sample(clock);
      if (frame !== null) {
        targetRef.current = frame.weights;
        shownAtRef.current = frame.at_ms;
      }
      if (shownAtRef.current !== null) {
        faceAgeMs = clock - shownAtRef.current;
        frameShown = faceAgeMs <= FRAME_FRESH_MS;
      }
      if (!frameShown) {
        // Audio is playing but no frame is fresh: let the energy move the jaw.
        const jaw = Math.min(1, d.audioLevel() * 6);
        targetRef.current = { ...targetRef.current, jawOpen: jaw };
      }
    } else {
      shownAtRef.current = null;
      if (Object.keys(targetRef.current).length > 0) targetRef.current = {};
    }

    smoothedRef.current = lerpWeights(smoothedRef.current, targetRef.current, d.smoothing);

    // A procedural blink whenever the stream is not closing the eyes itself.
    const blink = blinkRef.current;
    if (elapsed >= blink.nextAt) {
      blink.startedAt = elapsed;
      blink.nextAt = elapsed + 2.5 + Math.random() * 4;
    }
    const sinceBlink = elapsed - blink.startedAt;
    const blinkAmount =
      blink.startedAt >= 0 && sinceBlink < BLINK_SECONDS
        ? Math.sin((Math.PI * sinceBlink) / BLINK_SECONDS)
        : 0;
    let smoothed = smoothedRef.current;
    if (blinkAmount > (smoothed.eyeBlinkLeft ?? 0)) {
      smoothed = { ...smoothed, eyeBlinkLeft: blinkAmount, eyeBlinkRight: blinkAmount };
    }

    if (d.onTelemetry && elapsed - telemetryAtRef.current >= TELEMETRY_INTERVAL_S) {
      telemetryAtRef.current = elapsed;
      d.onTelemetry({ behindMs, faceAgeMs, fps: fpsRef.current, frameShown });
    }

    return { target: targetRef.current, smoothed };
  }, [driverRef]);
}

/** Idle breath, micro head motion, and the posture for each state. */
function usePosture(state: PresenceState) {
  const stateRef = useLatest(state);
  const leanRef = useRef(0);
  const glowRef = useRef(0.7);
  return useCallback(
    (root: THREE.Object3D | null, elapsed: number, delta: number) => {
      const s = stateRef.current;
      const step = Math.min(1, delta * 4);
      leanRef.current += ((s === "listening" ? 1 : 0) - leanRef.current) * step;
      const glowTarget =
        s === "listening" ? 2.4 : s === "thinking" ? 1.1 + 0.7 * Math.sin(elapsed * 4) : 0.7;
      glowRef.current += (glowTarget - glowRef.current) * Math.min(1, delta * 6);
      if (root) {
        root.rotation.x = 0.07 * leanRef.current + Math.sin(elapsed * 0.37) * 0.015;
        root.rotation.y = Math.sin(elapsed * 0.51) * 0.035;
        root.position.z = 0.12 * leanRef.current;
        root.position.y = Math.sin(elapsed * 1.1) * 0.008;
      }
      return { lean: leanRef.current, glow: glowRef.current };
    },
    [stateRef],
  );
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.22} />
      {/* Metal has nothing to reflect without an environment, and a
          meshStandardMaterial at metalness 0.95 with no IBL renders very nearly
          black. Measured on 2026-09-09: the first pass of this restyle shipped
          chrome that looked like dark grey plastic for exactly that reason.
          RoomEnvironment ships with three, so this costs no dependency. */}
      <MetalEnvironment />
      <directionalLight position={[2.5, 3, 3]} intensity={2.2} color="#fff1dc" />
      <directionalLight position={[-3, 1, 2.5]} intensity={0.7} color="#9fd3c7" />
      <directionalLight position={[0, 3, -4]} intensity={1.8} color="#4fb3a5" />
    </>
  );
}

/*
 * The placeholder's material language, ruled by Tee 2026-09-09 after he said the
 * old head looked like Mr Potato Head: chrome and gold plating over a dark core,
 * with a lit optic, taken from the cyborg concept he supplied.
 *
 * It is deliberately a MACHINE and not a face. The rigged DEVON avatar is to be
 * Tee's own likeness, which is an owned asset and its own arc. A placeholder that
 * wore somebody else's face, generated or otherwise, would be squatting on the
 * identity the real asset is meant to carry, and "identity owned, never rented"
 * has no exception path. So this reads as the shell that likeness will later sit
 * inside, rather than as a stand in for a person.
 */
/** Generates a PMREM environment once and hands it to the scene. */
function MetalEnvironment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const texture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const previous = scene.environment;
    scene.environment = texture;
    return () => {
      scene.environment = previous;
      texture.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
}

/**
 * A radial falloff sprite, generated once and shared.
 *
 * Additive blending alone does not make a glow: a capsule filled with a flat
 * colour renders a flat capsule however it is blended, which on 2026-09-09 put
 * two nested grey boxes around each eye. Light needs a gradient, so this is the
 * gradient, drawn into a canvas and used as an alpha map on a plane.
 */
function useGlowTexture() {
  return useMemo(() => {
    const size = 128;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.35, "rgba(255,255,255,0.38)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    return texture;
  }, []);
}

/** Bars in the mouth meter. Odd, so there is a true centre bar. */
const MOUTH_BARS = 11;
/** The cool interface accent, matching the estate's teal. */
const ACCENT = "#4fb3a5";
/** The lattice at rest, and where the face stands closest to the viewer. */
const DIM = [0.05, 0.13, 0.16] as const;
const LIT = [0.75, 1.0, 0.95] as const;

const PLATE = "#c6ced6";        // brushed chrome, the primary shell
const PLATE_DARK = "#404b56";   // shadowed plate and recesses
const GOLD = "#c9a227";         // machined accents, the concept's second metal
const CORE = "#2a3038";         // the dark body under the plating
const EYE = "#7fe9dc";          // the lit trace of the face itself
const SKIN = PLATE;             // kept so any older reference still resolves
const SKIN_DARK = PLATE_DARK;

function PlaceholderHead({ driver, onRigInfo }: { driver: AvatarDriver; onRigInfo?: (info: RigInfo) => void }) {
  const tick = useAvatarWeights(driver);
  const posture = usePosture(driver.state);
  const root = useRef<THREE.Group>(null);
  const glowTexture = useGlowTexture();

  const lineMaterial = useRef<THREE.LineBasicMaterial>(null);
  const pointMaterial = useRef<THREE.PointsMaterial>(null);
  const haloMaterial = useRef<THREE.MeshBasicMaterial>(null);
  const emerged = useRef(0);
  const motes = useRef<THREE.Points>(null);

  // The flat lattice, built once as a real BufferGeometry so the lines and the
  // vertices share one buffer: a node can then never disagree with the ends of
  // the lines that meet it.
  const { positions, colors, faceOnly, geom, moteGeom } = useMemo(() => {
    const flat = buildGridPlane(DEFAULT_GRID);
    const tint = new Float32Array(flat.length);
    const face = new Float32Array(vertexCount(DEFAULT_GRID));
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(flat, 3));
    g.setAttribute("color", new THREE.BufferAttribute(tint, 3));
    g.setIndex(new THREE.BufferAttribute(buildGridEdges(DEFAULT_GRID), 1));

    const motes = new THREE.BufferGeometry();
    motes.setAttribute("position", new THREE.BufferAttribute(buildMotes(220, DEFAULT_GRID), 3));
    return { positions: flat, colors: tint, faceOnly: face, geom: g, moteGeom: motes };
  }, []);

  useEffect(
    () => () => {
      geom.dispose();
      moteGeom.dispose();
    },
    [geom, moteGeom],
  );

  useEffect(() => {
    onRigInfo?.({ source: "placeholder", meshes: 0, matched: 0 });
  }, [onRigInfo]);

  useFrame(({ clock }, delta) => {
    const elapsed = clock.elapsedTime;
    const { smoothed: w } = tick(elapsed, delta);
    const { glow } = posture(root.current, elapsed, delta);

    // How far the face has come out of the sheet. Idle leaves a breath of
    // relief so the field is not dead flat; speaking pushes it fully out. The
    // approach is eased rather than snapped, because a face that pops is a jump
    // cut and a face that rises is presence.
    const target = 0.14 + 0.86 * glow;
    emerged.current += (target - emerged.current) * Math.min(1, delta * 3.2);

    applyField(
      positions,
      emerged.current,
      elapsed,
      {
        jawOpen: w.jawOpen ?? 0,
        mouthFunnel: w.mouthFunnel ?? 0,
        mouthPucker: w.mouthPucker ?? 0,
        blinkLeft: w.eyeBlinkLeft ?? 0,
        blinkRight: w.eyeBlinkRight ?? 0,
        browInnerUp: w.browInnerUp ?? 0,
      },
      DEFAULT_GRID,
      faceOnly,
    );
    // Depth written as light. The lattice is seen nearly face on, so relief
    // alone is close to invisible: without this the field renders as graph
    // paper, which is what it did before the aether landed.
    writeDepthColors(faceOnly, colors, DIM, LIT, 0.62);
    geom.attributes.position.needsUpdate = true;
    geom.attributes.color.needsUpdate = true;
    if (motes.current) {
      motes.current.rotation.z = elapsed * 0.012;
      motes.current.position.y = Math.sin(elapsed * 0.18) * 0.05;
    }

    if (lineMaterial.current) lineMaterial.current.opacity = 0.16 + 0.4 * emerged.current;
    if (pointMaterial.current) pointMaterial.current.opacity = 0.1 + 0.55 * emerged.current;
    if (haloMaterial.current) haloMaterial.current.opacity = 0.04 + 0.12 * glow;
  });

  return (
    <group ref={root} position={[0, 0.02, 0]} scale={0.62}>
      {/* The field behind everything, so the mesh sits in space. */}
      {glowTexture ? (
        <mesh position={[0, -0.02, -0.7]} scale={[2.6, 2.9, 1]}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial
            ref={haloMaterial}
            map={glowTexture}
            color={ACCENT}
            transparent
            opacity={0.1}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ) : null}

      {/* The lattice. */}
      <lineSegments geometry={geom}>
        <lineBasicMaterial
          ref={lineMaterial}
          vertexColors
          transparent
          opacity={0.5}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </lineSegments>

      {/* Motes: the aether itself, drifting in front of the lattice so the
          field has volume rather than being a single sheet. */}
      {glowTexture ? (
        <points ref={motes} geometry={moteGeom}>
          <pointsMaterial
            color={ACCENT}
            size={0.07}
            sizeAttenuation
            map={glowTexture}
            transparent
            opacity={0.3}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </points>
      ) : null}

      {/* Its vertices, brightening as the face emerges. */}
      <points geometry={geom}>
        <pointsMaterial
          ref={pointMaterial}
          vertexColors
          size={0.03}
          sizeAttenuation
          map={glowTexture ?? undefined}
          transparent
          opacity={0.5}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
    </group>
  );
}


type MorphMesh = THREE.Mesh & {
  morphTargetDictionary: { [key: string]: number };
  morphTargetInfluences: number[];
};

function collectMorphMeshes(scene: THREE.Object3D): MorphMesh[] {
  const meshes: MorphMesh[] = [];
  scene.traverse((object) => {
    const mesh = object as THREE.Mesh;
    if (mesh.isMesh && mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
      meshes.push(mesh as MorphMesh);
    }
  });
  return meshes;
}

function GltfRig({
  driver,
  modelUrl,
  onRigInfo,
}: {
  driver: AvatarDriver;
  modelUrl: string;
  onRigInfo?: (info: RigInfo) => void;
}) {
  const gltf = useLoader(GLTFLoader, modelUrl);
  const tick = useAvatarWeights(driver);
  const posture = usePosture(driver.state);
  const smoothingRef = useLatest(driver.smoothing);
  const root = useRef<THREE.Group>(null);

  const meshes = useMemo(() => collectMorphMeshes(gltf.scene), [gltf]);

  // Frame the head: prefer an object named like a head, else the box top.
  const offset = useMemo(() => {
    const scene = gltf.scene;
    scene.updateMatrixWorld(true);
    let head: THREE.Object3D | null = null;
    scene.traverse((object) => {
      if (head === null && /head/i.test(object.name)) head = object;
    });
    const target = new THREE.Vector3();
    if (head !== null) {
      (head as THREE.Object3D).getWorldPosition(target);
    } else {
      const box = new THREE.Box3().setFromObject(scene);
      box.getCenter(target);
      target.y = box.max.y - 0.15;
    }
    return new THREE.Vector3(-target.x, 0.15 - target.y, -target.z);
  }, [gltf]);

  useEffect(() => {
    const matched = ARKIT_BLENDSHAPES.filter((name) =>
      meshes.some((mesh) => mesh.morphTargetDictionary[name] !== undefined),
    ).length;
    onRigInfo?.({ source: "gltf", meshes: meshes.length, matched });
  }, [meshes, onRigInfo]);

  useFrame(({ clock }, delta) => {
    const elapsed = clock.elapsedTime;
    const { target } = tick(elapsed, delta);
    posture(root.current, elapsed, delta);
    const smoothing = smoothingRef.current;
    for (const mesh of meshes) {
      const dictionary = mesh.morphTargetDictionary;
      const influences = mesh.morphTargetInfluences;
      for (const name of ARKIT_BLENDSHAPES) {
        const index = dictionary[name];
        if (index === undefined) continue;
        influences[index] = THREE.MathUtils.lerp(influences[index] ?? 0, target[name] ?? 0, smoothing);
      }
    }
  });

  return (
    <group ref={root}>
      <primitive object={gltf.scene} position={[offset.x, offset.y, offset.z]} />
    </group>
  );
}

type BoundaryProps = {
  resetKey: string;
  fallback: ReactNode;
  onError: (message: string) => void;
  children: ReactNode;
};

class RigErrorBoundary extends Component<BoundaryProps, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    this.props.onError(error instanceof Error ? error.message : String(error));
  }

  componentDidUpdate(previous: BoundaryProps) {
    if (previous.resetKey !== this.props.resetKey && this.state.failed) {
      this.setState({ failed: false });
    }
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export type DevonAvatarCanvasProps = {
  driver: AvatarDriver;
  /** GLB to load; empty renders the procedural head. */
  modelUrl: string;
  onModelError?: (message: string) => void;
  onRigInfo?: (info: RigInfo) => void;
};

export function DevonAvatarCanvas({ driver, modelUrl, onModelError, onRigInfo }: DevonAvatarCanvasProps) {
  const handleError = useCallback(
    (message: string) => {
      // Drop the cached rejection so an edited URL can be retried.
      useLoader.clear(GLTFLoader, modelUrl);
      onModelError?.(message);
    },
    [modelUrl, onModelError],
  );

  const placeholder = <PlaceholderHead driver={driver} onRigInfo={onRigInfo} />;

  return (
    <Canvas
      frameloop="always"
      dpr={[1, 2]}
      camera={{ position: [0, 0.15, 3.1], fov: 32, near: 0.1, far: 50 }}
      gl={{ antialias: true, alpha: false }}
      style={{ background: STAGE_BACKGROUND }}
    >
      <color attach="background" args={[STAGE_BACKGROUND]} />
      <Lights />
      {modelUrl ? (
        <RigErrorBoundary resetKey={modelUrl} fallback={placeholder} onError={handleError}>
          <Suspense fallback={placeholder}>
            <GltfRig driver={driver} modelUrl={modelUrl} onRigInfo={onRigInfo} />
          </Suspense>
        </RigErrorBoundary>
      ) : (
        placeholder
      )}
    </Canvas>
  );
}
