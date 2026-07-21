import React from 'react';
import { Plus, History } from 'lucide-react';
import { motion } from 'framer-motion';

// Use character portrait PNGs directly from /public/
const getCharPortrait = (avatar) => `/${avatar.bgName}.png`;

export default function CharacterDock({ avatars, selectedAvatar, onSelectAvatar, onNewChat, onToggleHistory, theme = 'dark' }) {
  return (
    <div className="w-full md:w-[120px] lg:w-[140px] flex md:flex-col items-center p-3 md:p-4 border-b md:border-b-0 md:border-r border-border-glass bg-surface/55 backdrop-blur-2xl z-20 shrink-0 overflow-x-auto md:overflow-y-auto no-scrollbar gap-4 md:gap-6 shadow-[12px_0_40px_rgba(0,0,0,0.18)]">
      <div className="hidden md:flex flex-col items-center gap-2 mb-2 mt-2">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary via-secondary to-accent p-1 shadow-[0_0_22px_rgba(14,165,233,0.36)] flex-center">
          <img src="/nanban.png" alt="Nanban" className="w-full h-full object-cover rounded-xl" />
        </div>
        <span className="brand-font font-black text-xs tracking-[0.18em] bg-gradient-to-r from-cyan-300 via-fuchsia-300 to-amber-200 text-transparent bg-clip-text">
          NANBAN
        </span>
      </div>

      <div className="flex md:flex-col gap-3 md:mb-4 border-r md:border-r-0 md:border-b border-[var(--border-glass)] pr-4 md:pr-0 md:pb-4 shrink-0">
        <button onClick={onNewChat} aria-label="New chat" className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-[var(--surface)] hover:bg-[var(--surface-hover)] active:scale-95 flex items-center justify-center text-[var(--text-main)] transition-all duration-200 relative group border border-[var(--border-glass)]">
          <Plus size={20} />
          <span className="absolute left-14 hidden md:group-hover:block bg-black/80 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50">New Chat</span>
        </button>
        <button onClick={onToggleHistory} aria-label="History" className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-[var(--surface)] hover:bg-[var(--surface-hover)] active:scale-95 flex items-center justify-center text-[var(--text-main)] transition-all duration-200 relative group border border-[var(--border-glass)]">
          <History size={20} />
          <span className="absolute left-14 hidden md:group-hover:block bg-black/80 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50">History</span>
        </button>
      </div>

      <div className="flex md:flex-col gap-4 md:gap-6 w-full items-center flex-1">
        {avatars.map((av) => {
          const isSelected = selectedAvatar === av.file;
          return (
            <motion.button
              key={av.id}
              type="button"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onSelectAvatar(av.file)}
              className="relative flex flex-col items-center gap-2 cursor-pointer group outline-none"
              aria-label={`Select ${av.name}`}
            >
              {isSelected && (
                <motion.div
                  layoutId="activeRing"
                  className="absolute -inset-1.5 rounded-full border z-0"
                  style={{ borderColor: `${av.accent}aa`, boxShadow: `0 0 18px ${av.accent}88` }}
                  transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                />
              )}

              <div
                className="char-avatar-ring relative w-14 h-14 md:w-16 md:h-16 rounded-full overflow-hidden flex-center shadow-lg transition-all duration-300 z-10 border-2 bg-[var(--surface)]"
                style={{
                  borderColor: isSelected ? av.accent : 'var(--border-glass)',
                  boxShadow: isSelected ? `0 0 22px ${av.accent}70` : `0 8px 24px ${av.accent}20`,
                }}
              >
                {/* Character portrait PNG — object-top shows face */}
                <img
                  src={getCharPortrait(av)}
                  alt={av.name}
                  className="absolute inset-0 w-full h-full object-cover object-top scale-110 transition-transform duration-300 group-hover:scale-125"
                />
                {/* Subtle gradient overlay for depth */}
                <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/30" />
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ background: `radial-gradient(circle at 50% 0%, ${av.accent}44, transparent 70%)` }} />
              </div>

              <span className={`text-[10px] md:text-xs font-bold tracking-wide transition-colors ${isSelected ? 'text-[var(--text-main)]' : 'text-[var(--text-muted)] group-hover:text-[var(--text-main)]'}`}>
                {av.name}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}