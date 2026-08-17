import React, { useMemo, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import AvatarCanvas from '../../AvatarCanvas';
import { Maximize2, Minimize2, Heart, Sparkles, Flame, Lightbulb, Armchair, BookOpen, Zap } from 'lucide-react';

const IDLE_MICRO_GESTURES = [
  'head_tilt',
  'nodding',
  'coySmile',
  'attentive',
  'hair_touch',
  'sara_gentle',
  'look_nails',
  'kavya_open'
];

export default function HeroAvatar({ 
  audioPlayEvent, 
  emotion, 
  gestureOverride, 
  selectedAvatar = 'avatar.vrm', 
  zoomLevel, 
  onZoomChange, 
  theme = 'dark',
  userRapportEnergy = 0.35,
  status = 'Idle',
  lampOn = true,
  onToggleLamp,
  interactionPose = 'standing',
  onToggleSit,
  onToggleRead,
  onJump,
  transientGesture = null
}) {
  const [idleMicroGesture, setIdleMicroGesture] = useState(null);
  const [idleMicroEmotion, setIdleMicroEmotion] = useState(null);

  const isListening = status === 'Listening';
  const isThinking = status === 'Thinking';
  const isSpeaking = status === 'Speaking';
  const isIdle = status === 'Idle';

  // ── 2. Idle Reaction Micro-Animations ──────────────────────────────────────
  // Periodically triggers subtle companion-like reactions (e.g. curious head tilt, gentle smile)
  useEffect(() => {
    if (!isIdle) {
      setIdleMicroGesture(null);
      setIdleMicroEmotion(null);
      return;
    }

    const triggerReaction = () => {
      const chosenGesture = IDLE_MICRO_GESTURES[Math.floor(Math.random() * IDLE_MICRO_GESTURES.length)];
      const chosenEmotion = Math.random() > 0.4 ? 'happy' : 'attentive';

      setIdleMicroGesture(chosenGesture);
      setIdleMicroEmotion(chosenEmotion);

      // Reset back to relaxed idle after 3.8 seconds
      setTimeout(() => {
        setIdleMicroGesture(null);
        setIdleMicroEmotion(null);
      }, 3800);
    };

    // Random interval between 11s and 18s
    const randomIntervalMs = Math.floor(Math.random() * 7000) + 11000;
    const interval = setInterval(triggerReaction, randomIntervalMs);

    return () => clearInterval(interval);
  }, [isIdle]);

  const effectiveGesture = gestureOverride || idleMicroGesture;
  const effectiveEmotion = emotion !== 'neutral' ? emotion : (idleMicroEmotion || 'neutral');

  const isWarmState = effectiveEmotion === 'happy' || effectiveEmotion === 'comforting' || userRapportEnergy > 0.55;
  const affinityPercentage = Math.round(Math.min(100, Math.max(25, userRapportEnergy * 100)));

  // Generate 12 soft floating light motes / golden petal specks
  const motes = useMemo(() => [
    { id: 1, left: '12%', top: '72%', size: 5, delay: '0s', duration: '14s' },
    { id: 2, left: '22%', top: '82%', size: 4, delay: '3s', duration: '18s' },
    { id: 3, left: '35%', top: '76%', size: 6, delay: '7s', duration: '16s' },
    { id: 4, left: '48%', top: '86%', size: 3, delay: '2s', duration: '21s' },
    { id: 5, left: '58%', top: '68%', size: 5, delay: '5s', duration: '15s' },
    { id: 6, left: '70%', top: '80%', size: 6, delay: '9s', duration: '17s' },
    { id: 7, left: '82%', top: '74%', size: 4, delay: '1s', duration: '19s' },
    { id: 8, left: '92%', top: '84%', size: 5, delay: '6s', duration: '13s' },
    { id: 9, left: '28%', top: '65%', size: 3, delay: '11s', duration: '22s' },
    { id: 10, left: '64%', top: '88%', size: 4, delay: '4s', duration: '16s' },
    { id: 11, left: '40%', top: '92%', size: 5, delay: '8s', duration: '15s' },
    { id: 12, left: '78%', top: '66%', size: 3, delay: '10s', duration: '20s' },
  ], []);

  return (
    <div className="relative flex-1 flex flex-col items-center justify-center overflow-hidden w-full h-full">
      {/* Sci-Fi Grid Overlay */}
      <div className="animated-grid-bg" />

      {/* ── Sacred Geometry / Indian Classical Mandala Halo (Hypnotic subtle texture) ── */}
      <div className="mandala-overlay w-[480px] h-[480px] md:w-[700px] md:h-[700px]">
        <svg viewBox="0 0 400 400" className="w-full h-full stroke-amber-300 fill-none" strokeWidth="0.75">
          <circle cx="200" cy="200" r="185" strokeDasharray="3 6" opacity="0.6" />
          <circle cx="200" cy="200" r="170" strokeDasharray="8 4" opacity="0.4" />
          <circle cx="200" cy="200" r="150" opacity="0.5" />
          
          {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((deg) => (
            <g key={deg} transform={`rotate(${deg} 200 200)`}>
              <ellipse cx="200" cy="130" rx="16" ry="38" opacity="0.45" />
              <path d="M 200 60 Q 215 110 200 150 Q 185 110 200 60" opacity="0.35" />
              <circle cx="200" cy="80" r="4" fill="currentColor" fillOpacity="0.2" />
            </g>
          ))}

          <polygon points="200,90 295,255 105,255" opacity="0.35" />
          <polygon points="200,310 295,145 105,145" opacity="0.35" />
          <polygon points="200,105 282,248 118,248" opacity="0.25" transform="rotate(30 200 200)" />
          <polygon points="200,295 282,152 118,152" opacity="0.25" transform="rotate(30 200 200)" />

          <circle cx="200" cy="200" r="45" opacity="0.6" strokeDasharray="2 3" />
          <circle cx="200" cy="200" r="22" opacity="0.8" />
        </svg>
      </div>

      {/* ── 5. Soft Particle Drift / Golden Light Motes & Petals ── */}
      {motes.map((mote) => (
        <div
          key={mote.id}
          className="particle-mote"
          style={{
            left: mote.left,
            top: mote.top,
            width: `${mote.size}px`,
            height: `${mote.size}px`,
            animationDelay: mote.delay,
            animationDuration: mote.duration,
          }}
        />
      ))}

      {/* Dynamic atmospheric ambient aura (Cyan / Violet / Emerald / Warm Gold-Peach) */}
      <div 
        className={`ambient-glow w-[380px] h-[380px] md:w-[520px] md:h-[520px] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 ${
          isListening ? 'bg-cyan-500/30' :
          isThinking ? 'bg-violet-600/35' :
          isSpeaking ? 'bg-emerald-500/25' :
          isWarmState ? 'bg-amber-500/25' :
          'bg-cyan-600/15'
        }`}
      />

      {/* Secondary warm accent orb */}
      <div 
        className={`ambient-glow w-[280px] h-[280px] top-1/3 left-1/3 -translate-x-1/2 -translate-y-1/2 ${
          isListening ? 'bg-sky-400/25' :
          isThinking ? 'bg-fuchsia-600/30' :
          isSpeaking ? 'bg-teal-400/20' :
          isWarmState ? 'bg-orange-500/25' :
          'bg-amber-500/15'
        }`}
      />

      {/* ── 3. Hybrid Rings: "Ancient Meets Future" (Tech Cyan + Classical Temple Gold) ── */}
      <div className="relative z-10 w-full h-full flex items-center justify-center">
        {/* Orbit Rings Container */}
        <div className="absolute w-[340px] h-[340px] md:w-[500px] md:h-[500px] pointer-events-none rounded-full flex items-center justify-center">
          
          {/* Ring 1: Cybernetic Precision Holo-Ring (Cyan, Fast Clockwise Rotation) */}
          <div 
            className="holo-ring holo-ring-outer border-dashed transition-all duration-700"
            style={{
              borderColor: isListening ? 'rgba(6, 182, 212, 0.65)' : 'rgba(6, 182, 212, 0.35)',
              boxShadow: isListening ? '0 0 15px rgba(6, 182, 212, 0.3)' : 'none'
            }}
          />

          {/* Ring 2: Classical Indian Temple-Arch & Lotus Motif Ring (Gold, Slow Counter-Clockwise Rotation) */}
          <div className="absolute inset-4 rounded-full pointer-events-none animate-[mandala-spin-rev_70s_linear_infinite]">
            <svg viewBox="0 0 300 300" className="w-full h-full stroke-amber-400/50 fill-none" strokeWidth="0.8">
              <circle cx="150" cy="150" r="142" strokeDasharray="5 3" />
              <circle cx="150" cy="150" r="134" stroke="rgba(245, 197, 96, 0.25)" />
              {/* 16 Arch/Petal Nodes around perimeter */}
              {[0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 247.5, 270, 292.5, 315, 337.5].map((deg) => (
                <g key={deg} transform={`rotate(${deg} 150 150)`}>
                  <path d="M 144 10 Q 150 2 156 10 Q 150 16 144 10" stroke="rgba(245, 197, 96, 0.7)" fill="rgba(245, 197, 96, 0.15)" />
                  <circle cx="150" cy="10" r="1.5" fill="#f5c560" />
                </g>
              ))}
            </svg>
          </div>

        </div>

        {/* 3D Canvas */}
        <div className="relative w-full h-full">
          <AvatarCanvas 
            audioPlayEvent={audioPlayEvent} 
            emotion={effectiveEmotion} 
            gestureOverride={effectiveGesture} 
            avatarUrl={`/${selectedAvatar}`} 
            theme={theme} 
            zoomLevel={zoomLevel} 
            userRapportEnergy={userRapportEnergy}
            lampOn={lampOn}
            interactionPose={interactionPose}
            transientGesture={transientGesture}
          />
        </div>
      </div>
      
      {/* Cinematic Vignette */}
      <div className="avatar-vignette pointer-events-none" />

      {/* ── 4. Stylized Anime Character Nameplate (RPG Companion Style) ── */}
      <motion.div 
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute top-4 left-4 md:top-6 md:left-6 z-20 flex flex-col glass-panel-warm px-4 py-2.5 rounded-2xl border border-[var(--border-gold-glow)] shadow-2xl backdrop-blur-xl"
      >
        {/* Top: Icon + Name */}
        <div className="flex items-center gap-2">
          {/* Sparkling Lotus/Star jewel */}
          <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-amber-400 to-rose-400 flex items-center justify-center text-slate-950 shadow-[0_0_10px_rgba(245,197,96,0.6)]">
            <Sparkles size={11} className="animate-spin" style={{ animationDuration: '8s' }} />
          </div>

          <span className="font-bold tracking-widest text-sm md:text-base font-mono bg-gradient-to-r from-amber-200 via-amber-300 to-amber-500 bg-clip-text text-transparent">
            KAVYA
          </span>

          <span className="text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-300 border border-amber-400/30">
            COMPANION AI
          </span>
        </div>

        {/* Decorative Ornamental Gold Underline */}
        <div className="flex items-center gap-1 my-1 opacity-70">
          <div className="h-[1px] flex-1 bg-gradient-to-r from-transparent via-amber-400 to-transparent" />
          <div className="w-1.5 h-1.5 rotate-45 bg-amber-400" />
          <div className="h-[1px] flex-1 bg-gradient-to-r from-transparent via-amber-400 to-transparent" />
        </div>

        {/* Bottom: Subtitle Status */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono tracking-wider text-[var(--text-muted)]">
          <div className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
            isListening ? 'bg-cyan-400 shadow-[0_0_8px_#06b6d4] animate-pulse' :
            isThinking ? 'bg-violet-400 shadow-[0_0_8px_#8b5cf6] animate-pulse' :
            isSpeaking ? 'bg-emerald-400 shadow-[0_0_8px_#10b981] animate-pulse' :
            isWarmState ? 'bg-amber-400 shadow-[0_0_8px_#f5c560]' :
            'bg-amber-300/60'
          }`} />
          <span className="uppercase text-[var(--text-main)] font-semibold">
            {isIdle ? (idleMicroGesture ? `Attentive // ${idleMicroGesture.replace(/_/g, ' ')}` : (interactionPose === 'seated' ? 'Ready // Seated' : 'Ready // Attentive')) : status}
          </span>
        </div>
      </motion.div>

      {/* ── 1. Mood / Affection Indicator Widget ── */}
      <motion.div 
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        title={`Affinity Level: ${affinityPercentage}%`}
        className="absolute top-22 left-4 md:top-24 md:left-6 z-20 flex items-center gap-2 px-3 py-1.5 rounded-full glass-panel-warm border border-[var(--border-gold-glow)] shadow-lg cursor-default"
      >
        <motion.div
          animate={{ scale: [1, 1.25, 1] }}
          transition={{
            duration: isWarmState ? 1.2 : 2.5,
            repeat: Infinity,
            ease: "easeInOut"
          }}
          className={`flex items-center justify-center ${
            isWarmState ? 'text-amber-400 drop-shadow-[0_0_8px_rgba(245,197,96,0.8)]' : 'text-rose-400 drop-shadow-[0_0_6px_rgba(244,63,94,0.6)]'
          }`}
        >
          <Heart size={13} fill="currentColor" />
        </motion.div>
        
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-mono font-bold text-amber-300">
            {affinityPercentage}%
          </span>
          <span className="text-[9px] font-mono text-[var(--text-subtle)] uppercase">
            {affinityPercentage > 75 ? 'Rapport: High' : 'Rapport: Active'}
          </span>
        </div>
      </motion.div>

      {/* Floating Controls (Top-Right: Sit Switch + Lamp Switch + Zoom) */}
      <div className="absolute top-4 right-4 md:top-6 md:right-6 z-20 flex items-center gap-2 md:gap-3">
        {/* Sit on Chair Interactive Toggle Button */}
        {onToggleSit && (
          <button
            onClick={onToggleSit}
            title={interactionPose === 'seated' ? "Stand up" : "Sit on chair"}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-full transition-all duration-300 border text-[11px] font-mono cursor-pointer shadow-lg ${
              interactionPose === 'seated' 
                ? 'bg-cyan-500/25 border-cyan-400/60 text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.35)]' 
                : 'glass-panel text-slate-400 hover:text-white border-white/10'
            }`}
          >
            <Armchair size={13} className={interactionPose === 'seated' ? 'text-cyan-300 fill-cyan-300' : 'text-slate-400'} />
            <span className="font-semibold hidden sm:inline">{interactionPose === 'seated' ? 'SEATED' : 'SIT DOWN'}</span>
          </button>
        )}

        {/* Read Book Interactive Toggle Button */}
        {onToggleRead && (
          <button
            onClick={onToggleRead}
            title={interactionPose === 'reading' ? "Put book down" : "Read a book"}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-full transition-all duration-300 border text-[11px] font-mono cursor-pointer shadow-lg ${
              interactionPose === 'reading'
                ? 'bg-violet-500/25 border-violet-400/60 text-violet-300 shadow-[0_0_15px_rgba(139,92,246,0.35)]'
                : 'glass-panel text-slate-400 hover:text-white border-white/10'
            }`}
          >
            <BookOpen size={13} className={interactionPose === 'reading' ? 'text-violet-300' : 'text-slate-400'} />
            <span className="font-semibold hidden sm:inline">{interactionPose === 'reading' ? 'READING' : 'READ'}</span>
          </button>
        )}

        {/* Jump Button */}
        {onJump && (
          <button
            onClick={onJump}
            title="Jump!"
            className="flex items-center gap-1.5 px-3 py-2 rounded-full transition-all duration-300 border text-[11px] font-mono cursor-pointer shadow-lg glass-panel text-slate-400 hover:text-emerald-300 hover:border-emerald-400/40 border-white/10"
          >
            <Zap size={13} className="text-slate-400" />
            <span className="font-semibold hidden sm:inline">JUMP</span>
          </button>
        )}

        {/* Desk Lamp Interactive Toggle Button */}
        {onToggleLamp && (
          <button
            onClick={onToggleLamp}
            title={lampOn ? "Turn off Desk Lamp" : "Turn on Desk Lamp"}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-full transition-all duration-300 border text-[11px] font-mono cursor-pointer shadow-lg ${
              lampOn 
                ? 'bg-amber-500/25 border-amber-400/60 text-amber-300 shadow-[0_0_15px_rgba(245,197,96,0.35)]' 
                : 'glass-panel text-slate-400 hover:text-white border-white/10'
            }`}
          >
            <Lightbulb size={13} className={lampOn ? 'text-amber-300 fill-amber-300 animate-pulse' : 'text-slate-400'} />
            <span className="font-semibold hidden sm:inline">{lampOn ? 'LAMP ON' : 'LAMP OFF'}</span>
          </button>
        )}

        {/* Zoom Slider */}
        <div className="flex items-center gap-2 md:gap-3 px-3 md:px-4 py-2 rounded-full glass-panel border border-[var(--border-gold-glow)] shadow-lg">
          <Minimize2 size={13} className="text-[var(--text-muted)]" />
          <input
            type="range"
            min="0" max="100"
            value={zoomLevel}
            onChange={(e) => onZoomChange(parseFloat(e.target.value))}
            className="w-20 md:w-28 accent-amber-400 cursor-pointer h-1 rounded-full appearance-none bg-white/10"
          />
          <Maximize2 size={13} className="text-[var(--text-muted)]" />
        </div>
      </div>
    </div>
  );
}
