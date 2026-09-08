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
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import * as THREE from "three";
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

const STAGE_BACKGROUND = "#050a0e";
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
      <directionalLight position={[2.5, 3, 3]} intensity={2.2} color="#fff1dc" />
      <directionalLight position={[-3, 1, 2.5]} intensity={0.7} color="#9fd3c7" />
      <directionalLight position={[0, 3, -4]} intensity={1.8} color="#4fb3a5" />
    </>
  );
}

const SKIN = "#5f7385";
const SKIN_DARK = "#3d4d5c";
const EYE = "#4fb3a5";

function PlaceholderHead({ driver, onRigInfo }: { driver: AvatarDriver; onRigInfo?: (info: RigInfo) => void }) {
  const tick = useAvatarWeights(driver);
  const posture = usePosture(driver.state);
  const root = useRef<THREE.Group>(null);
  const jaw = useRef<THREE.Group>(null);
  const lidLeft = useRef<THREE.Group>(null);
  const lidRight = useRef<THREE.Group>(null);
  const lips = useRef<THREE.Mesh>(null);
  const browLeft = useRef<THREE.Mesh>(null);
  const browRight = useRef<THREE.Mesh>(null);
  const eyeLeft = useRef<THREE.MeshStandardMaterial>(null);
  const eyeRight = useRef<THREE.MeshStandardMaterial>(null);

  useEffect(() => {
    onRigInfo?.({ source: "placeholder", meshes: 0, matched: 0 });
  }, [onRigInfo]);

  useFrame(({ clock }, delta) => {
    const elapsed = clock.elapsedTime;
    const { smoothed: w } = tick(elapsed, delta);
    const { glow } = posture(root.current, elapsed, delta);

    if (jaw.current) jaw.current.rotation.x = (w.jawOpen ?? 0) * 0.42;
    if (lidLeft.current) lidLeft.current.rotation.x = (w.eyeBlinkLeft ?? 0) * (Math.PI / 2);
    if (lidRight.current) lidRight.current.rotation.x = (w.eyeBlinkRight ?? 0) * (Math.PI / 2);
    if (lips.current) {
      const funnel = w.mouthFunnel ?? 0;
      const pucker = w.mouthPucker ?? 0;
      const open = w.jawOpen ?? 0;
      lips.current.scale.set(
        1 - 0.35 * pucker - 0.2 * funnel,
        1 + 0.5 * funnel + 0.3 * pucker + 0.7 * open,
        1 + 0.5 * funnel + 0.6 * pucker,
      );
    }
    const innerUp = w.browInnerUp ?? 0;
    if (browLeft.current) {
      browLeft.current.position.y = 0.5 + innerUp * 0.1 - (w.browDownLeft ?? 0) * 0.06;
      browLeft.current.rotation.z = 0.12 + innerUp * 0.25;
    }
    if (browRight.current) {
      browRight.current.position.y = 0.5 + innerUp * 0.1 - (w.browDownRight ?? 0) * 0.06;
      browRight.current.rotation.z = -0.12 - innerUp * 0.25;
    }
    if (eyeLeft.current) eyeLeft.current.emissiveIntensity = glow;
    if (eyeRight.current) eyeRight.current.emissiveIntensity = glow;
  });

  return (
    <group ref={root} position={[0, -0.05, 0]}>
      {/* Cranium */}
      <mesh position={[0, 0.15, 0]} scale={[1, 1.12, 1]}>
        <sphereGeometry args={[0.72, 48, 32]} />
        <meshStandardMaterial color={SKIN} roughness={0.55} metalness={0.25} />
      </mesh>

      {/* Lower jaw, hinged near the ear line */}
      <group ref={jaw} position={[0, -0.05, -0.15]}>
        <mesh position={[0, -0.42, 0.28]} scale={[0.95, 0.55, 0.9]}>
          <sphereGeometry args={[0.5, 32, 16]} />
          <meshStandardMaterial color={SKIN} roughness={0.55} metalness={0.25} />
        </mesh>
      </group>

      {/* Eyes and their upper lids */}
      {[-1, 1].map((side) => (
        <group key={side} position={[side * 0.27, 0.28, 0.62]}>
          <mesh>
            <sphereGeometry args={[0.1, 24, 16]} />
            <meshStandardMaterial
              ref={side < 0 ? eyeLeft : eyeRight}
              color="#0b1418"
              emissive={EYE}
              emissiveIntensity={0.7}
              roughness={0.2}
            />
          </mesh>
          <group ref={side < 0 ? lidLeft : lidRight}>
            <mesh>
              <sphereGeometry args={[0.118, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
              <meshStandardMaterial color={SKIN_DARK} roughness={0.6} side={THREE.DoubleSide} />
            </mesh>
          </group>
        </group>
      ))}

      {/* Brows */}
      <mesh ref={browLeft} position={[-0.27, 0.5, 0.6]} rotation={[0, 0, 0.12]}>
        <boxGeometry args={[0.22, 0.035, 0.06]} />
        <meshStandardMaterial color="#1f2b35" roughness={0.8} />
      </mesh>
      <mesh ref={browRight} position={[0.27, 0.5, 0.6]} rotation={[0, 0, -0.12]}>
        <boxGeometry args={[0.22, 0.035, 0.06]} />
        <meshStandardMaterial color="#1f2b35" roughness={0.8} />
      </mesh>

      {/* Lips */}
      <mesh ref={lips} position={[0, -0.12, 0.68]}>
        <torusGeometry args={[0.17, 0.045, 12, 32]} />
        <meshStandardMaterial color="#7a5c62" roughness={0.5} />
      </mesh>

      {/* Neck and shoulders, so the lean reads as posture */}
      <mesh position={[0, -0.85, -0.05]}>
        <cylinderGeometry args={[0.28, 0.32, 0.5, 24]} />
        <meshStandardMaterial color={SKIN_DARK} roughness={0.7} />
      </mesh>
      <mesh position={[0, -1.25, -0.1]}>
        <boxGeometry args={[1.9, 0.35, 0.7]} />
        <meshStandardMaterial color="#1a2731" roughness={0.9} />
      </mesh>
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
