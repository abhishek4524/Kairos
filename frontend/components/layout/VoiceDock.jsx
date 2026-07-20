import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, SendHorizontal } from 'lucide-react';

export default function VoiceDock({ 
  isRecording, 
  onToggleMic, 
  onSendText, 
  status,
  activeAvatar 
}) {
  const [text, setText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (text.trim()) {
      onSendText(text);
      setText('');
    }
  };

  const isListening = status === 'Listening';
  
  return (
    <div className="relative w-[90%] max-w-2xl z-30 flex flex-col items-center gap-4">
      
      {/* Waveform / Visualizer (Mock for UI purpose, could be hooked to real data) */}
      <AnimatePresence>
        {(isListening || status === 'Speaking') && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="flex items-center gap-1.5 h-12"
          >
            {[...Array(12)].map((_, i) => (
              <motion.div
                key={i}
                className="w-1.5 rounded-full"
                style={{ 
                  background: isListening ? '#f43f5e' : (activeAvatar?.accent || '#8b5cf6') 
                }}
                animate={{ 
                  height: ['20%', '80%', '40%', '100%', '30%'] 
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  repeatType: "mirror",
                  delay: i * 0.1,
                  ease: "easeInOut"
                }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Dock Container */}
      <div className="w-full glass-panel rounded-full p-2 flex items-center shadow-[0_10px_40px_rgba(0,0,0,0.5)] border-t border-white/20">
        
        {/* Text Input */}
        <form onSubmit={handleSubmit} className="flex-1 flex items-center h-12 md:h-14 bg-white/5 rounded-full px-4 border border-white/5 focus-within:border-primary/50 transition-colors mr-2">
          <input 
            type="text" 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type a message..."
            className="w-full bg-transparent text-sm md:text-base text-gray-200 outline-none placeholder:text-gray-500"
          />
          <AnimatePresence>
            {text.trim() && (
              <motion.button 
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                type="submit"
                className="ml-2 w-8 h-8 rounded-full bg-primary flex-center text-white shadow-lg hover:bg-primary-hover transition-colors"
              >
                <SendHorizontal size={16} />
              </motion.button>
            )}
          </AnimatePresence>
        </form>

        {/* Mic Button */}
        <button 
          onClick={onToggleMic}
          className="relative group shrink-0 w-14 h-14 md:w-16 md:h-16 rounded-full flex-center transition-all duration-300"
        >
          {/* Animated Background Rings */}
          {isRecording && (
            <>
              <div className="absolute inset-0 rounded-full border-2 border-danger/40 animate-[ping_1.5s_cubic-bezier(0,0,0.2,1)_infinite]" />
              <div className="absolute inset-0 rounded-full border border-danger/20 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite_0.3s]" />
            </>
          )}

          {/* Button Base */}
          <div className={`
            absolute inset-1 rounded-full flex-center shadow-xl transition-all duration-300
            ${isRecording 
              ? 'bg-gradient-to-br from-rose-500 to-rose-700 shadow-[0_0_30px_rgba(225,29,72,0.6)]' 
              : 'bg-gradient-to-br from-primary to-accent hover:scale-105 shadow-[0_0_20px_rgba(79,70,229,0.4)]'
            }
          `}>
            {isRecording ? <MicOff className="text-white w-6 h-6" /> : <Mic className="text-white w-6 h-6" />}
          </div>
        </button>

      </div>
    </div>
  );
}
