import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Brain, FileText, Pin, PinOff, Trash2, Upload, RefreshCw,
  Clock, AlertCircle, CheckCircle, BookOpen, Sparkles, Database, Check
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
      className={`glass-panel rounded-2xl p-4 border transition-all ${
        fact.pinned
          ? 'border-blue-500/60 bg-blue-950/20 shadow-[0_4px_20px_rgba(59,130,246,0.15)]'
          : 'border-slate-800 hover:border-slate-700'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 shrink-0 ${fact.pinned ? 'text-blue-400' : 'text-slate-500'}`}>
          <Sparkles size={14} />
        </div>
        <p className="flex-1 text-sm text-slate-100 leading-relaxed font-sans">{fact.content}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onTogglePin(fact.id, !fact.pinned)}
            title={fact.pinned ? 'Unpin memory' : 'Pin memory — always included in context'}
            className={`p-1.5 rounded-xl transition-all cursor-pointer ${
              fact.pinned
                ? 'bg-blue-500/20 text-blue-300 hover:bg-blue-500/30'
                : 'text-slate-400 hover:text-blue-300 hover:bg-blue-500/10'
            }`}
          >
            {fact.pinned ? <Pin size={13} /> : <PinOff size={13} />}
          </button>
          <button
            onClick={() => onDelete(fact.id)}
            title="Delete this memory"
            className="p-1.5 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3 text-[10px] font-mono text-slate-500">
        <span className="flex items-center gap-1"><Clock size={10} /> {formatDate(fact.created_at)}</span>
        <span className="flex items-center gap-1">
          <BookOpen size={10} /> {fact.source || 'conversation'}
        </span>
        {fact.pinned && (
          <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">📌 PINNED</span>
        )}
      </div>
    </motion.div>
  );
}

