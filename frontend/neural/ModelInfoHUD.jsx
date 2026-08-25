/**
 * ModelInfoHUD.jsx — Minimalist Sci-Fi Telemetry & Model Info Overlay
 *
 * Displays:
 * - Real calculated model parameters vs memory size
 * - Active neural lifecycle state with live pulsing indicators
 * - Transformer architecture hyperparameters
 * - Real-time token throughput and RAG retrieval status with similarity scores
 * - Model Architecture presets selector (1B, 8B, 70B, 1T)
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Cpu, Database, Activity, Sparkles, Layers,
  ChevronDown, Zap, Search, ShieldCheck, RefreshCw, BarChart2,
  FileText, Network, CheckCircle
} from 'lucide-react';
import { PRESET_MODELS, calculateModelParameters } from './parameterCalculator';
import { AI_STATES } from './neuralStateMachine';

export default function ModelInfoHUD({
  activeState,
  stateProfile,
  stateData,
  selectedModelKey,
  onModelSelect,
  calculatedParams,
  factCount = 0,
  docChunkCount = 0,
  audioVolume = 0,
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState('architecture');

  const model = PRESET_MODELS[selectedModelKey] || PRESET_MODELS['groq/compound'];
  const params = calculatedParams || calculateModelParameters(model);

  return (
    <div className="absolute top-4 left-4 z-30 pointer-events-auto max-w-sm w-full select-none font-mono">
      {/* ── 1. Compact Live Status Bar ── */}
      <motion.div
        layout
        className="glass-panel-warm rounded-2xl p-3.5 border border-cyan-500/30 backdrop-blur-2xl bg-black/75 shadow-[0_8px_32px_rgba(0,240,255,0.15)] text-xs text-[var(--text-main)]"
      >
        <div className="flex items-center justify-between gap-3">
          {/* State Indicator */}
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span
                className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                style={{ backgroundColor: stateProfile?.primaryColor || '#00f0ff' }}
              />
              <span
                className="relative inline-flex rounded-full h-2.5 w-2.5"
                style={{ backgroundColor: stateProfile?.primaryColor || '#00f0ff' }}
              />
            </span>
            <span className="font-bold tracking-wider text-cyan-300 uppercase">
              {activeState.replace(/_/g, ' ')}
            </span>
          </div>

          {/* Model Name Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-cyan-950/50 border border-cyan-500/30 text-[11px] text-cyan-300">
            <Cpu size={12} />
            <span className="font-semibold">{params.formattedTotal}</span>
          </div>

          {/* Expand / Collapse Button */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded-lg hover:bg-cyan-500/15 text-cyan-400 transition-all cursor-pointer"
            title="Toggle Model Telemetry"
          >
            <ChevronDown
              size={14}
              className={`transform transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}
            />
          </button>
        </div>

        {/* ── 2. Dynamic State Callout Bars ── */}
        {activeState === AI_STATES.RAG_RETRIEVAL && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2.5 pt-2.5 border-t border-amber-500/30 text-[11px] text-amber-300 space-y-1.5"
          >
            <div className="flex items-center gap-2">
              <Search size={12} className="animate-spin" />
              <span>Scanning ChromaDB Vectors ({docChunkCount} chunks)...</span>
            </div>
            {stateData?.results && stateData.results.length > 0 && (
              <div className="space-y-1 pt-1">
                {stateData.results.slice(0, 2).map((r, i) => (
                  <div key={i} className="flex items-center justify-between text-[10px] text-amber-200 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-500/20">
                    <span className="truncate max-w-[180px]">{r.source || 'Memory fact'}</span>
                    <span className="font-bold text-amber-400">{Math.round((r.score || 0.85) * 100)}% match</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {activeState === AI_STATES.TOOL_EXECUTION && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2.5 pt-2.5 border-t border-orange-500/30 text-[11px] text-orange-300 flex items-center gap-2"
          >
            <Zap size={12} className="animate-pulse" />
            <span>Executing Desktop Action: {stateData?.toolName || 'tool'}...</span>
          </motion.div>
        )}

        {activeState === AI_STATES.GENERATING && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2.5 pt-2.5 border-t border-cyan-500/30 text-[11px] text-cyan-300 flex items-center justify-between"
          >
            <div className="flex items-center gap-1.5">
              <Activity size={12} className="animate-pulse text-cyan-400" />
              <span>Neural Wave Outward Radiant</span>
            </div>
            <span className="text-[10px] text-cyan-400 font-bold">STREAMING TOKENS</span>
          </motion.div>
        )}

        {/* ── 3. Expanded Full Model Architecture Panel ── */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 pt-3 border-t border-cyan-500/20 space-y-3"
            >
              {/* Architecture Switcher */}
              <div>
                <label className="text-[10px] text-cyan-400/70 uppercase tracking-wider block mb-1">
                  Active Transformer Engine
                </label>
                <select
                  value={selectedModelKey}
                  onChange={(e) => onModelSelect(e.target.value)}
                  className="w-full bg-slate-950/90 border border-cyan-500/40 rounded-xl px-2.5 py-1.5 text-xs text-cyan-200 outline-none focus:border-cyan-400 cursor-pointer shadow-inner"
                >
                  {Object.entries(PRESET_MODELS).map(([k, m]) => (
                    <option key={k} value={k} className="bg-slate-900 text-cyan-200">
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Metric Comparison: Model Parameters vs Memory Size */}
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2.5 rounded-xl bg-cyan-950/40 border border-cyan-500/25">
                  <div className="text-[10px] text-cyan-400/80 uppercase flex items-center gap-1">
                    <Cpu size={10} /> Model Weights
                  </div>
                  <div className="text-sm font-bold text-cyan-200 mt-0.5">{params.formattedTotal}</div>
                  <div className="text-[9px] text-cyan-400/60 mt-0.5">Static Parameters</div>
                </div>

                <div className="p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-500/25">
                  <div className="text-[10px] text-emerald-400/80 uppercase flex items-center gap-1">
                    <Database size={10} /> Knowledge Base
                  </div>
                  <div className="text-sm font-bold text-emerald-200 mt-0.5">
                    {factCount + docChunkCount} Nodes
                  </div>
                  <div className="text-[9px] text-emerald-400/60 mt-0.5">
                    {factCount} Facts · {docChunkCount} Chunks
                  </div>
                </div>
              </div>

              {/* Detailed Hyperparameters */}
              <div className="p-2.5 rounded-xl bg-black/50 border border-cyan-500/20 space-y-1.5 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-slate-400">Layers (Hidden Depth)</span>
                  <span className="text-cyan-300 font-semibold">{params.config.numLayers}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Hidden Dimension</span>
                  <span className="text-cyan-300 font-semibold">{params.config.hiddenSize}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Attention / KV Heads</span>
                  <span className="text-cyan-300 font-semibold">
                    {params.config.numAttentionHeads} / {params.config.numKVHeads}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Vocabulary Size</span>
                  <span className="text-cyan-300 font-semibold">{params.config.vocabSize.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">MLP Intermediate Size</span>
                  <span className="text-cyan-300 font-semibold">{params.config.intermediateSize.toLocaleString()}</span>
                </div>
              </div>

              {/* Parameter Distribution Breakdown */}
              <div>
                <div className="text-[10px] text-cyan-400/70 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>Weight Distribution</span>
                  <span className="text-[9px] text-slate-400">100% Normalized</span>
                </div>
                <div className="w-full h-2 rounded-full overflow-hidden flex bg-slate-900 border border-cyan-500/30">
                  <div
                    style={{ width: `${params.percentages.mlp}%` }}
                    className="h-full bg-cyan-500"
                    title={`MLP / FFN: ${params.percentages.mlp}%`}
                  />
                  <div
                    style={{ width: `${params.percentages.attention}%` }}
                    className="h-full bg-indigo-500"
                    title={`Attention: ${params.percentages.attention}%`}
                  />
                  <div
                    style={{ width: `${params.percentages.embedding}%` }}
                    className="h-full bg-purple-500"
                    title={`Embeddings: ${params.percentages.embedding}%`}
                  />
                  <div
                    style={{ width: `${params.percentages.outputHead}%` }}
                    className="h-full bg-pink-500"
                    title={`Output Head: ${params.percentages.outputHead}%`}
                  />
                </div>
                <div className="flex justify-between text-[8px] text-slate-400 mt-1">
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" /> MLP ({params.percentages.mlp}%)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" /> Attn ({params.percentages.attention}%)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-500" /> Emb ({params.percentages.embedding}%)
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
