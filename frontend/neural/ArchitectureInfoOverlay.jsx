import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import * as THREE from "three";
import { Cpu, Layers, Activity, Database, Network, X, Sparkles, Binary, Zap, Eye, Code, Terminal, ChevronRight } from "lucide-react";

/**
 * ArchitectureInfoOverlay — Interactive Cyberpunk 3D Diagnostic & Inspection Subsystem
 */
export default function ArchitectureInfoOverlay({
  cameraRef,
  controllerRef,
  containerRef,
  show = false,
  factCount = 12,
  docChunkCount = 4,
}) {
  const [callouts, setCallouts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const COMPONENT_DETAILS = {
    nucleus: {
      id: "nucleus",
      title: "OUTER PARAMETER SHELL (ICOSA HEDRON)",
      badge: "70B PARAMS · FP16",
      localPos: new THREE.Vector3(0, 1.4, 0),
      equation: "FFN(x) = max(0, xW₁ + b₁)W₂ + b₂",
      specs: [
        { label: "PARAMETER WEIGHTS", value: "70,612,492,288 float16" },
        { label: "COMPUTE ENGINE", value: "Groq LPU / NVIDIA Tensor" },
        { label: "ACTIVATION", value: "SwiGLU Non-Linearity" },
        { label: "LATENCY PER LAYER", value: "< 0.04ms" }
      ],
      role: "Computes multi-layer feed-forward neural projections and non-linear feature transformations. Represents the foundational weights of Kairos's 70B parameter brain.",
      icon: Cpu,
      color: "border-blue-500/60 text-blue-400 bg-blue-950/90 shadow-[0_0_25px_rgba(59,130,246,0.4)]",
      dotColor: "bg-blue-400 shadow-[0_0_15px_#60a5fa]",
      accent: "#3b82f6",
      align: "right",
    },
    octahedron: {
      id: "octahedron",
      title: "COUNTER-ROTATING ATTENTION MATRIX",
      badge: "128 ATTN HEADS",
      localPos: new THREE.Vector3(0, -1.3, 0),
      equation: "Attention(Q,K,V) = softmax(QKᵀ / √dₖ)V",
      specs: [
        { label: "ATTENTION HEADS", value: "128 Multi-Head QKV" },
        { label: "POS EMBEDDINGS", value: "RoPE (Rotary Positional)" },
        { label: "CONTEXT WINDOW", value: "8,192 Tokens Active" },
        { label: "KV-CACHE MEMORY", value: "Sub-Layer Dynamic Ring" }
      ],
      role: "Maintains real-time Query-Key-Value self-attention. Computes token-to-token contextual relevance and prevents context decay during long conversations.",
      icon: Layers,
      color: "border-cyan-500/60 text-cyan-300 bg-cyan-950/90 shadow-[0_0_25px_rgba(6,182,212,0.4)]",
      dotColor: "bg-cyan-400 shadow-[0_0_15px_#22d3ee]",
      accent: "#06b6d4",
      align: "left",
    },
    neurons: {
      id: "neurons",
      title: "INSTANCED SYNAPTIC NEURONS",
      badge: "2048 GPU NODES",
      localPos: new THREE.Vector3(2.1, 0.7, 0.4),
      equation: "aᵢ⁽ˡ⁾ = σ(∑ wᵢⱼ⁽ˡ⁾ aⱼ⁽ˡ⁻¹⁾ + bᵢ⁽ˡ⁾)",
      specs: [
        { label: "ACTIVE NODES", value: "2,048 Instanced Vertices" },
        { label: "RENDER PERFORMANCE", value: "60 FPS InstancedMesh" },
        { label: "COLOR DYNAMICS", value: "Cognitive Phase Palette" },
        { label: "DISPLACEMENT", value: "Dynamic Harmonic Pulse" }
      ],
      role: "Simulates artificial biological action potentials. Changes visual color and pulse frequency to signal system state machine transitions (IDLE → LISTENING → THINKING → GENERATING).",
      icon: Activity,
      color: "border-purple-500/60 text-purple-300 bg-purple-950/90 shadow-[0_0_25px_rgba(168,85,247,0.4)]",
      dotColor: "bg-purple-400 shadow-[0_0_15px_#c084fc]",
      accent: "#a855f7",
      align: "right",
    },
    pathways: {
      id: "pathways",
      title: "SYNAPTIC SIGNAL PATHWAYS",
      badge: "SUB-100MS LATENCY",
      localPos: new THREE.Vector3(-2.1, 0.7, -0.4),
      equation: "S(f, t) = |FFT(Audio_16kHz)|²",
      specs: [
        { label: "AUDIO SPECTRUM", value: "64-Bin WebAudio FFT" },
        { label: "AUDIO RESAMPLE", value: "16kHz PCM Downsample" },
        { label: "SIGNAL SPEED", value: "Sub-100ms End-to-End" },
        { label: "BARGE-IN CUTOFF", value: "Instant VAD Reset" }
      ],
      role: "Transmits live audio frequency spectrum data into vertex shaders for voice-reactive breathing and streams generated tokens directly to speech synthesis.",
      icon: Network,
      color: "border-emerald-500/60 text-emerald-300 bg-emerald-950/90 shadow-[0_0_25px_rgba(16,185,129,0.4)]",
      dotColor: "bg-emerald-400 shadow-[0_0_15px_#34d399]",
      accent: "#10b981",
      align: "left",
    },
    memory: {
      id: "memory",
      title: "CHROMADB VECTOR MEMORY CLUSTERS",
      badge: "RAG VECTOR STORE",
      localPos: new THREE.Vector3(2.6, -1.2, 0.9),
      equation: "CosSim(A, B) = (A · B) / (||A|| ||B||)",
      specs: [
        { label: "STORED FACTS", value: `${factCount} Long-Term Facts` },
        { label: "DOCUMENT CHUNKS", value: `${docChunkCount} Ingested RAG Chunks` },
        { label: "EMBEDDING SPACE", value: "all-MiniLM-L6-v2 (384d)" },
        { label: "SPREADSHEET ENGINE", value: "Pandas Exact Analytics" }
      ],
      role: "Provides persistent long-term vector memory and RAG context. Orbiting clusters represent stored facts and ingested document chunks retrieved semantically for zero hallucinations.",
      icon: Database,
      color: "border-amber-500/60 text-amber-300 bg-amber-950/90 shadow-[0_0_25px_rgba(245,158,11,0.4)]",
      dotColor: "bg-amber-400 shadow-[0_0_15px_#fbbf24]",
      accent: "#f59e0b",
      align: "right",
    },
  };

  useEffect(() => {
    if (!show) return;

    let reqId;
    const updatePositions = () => {
      reqId = requestAnimationFrame(updatePositions);

      if (!cameraRef.current || !controllerRef.current || !containerRef.current) return;
      const camera = cameraRef.current;
      const controller = controllerRef.current;
      const container = containerRef.current;
      const width = container.clientWidth;
      const height = container.clientHeight;

      if (!controller.group) return;

      const keys = Object.keys(COMPONENT_DETAILS);
      const projected = keys
        .map((key) => {
          const detail = COMPONENT_DETAILS[key];
          const worldPos = detail.localPos.clone().applyMatrix4(controller.group.matrixWorld);
          const v = worldPos.clone().project(camera);
          const x = (v.x * 0.5 + 0.5) * width;
          const y = (-v.y * 0.5 + 0.5) * height;
          const isVisible = v.z < 1.0 && x > 10 && x < width - 10 && y > 10 && y < height - 10;
          return { ...detail, x, y, isVisible };
        })
        .filter((t) => t.isVisible);

      setCallouts(projected);
    };

    updatePositions();
    return () => cancelAnimationFrame(reqId);
  }, [show, cameraRef, controllerRef, containerRef, factCount, docChunkCount]);

  if (!show) return null;

  const selectedItem = selectedId ? COMPONENT_DETAILS[selectedId] : null;

  return (
    <div className="absolute inset-0 pointer-events-none z-30 overflow-hidden">
      
      {/* SVG Connecting Laser Beam Lines */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none">
        {callouts.map((item) => {
          const isSel = selectedId === item.id;
          return (
            <g key={`line-${item.id}`}>
              <line
                x1={item.x}
                y1={item.y}
                x2={item.align === "left" ? item.x - 30 : item.x + 30}
                y2={item.y}
                stroke={item.accent}
                strokeWidth={isSel ? "2" : "1"}
                strokeDasharray={isSel ? "none" : "3,3"}
                opacity={isSel ? 0.9 : 0.5}
              />
            </g>
          );
        })}
      </svg>

      {/* 3D Projected Holographic Callout Cards */}
      <AnimatePresence>
        {callouts.map((item) => {
          const Icon = item.icon;
          const isSel = selectedId === item.id;

          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.2 }}
              style={{
                left: `${item.x}px`,
                top: `${item.y}px`,
                transform: item.align === "left" ? "translate(-108%, -50%)" : "translate(24px, -50%)",
              }}
              onClick={() => setSelectedId(isSel ? null : item.id)}
              className="absolute pointer-events-auto w-[250px] md:w-[270px] cursor-pointer group"
            >
              {/* Target Dot */}
              <div
                className={`absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full ${item.dotColor} ${
                  item.align === "left" ? "-right-4" : "-left-4"
                } ${isSel ? "scale-125 border-2 border-white" : ""}`}
              />

              {/* Callout Card */}
              <div className={`p-3 rounded-2xl border backdrop-blur-xl transition-all duration-300 ${item.color} ${isSel ? "ring-2 ring-cyan-400 scale-105" : "hover:scale-102"}`}>
                <div className="flex items-center justify-between gap-1 mb-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Icon size={13} className="shrink-0" />
                    <span className="text-[10px] font-mono font-bold tracking-wider uppercase truncate">{item.title}</span>
                  </div>
                  <span className="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold border border-white/20 bg-black/50 text-white shrink-0">
                    {item.badge}
                  </span>
                </div>

                <div className="text-[10px] font-mono font-semibold text-slate-200 mb-1 border-b border-white/10 pb-1 flex items-center justify-between">
                  <span>{item.weight}</span>
                  <ChevronRight size={12} className="text-slate-400 group-hover:translate-x-1 transition-transform" />
                </div>

                <div className="text-[9px] font-sans text-slate-300 leading-snug line-clamp-2">
                  {item.purpose}
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* Bottom Interactive Component Selector Bar */}
      <div className="absolute bottom-16 inset-x-0 flex justify-center z-40 pointer-events-auto px-4">
        <div className="flex items-center gap-1.5 p-1.5 rounded-full glass-panel border border-slate-700/80 bg-black/80 backdrop-blur-2xl shadow-2xl overflow-x-auto max-w-full">
          <div className="flex items-center gap-1 px-2 text-[10px] font-mono text-cyan-400 font-bold uppercase tracking-wider border-r border-slate-800 shrink-0">
            <Sparkles size={12} className="text-cyan-400 animate-pulse" />
            <span>3D DIAGNOSTICS</span>
          </div>

          {[
            { id: "nucleus", label: "01. NUCLEUS", icon: Cpu },
            { id: "octahedron", label: "02. ATTENTION", icon: Layers },
            { id: "neurons", label: "03. NEURONS", icon: Activity },
            { id: "pathways", label: "04. AXONS", icon: Network },
            { id: "memory", label: "05. CHROMADB", icon: Database },
          ].map((btn) => {
            const Icon = btn.icon;
            const isSel = selectedId === btn.id;
            return (
              <button
                key={btn.id}
                onClick={() => setSelectedId(isSel ? null : btn.id)}
                className={`px-3 py-1.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                  isSel
                    ? "bg-cyan-600 text-white border border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.5)]"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                <Icon size={12} />
                <span>{btn.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Expanded Holographic Diagnostic Inspection Modal */}
      <AnimatePresence>
        {selectedItem && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.25 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[92%] max-w-lg pointer-events-auto"
          >
            <div className={`p-5 rounded-3xl border backdrop-blur-2xl ${selectedItem.color} shadow-[0_20px_60px_rgba(0,0,0,0.9)]`}>
              
              {/* Modal Header */}
              <div className="flex items-start justify-between pb-3 border-b border-white/15 mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-black/40 border border-white/20 text-white">
                    <selectedItem.icon size={18} />
                  </div>
                  <div>
                    <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                      {selectedItem.title}
                    </h3>
                    <span className="text-[10px] font-mono text-cyan-300/80 font-semibold">
                      KAIROS 3D NEURAL CORE SUBSYSTEM
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => setSelectedId(null)}
                  className="p-1.5 rounded-xl bg-black/40 hover:bg-red-500/30 text-slate-300 hover:text-white border border-white/20 transition-all cursor-pointer"
                >
                  <X size={15} />
                </button>
              </div>

              {/* Mathematical Equation Card */}
              <div className="p-3 rounded-2xl bg-black/60 border border-cyan-500/30 mb-3.5 space-y-1">
                <div className="flex items-center gap-1.5 text-[9px] font-mono font-bold uppercase tracking-wider text-cyan-400">
                  <Binary size={12} />
                  <span>MATHEMATICAL & VECTOR FORMULATION</span>
                </div>
                <div className="text-xs font-mono font-bold text-white bg-slate-950/80 p-2 rounded-xl border border-slate-800 text-center tracking-wide">
                  {selectedItem.equation}
                </div>
              </div>

              {/* Specifications Grid */}
              <div className="grid grid-cols-2 gap-2 mb-3.5">
                {selectedItem.specs.map((spec, i) => (
                  <div key={i} className="p-2.5 rounded-xl bg-black/40 border border-white/10 space-y-0.5">
                    <div className="text-[8px] font-mono uppercase tracking-wider text-slate-400">{spec.label}</div>
                    <div className="text-xs font-mono font-bold text-white truncate">{spec.value}</div>
                  </div>
                ))}
              </div>

              {/* Functional Role Description */}
              <div className="p-3 rounded-2xl bg-black/40 border border-white/10 space-y-1">
                <div className="text-[9px] font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Zap size={11} className="text-amber-400" />
                  <span>ARCHITECTURAL PURPOSE & FUNCTION</span>
                </div>
                <p className="text-xs font-sans text-slate-200 leading-relaxed">
                  {selectedItem.role}
                </p>
              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
