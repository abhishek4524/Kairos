import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  HardDrive, Cpu, Mic, Database, Code, Sliders, Zap, 
  CheckCircle2, RefreshCw, ChevronLeft, ChevronRight,
  Terminal, Youtube, MessageSquare, Activity, Sparkles, Volume2, Clock
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function TelemetrySidebar({
  userId,
  sessionId,
  status = 'Idle',
  onOpenSandbox,
  onOpenMemory,
  onOpenSettings
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  
  // Host System Metrics
  const [metrics, setMetrics] = useState({
    cpu_percent: 23,
    memory_percent: 89,
    memory_used_gb: 13.99,
    memory_total_gb: 15.69,
    platform: 'Windows (64-bit)',
    status: 'Healthy'
  });

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

  const audioDb = status === 'Listening' ? '20dB' : status === 'Speaking' ? '18dB' : '0dB';
  const audioPercent = status === 'Listening' ? 20 : status === 'Speaking' ? 18 : 2;

  const cpuVal = Math.round(metrics.cpu_percent || 23);
  const ramVal = Math.round(metrics.memory_percent || 89);
  const latencyVal = 160;

  return (
    <aside 
      className={`relative z-20 h-full flex flex-col glass-panel border-r border-[var(--border-glass)] transition-all duration-300 select-none shrink-0 ${
        isCollapsed ? 'w-14' : 'w-[280px] md:w-[300px]'
      }`}
    >
      {/* ── Top Header ────────────────────────────────────────────── */}
      <div className="flex items-center justify-between p-3 border-b border-[var(--border-glass)] bg-slate-950/70">
        {!isCollapsed && (
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 shrink-0">
              <Zap size={14} />
            </div>
            <div className="min-w-0">
              <h2 className="text-[11px] font-bold font-mono tracking-wider uppercase text-white truncate">
                TELEMETRY & COCKPIT MATRIX
              </h2>
              <p className="text-[9px] font-mono text-slate-400 truncate">
                SYSTEM STATUS, DESKTOP INTEGRATIONS & LIVE METRICS
              </p>
            </div>
          </div>
        )}

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-blue-600/20 hover:text-blue-300 text-slate-400 border border-slate-700/60 transition-all cursor-pointer mx-auto"
          title={isCollapsed ? 'Expand Telemetry' : 'Collapse to Mini Rail'}
        >
          {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* ── Collapsed Mini Rail View ───────────────────────────────── */}
      {isCollapsed ? (
        <div className="flex-1 flex flex-col items-center py-4 gap-3 text-slate-400">
          <button 
            onClick={() => setIsCollapsed(false)} 
            className="p-2 rounded-xl bg-blue-600/10 text-blue-400 border border-blue-500/30 hover:bg-blue-600/20 cursor-pointer"
            title={`CPU: ${cpuVal}% | RAM: ${ramVal}%`}
          >
            <Activity size={16} />
          </button>
          <div className="text-[9px] font-mono text-blue-400 font-bold">{cpuVal}%</div>

          <div className="w-6 h-px bg-slate-800 my-1" />

          {onOpenSandbox && (
            <button 
              onClick={onOpenSandbox} 
              className="p-2 rounded-xl bg-slate-900 text-slate-300 hover:text-blue-300 hover:bg-slate-800 border border-slate-800 cursor-pointer"
              title="Launch Code Sandbox"
            >
              <Code size={16} />
            </button>
          )}

          {onOpenMemory && (
            <button 
              onClick={onOpenMemory} 
              className="p-2 rounded-xl bg-slate-900 text-slate-300 hover:text-blue-300 hover:bg-slate-800 border border-slate-800 cursor-pointer"
              title="Manage Long-Term Memory"
            >
              <Database size={16} />
            </button>
          )}

          {onOpenSettings && (
            <button 
              onClick={onOpenSettings} 
              className="p-2 rounded-xl bg-slate-900 text-slate-300 hover:text-blue-300 hover:bg-slate-800 border border-slate-800 cursor-pointer"
              title="Configure Settings"
            >
              <Sliders size={16} />
            </button>
          )}

          <div className="mt-auto">
            <button 
              onClick={fetchMetrics} 
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 cursor-pointer"
              title="Refresh Metrics"
            >
              <RefreshCw size={13} />
            </button>
          </div>
        </div>
      ) : (
        /* ── Full Expanded Space-Efficient Panel ─────────────────── */
        <div className="flex-1 overflow-y-auto chat-scroll p-3 space-y-3.5 text-xs font-mono">

          {/* ── Quick Actions ────────────────────────────────────── */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
              <Zap size={11} className="text-blue-400" />
              <span>QUICK ACTIONS:</span>
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {onOpenSandbox && (
                <button
                  onClick={onOpenSandbox}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-blue-600/15 text-slate-200 hover:text-blue-200 border border-slate-800 hover:border-blue-500/40 transition-all cursor-pointer shadow-sm"
                >
                  <span className="flex items-center gap-2">
                    <Code size={13} className="text-blue-400" />
                    <span className="text-[11px] font-semibold">Launch Code Sandbox</span>
                  </span>
                  <span className="text-[10px] text-blue-400">↗</span>
                </button>
              )}

              {onOpenMemory && (
                <button
                  onClick={onOpenMemory}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-blue-600/15 text-slate-200 hover:text-blue-200 border border-slate-800 hover:border-blue-500/40 transition-all cursor-pointer shadow-sm"
                >
                  <span className="flex items-center gap-2">
                    <Database size={13} className="text-sky-400" />
                    <span className="text-[11px] font-semibold">Manage Long-Term Memory</span>
                  </span>
                  <span className="text-[10px] text-sky-400">↗</span>
                </button>
              )}

              {onOpenSettings && (
                <button
                  onClick={onOpenSettings}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-blue-600/15 text-slate-200 hover:text-blue-200 border border-slate-800 hover:border-blue-500/40 transition-all cursor-pointer shadow-sm"
                >
                  <span className="flex items-center gap-2">
                    <Sliders size={13} className="text-blue-300" />
                    <span className="text-[11px] font-semibold">Configure Settings</span>
                  </span>
                  <span className="text-[10px] text-blue-300">↗</span>
                </button>
              )}
            </div>
          </div>

          {/* ── Live Cockpit Telemetry & Hardware Meters (Normal Clean Meters) ─ */}
          <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2.5 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-white tracking-wider">
                <Activity size={12} className="text-blue-400" />
                <span>Live Cockpit Telemetry & Hardware Meters</span>
              </div>
              <button 
                onClick={fetchMetrics} 
                className="text-slate-500 hover:text-blue-300 cursor-pointer transition-colors"
                title="Refresh"
              >
                <RefreshCw size={11} />
              </button>
            </div>

            {/* 1. HOST CPU LOAD */}
            <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1.5 text-slate-300 font-semibold uppercase">
                  <Cpu size={12} className="text-blue-400" />
                  HOST CPU LOAD
                </span>
                <span className="font-bold text-blue-400">{cpuVal}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, Math.max(0, cpuVal))}%` }}
                  transition={{ duration: 0.5, ease: 'easeOut' }}
                  className="h-full bg-blue-500 rounded-full"
                />
              </div>
            </div>

            {/* 2. RAM USAGE */}
            <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1.5 text-slate-300 font-semibold uppercase">
                  <HardDrive size={12} className="text-sky-400" />
                  RAM USAGE
                </span>
                <span className="font-bold text-sky-400">{ramVal}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, Math.max(0, ramVal))}%` }}
                  transition={{ duration: 0.5, ease: 'easeOut' }}
                  className="h-full bg-sky-400 rounded-full"
                />
              </div>
            </div>

            {/* 3. AUDIO ACTIVITY */}
            <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1.5 text-slate-300 font-semibold uppercase">
                  <Volume2 size={12} className="text-blue-400" />
                  AUDIO ACTIVITY
                </span>
                <span className="font-bold text-blue-300">{audioDb} ({audioPercent}%)</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${audioPercent}%` }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className="h-full bg-blue-400 rounded-full"
                />
              </div>
            </div>

            {/* 4. RESPONSE LATENCY */}
            <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1.5 text-slate-300 font-semibold uppercase">
                  <Clock size={12} className="text-emerald-400" />
                  RESPONSE LATENCY
                </span>
                <span className="font-bold text-emerald-400">{latencyVal}ms (32%)</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: '32%' }}
                  transition={{ duration: 0.5, ease: 'easeOut' }}
                  className="h-full bg-emerald-400 rounded-full"
                />
              </div>
            </div>

          </div>

          {/* ── System Hardware & Engine Specs ───────────────────── */}
          <div className="space-y-2">
            
            {/* Host RAM */}
            <div className="p-2.5 rounded-xl bg-slate-900/70 border border-slate-800 flex items-start gap-2.5">
              <HardDrive size={15} className="text-blue-400 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="text-[10px] text-slate-400 uppercase">Host RAM</div>
                <div className="text-xs font-bold text-white">
                  {metrics.memory_used_gb || '13.99'} / {metrics.memory_total_gb || '15.69'} GB
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">Platform: {metrics.platform || 'Windows (64-bit)'}</div>
              </div>
            </div>

            {/* LLM Engine */}
            <div className="p-2.5 rounded-xl bg-slate-900/70 border border-slate-800 flex items-start gap-2.5">
              <Cpu size={15} className="text-sky-400 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="text-[10px] text-slate-400 uppercase">LLM Engine</div>
                <div className="text-xs font-bold text-white">Llama 3.3 70B</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Groq LPUs (ultra-fast reasoning)</div>
              </div>
            </div>

            {/* STT Pipeline */}
            <div className="p-2.5 rounded-xl bg-slate-900/70 border border-slate-800 flex items-start gap-2.5">
              <Mic size={15} className="text-blue-400 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="text-[10px] text-slate-400 uppercase">STT Pipeline</div>
                <div className="text-xs font-bold text-white">Whisper Large v3</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Continuous VAD Endpointing</div>
              </div>
            </div>

            {/* Vector Memory */}
            <div className="p-2.5 rounded-xl bg-slate-900/70 border border-slate-800 flex items-start gap-2.5">
              <Database size={15} className="text-sky-400 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="text-[10px] text-slate-400 uppercase">Vector Memory</div>
                <div className="text-xs font-bold text-white">ChromaDB Local</div>
                <div className="text-[10px] text-slate-500 mt-0.5">all-MiniLM-L6-v2 Embeddings</div>
              </div>
            </div>

          </div>

          {/* ── Desktop Integrations Grid ─────────────────────────── */}
          <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-400">
              <span className="flex items-center gap-1.5 text-white font-bold">
                <Sparkles size={11} className="text-blue-400" />
                <span>Desktop Integrations</span>
              </span>
              <span className="text-emerald-400 font-bold flex items-center gap-1 text-[9px]">
                <CheckCircle2 size={10} /> ALL ACTIVE
              </span>
            </div>

            <div className="grid grid-cols-2 gap-1.5 text-[10px]">
              <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center gap-2">
                <Code size={13} className="text-blue-400 shrink-0" />
                <span className="truncate text-slate-200">VS Code</span>
              </div>
              <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center gap-2">
                <Terminal size={13} className="text-sky-400 shrink-0" />
                <span className="truncate text-slate-200">Sandbox</span>
              </div>
              <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center gap-2">
                <Youtube size={13} className="text-red-400 shrink-0" />
                <span className="truncate text-slate-200">YouTube</span>
              </div>
              <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center gap-2">
                <MessageSquare size={13} className="text-emerald-400 shrink-0" />
                <span className="truncate text-slate-200">WhatsApp</span>
              </div>
            </div>
          </div>

        </div>
      )}
    </aside>
  );
}
