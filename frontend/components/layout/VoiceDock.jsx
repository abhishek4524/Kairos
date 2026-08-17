import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, SendHorizontal, Sparkles } from 'lucide-react';

export default function VoiceDock({ 
  isRecording, 
  onToggleMic, 
  onSendText, 
  status,
  activeAvatar,
  isContinuousListening = false,
  onToggleContinuousListening
}) {
  const [text, setText] = useState('');
  const [showFeedbackFlash, setShowFeedbackFlash] = useState(false);
  const prevStatusRef = useRef(status);

  // Trigger positive feedback flash when speech recognition completes (Listening -> Thinking)
  useEffect(() => {
    if (prevStatusRef.current === 'Listening' && status === 'Thinking') {
      setShowFeedbackFlash(true);
      const timer = setTimeout(() => setShowFeedbackFlash(false), 1400);
      return () => clearTimeout(timer);
    }
    prevStatusRef.current = status;
  }, [status]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (text.trim()) {
      onSendText(text);
      setText('');
      setShowFeedbackFlash(true);
      setTimeout(() => setShowFeedbackFlash(false), 1400);
    }
  };

  const isListening = status === 'Listening';
  const isSpeaking = status === 'Speaking';
  const isThinking = status === 'Thinking';
  
  return (
    <div className="relative w-[92%] max-w-2xl z-30 flex flex-col items-center gap-3">
      
      {/* Sci-Fi Waveform / Equalizer Visualizer */}
      <AnimatePresence>
        {(isListening || isSpeaking || isThinking) && (
          <motion.div 
            initial={{ opacity: 0, y: 15, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="flex items-center gap-1.5 px-6 py-2 rounded-full glass-panel border border-[var(--border-gold-glow)]"
          >
            <div className="flex items-center gap-1 h-6">
              {[...Array(16)].map((_, i) => (
                <motion.div
                  key={i}
                  className="w-1 rounded-full"
                  style={{ 
                    background: isListening 
                      ? '#06b6d4' 
                      : isThinking 
                      ? '#8b5cf6' 
                      : '#f5c560' 
                  }}
                  animate={{ 
                    height: isThinking ? ['25%', '60%', '25%'] : ['15%', '100%', '35%', '85%', '20%'] 
                  }}
                  transition={{
                    duration: isThinking ? 1.2 : 0.8 + (i % 4) * 0.2,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: i * 0.05,
                    ease: "easeInOut"
                  }}
                />
              ))}
            </div>
            <span className="text-[11px] font-mono tracking-widest uppercase text-[var(--text-main)] ml-2">
              {isListening ? 'VOICE CAPTURE ACTIVE' : isThinking ? 'PROCESSING QUERY' : 'SYNTHESIZING AUDIO'}
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Glass Dock Container */}
      <div className="w-full glass-panel-warm rounded-full p-2 md:p-2.5 flex items-center shadow-[0_12px_45px_rgba(0,0,0,0.5)] border border-[var(--border-gold-glow)] gap-2">
        
        {/* Text Input */}
        <form onSubmit={handleSubmit} className="flex-1 flex items-center h-12 md:h-13 bg-[var(--surface-hover)] rounded-full px-4 border border-[var(--border-gold-glow)] focus-within:border-amber-400 focus-within:shadow-[0_0_18px_rgba(245,197,96,0.35)] transition-all duration-300">
          <input 
            type="text" 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type a message or command ('switch to dark mode')..."
            className="w-full bg-transparent text-sm md:text-base text-[var(--text-main)] outline-none placeholder:text-[var(--text-subtle)] font-sans"
          />
          <AnimatePresence>
            {text.trim() && (
              <motion.button 
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                type="submit"
                className="ml-2 w-8 h-8 rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-violet-600 flex-center text-slate-950 font-bold shadow-lg hover:brightness-110 transition-all cursor-pointer shrink-0"
              >
                <SendHorizontal size={15} />
              </motion.button>
            )}
          </AnimatePresence>
        </form>

        {/* Continuous Listening Toggle Button */}
        <button
          type="button"
          onClick={onToggleContinuousListening}
          title={isContinuousListening ? "Continuous Listening: ON (Kavya will listen automatically)" : "Continuous Listening: OFF"}
          className={`shrink-0 w-11 h-11 md:w-12 md:h-12 rounded-full flex items-center justify-center transition-all cursor-pointer ${
            isContinuousListening
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/60 shadow-[0_0_20px_rgba(16,185,129,0.4)]'
              : 'bg-[var(--surface-hover)] text-[var(--text-muted)] border border-[var(--border-gold-glow)] hover:text-amber-300 hover:border-amber-400/40'
          }`}
        >
          <span className="text-base font-bold tracking-tight">∞</span>
        </button>

        {/* Mic Glowing Orb Button */}
        <button 
          onClick={onToggleMic}
          className="relative group shrink-0 w-13 h-13 md:w-14 md:h-14 rounded-full flex-center transition-all duration-300 cursor-pointer"
        >
          {/* 3. Positive Recognition Feedback Flash Ring (Warm Temple Gold Halo) */}
          <AnimatePresence>
            {showFeedbackFlash && (
              <motion.div 
                initial={{ scale: 0.8, opacity: 1 }}
                animate={{ scale: 1.8, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.2, ease: "easeOut" }}
                className="absolute inset-0 rounded-full border-2 border-amber-400 shadow-[0_0_30px_rgba(245,197,96,0.9)] pointer-events-none z-10"
              />
            )}
          </AnimatePresence>

          {/* Animated Pulsing Laser Rings when Recording */}
          {isRecording && (
            <>
              <div className="absolute inset-0 rounded-full border-2 border-rose-500/60 mic-laser-pulse" />
              <div className="absolute inset-0 rounded-full border border-amber-400/50 mic-laser-pulse" style={{ animationDelay: '0.4s' }} />
            </>
          )}

          {/* Button Base */}
          <div className={`
            absolute inset-0.5 rounded-full flex-center shadow-2xl transition-all duration-300
            ${isRecording 
              ? 'bg-gradient-to-br from-rose-500 via-red-600 to-rose-700 shadow-[0_0_30px_rgba(244,63,94,0.7)]' 
              : 'bg-gradient-to-br from-amber-400 via-teal-500 to-violet-600 group-hover:scale-105 shadow-[0_0_25px_rgba(245,197,96,0.45)] text-slate-950 font-bold'
            }
          `}>
            {isRecording ? <MicOff className="text-white w-5 h-5 md:w-6 md:h-6" /> : <Mic className="text-slate-950 w-5 h-5 md:w-6 md:h-6" />}
          </div>
        </button>

      </div>
    </div>
  );
}
