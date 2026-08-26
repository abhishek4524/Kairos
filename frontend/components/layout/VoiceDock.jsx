import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, SendHorizontal } from 'lucide-react';

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
      
      {/* Waveform Visualizer */}
      <AnimatePresence>
        {(isListening || isSpeaking || isThinking) && (
          <motion.div 
            initial={{ opacity: 0, y: 15, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="flex items-center gap-1.5 px-6 py-2 rounded-full glass-panel border border-blue-500/30"
          >
            <div className="flex items-center gap-1 h-6">
              {[...Array(16)].map((_, i) => (
                <motion.div
                  key={i}
                  className="w-1 rounded-full"
                  style={{ 
                    background: isListening 
                      ? '#60a5fa' 
                      : isThinking 
                      ? '#38bdf8' 
                      : '#3b82f6' 
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
            <span className="text-[11px] font-mono tracking-widest uppercase text-slate-200 ml-2">
              {isListening ? 'VOICE CAPTURE ACTIVE' : isThinking ? 'PROCESSING QUERY' : 'SYNTHESIZING AUDIO'}
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Glass Dock Container */}
      <div className="w-full glass-panel rounded-full p-2 md:p-2.5 flex items-center shadow-[0_12px_45px_rgba(0,0,0,0.6)] border border-slate-700/60 gap-2">
        
        {/* Text Input */}
        <form onSubmit={handleSubmit} className="flex-1 flex items-center h-12 md:h-13 bg-slate-900/80 rounded-full px-4 border border-slate-700/80 focus-within:border-blue-400 focus-within:shadow-[0_0_18px_rgba(59,130,246,0.3)] transition-all duration-300">
          <input 
            type="text" 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type a message or command (e.g., 'ready to work', 'open vs code')..."
            className="w-full bg-transparent text-sm md:text-base text-white outline-none placeholder:text-slate-500 font-sans"
          />
          <AnimatePresence>
            {text.trim() && (
              <motion.button 
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                type="submit"
                className="ml-2 w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-500 flex-center text-white font-bold shadow-lg transition-all cursor-pointer shrink-0"
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
          title={isContinuousListening ? "Continuous Listening: ON (Kairos will listen automatically)" : "Continuous Listening: OFF"}
          className={`shrink-0 w-11 h-11 md:w-12 md:h-12 rounded-full flex items-center justify-center transition-all cursor-pointer ${
            isContinuousListening
              ? 'bg-blue-600 text-white border border-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.4)]'
              : 'bg-slate-900/80 text-slate-400 border border-slate-700 hover:text-blue-300 hover:border-blue-500/40'
          }`}
        >
          <span className="text-base font-bold tracking-tight">∞</span>
        </button>

        {/* Mic Glowing Button */}
        <button 
          onClick={onToggleMic}
          className="relative group shrink-0 w-13 h-13 md:w-14 md:h-14 rounded-full flex-center transition-all duration-300 cursor-pointer"
        >
          {/* Recognition Feedback Flash Ring */}
          <AnimatePresence>
            {showFeedbackFlash && (
              <motion.div 
                initial={{ scale: 0.8, opacity: 1 }}
                animate={{ scale: 1.8, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.2, ease: "easeOut" }}
                className="absolute inset-0 rounded-full border-2 border-blue-400 shadow-[0_0_30px_rgba(59,130,246,0.8)] pointer-events-none z-10"
              />
            )}
          </AnimatePresence>

          {/* Animated Pulsing Laser Rings when Recording */}
          {isRecording && (
            <>
              <div className="absolute inset-0 rounded-full border-2 border-red-500/60 mic-laser-pulse" />
              <div className="absolute inset-0 rounded-full border border-blue-400/50 mic-laser-pulse" style={{ animationDelay: '0.4s' }} />
            </>
          )}

          {/* Button Base */}
          <div className={`
            absolute inset-0.5 rounded-full flex-center shadow-2xl transition-all duration-300
            ${isRecording 
              ? 'bg-red-600 shadow-[0_0_30px_rgba(239,68,68,0.7)]' 
              : 'bg-blue-600 hover:bg-blue-500 group-hover:scale-105 shadow-[0_0_25px_rgba(59,130,246,0.5)] text-white font-bold'
            }
          `}>
            {isRecording ? <MicOff className="text-white w-5 h-5 md:w-6 md:h-6" /> : <Mic className="text-white w-5 h-5 md:w-6 md:h-6" />}
          </div>
        </button>

      </div>
    </div>
  );
}
