import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, CameraOff, ChevronDown, ChevronUp, Monitor, Box, Activity, GripVertical } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const STREAM_URL = `${API_BASE}/api/gesture/stream`;

export default function GesturePreview({ onGestureData }) {
  const [isRunning, setIsRunning] = useState(false);
  const [isFolded, setIsFolded] = useState(false);
  const [mode, setMode] = useState("system");
  const [status, setStatus] = useState(null);
  const [streamError, setStreamError] = useState(false);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/gesture/status`);
        if (res.ok) {
          const data = await res.json();
          const s = data.status;
          setStatus(s);
          setIsRunning(s.is_running);
          setMode(s.mode || "system");
          if (onGestureData && s.scifi) onGestureData(s.scifi);
        }
      } catch (_) {}
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, [onGestureData]);

  const handleStart = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/gesture/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ show_preview: false, camera_id: 0, mode }),
      });
      if (res.ok) { setIsRunning(true); setStreamError(false); }
    } catch (_) {}
  };

  const handleStop = async () => {
    try {
      await fetch(`${API_BASE}/api/gesture/stop`, { method: "POST" });
      setIsRunning(false);
    } catch (_) {}
  };

  const handleModeSwitch = async (newMode) => {
    setMode(newMode);
    try {
      await fetch(`${API_BASE}/api/gesture/mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: newMode }),
      });
    } catch (_) {}
  };

  const handChip = (state) => {
    if (state === "OPEN") return "text-emerald-400 border-emerald-500/40 bg-emerald-950/40";
    if (state === "CLOSED") return "text-red-400 border-red-500/40 bg-red-950/40";
    return "text-slate-500 border-slate-700/40 bg-slate-900/40";
  };

  return (
    <motion.div
      drag
      dragMomentum={false}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="absolute top-12 left-[310px] z-50 w-[280px] pointer-events-auto cursor-grab active:cursor-grabbing"
    >
      <div className="rounded-2xl border border-slate-700/60 bg-slate-950/85 backdrop-blur-xl shadow-[0_10px_38px_rgba(0,0,0,0.8)] overflow-hidden border-cyan-500/20 hover:border-cyan-500/40 transition-all">

        {/* Header — Drag Handle */}
        <div className="flex items-center justify-between px-2.5 py-2 border-b border-slate-800/80 bg-black/40">
          <div className="flex items-center gap-1.5">
            <GripVertical size={13} className="text-slate-500 hover:text-cyan-400 cursor-grab shrink-0" />
            <div className={`w-2 h-2 rounded-full ${isRunning ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-200">GESTURE CTRL</span>
          </div>
          <div className="flex items-center gap-1">
            {/* Mode pill */}
            <div className="flex items-center rounded-full border border-slate-700 bg-slate-900 overflow-hidden">
              <button onClick={() => handleModeSwitch("system")} title="System: brightness & volume"
                className={`px-2 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer flex items-center gap-1 ${mode === "system" ? "bg-blue-600/80 text-white" : "text-slate-500 hover:text-slate-200"}`}>
                <Monitor size={9} />SYS
              </button>
              <button onClick={() => handleModeSwitch("avatar")} title="3D Model: hologram control"
                className={`px-2 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer flex items-center gap-1 ${mode === "avatar" ? "bg-cyan-600/80 text-white" : "text-slate-500 hover:text-slate-200"}`}>
                <Box size={9} />3D
              </button>
            </div>
            {/* Start/stop */}
            <button onClick={isRunning ? handleStop : handleStart} title={isRunning ? "Stop camera" : "Start camera"}
              className={`p-1.5 rounded-lg border transition-all cursor-pointer ${isRunning ? "bg-red-600/20 border-red-500/40 text-red-400 hover:bg-red-600/30" : "bg-blue-600/20 border-blue-500/40 text-blue-400 hover:bg-blue-600/30"}`}>
              {isRunning ? <CameraOff size={11} /> : <Camera size={11} />}
            </button>
            {/* Fold */}
            <button onClick={() => setIsFolded(!isFolded)} title={isFolded ? "Expand" : "Collapse"}
              className="p-1 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 cursor-pointer transition-all">
              {isFolded ? <ChevronDown size={11} /> : <ChevronUp size={11} />}
            </button>
          </div>
        </div>

        {/* MJPEG Stream */}
        <AnimatePresence>
          {!isFolded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="relative overflow-hidden"
            >
              {isRunning && !streamError ? (
                <div className="relative select-none">
                  <img src={STREAM_URL} alt="Gesture Camera Feed" className="w-full block pointer-events-none"
                    style={{ height: "158px", objectFit: "cover" }}
                    onError={() => setStreamError(true)}
                    onLoad={() => setStreamError(false)}
                  />
                  {/* Cyberpunk corner reticles */}
                  <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-1.5 left-1.5 w-5 h-5 border-t-2 border-l-2 border-cyan-400/80" />
                    <div className="absolute top-1.5 right-1.5 w-5 h-5 border-t-2 border-r-2 border-cyan-400/80" />
                    <div className="absolute bottom-1.5 left-1.5 w-5 h-5 border-b-2 border-l-2 border-cyan-400/80" />
                    <div className="absolute bottom-1.5 right-1.5 w-5 h-5 border-b-2 border-r-2 border-cyan-400/80" />
                    <div className="absolute top-0 inset-x-0 px-2 py-1 bg-gradient-to-b from-black/60 to-transparent flex items-center justify-between">
                      <span className="text-[8px] font-mono text-cyan-400/80 uppercase tracking-widest">
                        {mode === "system" ? "SYSTEM CTRL" : "HOLO MATRIX"}
                      </span>
                      <span className="text-[8px] font-mono text-emerald-400/80 animate-pulse">LIVE</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-[158px] bg-black/60 border-t border-slate-800/60">
                  <Camera size={24} className="text-slate-600 mb-2" />
                  <span className="text-[10px] font-mono text-slate-500">{isRunning ? "Stream unavailable" : "Camera offline"}</span>
                  {!isRunning && (
                    <button onClick={handleStart}
                      className="mt-2 px-3 py-1 rounded-full bg-blue-600/30 border border-blue-500/40 text-blue-300 text-[9px] font-mono cursor-pointer hover:bg-blue-600/50 transition-all">
                      Start Camera
                    </button>
                  )}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Telemetry footer */}
        {status && (
          <div className="px-3 py-2 border-t border-slate-800/80 space-y-1.5 bg-black/20">
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <div className="flex justify-between text-[8px] font-mono text-slate-500 mb-0.5">
                  <span>BRIGHT</span><span className="text-slate-300">{status.brightness ?? 50}%</span>
                </div>
                <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-yellow-500/80 rounded-full transition-all duration-300" style={{ width: `${status.brightness ?? 50}%` }} />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex justify-between text-[8px] font-mono text-slate-500 mb-0.5">
                  <span>VOL</span><span className="text-slate-300">{status.volume ?? 50}%</span>
                </div>
                <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500/80 rounded-full transition-all duration-300" style={{ width: `${status.volume ?? 50}%` }} />
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <Activity size={9} className="text-slate-500 shrink-0" />
              <span className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold border ${handChip(status.right_hand)}`}>R: {status.right_hand || "NONE"}</span>
              <span className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold border ${handChip(status.left_hand)}`}>L: {status.left_hand || "NONE"}</span>
              {status.scifi?.r_repulsor && (
                <span className="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold border border-orange-500/40 bg-orange-950/40 text-orange-400 animate-pulse">BLAST</span>
              )}
            </div>
          </div>
        )}

      </div>
    </motion.div>
  );
}
