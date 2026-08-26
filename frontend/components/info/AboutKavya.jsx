import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  X, Sparkles, Brain, Ear, Volume2, Eye, Database, Wrench, 
  CheckCircle2, Clock, Lock, ShieldCheck, Heart, Zap, Cpu, 
  Award, Layers, ChevronDown, ChevronUp, Bot, Star
} from 'lucide-react';
import RetroDial from '../common/RetroDial';

export default function AboutKavya({ onClose, theme = 'dark', userRapportEnergy = 0.35, messageCount = 0 }) {
  const [expandedSystem, setExpandedSystem] = useState(null);

  const toggleSystem = (id) => {
    setExpandedSystem(expandedSystem === id ? null : id);
  };

  const systems = [
    {
      id: 'mind',
      title: 'Mind // LLM Engine',
      subtitle: 'Groq Llama 3.3 70B Versatile',
      icon: Brain,
      color: 'text-blue-400',
      border: 'border-blue-500/30',
      bgGlow: 'from-blue-950/40 to-slate-950/60',
      status: 'ONLINE',
      statusColor: 'text-blue-400',
      summary: 'High-speed reasoning, multilingual comprehension, and context memory.',
      details: 'Processes queries natively with strict English TTS synthesis and agentic tool dispatching.'
    },
    {
      id: 'ears',
      title: 'Ears // Speech Recognition',
      subtitle: 'Whisper Large v3 + Energy VAD',
      icon: Ear,
      color: 'text-sky-400',
      border: 'border-sky-500/30',
      bgGlow: 'from-sky-950/40 to-slate-950/60',
      status: 'ACTIVE',
      statusColor: 'text-sky-400',
      summary: 'Voice Activity Detection with 16kHz WebSocket audio downsampling.',
      details: 'Detects natural user speech pauses and filters ambient background noise.'
    },
    {
      id: 'voice',
      title: 'Voice // Neural Speech Synthesis',
      subtitle: 'Edge-TTS (en-US-ChristopherNeural)',
      icon: Volume2,
      color: 'text-blue-300',
      border: 'border-blue-500/30',
      bgGlow: 'from-blue-950/40 to-slate-950/60',
      status: 'ONLINE',
      statusColor: 'text-blue-300',
      summary: 'Clear, modern English neural voice with low-latency streaming.',
      details: 'Feeds live audio frequency analysis directly into the Living AI Core 3D visualizer.'
    },
    {
      id: 'presence',
      title: 'Presence // 3D Neural Core',
      subtitle: 'Three.js Living AI Core',
      icon: Eye,
      color: 'text-sky-300',
      border: 'border-blue-500/30',
      bgGlow: 'from-blue-950/40 to-slate-950/60',
      status: '60 FPS',
      statusColor: 'text-blue-400',
      summary: 'Interactive orbital 3D neural brain core with audio-reactive pulsing.',
      details: 'Smooth orbit controls, multi-angle zoom, and live state transitions.'
    },
    {
      id: 'memory',
      title: 'Memory // Context & Recall',
      subtitle: 'SQLite Local Store + ChromaDB RAG',
      icon: Database,
      color: 'text-blue-400',
      border: 'border-blue-500/30',
      bgGlow: 'from-blue-950/40 to-slate-950/60',
      status: 'ONLINE',
      statusColor: 'text-blue-400',
      summary: 'Local SQLite conversation turns and ChromaDB vector embeddings with interactive document filtering.',
      details: 'Extracts user facts and indexes documents locally on disk with zero external database dependencies.'
    },
    {
      id: 'hands',
      title: 'Hands // Agentic Desktop Tools',
      subtitle: 'Windows Native Subprocess Execution',
      icon: Wrench,
      color: 'text-blue-300',
      border: 'border-blue-500/30',
      bgGlow: 'from-blue-950/40 to-slate-950/60',
      status: 'CONNECTED',
      statusColor: 'text-blue-400',
      summary: 'Work Mode workspace launcher, VS Code automation, App manager, & Code Sandbox.',
      details: 'Executes desktop automation tasks seamlessly via agentic tool tags.'
    }
  ];

  const roadmapItems = [
    { name: 'Fast Voice Transcription', desc: 'Real-time Whisper STT + VAD', state: 'unlocked', icon: '🎙️' },
    { name: 'Living AI 3D Core', desc: 'Audio-reactive particle pulse core', state: 'unlocked', icon: '🌐' },
    { name: 'Work Mode Launcher', desc: 'Automates Chrome tabs + VS Code + Brave', state: 'unlocked', icon: '⚡' },
    { name: 'RAG Document Selection', desc: 'Select/unselect knowledge documents for chat', state: 'unlocked', icon: '📄' },
    { name: 'Code Sandbox Execution', desc: 'Run Python/JS scripts in isolated env', state: 'unlocked', icon: '💻' },
    { name: 'Pure Local SQLite Memory', desc: 'Zero cloud database dependencies', state: 'unlocked', icon: '🔒' },
  ];

  const affinityScore = Math.round(Math.min(100, Math.max(25, userRapportEnergy * 100)));

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`fixed inset-0 z-50 overflow-y-auto bg-[var(--background)]/95 backdrop-blur-2xl p-4 md:p-8 ${theme}`}
    >
      {/* Sci-Fi Background Overlay */}
      <div className="animated-grid-bg" />

      <div className="max-w-5xl mx-auto relative z-10 space-y-8 pb-12">
        
        {/* ── Top Header Navigation ──────────────────────────────────── */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-glass)]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-300">
              <Star size={16} />
            </div>
            <span className="text-xs font-mono font-bold tracking-widest uppercase text-blue-300">
              CHARACTER CODEX // KAIROS V2.0
            </span>
          </div>

          <button 
            onClick={onClose}
            className="w-10 h-10 rounded-2xl glass-panel hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/40 flex items-center justify-center text-slate-300 transition-all cursor-pointer border border-slate-700 shadow-lg"
            title="Close Codex"
          >
            <X size={20} />
          </button>
        </div>

        {/* ── 1. Hero Character Profile Card ─────────────────────────── */}
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 shadow-2xl relative overflow-hidden flex flex-col md:flex-row items-center gap-6 md:gap-8">
          
          {/* Portrait Icon Render */}
          <div className="relative shrink-0">
            <div className="w-28 h-28 md:w-36 md:h-36 rounded-3xl bg-gradient-to-tr from-blue-600 via-sky-500 to-indigo-600 p-1 shadow-[0_0_35px_rgba(59,130,246,0.4)]">
              <div className="w-full h-full rounded-[22px] bg-slate-950 flex flex-col items-center justify-center relative overflow-hidden">
                <Bot size={54} className="text-blue-300 animate-pulse" />
                <div className="absolute bottom-2 text-[9px] font-mono tracking-widest font-bold text-blue-200">
                  AI CORE // 3D
                </div>
              </div>
            </div>
            {/* Level Edition Badge */}
            <div className="absolute -bottom-2 -right-2 px-2.5 py-1 rounded-full bg-slate-950 border border-blue-400 text-[10px] font-mono font-bold text-blue-300 shadow-md">
              LVL 2.0
            </div>
          </div>

          {/* Character Identity & Lore */}
          <div className="flex-1 text-center md:text-left space-y-2">
            <div className="flex flex-wrap items-center justify-center md:justify-start gap-2.5">
              <h1 className="text-3xl md:text-4xl font-bold font-mono tracking-wide text-white">
                KAIROS
              </h1>
              <span className="px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40 text-xs font-mono font-semibold">
                NEURAL EDITION
              </span>
              <span className="px-2.5 py-1 rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/40 text-xs font-mono font-semibold">
                PROFESSIONAL DESKTOP AI
              </span>
            </div>

            <p className="text-sm md:text-base text-slate-300 leading-relaxed font-sans max-w-2xl">
              "Abhishek's personal AI assistant — loyal, intelligent, and agentic. Designed with an ultra-fast neural core, on-device vector memory, and automated desktop workspace workflows."
            </p>

            <div className="pt-2 flex flex-wrap items-center justify-center md:justify-start gap-4 text-xs font-mono text-slate-400">
              <span className="flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-blue-400" /> Private & Local SQLite
              </span>
              <span className="flex items-center gap-1.5">
                <Zap size={14} className="text-blue-400" /> Ultra-Low Latency (~200ms)
              </span>
              <span className="flex items-center gap-1.5">
                <Brain size={14} className="text-blue-400" /> Dynamic RAG Knowledge
              </span>
              <span className="flex items-center gap-1.5">
                <Heart size={14} className="text-rose-400" /> High Empathy Rapport
              </span>
            </div>
          </div>
          <div className="shrink-0 hidden lg:block">
            <RetroDial 
              value={affinityScore}
              max={100}
              label="RAPPORT SCORE"
              unit="%"
              variant="gold"
              size={95}
            />
          </div>
        </div>

        {/* ── 4. Session Companion Stats ──────────────────────────────── */}
        <div>
          <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-amber-300 mb-3 flex items-center gap-2">
            <Sparkles size={16} /> Companion Session Metrics
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-panel-warm p-3.5 rounded-2xl border border-[var(--border-gold-glow)]">
              <div className="text-[10px] font-mono text-[var(--text-muted)] uppercase">Turns Exchanged</div>
              <div className="text-xl font-bold font-mono text-amber-300 mt-0.5">{messageCount || 12} messages</div>
            </div>
            <div className="glass-panel-warm p-3.5 rounded-2xl border border-[var(--border-gold-glow)]">
              <div className="text-[10px] font-mono text-[var(--text-muted)] uppercase">Current Affinity</div>
              <div className="text-xl font-bold font-mono text-rose-300 mt-0.5">{affinityScore}% (Warm)</div>
            </div>
            <div className="glass-panel-warm p-3.5 rounded-2xl border border-[var(--border-gold-glow)]">
              <div className="text-[10px] font-mono text-[var(--text-muted)] uppercase">Voice Engine</div>
              <div className="text-xl font-bold font-mono text-emerald-300 mt-0.5">Neerja Neural</div>
            </div>
            <div className="glass-panel-warm p-3.5 rounded-2xl border border-[var(--border-gold-glow)]">
              <div className="text-[10px] font-mono text-[var(--text-muted)] uppercase">Active Persona</div>
              <div className="text-xl font-bold font-mono text-cyan-300 mt-0.5">Friendly Companion</div>
            </div>
          </div>
        </div>

        {/* ── 2. Core Systems Ability Sheet ───────────────────────────── */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-amber-300 flex items-center gap-2">
              <Layers size={16} /> Subsystem Matrix & Specs
            </h2>
            <span className="text-[11px] font-mono text-[var(--text-subtle)]">
              CLICK CARDS TO EXPAND DETAILS
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {systems.map((sys) => {
              const isExpanded = expandedSystem === sys.id;
              const Icon = sys.icon;
              return (
                <div 
                  key={sys.id}
                  onClick={() => toggleSystem(sys.id)}
                  className={`glass-panel-warm p-4 rounded-2xl border ${sys.border} cursor-pointer transition-all duration-300 hover:brightness-105 shadow-md`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className={`p-2.5 rounded-xl bg-slate-900/80 border ${sys.border} ${sys.color}`}>
                        <Icon size={20} />
                      </div>
                      <div>
                        <div className="text-sm font-bold font-mono text-[var(--text-main)]">{sys.title}</div>
                        <div className="text-xs text-[var(--text-muted)] font-mono">{sys.subtitle}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-slate-900/80 border border-white/10 ${sys.statusColor}`}>
                        {sys.status}
                      </span>
                      {isExpanded ? <ChevronUp size={16} className="text-amber-400" /> : <ChevronDown size={16} className="text-[var(--text-muted)]" />}
                    </div>
                  </div>

                  <p className="text-xs text-[var(--text-main)] mt-2.5 leading-relaxed font-sans">
                    {sys.summary}
                  </p>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-3 pt-3 border-t border-[var(--border-glass)] text-xs text-[var(--text-muted)] leading-relaxed font-mono bg-slate-950/40 p-2.5 rounded-xl"
                      >
                        {sys.details}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── 3. Abilities Unlocked & Roadmap Grid ────────────────────── */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-amber-300 flex items-center gap-2">
              <Award size={16} /> Abilities & Roadmap Matrix
            </h2>
            <span className="text-[11px] font-mono text-[var(--text-subtle)]">
              6 / 10 MODULES UNLOCKED
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {abilities.map((ability, idx) => (
              <div 
                key={idx}
                className={`p-3.5 rounded-2xl border transition-all ${
                  ability.state === 'unlocked'
                    ? 'glass-panel-warm border-amber-400/40 bg-amber-950/10'
                    : ability.state === 'in-progress'
                    ? 'glass-panel border-cyan-400/40 bg-cyan-950/10'
                    : 'glass-panel border-white/5 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xl">{ability.icon}</span>
                  <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase ${
                    ability.state === 'unlocked'
                      ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                      : ability.state === 'in-progress'
                      ? 'bg-cyan-400/20 text-cyan-300 border border-cyan-400/40'
                      : 'bg-white/5 text-[var(--text-subtle)] border border-white/10'
                  }`}>
                    {ability.state === 'unlocked' ? 'UNLOCKED ✓' : ability.state === 'in-progress' ? 'IN PROGRESS ⏳' : 'ROADMAP 🔒'}
                  </span>
                </div>
                <div className="text-xs font-bold font-mono text-[var(--text-main)]">{ability.name}</div>
                <div className="text-[11px] text-[var(--text-muted)] font-sans mt-0.5">{ability.desc}</div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </motion.div>
  );
}
