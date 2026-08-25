import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Brain, FileText, Pin, PinOff, Trash2, Upload, RefreshCw,
  Clock, AlertCircle, CheckCircle, BookOpen, Sparkles, Database, ChevronDown
} from 'lucide-react';
import { neuralStateMachine } from '../../neural/neuralStateMachine';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function formatDate(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function FactCard({ fact, onDelete, onTogglePin }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`glass-panel-warm rounded-2xl p-4 border transition-all ${
        fact.pinned
          ? 'border-amber-400/60 shadow-[0_4px_20px_rgba(245,197,96,0.15)]'
          : 'border-[var(--border-gold-glow)]'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 shrink-0 ${fact.pinned ? 'text-amber-400' : 'text-[var(--text-subtle)]'}`}>
          <Sparkles size={14} />
        </div>
        <p className="flex-1 text-sm text-[var(--text-main)] leading-relaxed font-sans">{fact.content}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onTogglePin(fact.id, !fact.pinned)}
            title={fact.pinned ? 'Unpin memory' : 'Pin memory — always included in context'}
            className={`p-1.5 rounded-xl transition-all cursor-pointer ${
              fact.pinned
                ? 'bg-amber-400/20 text-amber-400 hover:bg-amber-400/30'
                : 'text-[var(--text-muted)] hover:text-amber-300 hover:bg-amber-400/10'
            }`}
          >
            {fact.pinned ? <Pin size={13} /> : <PinOff size={13} />}
          </button>
          <button
            onClick={() => onDelete(fact.id)}
            title="Delete this memory"
            className="p-1.5 rounded-xl text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-400/10 transition-all cursor-pointer"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3 text-[10px] font-mono text-[var(--text-subtle)]">
        <span className="flex items-center gap-1"><Clock size={10} /> {formatDate(fact.created_at)}</span>
        <span className="flex items-center gap-1">
          <BookOpen size={10} /> {fact.source || 'conversation'}
        </span>
        {fact.pinned && (
          <span className="px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-300 border border-amber-400/30">📌 PINNED</span>
        )}
      </div>
    </motion.div>
  );
}

function DocRow({ doc, onDelete, userId }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass-panel-warm rounded-2xl p-4 border border-[var(--border-gold-glow)] flex items-center gap-3"
    >
      <div className="p-2.5 rounded-xl bg-cyan-950/40 border border-cyan-500/30 text-cyan-400 shrink-0">
        <FileText size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold font-mono text-[var(--text-main)] truncate">{doc.doc_name}</div>
        <div className="text-[11px] font-mono text-[var(--text-muted)] mt-0.5 flex items-center gap-2">
          <Database size={10} /> {doc.chunk_count} chunks
          <Clock size={10} /> {formatDate(doc.created_at)}
        </div>
      </div>
      <button
        onClick={() => onDelete(doc.doc_id)}
        title="Delete this document from memory"
        className="p-2 rounded-xl text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-400/10 transition-all cursor-pointer shrink-0"
      >
        <Trash2 size={15} />
      </button>
    </motion.div>
  );
}

