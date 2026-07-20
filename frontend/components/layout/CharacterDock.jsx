import React from 'react';
import { Sparkles, Plus, History } from 'lucide-react';
import { motion } from 'framer-motion';

export default function CharacterDock({ avatars, selectedAvatar, onSelectAvatar, onNewChat, onToggleHistory }) {
  return (
    <div className="w-full md:w-[120px] lg:w-[140px] flex md:flex-col items-center p-3 md:p-4 border-b md:border-b-0 md:border-r border-border-glass bg-surface/50 backdrop-blur-xl z-20 shrink-0 overflow-x-auto md:overflow-y-auto no-scrollbar gap-4 md:gap-6">
      
      {/* Brand Logo (Desktop) */}
      <div className="hidden md:flex flex-col items-center gap-2 mb-2 mt-2">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary to-accent p-1 shadow-[0_0_20px_rgba(147,51,234,0.5)] flex-center">
          <img src="/nanban.png" alt="Nanban" className="w-full h-full object-cover rounded-xl" />
        </div>
        <span className="font-bold text-xs bg-gradient-to-r from-cyan-400 via-purple-500 to-pink-500 text-transparent bg-clip-text">
          NANBAN
        </span>
      </div>

      {/* Action Buttons (New Chat / History) */}
      <div className="flex md:flex-col gap-3 md:mb-4 border-r md:border-r-0 md:border-b border-white/10 pr-4 md:pr-0 md:pb-4 shrink-0">
        <button onClick={onNewChat} className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-300 transition-colors relative group">
          <Plus size={20} />
          <span className="absolute left-14 hidden md:group-hover:block bg-black/80 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50">New Chat</span>
        </button>
        <button onClick={onToggleHistory} className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-300 transition-colors relative group">
          <History size={20} />
          <span className="absolute left-14 hidden md:group-hover:block bg-black/80 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50">History</span>
        </button>
      </div>

      {/* Character List */}
      <div className="flex md:flex-col gap-4 md:gap-6 w-full items-center flex-1">
        {avatars.map((av, idx) => {
          const isSelected = selectedAvatar === av.file;
          
          return (
            <motion.div 
              key={av.id}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onSelectAvatar(av.file)}
              className="relative flex flex-col items-center gap-2 cursor-pointer group"
            >
              {/* Outer Ring for Selected */}
              {isSelected && (
                <motion.div 
                  layoutId="activeRing"
                  className="absolute -inset-1.5 rounded-full border border-primary/50 shadow-[0_0_15px_rgba(79,70,229,0.5)] z-0"
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                />
              )}
              
              {/* Avatar Circle */}
              <div 
                className={`relative w-14 h-14 md:w-16 md:h-16 rounded-full flex-center text-2xl shadow-lg transition-all z-10`}
                style={{
                  background: isSelected ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.03)',
                  border: `2px solid ${isSelected ? av.accent : 'rgba(255,255,255,0.1)'}`,
                }}
              >
                {/* Subtle inner glow */}
                <div 
                  className="absolute inset-0 rounded-full opacity-50" 
                  style={{ background: `radial-gradient(circle at 50% 0%, ${av.accent}40, transparent 70%)` }} 
                />
                <span className="relative z-10 transition-transform group-hover:scale-110">{av.emoji}</span>
              </div>
              
              {/* Name Tag */}
              <span className={`text-[10px] md:text-xs font-bold tracking-wide transition-colors ${isSelected ? 'text-white' : 'text-text-muted group-hover:text-gray-300'}`}>
                {av.name}
              </span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
