import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Settings, History, Sun, Moon } from 'lucide-react';

function Bubble({ role, text, emotion, activeAvatar }) {
  const isUser = role === 'user';
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className={`flex flex-col mb-4 ${isUser ? 'items-end' : 'items-start'}`}
    >
      {!isUser && emotion && (
        <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted mb-1 ml-2">
          {emotion}
        </span>
      )}
      <div 
        className={`max-w-[85%] px-5 py-3 text-sm md:text-base leading-relaxed ${
          isUser 
            ? 'bg-gradient-to-br from-primary to-accent text-white rounded-[24px_24px_4px_24px] shadow-[0_4px_20px_rgba(147,51,234,0.3)]'
            : 'assistant-bubble bg-[var(--surface)] backdrop-blur-md text-[var(--text-main)] rounded-[24px_24px_24px_4px] border border-[var(--border-glass)] shadow-lg'
        }`}
        style={{
          boxShadow: !isUser && activeAvatar ? `0 4px 20px ${activeAvatar.accent}15` : undefined,
          borderColor: !isUser && activeAvatar ? `${activeAvatar.accent}40` : undefined,
        }}
      >
        {text}
      </div>
    </motion.div>
  );
}

export default function ChatPanel({ 
  messages, 
  status, 
  emotion, 
  activeAvatar,
  preferredLanguage,
  onLanguageChange,
  theme,
  onThemeToggle,
  onHistoryClick
}) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages, status]);

  return (
    <div className="w-full md:w-[380px] lg:w-[420px] flex flex-col h-full bg-surface/40 backdrop-blur-2xl border-l border-border-glass z-20 shrink-0">
      
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-glass)] bg-[var(--surface)]">
        
        {/* Status Pill */}
        <div className="status-pill flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface)] border border-[var(--border-glass)]">
          <div className={`w-2 h-2 rounded-full ${
            status === 'Listening' ? 'bg-danger animate-pulse' :
            status === 'Thinking' ? 'bg-accent animate-pulse' :
            status === 'Speaking' ? 'bg-success animate-pulse' : 'bg-gray-500'
          }`} style={{
            boxShadow: `0 0 10px ${
              status === 'Listening' ? '#e11d48' :
              status === 'Thinking' ? '#9333ea' :
              status === 'Speaking' ? '#10b981' : 'transparent'
            }`
          }} />
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
            {status === 'Thinking' ? (activeAvatar ? `${activeAvatar.name} is thinking...` : 'Thinking...') : status}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <select 
            value={preferredLanguage}
            onChange={e => onLanguageChange(e.target.value)}
            className="bg-[var(--surface)] border border-[var(--border-glass)] text-[var(--text-main)] text-xs font-bold rounded-lg px-2 py-1.5 outline-none cursor-pointer hover:bg-[var(--surface-hover)] transition-colors"
          >
            <option value="en">EN</option>
            <option value="hi">HI</option>
            <option value="ur">UR</option>
            <option value="pa">PA</option>
          </select>

          <button onClick={onThemeToggle} className="p-1.5 rounded-lg bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--text-main)] transition-colors border border-transparent hover:border-[var(--border-glass)]">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto chat-scroll p-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-text-muted gap-4 opacity-70">
            <MessageSquare size={48} strokeWidth={1} />
            <p className="text-sm text-center">Say hello to start the conversation.</p>
          </div>
        )}
        
        <AnimatePresence>
          {messages.map((msg, i) => (
            <Bubble 
              key={i} 
              role={msg.role} 
              text={msg.text} 
              emotion={msg.emotion} 
              activeAvatar={activeAvatar} 
            />
          ))}
          {status === 'Thinking' && (
            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-start mb-4"
            >
              <div className="assistant-bubble bg-[var(--surface)] backdrop-blur-md rounded-[24px_24px_24px_4px] px-5 py-4 border border-[var(--border-glass)]">
                <div className="flex gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-gray-400 thinking-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-gray-400 thinking-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-gray-400 thinking-dot" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
