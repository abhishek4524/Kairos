import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Settings, User, Mic, Volume2, Globe, Shield, Trash2, Download, 
  Check, X, RefreshCw, Sparkles, Terminal, Code, Youtube, MessageSquare, 
  Sliders, Moon, Sun, AlertTriangle, Eye
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function SettingsModal({ 
  onClose, 
  theme = 'dark',
  preferredLanguage = 'en',
  onLanguageChange,
  vadSensitivity = 'medium',
  onVadSensitivityChange,
  isContinuousListening = false,
  onToggleContinuousListening,
  userId,
  onOpenMemory
}) {
  const [activeTab, setActiveTab] = useState('general');
  const [assistantName, setAssistantName] = useState(() => localStorage.getItem('kavya_assistant_name') || 'Kairos');
  const [autoGreeting, setAutoGreeting] = useState(() => localStorage.getItem('kavya_auto_greeting') !== 'false');
  
  const [memoryStats, setMemoryStats] = useState({ facts: 0, docs: 0 });
  const [saveToast, setSaveToast] = useState(false);
  const [clearStatus, setClearStatus] = useState('');

  useEffect(() => {
    if (userId) {
      Promise.all([
        fetch(`${API_BASE}/api/memory/facts/${encodeURIComponent(userId)}`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/memory/documents/${encodeURIComponent(userId)}`).then(r => r.json()).catch(() => [])
      ]).then(([facts, docs]) => {
        setMemoryStats({
          facts: Array.isArray(facts) ? facts.length : 0,
          docs: Array.isArray(docs) ? docs.length : 0
        });
      });
    }
  }, [userId]);

  const handleSaveGeneral = () => {
    localStorage.setItem('kavya_assistant_name', assistantName);
    localStorage.setItem('kavya_auto_greeting', String(autoGreeting));
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2000);
  };

  const handleExportData = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/history/${encodeURIComponent(userId)}`);
      const data = await res.json();
      const exportBlob = new Blob([JSON.stringify({
        userId,
        exportDate: new Date().toISOString(),
        history: data,
        settings: { assistantName, preferredLanguage, vadSensitivity, theme }
      }, null, 2)], { type: 'application/json' });

      const url = URL.createObjectURL(exportBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `kairos_export_${userId.slice(0, 8)}_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Failed to export data: ' + e.message);
    }
  };

  const handleClearShortTermHistory = async () => {
    if (!confirm('Are you sure you want to clear your current conversation history?')) return;
    try {
      await fetch(`${API_BASE}/api/history/${encodeURIComponent(userId)}`, { method: 'DELETE' });
      setClearStatus('Session history cleared');
      setTimeout(() => setClearStatus(''), 3000);
    } catch (e) {
      alert('Failed to clear: ' + e.message);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`fixed inset-0 z-50 flex items-center justify-center bg-[var(--background)]/95 backdrop-blur-2xl p-4 md:p-6 ${theme}`}
    >
      <div className="animated-grid-bg" />

      {/* Main Settings Modal Container */}
      <div className="relative z-10 w-full max-w-3xl h-[85vh] flex flex-col glass-panel rounded-3xl border border-[var(--border-glass)] shadow-2xl overflow-hidden">
        
        {/* ── Top Header ────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-glass)] bg-[var(--surface)] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-md">
              <Settings size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold font-mono tracking-wider uppercase text-white">
                SYSTEM CONFIGURATION // SETTINGS
              </h2>
              <p className="text-[10px] font-mono text-slate-400">
                Customize audio, AI persona, integrations, and local privacy
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-800 hover:bg-red-500/20 hover:text-red-300 text-slate-300 transition-all border border-slate-700 cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* ── Tab Navigation & Content ───────────────────────────────── */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          
          {/* Left Tab Sidebar */}
          <div className="w-full md:w-52 p-3 bg-slate-950/50 border-b md:border-b-0 md:border-r border-[var(--border-glass)] flex md:flex-col gap-1.5 shrink-0 overflow-x-auto">
            {[
              { id: 'general', label: 'General', icon: User },
              { id: 'voice', label: 'Voice & Mic', icon: Mic },
              { id: 'integrations', label: 'Integrations', icon: Sliders },
              { id: 'privacy', label: 'Memory & Privacy', icon: Shield },
            ].map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-2xl text-xs font-mono font-semibold transition-all cursor-pointer whitespace-nowrap ${
                    isActive
                      ? 'bg-blue-600 text-white border border-blue-400 shadow-sm'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon size={14} className={isActive ? 'text-white' : ''} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Right Content Area */}
          <div className="flex-1 p-6 overflow-y-auto space-y-6">
            
            {/* ── Tab: General ──────────────────────────────────────── */}
            {activeTab === 'general' && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
                <div>
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Assistant Identity
                  </h3>
                  <p className="text-xs text-slate-400 mb-3">Customize your companion's display name.</p>
                  <div className="flex items-center gap-3">
                    <input
                      type="text"
                      value={assistantName}
                      onChange={(e) => setAssistantName(e.target.value)}
                      className="glass-panel px-4 py-2 rounded-xl text-sm font-mono text-white border border-slate-700 outline-none focus:border-blue-400 w-64"
                    />
                    <button
                      onClick={handleSaveGeneral}
                      className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white border border-blue-400/40 text-xs font-mono font-bold transition-all cursor-pointer flex items-center gap-1.5"
                    >
                      {saveToast ? <Check size={13} className="text-sky-300" /> : <Sparkles size={13} />}
                      <span>{saveToast ? 'Saved!' : 'Save'}</span>
                    </button>
                  </div>
                </div>

                <div className="pt-4 border-t border-[var(--border-glass)]">
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Interface Theme
                  </h3>
                  <p className="text-xs text-slate-400 mb-3">Enterprise Dark Mode active (White, Slate Gray, Electric Blue).</p>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-blue-950/40 border border-blue-500/40 w-fit text-xs font-mono text-blue-300">
                    <Moon size={13} className="text-blue-400" />
                    <span>Dark Mode (Fixed)</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-[var(--border-glass)]">
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Startup Behavior
                  </h3>
                  <label className="flex items-center gap-3 cursor-pointer mt-2">
                    <input
                      type="checkbox"
                      checked={autoGreeting}
                      onChange={(e) => setAutoGreeting(e.target.checked)}
                      className="w-4 h-4 accent-blue-500 rounded cursor-pointer"
                    />
                    <span className="text-xs font-sans text-slate-200">
                      Greet user automatically upon application startup
                    </span>
                  </label>
                </div>
              </motion.div>
            )}

            {/* ── Tab: Voice & Mic ──────────────────────────────────── */}
            {activeTab === 'voice' && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
                <div>
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Speech Input Language
                  </h3>
                  <p className="text-xs text-slate-400 mb-3">
                    Select transcription comprehension language (output remains English only).
                  </p>
                  <select
                    value={preferredLanguage}
                    onChange={(e) => onLanguageChange(e.target.value)}
                    className="glass-panel px-4 py-2 rounded-xl text-xs font-mono text-slate-200 border border-slate-700 outline-none cursor-pointer w-64"
                  >
                    <option value="en">English (Fixed)</option>
                    <option value="hi">Hindi (Auto-transcribe)</option>
                    <option value="auto">Auto-Detect (Hinglish/Multilingual)</option>
                  </select>
                </div>

                <div className="pt-4 border-t border-[var(--border-glass)]">
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Voice Activity Detection (VAD) Gate
                  </h3>
                  <p className="text-xs text-slate-400 mb-3">Adjust microphone noise gate threshold.</p>
                  <div className="flex gap-2">
                    {['low', 'medium', 'high'].map((level) => (
                      <button
                        key={level}
                        onClick={() => onVadSensitivityChange(level)}
                        className={`px-4 py-2 rounded-xl text-xs font-mono font-bold uppercase transition-all cursor-pointer ${
                          vadSensitivity === level
                            ? 'bg-blue-600 text-white border border-blue-400 shadow-sm'
                            : 'glass-panel text-slate-400 border border-slate-800 hover:text-white'
                        }`}
                      >
                        {level} Noise Gate
                      </button>
                    ))}
                  </div>
                </div>

                <div className="pt-4 border-t border-[var(--border-glass)]">
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Continuous Listening Mode
                  </h3>
                  <p className="text-xs text-slate-400 mb-3">Automatically re-arm microphone after each response.</p>
                  <button
                    onClick={onToggleContinuousListening}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer ${
                      isContinuousListening
                        ? 'bg-blue-600 text-white border border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]'
                        : 'glass-panel text-slate-400 border border-slate-800 hover:text-white'
                    }`}
                  >
                    <span>∞ Continuous Mode: {isContinuousListening ? 'ACTIVE (Listening)' : 'OFF (Push to talk)'}</span>
                  </button>
                </div>
              </motion.div>
            )}

            {/* ── Tab: Integrations ─────────────────────────────────── */}
            {activeTab === 'integrations' && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                  Connected Desktop Integrations
                </h3>
                <p className="text-xs text-slate-400 mb-3">Manage agentic tool bridges and app launch permissions.</p>

                {[
                  { key: 'vscode', name: 'Visual Studio Code', icon: Code, desc: 'Write files and open directly in VS Code', color: 'text-blue-400' },
                  { key: 'sandbox', name: 'Monaco Code Sandbox', icon: Terminal, desc: 'Execute Python/JS in isolated subprocesses', color: 'text-blue-400' },
                  { key: 'youtube', name: 'YouTube Music & Video', icon: Youtube, desc: 'Search and autoplay music in default browser', color: 'text-blue-400' },
                  { key: 'whatsapp', name: 'WhatsApp Web Protocol', icon: MessageSquare, desc: 'Open chats with permission confirmation', color: 'text-blue-400' },
                ].map((item) => (
                  <div key={item.key} className="glass-panel p-3.5 rounded-2xl border border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-xl bg-slate-900 border border-slate-800 ${item.color}`}>
                        <item.icon size={16} />
                      </div>
                      <div>
                        <div className="text-xs font-bold font-mono text-slate-200">{item.name}</div>
                        <div className="text-[11px] text-slate-400">{item.desc}</div>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-300 border border-blue-500/30">
                      CONNECTED ✓
                    </span>
                  </div>
                ))}
              </motion.div>
            )}

            {/* ── Tab: Memory & Privacy ─────────────────────────────── */}
            {activeTab === 'privacy' && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
                <div>
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    On-Device Storage & Local Privacy
                  </h3>
                  <p className="text-xs text-slate-400 mb-3">
                    All conversational memory and ChromaDB vector embeddings are stored locally on this machine.
                  </p>
                  
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="glass-panel p-3 rounded-2xl border border-slate-800">
                      <div className="text-[10px] font-mono text-slate-400 uppercase">Stored Facts</div>
                      <div className="text-lg font-bold font-mono text-blue-300">{memoryStats.facts} facts</div>
                    </div>
                    <div className="glass-panel p-3 rounded-2xl border border-slate-800">
                      <div className="text-[10px] font-mono text-slate-400 uppercase">Ingested Docs</div>
                      <div className="text-lg font-bold font-mono text-sky-300">{memoryStats.docs} documents</div>
                    </div>
                  </div>

                  {onOpenMemory && (
                    <button
                      onClick={() => { onClose(); onOpenMemory(); }}
                      className="px-4 py-2 rounded-xl bg-blue-600/20 text-blue-300 border border-blue-500/40 hover:bg-blue-600/30 text-xs font-mono font-bold transition-all cursor-pointer flex items-center gap-1.5 mb-4"
                    >
                      <Eye size={13} />
                      <span>Open Memory Manager (View / Pin / Delete / RAG Selection) ↗</span>
                    </button>
                  )}
                </div>

                <div className="pt-4 border-t border-[var(--border-glass)] space-y-3">
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-blue-300 mb-1">
                    Data Export & Privacy Controls
                  </h3>

                  <div className="flex flex-wrap gap-2.5">
                    <button
                      onClick={handleExportData}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl glass-panel border border-slate-700 text-xs font-mono font-bold text-blue-300 hover:text-white transition-all cursor-pointer"
                    >
                      <Download size={13} />
                      <span>Export Data (.JSON)</span>
                    </button>

                    <button
                      onClick={handleClearShortTermHistory}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 text-xs font-mono font-bold transition-all cursor-pointer"
                    >
                      <Trash2 size={13} />
                      <span>Clear Session History</span>
                    </button>
                  </div>

                  {clearStatus && (
                    <p className="text-xs font-mono text-sky-400 animate-pulse">{clearStatus}</p>
                  )}
                </div>
              </motion.div>
            )}

          </div>

        </div>

      </div>
    </motion.div>
  );
}