function DocRow({ doc, onDelete, userId, isSelected, onToggleSelect, allDocIds }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`glass-panel rounded-2xl p-4 border flex items-center gap-3 transition-all ${
        isSelected
          ? 'border-blue-500/40 bg-blue-950/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]'
          : 'border-slate-800/80 bg-slate-900/40'
      }`}
    >
      <div className="p-2.5 rounded-xl bg-blue-950/50 border border-blue-500/30 text-blue-400 shrink-0">
        <FileText size={18} />
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold font-mono text-slate-100 truncate">{doc.doc_name}</div>
        <div className="text-[11px] font-mono text-slate-400 mt-0.5 flex items-center gap-3">
          <span className="flex items-center gap-1"><Database size={10} /> {doc.chunk_count} chunks</span>
          <span className="flex items-center gap-1"><Clock size={10} /> {formatDate(doc.created_at)}</span>
        </div>
      </div>

      {onToggleSelect && (
        <button
          onClick={() => onToggleSelect(doc.doc_id, allDocIds)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-semibold transition-all cursor-pointer border ${
            isSelected
              ? 'bg-blue-600/25 text-blue-200 border-blue-500/60 shadow-[0_0_12px_rgba(59,130,246,0.2)]'
              : 'bg-slate-800/80 text-slate-400 border-slate-700 hover:border-slate-600'
          }`}
          title={isSelected ? 'Included in Chat RAG — click to exclude' : 'Excluded from Chat RAG — click to include'}
        >
          <div className={`w-3.5 h-3.5 rounded flex items-center justify-center text-[10px] ${
            isSelected ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-500'
          }`}>
            {isSelected ? <Check size={10} strokeWidth={3} /> : null}
          </div>
          <span>{isSelected ? 'Active in Chat' : 'Inactive'}</span>
        </button>
      )}

      <button
        onClick={() => onDelete(doc.doc_id)}
        title="Delete this document from memory"
        className="p-2 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer shrink-0"
      >
        <Trash2 size={15} />
      </button>
    </motion.div>
  );
}

export default function MemoryPanel({ 
  onClose, 
  userId, 
  theme = 'dark',
  selectedDocIds = null,
  onToggleSelectDoc,
  onSelectAllDocs,
  onDeselectAllDocs
}) {
  const [activeTab, setActiveTab] = useState('memories');
  const [facts, setFacts] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadStatus, setUploadStatus] = useState(null); 
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

  useEffect(() => {
    refresh();
  }, [userId]);

  const handleDeleteFact = async (factId) => {
    await fetch(`${API}/api/memory/facts/${encodeURIComponent(factId)}?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' });
    setFacts(prev => prev.filter(f => f.id !== factId));
  };

  const handleTogglePin = async (factId, pinned) => {
    await fetch(`${API}/api/memory/facts/${encodeURIComponent(factId)}/pin?user_id=${encodeURIComponent(userId)}&pinned=${pinned}`, { method: 'POST' });
    setFacts(prev => prev.map(f => f.id === factId ? { ...f, pinned } : f));
  };

  const handleDeleteDoc = async (docId) => {
    await fetch(`${API}/api/memory/documents/${encodeURIComponent(docId)}?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' });
    setDocuments(prev => prev.filter(d => d.doc_id !== docId));
  };

  const handleUpload = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'txt', 'md'].includes(ext)) {
      setUploadStatus('error');
      setUploadMsg('Only .pdf, .txt, and .md files are supported.');
      setTimeout(() => setUploadStatus(null), 3000);
      return;
    }

    setUploadStatus('uploading');
    setUploadMsg(`Ingesting ${file.name}...`);
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
        setUploadMsg(`Ingested "${data.doc_name}" into ${data.chunks_stored} searchable chunks!`);
        fetchDocs();
        neuralStateMachine.onActionExecuted('document_ingested');
        setTimeout(() => setUploadStatus(null), 4000);
      } else {
        throw new Error(data.detail || 'Ingestion failed');
      }
    } catch (e) {
      setUploadStatus('error');
      setUploadMsg(`Failed: ${e.message}`);
      setTimeout(() => setUploadStatus(null), 4000);
    }
  };

  const pinnedFacts = facts.filter(f => f.pinned);
  const unpinnedFacts = facts.filter(f => !f.pinned);
  const allDocIds = documents.map(d => d.doc_id);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`fixed inset-0 z-50 overflow-y-auto bg-[var(--background)]/95 backdrop-blur-2xl p-4 md:p-8 ${theme}`}
    >
      <div className="animated-grid-bg" />

      <div className="max-w-4xl mx-auto relative z-10 space-y-6 pb-12">

        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-glass)]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(59,130,246,0.4)]">
              <Brain size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold font-mono tracking-wider text-white">KAIROS // LONG-TERM MEMORY</h1>
              <p className="text-[11px] font-mono text-slate-400">
                {facts.length} facts · {documents.length} documents · ChromaDB
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={refresh}
              title="Refresh memory"
              className="p-2.5 rounded-xl glass-panel border border-slate-700 text-slate-400 hover:text-blue-300 transition-all cursor-pointer"
            >
              <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={onClose}
              className="p-2.5 rounded-xl glass-panel border border-slate-700 text-slate-300 hover:text-red-300 hover:bg-red-500/10 transition-all cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="px-3 py-1.5 rounded-full glass-panel border border-blue-500/40 text-xs font-mono text-blue-300">
            📌 {pinnedFacts.length} Pinned
          </div>
          <div className="px-3 py-1.5 rounded-full glass-panel border border-slate-700 text-xs font-mono text-slate-300">
            🧠 {facts.length} Memories
          </div>
          <div className="px-3 py-1.5 rounded-full glass-panel border border-blue-500/30 text-xs font-mono text-blue-300">
            📄 {documents.length} Documents
          </div>
          <div className="px-3 py-1.5 rounded-full glass-panel border border-sky-500/30 text-xs font-mono text-sky-300">
            ⚡ Auto-extracts from every turn
          </div>
        </div>

        <div className="flex gap-1 p-1 glass-panel rounded-2xl border border-[var(--border-glass)] w-fit">
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
                    ? 'bg-blue-600 text-white border border-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.3)]'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Icon size={13} />
                {tab.label}
              </button>
            );
          })}
        </div>

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
                <div className="text-center py-16 text-slate-400 font-mono text-sm">
                  <Brain size={32} className="mx-auto mb-3 animate-pulse text-blue-400" />
                  Loading memories from ChromaDB...
                </div>
              ) : facts.length === 0 ? (
                <div className="text-center py-16 text-slate-400 font-mono text-sm glass-panel rounded-3xl border border-[var(--border-glass)] p-8">
                  <Brain size={40} className="mx-auto mb-3 text-blue-400/30" />
                  <p className="text-slate-300">No memories yet.</p>
                  <p className="text-xs mt-1 text-slate-500">Start a conversation — Kairos will automatically extract and remember facts about you.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {pinnedFacts.length > 0 && (
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-blue-300 mb-2 flex items-center gap-1.5">
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
                      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-2 mt-4 flex items-center gap-1.5">
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

          {activeTab === 'documents' && (
            <motion.div
              key="documents"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setIsDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
                onClick={() => fileInputRef.current?.click()}
                className={`rounded-3xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
                  isDragOver
                    ? 'border-blue-400 bg-blue-500/10 shadow-[0_0_30px_rgba(59,130,246,0.2)]'
                    : 'border-slate-800 hover:border-blue-500/50 glass-panel'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md"
                  className="hidden"
                  onChange={(e) => handleUpload(e.target.files[0])}
                />
                <Upload size={32} className={`mx-auto mb-3 ${isDragOver ? 'text-blue-400' : 'text-slate-400'}`} />
                <p className="text-sm font-semibold font-mono text-white">
                  {isDragOver ? 'Drop to ingest' : 'Drag & drop or click to upload'}
                </p>
                <p className="text-xs text-slate-400 mt-1">PDF, TXT, or Markdown — chunked, embedded & stored locally</p>
              </div>

              <AnimatePresence>
                {uploadStatus && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-sm font-mono ${
                      uploadStatus === 'uploading' ? 'border-blue-500/40 bg-blue-950/40 text-blue-300' :
                      uploadStatus === 'success'   ? 'border-sky-500/40 bg-sky-950/40 text-sky-300' :
                      'border-red-500/40 bg-red-950/40 text-red-300'
                    }`}
                  >
                    {uploadStatus === 'uploading' && <RefreshCw size={15} className="animate-spin shrink-0" />}
                    {uploadStatus === 'success' && <CheckCircle size={15} className="shrink-0" />}
                    {uploadStatus === 'error' && <AlertCircle size={15} className="shrink-0" />}
                    <span>{uploadMsg}</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {documents.length > 0 && (
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
                  <div className="flex items-center gap-1.5 uppercase tracking-wider">
                    <Database size={12} className="text-blue-400" />
                    <span>{documents.length} Documents in Knowledge Base</span>
                  </div>
                  {onSelectAllDocs && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onSelectAllDocs(allDocIds)}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-blue-600/20 text-slate-300 hover:text-blue-300 border border-slate-700 transition-all cursor-pointer"
                      >
                        Select All for Chat
                      </button>
                      <button
                        onClick={() => onDeselectAllDocs && onDeselectAllDocs()}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-all cursor-pointer"
                      >
                        Deselect All
                      </button>
                    </div>
                  )}
                </div>
              )}

              {isLoading ? (
                <div className="text-center py-12 text-slate-400 font-mono text-sm">
                  <RefreshCw size={24} className="mx-auto mb-3 animate-spin text-blue-400" />
                  Loading documents...
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-10 text-slate-400 font-mono text-sm glass-panel rounded-3xl border border-[var(--border-glass)] p-8">
                  <FileText size={36} className="mx-auto mb-3 text-blue-400/30" />
                  <p>No documents ingested yet.</p>
                  <p className="text-xs mt-1 text-slate-500">Upload PDFs, notes, or markdown files to give Kairos reference knowledge.</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {documents.map(doc => {
                    const isSelected = selectedDocIds === null || selectedDocIds.includes(doc.doc_id);
                    return (
                      <DocRow 
                        key={doc.doc_id} 
                        doc={doc} 
                        onDelete={handleDeleteDoc} 
                        userId={userId} 
                        isSelected={isSelected}
                        onToggleSelect={onToggleSelectDoc}
                        allDocIds={allDocIds}
                      />
                    );
                  })}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </motion.div>
  );
}
