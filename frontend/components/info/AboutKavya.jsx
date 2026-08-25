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
      color: 'text-violet-400',
      border: 'border-violet-500/30',
      bgGlow: 'from-violet-950/40 to-slate-950/60',
      status: 'ONLINE',
      statusColor: 'text-emerald-400',
      summary: 'High-speed reasoning, multilingual comprehension, and context memory.',
      details: 'Processes Hindi, English, and Hinglish queries natively. System prompt strictly enforces natural, high-quality English output with warm companion tonality and emotion markup.'
    },
    {
      id: 'ears',
      title: 'Ears // Speech Recognition',
      subtitle: 'Whisper Large v3 + RMS Energy VAD',
      icon: Ear,
      color: 'text-cyan-400',
      border: 'border-cyan-500/30',
      bgGlow: 'from-cyan-950/40 to-slate-950/60',
      status: 'ACTIVE',
      statusColor: 'text-cyan-400',
      summary: 'WebRTC / Energy Voice Activity Detection with 16kHz WebSocket audio downsampling.',
      details: 'Detects natural user speech pauses and filters out ambient background noise before transmitting to Groq Whisper for instant transcription.'
    },
    {
      id: 'voice',
      title: 'Voice // Neural Speech Synthesis',
      subtitle: 'Edge-TTS (en-IN-NeerjaNeural)',
      icon: Volume2,
      color: 'text-amber-400',
      border: 'border-amber-500/30',
      bgGlow: 'from-amber-950/40 to-slate-950/60',
      status: 'LOCKED (EN)',
      statusColor: 'text-amber-300',
      summary: 'Expressive Indian-accented English neural voice with low-latency streaming.',
      details: 'Runs asynchronously with audio playback event triggers that feed real-time mouth visemes and blendshape morph targets to the 3D avatar.'
    },
    {
      id: 'presence',
      title: 'Presence // 3D Avatar Engine',
      subtitle: 'Three.js + VRM Character Rigging',
      icon: Eye,
      color: 'text-rose-400',
      border: 'border-rose-500/30',
      bgGlow: 'from-rose-950/40 to-slate-950/60',
      status: '60 FPS',
      statusColor: 'text-emerald-400',
      summary: 'Realistic body language gestures, micro-blinks, breathing, and gaze tracking.',
      details: 'Implements Allan Pease body language research (open palms, attentiveness, friendly head tilts) with live procedural idle micro-reactions.'
    },
    {
      id: 'memory',
      title: 'Memory // Context & Recall',
      subtitle: 'SQLite Local Store + Redis Cache',
      icon: Database,
      color: 'text-emerald-400',
      border: 'border-emerald-500/30',
      bgGlow: 'from-emerald-950/40 to-slate-950/60',
      status: 'ONLINE',
      statusColor: 'text-emerald-400',
      summary: 'Session conversation logs and personalized rapport tracking in local storage.',
      details: 'Stores conversation history locally on device. RAG vector embeddings and semantic search pipeline scheduled for upcoming memory expansion.'
    },
    {
      id: 'hands',
      title: 'Hands // OS Control & Tools',
      subtitle: 'Desktop Automation Controller',
      icon: Wrench,
      color: 'text-orange-400',
      border: 'border-orange-500/30',
      bgGlow: 'from-orange-950/40 to-slate-950/60',
      status: 'PLANNED',
      statusColor: 'text-amber-400',
      summary: 'Autonomous system tasks, file operations, web browsing, and app integrations.',
      details: 'Extensible tool-calling sandbox to perform real desktop actions on behalf of the user securely with permission verification.'
    }
  ];

  const abilities = [
    { name: 'Voice Interaction', desc: 'Real-time two-way audio streaming', state: 'unlocked', icon: '🎙️' },
    { name: 'Hinglish Comprehension', desc: 'Understands Hindi, Hinglish, & English', state: 'unlocked', icon: '🌐' },
    { name: '3D VRM Lipsync', desc: 'Audio-reactive blendshape phonemes', state: 'unlocked', icon: '🎭' },
    { name: 'Voice Theme Switcher', desc: '"Switch to dark / light mode"', state: 'unlocked', icon: '🎨' },
    { name: 'Analog Telemetry Dials', desc: 'Real-time cockpit performance meters', state: 'unlocked', icon: '📊' },
    { name: 'Companion Idle Reactions', desc: 'Natural blinks, smiles, & head tilts', state: 'unlocked', icon: '✨' },
    { name: 'Code Sandbox Execution', desc: 'Run Python/JS scripts in isolated env', state: 'in-progress', icon: '💻' },
    { name: 'WhatsApp & App Connect', desc: 'Read and send messages hands-free', state: 'locked', icon: '📱' },
    { name: 'Long-Term RAG Knowledge', desc: 'Recall personal notes and preferences', state: 'locked', icon: '🧠' },
    { name: 'Desktop OS Controller', desc: 'Automate mouse, keyboard, and files', state: 'locked', icon: '⚡' }
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
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-gold-glow)]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-amber-400/20 border border-amber-400/40 flex items-center justify-center text-amber-300">
              <Star size={16} />
            </div>
            <span className="text-xs font-mono font-bold tracking-widest uppercase text-amber-300">
              CHARACTER CODEX // KAIROS V2.0
            </span>
          </div>

          <button 
            onClick={onClose}
            className="w-10 h-10 rounded-2xl glass-panel-warm hover:bg-rose-500/20 hover:text-rose-300 hover:border-rose-500/40 flex items-center justify-center text-[var(--text-main)] transition-all cursor-pointer border border-[var(--border-gold-glow)] shadow-lg"
            title="Close Codex"
          >
            <X size={20} />
          </button>
        </div>

        {/* ── 1. Hero Character Profile Card ─────────────────────────── */}
        <div className="glass-panel-warm rounded-3xl p-6 md:p-8 border border-[var(--border-gold-glow)] shadow-2xl relative overflow-hidden flex flex-col md:flex-row items-center gap-6 md:gap-8">
          
          {/* Subtle Mandala Texture Background */}
          <div className="mandala-overlay w-[380px] h-[380px] opacity-20 -left-10 -top-10">
            <svg viewBox="0 0 200 200" className="w-full h-full stroke-amber-400 fill-none" strokeWidth="0.5">
              <circle cx="100" cy="100" r="90" strokeDasharray="3 4" />
              <circle cx="100" cy="100" r="70" />
            </svg>
          </div>

          {/* Portrait Icon Render */}
          <div className="relative shrink-0">
            <div className="w-28 h-28 md:w-36 md:h-36 rounded-3xl bg-gradient-to-tr from-amber-500 via-rose-500 to-violet-600 p-1 shadow-[0_0_35px_rgba(245,197,96,0.4)]">
              <div className="w-full h-full rounded-[22px] bg-slate-950 flex flex-col items-center justify-center relative overflow-hidden">
                <Bot size={54} className="text-amber-300 animate-pulse" />
                <div className="absolute bottom-2 text-[9px] font-mono tracking-widest font-bold text-amber-200">
                  AI CORE // 3D
                </div>
              </div>
            </div>
            {/* Level Edition Badge */}
            <div className="absolute -bottom-2 -right-2 px-2.5 py-1 rounded-full bg-slate-950 border border-amber-400 text-[10px] font-mono font-bold text-amber-300 shadow-md">
              LVL 2.0
            </div>
          </div>

          {/* Character Identity & Lore */}
          <div className="flex-1 text-center md:text-left space-y-2">
            <div className="flex flex-wrap items-center justify-center md:justify-start gap-2.5">
              <h1 className="text-3xl md:text-4xl font-bold font-mono tracking-wide text-[var(--text-main)]">
                KAIROS
              </h1>
              <span className="px-2.5 py-1 rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/40 text-xs font-mono font-semibold">
                NEURAL EDITION
              </span>
              <span className="px-2.5 py-1 rounded-full bg-cyan-400/20 text-cyan-300 border border-cyan-400/40 text-xs font-mono font-semibold">
                ENGLISH-ONLY TTS
              </span>
            </div>

            <p className="text-sm md:text-base text-[var(--text-muted)] leading-relaxed font-sans max-w-2xl">
              "Your personal AI companion — friendly, capable, and always listening. Designed with a blend of soft anime warmth, Indian classical grace, and retro-futuristic intelligence."
            </p>

            <div className="pt-2 flex flex-wrap items-center justify-center md:justify-start gap-4 text-xs font-mono text-[var(--text-subtle)]">
              <span className="flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-emerald-400" /> Private & Browser-Local
              </span>
              <span className="flex items-center gap-1.5">
                <Zap size={14} className="text-amber-400" /> Ultra-Low Latency (~200ms)
              </span>
              <span className="flex items-center gap-1.5">
                <Heart size={14} className="text-rose-400" /> High Empathy Rapport
              </span>
            </div>
          </div>

          {/* Affinity Dial Widget */}
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
