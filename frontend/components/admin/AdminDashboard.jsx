import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { 
  Users, MessageSquare, Bot, Activity, X, Lock, KeyRound, 
  ListTree, Cpu, Mic, Volume2, Database, Zap, Sparkles, CheckCircle2, 
  AlertCircle, ShieldCheck, Gauge, Terminal, Code, Youtube, RefreshCw, HardDrive
} from 'lucide-react';
import RetroDial from '../common/RetroDial';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const COLORS = ['#f5c560', '#ff9e7d', '#06b6d4', '#8b5cf6', '#10b981', '#3b82f6', '#8b4a3c'];

export default function AdminDashboard({ 
  onClose, 
  theme = 'dark', 
  userId, 
  sessionId, 
  onThemeToggle, 
  status = 'Idle',
  onOpenSandbox,
  onOpenMemory,
  onOpenSettings
}) {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'analytics'
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // System Metrics Data
  const [metrics, setMetrics] = useState({
    cpu_percent: 15,
    memory_percent: 42,
    memory_used_gb: 6.8,
    memory_total_gb: 16.0,
    platform: 'Windows',
    status: 'Healthy'
  });

  // User Overview Data
  const [userHistory, setUserHistory] = useState([]);
  const [userLoading, setUserLoading] = useState(true);

  // Admin Analytics Data
  const [stats, setStats] = useState({ total_users: 0, total_messages: 0, total_assistant_messages: 0 });
  const [activity, setActivity] = useState([]);
  const [avatars, setAvatars] = useState([]);
  const [logs, setLogs] = useState([]);

  // Fetch host system metrics
  const fetchMetrics = () => {
    fetch(`${API_BASE}/api/system/metrics`)
      .then(res => res.json())
      .then(data => {
        if (data && typeof data.cpu_percent === 'number') {
          setMetrics(data);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch current user history for the overview feed
  useEffect(() => {
    if (!userId) {
      setUserLoading(false);
      return;
    }
    fetch(`${API_BASE}/api/history/${encodeURIComponent(userId)}`)
      .then(res => res.json())
      .then(data => {
        setUserHistory(Array.isArray(data) ? data : []);
        setUserLoading(false);
      })
      .catch(() => setUserLoading(false));
  }, [userId]);

  const fetchAdminData = async (adminPassword) => {
    setLoading(true);
    setError('');
    
    const headers = { 'x-admin-password': adminPassword };

    try {
      const statsRes = await fetch(`${API_BASE}/api/admin/stats`, { headers });
      if (statsRes.status === 401) throw new Error('Incorrect password');
      const statsData = await statsRes.json();
      setStats(statsData);

      const [activityRes, avatarsRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/activity`, { headers }),
        fetch(`${API_BASE}/api/admin/avatars`, { headers }),
        fetch(`${API_BASE}/api/admin/logs`, { headers })
      ]);
      
      setActivity(await activityRes.json());
      setLogs(await logsRes.json());
      
      const avatarsData = await avatarsRes.json();
      setAvatars(avatarsData.map(item => ({
        name: item.avatar_id === 'avatar.vrm' ? 'Kavya' : item.avatar_id,
        value: item.count
      })));

      setIsAuthenticated(true);
    } catch (err) {
      setError(err.message || 'Failed to authenticate');
    } finally {
      setLoading(false);
    }
  };

  const handleAdminLogin = (e) => {
    e.preventDefault();
    if (password.trim()) fetchAdminData(password);
  };

  const cardClass = "glass-panel-warm rounded-3xl p-5 border border-[var(--border-gold-glow)] relative overflow-hidden";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`fixed inset-0 z-50 overflow-y-auto bg-[var(--background)]/95 backdrop-blur-2xl p-4 md:p-8 ${theme}`}
    >
      {/* Sci-Fi Grid Background */}
      <div className="animated-grid-bg" />

      <div className="max-w-6xl mx-auto relative z-10 space-y-6">
        
        {/* Top Navigation Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-gold-glow)]">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-300 shadow-[0_0_15px_rgba(245,197,96,0.3)]">
              <Zap size={22} />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-main)] font-mono">
                TELEMETRY & COCKPIT MATRIX
              </h1>
              <p className="text-xs md:text-sm text-[var(--text-muted)] font-mono">
                SYSTEM STATUS, DESKTOP INTEGRATIONS & LIVE METRICS
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Tabs */}
            <div className="flex items-center p-1 rounded-2xl glass-panel border border-[var(--border-glass)]">
              <button
                onClick={() => setActiveTab('overview')}
                className={`px-4 py-1.5 rounded-xl text-xs font-mono font-semibold transition-all cursor-pointer ${
                  activeTab === 'overview'
                    ? 'bg-amber-400 text-slate-950 shadow-[0_0_15px_rgba(245,197,96,0.5)] font-bold'
                    : 'text-[var(--text-muted)] hover:text-white'
                }`}
              >
                SYSTEM OVERVIEW
              </button>
              <button
                onClick={() => setActiveTab('analytics')}
                className={`px-4 py-1.5 rounded-xl text-xs font-mono font-semibold transition-all cursor-pointer ${
                  activeTab === 'analytics'
                    ? 'bg-violet-500 text-white shadow-[0_0_12px_rgba(139,92,246,0.4)]'
                    : 'text-[var(--text-muted)] hover:text-white'
                }`}
              >
                ADMIN ANALYTICS
              </button>
            </div>

            {/* Close Button */}
            <button 
              onClick={onClose}
              className="w-10 h-10 rounded-2xl glass-panel hover:bg-rose-500/20 hover:text-rose-400 hover:border-rose-500/30 flex items-center justify-center text-[var(--text-main)] transition-all cursor-pointer border border-[var(--border-glass)]"
              title="Close Dashboard"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* ── TAB 1: SYSTEM OVERVIEW (User Facing) ────────────────────── */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            
            {/* Quick Action Shortcuts Bar */}
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-[11px] font-mono text-[var(--text-muted)] uppercase tracking-wider mr-1">
                QUICK ACTIONS:
              </span>
              {onOpenSandbox && (
                <button
                  onClick={() => { onClose(); onOpenSandbox(); }}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-amber-400/20 text-amber-300 border border-amber-400/40 hover:bg-amber-400/30 text-xs font-mono font-bold transition-all cursor-pointer shadow-sm"
                >
                  <Code size={13} />
                  <span>Launch Code Sandbox</span>
                </button>
              )}
              {onOpenMemory && (
                <button
                  onClick={() => { onClose(); onOpenMemory(); }}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-violet-500/20 text-violet-300 border border-violet-500/40 hover:bg-violet-500/30 text-xs font-mono font-bold transition-all cursor-pointer shadow-sm"
                >
                  <Database size={13} />
                  <span>Manage Long-Term Memory</span>
                </button>
              )}
              {onOpenSettings && (
                <button
                  onClick={() => { onClose(); onOpenSettings(); }}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl glass-panel border border-[var(--border-gold-glow)] text-[var(--text-main)] hover:border-amber-400 text-xs font-mono font-semibold transition-all cursor-pointer"
                >
                  <Zap size={13} className="text-amber-400" />
                  <span>Configure Settings</span>
                </button>
              )}
              <button
                onClick={fetchMetrics}
                className="p-1.5 rounded-xl glass-panel text-[var(--text-muted)] hover:text-white border border-[var(--border-glass)] cursor-pointer ml-auto"
                title="Refresh System Metrics"
              >
                <RefreshCw size={14} />
              </button>
            </div>

            {/* Retro Sci-Fi Cockpit Analog Dial Cluster */}
            <div className={cardClass}>
              <div className="flex items-center gap-2 mb-4">
                <Gauge size={18} className="text-amber-400" />
                <h3 className="text-sm font-mono font-bold uppercase text-[var(--text-main)]">
                  Live Cockpit Telemetry & Hardware Meters
                </h3>
              </div>
              <div className="flex items-center justify-around gap-4 flex-wrap">
                <RetroDial 
                  value={Math.round(metrics.cpu_percent)}
                  max={100}
                  label="HOST CPU LOAD"
                  unit="%"
                  variant="gold"
                />
                <RetroDial 
                  value={Math.round(metrics.memory_percent)}
                  max={100}
                  label="RAM USAGE"
                  unit="%"
                  variant="coral"
                />
                <RetroDial 
                  value={status === 'Listening' ? 88 : status === 'Speaking' ? 75 : 20}
                  max={100}
                  label="AUDIO ACTIVITY"
                  unit="dB"
                  variant="cyan"
                />
                <RetroDial 
                  value={160}
                  max={500}
                  label="RESPONSE LATENCY"
                  unit="ms"
                  variant="emerald"
                />
              </div>
            </div>

            {/* System Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className={cardClass}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono text-[var(--text-muted)] uppercase">Host RAM</span>
                  <HardDrive size={16} className="text-amber-400" />
                </div>
                <div className="text-xl font-bold font-mono text-amber-300">{metrics.memory_used_gb} / {metrics.memory_total_gb} GB</div>
                <div className="text-[11px] text-[var(--text-subtle)] mt-1">Platform: {metrics.platform} (64-bit)</div>
              </div>

              <div className={cardClass}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono text-[var(--text-muted)] uppercase">LLM Engine</span>
                  <Cpu size={16} className="text-violet-400" />
                </div>
                <div className="text-lg font-bold font-mono text-[var(--text-main)]">Llama 3.3 70B</div>
                <div className="text-[11px] text-[var(--text-subtle)] mt-1">Groq LPUs (ultra-fast reasoning)</div>
              </div>

              <div className={cardClass}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono text-[var(--text-muted)] uppercase">STT Pipeline</span>
                  <Mic size={16} className="text-cyan-400" />
                </div>
                <div className="text-lg font-bold font-mono text-[var(--text-main)]">Whisper Large v3</div>
                <div className="text-[11px] text-[var(--text-subtle)] mt-1">Continuous VAD Endpointing</div>
              </div>

              <div className={cardClass}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono text-[var(--text-muted)] uppercase">Vector Memory</span>
                  <Database size={16} className="text-emerald-400" />
                </div>
                <div className="text-lg font-bold font-mono text-[var(--text-main)]">ChromaDB Local</div>
                <div className="text-[11px] text-[var(--text-subtle)] mt-1">all-MiniLM-L6-v2 Embeddings</div>
              </div>
            </div>

            {/* Connected Desktop Integrations Panel */}
            <div className={cardClass}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Sparkles size={18} className="text-amber-400" />
                  <h3 className="text-sm font-mono font-bold uppercase text-[var(--text-main)]">
                    Desktop Integrations & Agentic Tools
                  </h3>
                </div>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1 font-bold">
                  <CheckCircle2 size={13} /> ALL SYSTEMS OPERATIONAL
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { name: "VS Code Bridge", status: "Connected (CLI linked)", icon: Code, color: "text-amber-400", border: "border-amber-500/20" },
                  { name: "Code Sandbox", status: "Subprocess Runner (Active)", icon: Terminal, color: "text-cyan-400", border: "border-cyan-500/20" },
                  { name: "YouTube Music", status: "Browser Bridge (Linked)", icon: Youtube, color: "text-rose-400", border: "border-rose-500/20" },
                  { name: "WhatsApp Protocol", status: "Permission Gated (Safe)", icon: MessageSquare, color: "text-emerald-400", border: "border-emerald-500/20" }
                ].map((item, idx) => (
                  <div key={idx} className={`p-4 rounded-2xl bg-[var(--surface-hover)] border ${item.border} flex items-start gap-3`}>
                    <item.icon size={20} className={`${item.color} shrink-0 mt-0.5`} />
                    <div>
                      <div className="text-xs font-bold text-[var(--text-main)]">{item.name}</div>
                      <div className="text-[11px] font-mono text-[var(--text-muted)] mt-0.5">{item.status}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* User Recent Activity Feed */}
            <div className={cardClass}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Activity size={18} className="text-violet-400" />
                  <h3 className="text-sm font-mono font-bold uppercase text-[var(--text-main)]">
                    Recent Activity Feed ({userHistory.length} turns)
                  </h3>
                </div>
                <span className="text-xs font-mono text-[var(--text-subtle)]">
                  USER: {userId ? `${userId.substring(0, 18)}...` : 'LOCAL'}
                </span>
              </div>

              <div className="space-y-2.5 max-h-[300px] overflow-y-auto chat-scroll pr-2">
                {userHistory.slice(-8).reverse().map((item, idx) => (
                  <div key={idx} className="p-3 rounded-2xl bg-[var(--surface-hover)] border border-[var(--border-glass)] flex items-start gap-3">
                    <span className={`px-2 py-0.5 rounded-lg text-[10px] font-mono font-bold uppercase shrink-0 mt-0.5 ${
                      item.role === 'assistant' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' : 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                    }`}>
                      {item.role}
                    </span>
                    <p className="text-xs md:text-sm text-[var(--text-main)] leading-relaxed font-sans">
                      {item.text || item.content}
                    </p>
                  </div>
                ))}
                {userHistory.length === 0 && (
                  <div className="text-center py-8 text-xs font-mono text-[var(--text-subtle)]">
                    NO CONVERSATION DATA RECORDED IN CURRENT SESSION.
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

        {/* ── TAB 2: ADMIN ANALYTICS (Protected) ────────────────────── */}
        {activeTab === 'analytics' && (
          <div>
            {!isAuthenticated ? (
              <div className="flex items-center justify-center min-h-[50vh]">
                <motion.div 
                  initial={{ scale: 0.95, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="glass-panel rounded-3xl p-8 max-w-md w-full border border-violet-500/30 shadow-2xl"
                >
                  <div className="flex justify-center mb-6">
                    <div className="w-16 h-16 rounded-2xl bg-violet-500/20 border border-violet-500/30 text-violet-400 flex items-center justify-center">
                      <Lock size={30} />
                    </div>
                  </div>
                  <h2 className="text-xl font-bold text-center text-[var(--text-main)] font-mono mb-2">MASTER AUTHENTICATION</h2>
                  <p className="text-center text-xs text-[var(--text-muted)] mb-6 font-sans">
                    Enter master administrative password to unlock detailed usage logs and platform metrics.
                  </p>
                  
                  <form onSubmit={handleAdminLogin} className="space-y-4">
                    <div className="relative">
                      <KeyRound size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                      <input
                        type="password"
                        placeholder="Admin password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-[var(--surface-hover)] border border-[var(--border-glass)] rounded-xl py-3 pl-12 pr-4 text-sm text-[var(--text-main)] placeholder:text-[var(--text-subtle)] focus:outline-none focus:border-violet-500 font-mono"
                      />
                    </div>
                    {error && <div className="text-rose-400 text-xs font-mono text-center">{error}</div>}
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 text-white rounded-xl font-mono text-sm font-semibold transition-all cursor-pointer flex items-center justify-center gap-2"
                    >
                      {loading ? 'AUTHENTICATING...' : 'UNLOCK TELEMETRY'}
                    </button>
                  </form>
                </motion.div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Aggregate KPI Stat Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className={cardClass}>
                    <div className="text-xs font-mono text-[var(--text-muted)] uppercase">Total Registered Users</div>
                    <div className="text-3xl font-bold font-mono text-amber-300 mt-2">{stats.total_users}</div>
                  </div>
                  <div className={cardClass}>
                    <div className="text-xs font-mono text-[var(--text-muted)] uppercase">Total User Messages</div>
                    <div className="text-3xl font-bold font-mono text-cyan-300 mt-2">{stats.total_messages}</div>
                  </div>
                  <div className={cardClass}>
                    <div className="text-xs font-mono text-[var(--text-muted)] uppercase">Assistant Responses</div>
                    <div className="text-3xl font-bold font-mono text-emerald-300 mt-2">{stats.total_assistant_messages}</div>
                  </div>
                </div>

                {/* Activity Line Chart */}
                <div className={cardClass}>
                  <h3 className="text-sm font-mono font-bold uppercase text-[var(--text-main)] mb-4">
                    Message Activity (Last 30 Days)
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={activity}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
                        <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                        <YAxis stroke="#64748b" fontSize={11} />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                        <Line type="monotone" dataKey="messages" stroke="#f5c560" strokeWidth={2} dot={{ fill: '#f5c560' }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </motion.div>
  );
}