export default function MemoryPanel({ onClose, userId, theme = 'dark' }) {
  const [activeTab, setActiveTab] = useState('memories');
  const [facts, setFacts] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadStatus, setUploadStatus] = useState(null); // 'uploading' | 'success' | 'error'
  const [uploadMsg, setUploadMsg] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const fetchFacts = async () => {
    try {
      const res = await fetch(`${API}/api/memory/facts/${encodeURIComponent(userId)}`);
      const data = await res.json();
      setFacts(Array.isArray(data) ? data : []);
    } catch (e) {
      setFacts([]);
    }
  };

  const fetchDocs = async () => {
    try {
      const res = await fetch(`${API}/api/memory/documents/${encodeURIComponent(userId)}`);
      const data = await res.json();
      setDocuments(Array.isArray(data) ? data : []);
    } catch (e) {
      setDocuments([]);
    }
  };

  const refresh = async () => {
    setIsLoading(true);
    await Promise.all([fetchFacts(), fetchDocs()]);
    setIsLoading(false);
  };

  useEffect(() => { refresh(); }, [userId]);

  const handleDeleteFact = async (factId) => {
    await fetch(`${API}/api/memory/facts/${encodeURIComponent(factId)}`, { method: 'DELETE' });
    setFacts(prev => prev.filter(f => f.id !== factId));
    neuralStateMachine.onMemoryUpdate('deleted');
  };

  const handleTogglePin = async (factId, pinned) => {
    await fetch(`${API}/api/memory/facts/${encodeURIComponent(factId)}/pin`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned }),
    });
    setFacts(prev => prev.map(f => f.id === factId ? { ...f, pinned } : f));
    neuralStateMachine.onMemoryUpdate('updated');
  };

  const handleDeleteDoc = async (docId) => {
    await fetch(`${API}/api/memory/documents/${encodeURIComponent(docId)}?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' });
    setDocuments(prev => prev.filter(d => d.doc_id !== docId));
    setFacts(prev => prev.filter(f => f.source !== docId));
    neuralStateMachine.onMemoryUpdate('deleted');
  };

  const handleUpload = async (file) => {
    if (!file) return;
    const allowed = ['.pdf', '.txt', '.md'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
      setUploadStatus('error');
      setUploadMsg('Only .pdf, .txt, and .md files are supported');
      setTimeout(() => setUploadStatus(null), 4000);
      return;
    }

    setUploadStatus('uploading');
    setUploadMsg(`Ingesting "${file.name}"...`);
    neuralStateMachine.onRagIngestion(file.name, 6);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API}/api/memory/ingest?user_id=${encodeURIComponent(userId)}`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setUploadStatus('success');
        setUploadMsg(`✓ Ingested "${data.doc_name}" — ${data.chunk_count} chunks stored`);
        neuralStateMachine.onRagIngestion(data.doc_name, data.chunk_count);
        await refresh();
      } else {
        setUploadStatus('error');
        setUploadMsg(data.detail || 'Ingestion failed');
        neuralStateMachine.onError(data.detail || 'Ingestion failed');
      }
    } catch (e) {
      setUploadStatus('error');
      setUploadMsg('Upload failed — is the backend running?');
      neuralStateMachine.onError('Upload failed');
    }
    setTimeout(() => setUploadStatus(null), 5000);
  };

  const pinnedFacts = facts.filter(f => f.pinned);
  const unpinnedFacts = facts.filter(f => !f.pinned);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`fixed inset-0 z-50 overflow-y-auto bg-[var(--background)]/95 backdrop-blur-2xl p-4 md:p-8 ${theme}`}
    >
      <div className="animated-grid-bg" />

      <div className="max-w-4xl mx-auto relative z-10 space-y-6 pb-12">

        {/* ── Header ────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-gold-glow)]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-500 to-cyan-500 flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.4)]">
              <Brain size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold font-mono tracking-wider text-[var(--text-main)]">KAIROS // LONG-TERM MEMORY</h1>
              <p className="text-[11px] font-mono text-[var(--text-muted)]">
                {facts.length} facts · {documents.length} documents · ChromaDB
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={refresh}
              title="Refresh memory"
              className="p-2.5 rounded-xl glass-panel border border-[var(--border-gold-glow)] text-[var(--text-muted)] hover:text-amber-300 transition-all cursor-pointer"
            >
              <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={onClose}
              className="p-2.5 rounded-xl glass-panel-warm border border-[var(--border-gold-glow)] text-[var(--text-main)] hover:text-rose-300 hover:bg-rose-500/10 transition-all cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── Stats Chips ─────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="px-3 py-1.5 rounded-full glass-panel-warm border border-amber-400/40 text-xs font-mono text-amber-300">
            📌 {pinnedFacts.length} Pinned
          </div>
          <div className="px-3 py-1.5 rounded-full glass-panel border border-[var(--border-gold-glow)] text-xs font-mono text-[var(--text-muted)]">
            🧠 {facts.length} Memories
          </div>
          <div className="px-3 py-1.5 rounded-full glass-panel border border-cyan-500/30 text-xs font-mono text-cyan-300">
            📄 {documents.length} Documents
          </div>
          <div className="px-3 py-1.5 rounded-full glass-panel border border-emerald-500/30 text-xs font-mono text-emerald-300">
            ⚡ Auto-extracts from every turn
          </div>
        </div>

        {/* ── Tabs ────────────────────────────────────────────────────── */}
        <div className="flex gap-1 p-1 glass-panel rounded-2xl border border-[var(--border-gold-glow)] w-fit">
          {[
            { id: 'memories', label: 'Memories', icon: Brain },
            { id: 'documents', label: 'Documents', icon: FileText },
          ].map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40 shadow-[0_0_12px_rgba(245,197,96,0.15)]'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
                }`}
              >
                <Icon size={13} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── Memories Tab ─────────────────────────────────────────────── */}
        <AnimatePresence mode="wait">
          {activeTab === 'memories' && (
            <motion.div
              key="memories"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              {isLoading ? (
                <div className="text-center py-16 text-[var(--text-muted)] font-mono text-sm">
                  <Brain size={32} className="mx-auto mb-3 animate-pulse text-violet-400" />
                  Loading memories from ChromaDB...
                </div>
              ) : facts.length === 0 ? (
                <div className="text-center py-16 text-[var(--text-muted)] font-mono text-sm glass-panel-warm rounded-3xl border border-[var(--border-gold-glow)] p-8">
                  <Brain size={40} className="mx-auto mb-3 text-amber-400/40" />
                  <p className="text-[var(--text-muted)]">No memories yet.</p>
                  <p className="text-xs mt-1 text-[var(--text-subtle)]">Start a conversation — Kairos will automatically extract and remember facts about you.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {pinnedFacts.length > 0 && (
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-2 flex items-center gap-1.5">
                        <Pin size={10} /> Pinned Memories — Always injected into context
                      </div>
                      <div className="space-y-2">
                        {pinnedFacts.map(f => (
                          <FactCard key={f.id} fact={f} onDelete={handleDeleteFact} onTogglePin={handleTogglePin} />
                        ))}
                      </div>
                    </div>
                  )}

                  {unpinnedFacts.length > 0 && (
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-subtle)] mb-2 mt-4 flex items-center gap-1.5">
                        <Brain size={10} /> All Memories — Retrieved by semantic search
                      </div>
                      <div className="space-y-2">
                        {unpinnedFacts.map(f => (
                          <FactCard key={f.id} fact={f} onDelete={handleDeleteFact} onTogglePin={handleTogglePin} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          )}

          {/* ── Documents Tab ─────────────────────────────────────────── */}
          {activeTab === 'documents' && (
            <motion.div
              key="documents"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              {/* Upload Dropzone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setIsDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
                onClick={() => fileInputRef.current?.click()}
                className={`rounded-3xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
                  isDragOver
                    ? 'border-amber-400/80 bg-amber-400/10 shadow-[0_0_30px_rgba(245,197,96,0.2)]'
                    : 'border-[var(--border-gold-glow)] hover:border-amber-400/50 glass-panel-warm'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md"
                  className="hidden"
                  onChange={(e) => handleUpload(e.target.files[0])}
                />
                <Upload size={32} className={`mx-auto mb-3 ${isDragOver ? 'text-amber-400' : 'text-[var(--text-muted)]'}`} />
                <p className="text-sm font-semibold font-mono text-[var(--text-main)]">
                  {isDragOver ? 'Drop to ingest' : 'Drag & drop or click to upload'}
                </p>
                <p className="text-xs text-[var(--text-muted)] mt-1">PDF, TXT, or Markdown — chunked, embedded & stored locally</p>
              </div>

              {/* Upload Status Toast */}
              <AnimatePresence>
                {uploadStatus && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-sm font-mono ${
                      uploadStatus === 'uploading' ? 'border-cyan-500/40 bg-cyan-950/30 text-cyan-300' :
                      uploadStatus === 'success'   ? 'border-emerald-500/40 bg-emerald-950/30 text-emerald-300' :
                      'border-rose-500/40 bg-rose-950/30 text-rose-300'
                    }`}
                  >
                    {uploadStatus === 'uploading' && <RefreshCw size={15} className="animate-spin shrink-0" />}
                    {uploadStatus === 'success' && <CheckCircle size={15} className="shrink-0" />}
                    {uploadStatus === 'error' && <AlertCircle size={15} className="shrink-0" />}
                    <span>{uploadMsg}</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Documents List */}
              {isLoading ? (
                <div className="text-center py-12 text-[var(--text-muted)] font-mono text-sm">
                  <RefreshCw size={24} className="mx-auto mb-3 animate-spin text-cyan-400" />
                  Loading documents...
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-10 text-[var(--text-muted)] font-mono text-sm glass-panel rounded-3xl border border-[var(--border-gold-glow)] p-8">
                  <FileText size={36} className="mx-auto mb-3 text-cyan-400/30" />
                  <p>No documents ingested yet.</p>
                  <p className="text-xs mt-1 text-[var(--text-subtle)]">Upload PDFs, notes, or markdown files to give Kairos reference knowledge.</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-subtle)] mb-2 flex items-center gap-1.5">
                    <Database size={10} /> {documents.length} Document{documents.length !== 1 ? 's' : ''} in Knowledge Base
                  </div>
                  {documents.map(doc => (
                    <DocRow key={doc.doc_id} doc={doc} onDelete={handleDeleteDoc} userId={userId} />
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </motion.div>
  );
}
