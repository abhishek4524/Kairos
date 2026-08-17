import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Search, Trash2, MessageSquare, AlertCircle } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function HistoryList({ userId, onSelectSession, currentSessionId }) {
  const [sessions, setSessions] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchSessions = () => {
    setLoading(true);
    fetch(`${API_BASE}/api/sessions?user_id=${encodeURIComponent(userId)}`)
      .then(res => res.json())
      .then(data => {
        setSessions(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchSessions();
  }, [userId]);

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation session?')) return;

    try {
      await fetch(`${API_BASE}/api/history/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    } catch (err) {
      alert('Failed to delete session: ' + err.message);
    }
  };

  const filteredSessions = sessions.filter(s => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (s.preview || '').toLowerCase().includes(q) || (s.session_id || '').toLowerCase().includes(q);
  });

  return (
    <div className="flex flex-col gap-3">
      {/* Search Bar */}
      <div className="relative mb-1">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          type="text"
          placeholder="Search conversation history..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-9 pr-4 py-2 rounded-xl glass-panel text-xs font-mono text-[var(--text-main)] border border-[var(--border-gold-glow)] outline-none focus:border-amber-400 transition-all placeholder:text-[var(--text-subtle)]"
        />
      </div>

      {/* Session Cards List */}
      <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto pr-1">
        <AnimatePresence>
          {filteredSessions.map(s => {
            const isCurrent = s.session_id === currentSessionId;
            return (
              <motion.div
                key={s.session_id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                onClick={() => onSelectSession(s.session_id)}
                className={`group text-left p-3 rounded-2xl transition-all cursor-pointer border flex items-center justify-between gap-3 ${
                  isCurrent 
                    ? 'bg-amber-400/15 border-amber-400/60 shadow-[0_0_15px_rgba(245,197,96,0.15)]' 
                    : 'glass-panel-warm border-[var(--border-gold-glow)] hover:border-amber-400/40'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-[var(--text-main)] font-semibold text-xs truncate font-sans">
                    {s.preview || 'Conversation Stream'}
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--text-subtle)] mt-1">
                    <Clock size={10} />
                    <span>{new Date(s.created_at * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>

                <button
                  onClick={(e) => handleDeleteSession(e, s.session_id)}
                  title="Delete Session"
                  className="p-1.5 rounded-lg opacity-60 group-hover:opacity-100 hover:bg-rose-500/20 hover:text-rose-400 text-[var(--text-muted)] transition-all cursor-pointer shrink-0"
                >
                  <Trash2 size={13} />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {filteredSessions.length === 0 && !loading && (
          <div className="text-[var(--text-subtle)] text-xs font-mono text-center py-10 opacity-70">
            {searchQuery ? 'NO MATCHING SESSIONS FOUND.' : 'NO ARCHIVED SESSIONS DETECTED.'}
          </div>
        )}
      </div>
    </div>
  );
}
