/**
 * LivingAICoreCanvas.jsx — High-Performance 3D Living AI Core Canvas Component
 *
 * Real-time 3D representation of the AI's computational state:
 * - Multi-shell spherical neural network / artificial brain in an obsidian void
 * - Real-time state machine subscription
 * - Audio-reactive frequency modulation via AnalyserNode
 * - Dynamic geometry scaling from mathematical parameter calculation (1B - 1T)
 * - Orbit / Parallax controls, cinematic camera presets, and auto-drift
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { NeuralController } from './NeuralController';
import { neuralStateMachine, AI_STATES } from './neuralStateMachine';
import { PRESET_MODELS, calculateModelParameters, mapParametersToVisualSpecs } from './parameterCalculator';
import ModelInfoHUD from './ModelInfoHUD';
import ArchitectureInfoOverlay from './ArchitectureInfoOverlay';
import { Eye, Focus, Globe, Compass, ZoomIn, ZoomOut, RotateCcw, Volume2, Info } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function LivingAICoreCanvas({
  audioPlayEvent,
  userId = 'default_user',
  qualityTier = 'high',
  gestureOverride = null,
}) {
  const mountRef = useRef(null);
  const controllerRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const reqIdRef = useRef(null);

  const gestureOverrideRef = useRef(gestureOverride);
  useEffect(() => {
    gestureOverrideRef.current = gestureOverride;
  }, [gestureOverride]);

  const [activeState, setActiveState] = useState(AI_STATES.IDLE);
  const [stateProfile, setStateProfile] = useState(neuralStateMachine.getProfile());
  const [stateData, setStateData] = useState({});
  const [selectedModelKey, setSelectedModelKey] = useState('groq/compound');
  const [calculatedParams, setCalculatedParams] = useState(null);
  const [factCount, setFactCount] = useState(12);
  const [docChunkCount, setDocChunkCount] = useState(4);
  const [activeCameraPreset, setActiveCameraPreset] = useState('overview');
  const [audioLevel, setAudioLevel] = useState(0);
  const [showInspectOverlay, setShowInspectOverlay] = useState(false);

  // Audio Analyser ref
  const audioDataArrayRef = useRef(new Uint8Array(64));
  const cameraTargetPosRef = useRef(new THREE.Vector3(0, 1.2, 7.5));
  const isTransitioningPresetRef = useRef(false);
  const [autoSpin, setAutoSpin] = useState(true);

  // 1. Fetch Real Model Config & Memory Counts on Mount
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const factsRes = await fetch(`${API_BASE}/api/memory/facts/${userId}`);
        if (factsRes.ok) {
          const facts = await factsRes.json();
          if (Array.isArray(facts)) setFactCount(facts.length);
        }

        const docsRes = await fetch(`${API_BASE}/api/memory/documents/${userId}`);
        if (docsRes.ok) {
          const docs = await docsRes.json();
          if (Array.isArray(docs)) {
            const totalChunks = docs.reduce((acc, d) => acc + (d.chunk_count || 0), 0);
            setDocChunkCount(totalChunks);
          }
        }
      } catch (err) {
        console.warn('[LivingAICore] Metadata fetch fallback to defaults:', err);
      }
    };
    fetchMetadata();
  }, [userId]);

  // 2. Subscribe to Neural State Machine
  useEffect(() => {
    const unsubscribe = neuralStateMachine.subscribe((state, data, profile) => {
      setActiveState(state);
      setStateData(data);
      setStateProfile(profile);

      if (controllerRef.current) {
        controllerRef.current.setState(state, data, profile);
      }
    });
    return unsubscribe;
  }, []);

  // 3. Update Memory Cluster Counts in 3D Scene
  useEffect(() => {
    if (controllerRef.current) {
      controllerRef.current.updateMemoryCount(factCount, docChunkCount);
    }
  }, [factCount, docChunkCount]);

  // 4. Model Architecture Selection & Parameter Mapping
  useEffect(() => {
    const model = PRESET_MODELS[selectedModelKey] || PRESET_MODELS['groq/compound'];
    const calculated = calculateModelParameters(model);
    setCalculatedParams(calculated);

    if (sceneRef.current && cameraRef.current) {
      if (controllerRef.current) {
        controllerRef.current.dispose();
      }
      const specs = mapParametersToVisualSpecs(calculated, qualityTier);
      controllerRef.current = new NeuralController(sceneRef.current, cameraRef.current, specs);
      controllerRef.current.setState(activeState, stateData, stateProfile);
      controllerRef.current.updateMemoryCount(factCount, docChunkCount);
    }
  }, [selectedModelKey, qualityTier]);

  // Camera Presets Transition Handler
  const setCameraPreset = (preset) => {
    setActiveCameraPreset(preset);
    isTransitioningPresetRef.current = true;
    if (!cameraRef.current || !controlsRef.current) return;

    if (preset === 'core') {
      cameraTargetPosRef.current.set(0, 0.2, 3.4);
      controlsRef.current.target.set(0, 0, 0);
    } else if (preset === 'overview') {
      cameraTargetPosRef.current.set(0, 1.2, 7.5);
      controlsRef.current.target.set(0, 0, 0);
    } else if (preset === 'knowledge') {
      cameraTargetPosRef.current.set(4.5, 2.2, 5.2);
      controlsRef.current.target.set(0.5, 0, 0);
    }
  };

  // Direct Smooth Zoom Handlers
  const handleZoomIn = () => {
    isTransitioningPresetRef.current = false;
    if (!cameraRef.current || !controlsRef.current) return;
    const dir = new THREE.Vector3().subVectors(controlsRef.current.target, cameraRef.current.position).normalize();
    cameraRef.current.position.addScaledVector(dir, 1.4);
  };

  const handleZoomOut = () => {
    isTransitioningPresetRef.current = false;
    if (!cameraRef.current || !controlsRef.current) return;
    const dir = new THREE.Vector3().subVectors(cameraRef.current.position, controlsRef.current.target).normalize();
    cameraRef.current.position.addScaledVector(dir, 1.4);
  };

  const handleResetCamera = () => {
    setCameraPreset('overview');
  };

  // 5. Initialize Three.js Scene
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x02040a); // Deep Obsidian Void
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.copy(cameraTargetPosRef.current);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: 'high-performance',
      alpha: false,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.75; // Lower → no overblown glow
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // OrbitControls — fully enabled with fluid damping & fast response
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.9;
    controls.zoomSpeed = 1.8;
    controls.panSpeed = 1.0;
    controls.minDistance = 1.0;
    controls.maxDistance = 25.0;
    controls.enableZoom = true;
    controls.enablePan = true;
    controls.enableRotate = true;
    controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };
    controls.touches = {
      ONE: THREE.TOUCH.ROTATE,
      TWO: THREE.TOUCH.DOLLY_PAN,
    };

    // When user drags/zooms, cancel camera preset interpolation so mouse has 100% control
    controls.addEventListener('start', () => {
      isTransitioningPresetRef.current = false;
    });

    controlsRef.current = controls;

    // Lighting — subtle deep fill, no harsh hot spots
    const ambientLight = new THREE.AmbientLight(0x070b14, 1.5);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x1e3a5f, 1.2); // Deep navy
    dirLight1.position.set(6, 6, 6);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x1a1f5e, 0.8); // Dark indigo
    dirLight2.position.set(-6, -4, -5);
    scene.add(dirLight2);

    // Initial Neural Controller Setup
    const model = PRESET_MODELS[selectedModelKey] || PRESET_MODELS['groq/compound'];
    const calculated = calculateModelParameters(model);
    setCalculatedParams(calculated);
    const specs = mapParametersToVisualSpecs(calculated, qualityTier);

    const controller = new NeuralController(scene, camera, specs);
    controllerRef.current = controller;
    controller.setState(activeState, stateData, stateProfile);
    controller.updateMemoryCount(factCount, docChunkCount);

    // ── Master Render Loop ──
    const clock = new THREE.Clock();

    const animate = () => {
      reqIdRef.current = requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.1);
      const totalTime = clock.getElapsedTime();

      // Audio Reactivity
      if (audioPlayEvent?.analyser) {
        audioPlayEvent.analyser.getByteFrequencyData(audioDataArrayRef.current);
        let sum = 0;
        for (let i = 0; i < 24; i++) sum += audioDataArrayRef.current[i];
        const avgVol = (sum / 24.0) / 255.0;
        setAudioLevel(avgVol);
        if (controllerRef.current) {
          controllerRef.current.setAudioVolume(avgVol * 1.6);
        }
      } else {
        setAudioLevel(0);
        if (controllerRef.current) controllerRef.current.setAudioVolume(0);
      }

      // Smooth Camera Lerp only during explicit preset changes
      if (isTransitioningPresetRef.current) {
        camera.position.lerp(cameraTargetPosRef.current, dt * 4.5);
        if (camera.position.distanceTo(cameraTargetPosRef.current) < 0.05) {
          isTransitioningPresetRef.current = false;
        }
      }

      controls.update();

      if (controllerRef.current) {
        if (gestureOverrideRef.current) {
          controllerRef.current.applyGestureControl(gestureOverrideRef.current, dt);
        }
        controllerRef.current.update(dt, totalTime);
      }

      renderer.render(scene, camera);
    };

    animate();

    // Resize Observer
    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // Cleanup
    return () => {
      resizeObserver.disconnect();
      if (reqIdRef.current) cancelAnimationFrame(reqIdRef.current);
      if (controllerRef.current) controllerRef.current.dispose();
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div className="relative w-full h-full overflow-hidden bg-[#02040a]">
      {/* 3D WebGL Canvas — pointer-events-auto so mouse/touch/scroll works */}
      <div ref={mountRef} className="absolute inset-0 w-full h-full pointer-events-auto cursor-grab active:cursor-grabbing" />

      {/* Subtle deep-space atmospheric glow — very low opacity, not blinding */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-blue-900/5 blur-[140px] pointer-events-none" />
      <div className="absolute top-1/3 left-1/3 -translate-x-1/2 -translate-y-1/2 w-[380px] h-[380px] rounded-full bg-indigo-950/5 blur-[110px] pointer-events-none" />

      {/* Model Information Telemetry HUD */}
      <ModelInfoHUD
        activeState={activeState}
        stateProfile={stateProfile}
        stateData={stateData}
        selectedModelKey={selectedModelKey}
        onModelSelect={setSelectedModelKey}
        calculatedParams={calculatedParams}
        factCount={factCount}
        docChunkCount={docChunkCount}
        audioVolume={audioLevel}
      />

      {/* ── Top-Right Camera Perspective & Interactive Zoom Controls ── */}
      <div className="absolute top-4 right-4 z-30 pointer-events-auto flex items-center gap-1.5 p-1.5 rounded-2xl border border-slate-700/40 backdrop-blur-xl bg-black/70 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
        {/* Preset views */}
        <button
          onClick={() => setCameraPreset('overview')}
          title="Overview Perspective"
          className={`p-2 rounded-xl text-xs font-mono transition-all cursor-pointer flex items-center gap-1 ${
            activeCameraPreset === 'overview'
              ? 'bg-blue-900/40 text-blue-300 border border-blue-700/50 shadow-[0_0_10px_rgba(29,78,216,0.2)]'
              : 'text-slate-500 hover:text-blue-300 hover:bg-blue-900/20'
          }`}
        >
          <Globe size={13} />
          <span className="hidden sm:inline">GALAXY</span>
        </button>

        <button
          onClick={() => setCameraPreset('core')}
          title="Macro Nucleus Focus"
          className={`p-2 rounded-xl text-xs font-mono transition-all cursor-pointer flex items-center gap-1 ${
            activeCameraPreset === 'core'
              ? 'bg-blue-900/40 text-blue-300 border border-blue-700/50 shadow-[0_0_10px_rgba(29,78,216,0.2)]'
              : 'text-slate-500 hover:text-blue-300 hover:bg-blue-900/20'
          }`}
        >
          <Focus size={13} />
          <span className="hidden sm:inline">CORE</span>
        </button>

        <button
          onClick={() => setCameraPreset('knowledge')}
          title="Orbital Knowledge Clusters"
          className={`p-2 rounded-xl text-xs font-mono transition-all cursor-pointer flex items-center gap-1 ${
            activeCameraPreset === 'knowledge'
              ? 'bg-blue-900/40 text-blue-300 border border-blue-700/50 shadow-[0_0_10px_rgba(29,78,216,0.2)]'
              : 'text-slate-500 hover:text-blue-300 hover:bg-blue-900/20'
          }`}
        >
          <Compass size={13} />
          <span className="hidden sm:inline">MEMORY</span>
        </button>

        {/* Divider */}
        <div className="w-[1px] h-4 bg-slate-700/50 mx-0.5" />

        {/* Quick Zoom In */}
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-2 rounded-xl text-slate-400 hover:text-blue-300 hover:bg-blue-900/30 transition-all cursor-pointer flex items-center justify-center"
        >
          <ZoomIn size={14} />
        </button>

        {/* Quick Zoom Out */}
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-2 rounded-xl text-slate-400 hover:text-blue-300 hover:bg-blue-900/30 transition-all cursor-pointer flex items-center justify-center"
        >
          <ZoomOut size={14} />
        </button>

        {/* Reset Camera */}
        <button
          onClick={handleResetCamera}
          title="Reset Camera View"
          className="p-2 rounded-xl text-slate-400 hover:text-blue-300 hover:bg-blue-900/30 transition-all cursor-pointer flex items-center justify-center"
        >
          <RotateCcw size={13} />
        </button>

        {/* Divider */}
        <div className="w-[1px] h-4 bg-slate-700/50 mx-0.5" />

        {/* 3D Holographic Architecture Infographics Toggle */}
        <button
          onClick={() => setShowInspectOverlay(!showInspectOverlay)}
          title="Toggle 3D Holographic Component Infographics"
          className={`p-2 rounded-xl text-xs font-mono transition-all cursor-pointer flex items-center gap-1.5 ${
            showInspectOverlay
              ? 'bg-cyan-600/40 text-cyan-200 border border-cyan-500/60 shadow-[0_0_15px_rgba(6,182,212,0.4)] animate-pulse'
              : 'text-slate-400 hover:text-cyan-300 hover:bg-cyan-900/30'
          }`}
        >
          <Info size={14} />
          <span className="hidden md:inline font-bold">INFO OVERLAY</span>
        </button>
      </div>

      {/* 3D Holographic Component Infographics Overlay */}
      <ArchitectureInfoOverlay
        cameraRef={cameraRef}
        controllerRef={controllerRef}
        containerRef={mountRef}
        show={showInspectOverlay}
        factCount={factCount}
        docChunkCount={docChunkCount}
      />

      {/* ── Mouse Control Hint — bottom-left, pointer-events-none so it never blocks canvas ── */}
      <div className="absolute bottom-5 left-4 z-20 pointer-events-none">
        <div className="flex flex-col gap-1 text-[9px] font-mono text-slate-700 uppercase tracking-wider select-none">
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.5 rounded border border-slate-800 bg-black/40 text-slate-600">drag</span>
            <span>Rotate 3D</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.5 rounded border border-slate-800 bg-black/40 text-slate-600">scroll</span>
            <span>Zoom In/Out</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.5 rounded border border-slate-800 bg-black/40 text-slate-600">right-drag</span>
            <span>Pan Camera</span>
          </div>
        </div>
      </div>

      {/* ── Bottom Subtle Telemetry & Audio EQ Bar ── */}
      <div className="absolute bottom-5 inset-x-0 flex flex-col items-center pointer-events-none z-20 space-y-2">
        {/* Live Audio Equalizer Wave */}
        {audioLevel > 0.05 && (
          <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-slate-900/60 border border-blue-900/40 backdrop-blur-md">
            <Volume2 size={11} className="text-blue-400/70 animate-pulse" />
            <div className="flex items-center gap-0.5 h-3">
              {[0.4, 0.8, 1.2, 0.6, 0.9, 0.5, 0.7].map((factor, i) => (
                <div
                  key={i}
                  className="w-1 bg-blue-500/70 rounded-full transition-all duration-75"
                  style={{ height: `${Math.max(3, audioLevel * factor * 12)}px` }}
                />
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 text-[10px] font-mono tracking-widest text-slate-600 uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-700 animate-pulse" />
          <span>KAIROS LIVING AI CORE</span>
          <span>·</span>
          <span>AUTONOMOUS NEURAL SUB-SYSTEM</span>
          <span>·</span>
          <span>60 FPS REAL-TIME</span>
        </div>
      </div>
    </div>
  );
}
