import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageSquare, Settings, History, LayoutDashboard, 
  BookOpen, Brain, Copy, Sparkles, Cpu, Bot, 
  CheckCircle2, XCircle, Code, AppWindow, Youtube, Terminal,
  FileText, Check, ChevronRight, Play, MousePointer, ArrowDownUp
} from 'lucide-react';

function ActionChip({ action, onApprove, onDeny, onOpenSandbox }) {
  const [executed, setExecuted] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [denied, setDenied] = useState(false);

  // Auto-execute if confirmation is not required
  useEffect(() => {
    if (!action.confirmation && !executed && !executing) {
      handleExecute();
    }
  }, [action]);

  const handleExecute = async () => {
    setExecuting(true);
    try {
      if (action.tool === 'write_and_run_sandbox_code' && onOpenSandbox) {
        onOpenSandbox({
          code: action.params.code,
          language: action.params.language || 'python',
          filename: action.params.filename || 'solution.py',
          autoRun: action.params.auto_run ?? true
        });
      } else if (typeof window !== 'undefined' && window.kavya?.executeTool) {
        await window.kavya.executeTool(action.tool, action.params);
      } else {
        // Fallback for standard browser
        if (action.tool === 'search_and_play_youtube' || action.tool === 'open_youtube_in_brave' || action.tool === 'youtube_search') {
          const q = action.params?.query;
          const url = q ? `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}` : 'https://www.youtube.com';
          window.open(url, '_blank');
        } else if (action.tool === 'check_whatsapp_notifications') {
          window.open('https://web.whatsapp.com', '_blank');
        }
      }
      setExecuted(true);
    } catch (err) {
      console.error('[ActionChip] Execution failed:', err);
    } finally {
      setExecuting(false);
    }
  };

  const getToolIcon = () => {
    switch (action.tool) {
      case 'open_app': return <AppWindow size={14} className="text-blue-400" />;
      case 'open_youtube_in_brave':
      case 'youtube_search':
      case 'search_and_play_youtube': return <Youtube size={14} className="text-red-400" />;
      case 'youtube_play_video':
      case 'youtube_control': return <Play size={14} className="text-emerald-400" />;
      case 'scroll_page': return <ArrowDownUp size={14} className="text-sky-400" />;
      case 'cursor_control': return <MousePointer size={14} className="text-blue-400" />;
      case 'open_vscode_and_write_code': return <Code size={14} className="text-blue-400" />;
      case 'write_and_run_sandbox_code': return <Terminal size={14} className="text-blue-400" />;
      case 'check_whatsapp_notifications': return <MessageSquare size={14} className="text-blue-400" />;
      default: return <Sparkles size={14} className="text-blue-400" />;
    }
  };

  if (action.confirmation && !executed && !denied) {
    return (
      <div className="my-2.5 p-3 rounded-2xl bg-blue-950/40 border border-blue-500/40 text-xs font-mono space-y-2">
        <div className="flex items-center gap-2 text-blue-300 font-bold">
          <Sparkles size={15} />
          <span>CONFIRMATION REQUIRED // {action.summary || action.tool}</span>
        </div>
        <p className="text-[11px] text-[var(--text-muted)] font-sans">
          Kairos is requesting permission to execute: <span className="text-white font-semibold">{action.summary || action.tool}</span>.
        </p>
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={handleExecute}
            disabled={executing}
            className="px-3 py-1 rounded-xl bg-blue-600 hover:bg-blue-500 text-white border border-blue-400/50 transition-all font-bold cursor-pointer"
          >
            {executing ? 'Executing...' : '✓ Approve & Run'}
          </button>
          <button
            onClick={() => setDenied(true)}
            className="px-3 py-1 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 transition-all cursor-pointer"
          >
            ✕ Decline
          </button>
        </div>
      </div>
    );
  }

  if (denied) {
    return (
      <div className="my-2 px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-700/50 text-[11px] font-mono text-slate-400 flex items-center gap-2">
        <XCircle size={13} />
        <span>Action Declined: {action.summary || action.tool}</span>
      </div>
    );
  }

  return (
    <div 
      onClick={() => {
        if (action.tool === 'write_and_run_sandbox_code' && onOpenSandbox) {
          onOpenSandbox({
            code: action.params.code,
            language: action.params.language || 'python',
            filename: action.params.filename || 'solution.py',
            autoRun: false
          });
        }
      }}
      className={`my-2 px-3.5 py-2 rounded-2xl glass-panel border border-blue-500/20 text-[11px] font-mono flex items-center justify-between gap-3 shadow-md ${
        action.tool === 'write_and_run_sandbox_code' ? 'cursor-pointer hover:border-blue-400/50 transition-all' : ''
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <div className="p-1 rounded-lg bg-slate-900 border border-blue-500/20 shrink-0">
          {getToolIcon()}
        </div>
        <span className="font-semibold text-slate-200 truncate">
          {action.summary || `Execute ${action.tool}`}
        </span>
      </div>
      <div className="flex items-center gap-1 text-blue-400 shrink-0 font-bold text-[10px]">
        <CheckCircle2 size={13} />
        <span>{action.tool === 'write_and_run_sandbox_code' ? 'OPEN IN SANDBOX ↗' : 'EXECUTED'}</span>
      </div>
    </div>
  );
}

function FormattedContent({ text, onOpenSandbox }) {
  if (!text) return null;

  // Extract [ACTION:{...}] tag if present
  let actionData = null;
  let cleanText = text;

  const actionMatch = text.match(/\[ACTION:(\{.*?\})\]/s);
  if (actionMatch) {
    try {
      actionData = JSON.parse(actionMatch[1]);
      cleanText = text.replace(/\[ACTION:(\{.*?\})\]/s, '').trim();
    } catch (e) {
      console.warn('[FormattedContent] Failed to parse action JSON:', e);
    }
  }
  
  const parts = cleanText.split(/(```[\s\S]*?```)/g);
  
  return (
    <div className="space-y-2">
      {actionData && <ActionChip action={actionData} onOpenSandbox={onOpenSandbox} />}

      {parts.map((part, index) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const match = part.slice(3, -3).trim();
          const firstLineIndex = match.indexOf('\n');
          let lang = 'code';
          let code = match;
          
          if (firstLineIndex !== -1 && !match.substring(0, firstLineIndex).includes(' ')) {
            lang = match.substring(0, firstLineIndex).trim();
            code = match.substring(firstLineIndex + 1);
          }

          return (
            <div key={index} className="my-2 rounded-xl overflow-hidden border border-blue-500/25 bg-slate-950/90">
              <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-900/80 border-b border-blue-500/20 text-[11px] font-mono text-blue-300">
                <span>{lang}</span>
                <div className="flex items-center gap-2">
                  {onOpenSandbox && (
                    <button
                      onClick={() => onOpenSandbox({ code, language: lang === 'js' || lang === 'javascript' ? 'javascript' : 'python', autoRun: false })}
                      className="hover:text-blue-200 transition-colors flex items-center gap-1 cursor-pointer"
                      title="Run in Sandbox"
                    >
                      <Terminal size={12} />
                      <span>Sandbox</span>
                    </button>
                  )}
                  <button
                    onClick={() => navigator.clipboard.writeText(code)}
                    className="hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
                    title="Copy code"
                  >
                    <Copy size={12} />
                    <span>Copy</span>
                  </button>
                </div>
              </div>
              <pre className="p-3 text-xs md:text-sm font-mono text-blue-200 overflow-x-auto leading-relaxed">
                <code>{code}</code>
              </pre>
            </div>
          );
        }
        return <p key={index} className="whitespace-pre-wrap">{part}</p>;
      })}
    </div>
  );
}

function Bubble({ role, text, emotion, activeAvatar, onOpenSandbox }) {
  const isUser = role === 'user';
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className={`flex flex-col mb-4 ${isUser ? 'items-end' : 'items-start'}`}
    >
      {!isUser && (
        <div className="flex items-center gap-1.5 mb-1.5 ml-2">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400 font-semibold">
            {emotion || 'Kairos'}
          </span>
        </div>
      )}
      <div 
        className={`max-w-[88%] px-5 py-3.5 text-sm md:text-base leading-relaxed ${
          isUser 
            ? 'bg-blue-600 text-white rounded-[22px_22px_4px_22px] shadow-[0_6px_20px_rgba(59,130,246,0.3)] border border-blue-400/30 font-normal'
            : 'bg-[var(--surface)] backdrop-blur-2xl text-slate-100 rounded-[22px_22px_22px_4px] border border-blue-500/20 shadow-[0_8px_24px_rgba(0,0,0,0.35)]'
        }`}
      >
        <FormattedContent text={text} onOpenSandbox={onOpenSandbox} />
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
  userId,
  selectedDocIds,
  onToggleSelectDoc,
  onSelectAllDocs,
  onDeselectAllDocs,
  onHistoryClick, 
  onDashboardClick, 
  onAboutClick, 
  onMemoryClick, 
  onSandboxClick, 
  onOpenSandbox, 
  onSettingsClick, 
  vadSensitivity = 'medium', 
  onVadSensitivityChange 
}) {
  const scrollRef = useRef(null);
  const [availableDocs, setAvailableDocs] = useState([]);
  const [isDocSelectorOpen, setIsDocSelectorOpen] = useState(false);

  // Fetch ingested documents for RAG selection bar
  useEffect(() => {
    if (userId) {
      fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/memory/documents/${encodeURIComponent(userId)}`)
        .then(res => res.json())
        .then(data => setAvailableDocs(Array.isArray(data) ? data : []))
        .catch(() => setAvailableDocs([]));
    }
  }, [userId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages, status]);

  const isListening = status === 'Listening';
  const isThinking = status === 'Thinking';
  const isSpeaking = status === 'Speaking';

  const allDocIds = availableDocs.map(d => d.doc_id);
  const activeCount = selectedDocIds === null ? availableDocs.length : selectedDocIds.length;

  return (
    <div className="w-full md:w-[390px] lg:w-[440px] flex flex-col h-full bg-[var(--surface-glass)] backdrop-blur-3xl border-l border-[var(--border-glass)] z-20 shrink-0 relative shadow-2xl">
      
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border-glass)] bg-[var(--surface)]">
        
        {/* Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-blue-500/30">
          <div className={`w-2 h-2 rounded-full transition-all duration-300 ${
            isListening ? 'bg-blue-400 shadow-[0_0_10px_#60a5fa] animate-pulse' :
            isThinking ? 'bg-sky-300 shadow-[0_0_10px_#38bdf8] animate-pulse' :
            isSpeaking ? 'bg-blue-500 shadow-[0_0_10px_#3b82f6] animate-pulse' :
            'bg-slate-400'
          }`} />
          <span className="text-[11px] font-mono font-semibold tracking-wider uppercase text-slate-200">
            {isThinking ? 'PROCESSING...' : status}
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5">
          {/* Language Selector */}
          <select 
            value={preferredLanguage}
            onChange={e => onLanguageChange(e.target.value)}
            className="bg-slate-900/80 border border-slate-700 text-slate-200 text-xs font-mono font-semibold rounded-xl px-2 py-1.5 outline-none cursor-pointer hover:border-blue-500 transition-all"
            title="Speech Transcription Language"
          >
            <option value="en">EN</option>
            <option value="hi">HI</option>
            <option value="auto">AUTO</option>
          </select>

          {/* Sandbox Button */}
          {onSandboxClick && (
            <button 
              onClick={onSandboxClick} 
              className="p-2 rounded-xl bg-slate-900/80 hover:bg-blue-600/20 hover:text-blue-300 text-slate-300 transition-all border border-slate-700/60 hover:border-blue-500/40 cursor-pointer shadow-sm" 
              title="Code Sandbox (Monaco Editor)"
            >
              <Code size={15} />
            </button>
          )}

          {/* Memory Panel Button */}
          {onMemoryClick && (
            <button 
              onClick={onMemoryClick} 
              className="p-2 rounded-xl bg-slate-900/80 hover:bg-blue-600/20 hover:text-blue-300 text-slate-300 transition-all border border-slate-700/60 hover:border-blue-500/40 cursor-pointer shadow-sm" 
              title="Long-Term Memory & Documents"
            >
              <Brain size={15} />
            </button>
          )}

          {/* History Button */}
          <button 
            onClick={onHistoryClick} 
            className="p-2 rounded-xl bg-slate-900/80 hover:bg-blue-600/20 hover:text-blue-300 text-slate-300 transition-all border border-slate-700/60 hover:border-blue-500/40 cursor-pointer shadow-sm" 
            title="Conversation History"
          >
            <History size={15} />
          </button>

          {/* Settings Button */}
          <button 
            onClick={onSettingsClick} 
            className="p-2 rounded-xl bg-slate-900/80 hover:bg-blue-600/20 hover:text-blue-300 text-slate-300 transition-all border border-slate-700/60 hover:border-blue-500/40 cursor-pointer shadow-sm" 
            title="Voice & App Settings"
          >
            <Settings size={15} />
          </button>
        </div>
      </div>

      {/* ── Interactive RAG Document Grounding Bar ──────────────────────── */}
      {availableDocs.length > 0 && (
        <div className="px-4 py-2 border-b border-[var(--border-glass)] bg-slate-950/60">
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <div 
              onClick={() => setIsDocSelectorOpen(!isDocSelectorOpen)}
              className="flex items-center gap-1.5 text-[11px] font-mono text-slate-300 hover:text-blue-300 transition-colors cursor-pointer"
            >
              <FileText size={12} className="text-blue-400" />
              <span className="font-semibold uppercase tracking-wider">RAG Context:</span>
              <span className="px-1.5 py-0.2 rounded-md bg-blue-500/20 text-blue-300 text-[10px] border border-blue-500/30">
                {activeCount} of {availableDocs.length} active
              </span>
            </div>
            
            <div className="flex items-center gap-1.5 text-[10px] font-mono">
              <button 
                onClick={() => onSelectAllDocs && onSelectAllDocs(allDocIds)}
                className="px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-blue-600/20 text-slate-400 hover:text-blue-300 border border-slate-700 hover:border-blue-500/30 transition-all cursor-pointer"
              >
                All
              </button>
              <button 
                onClick={() => onDeselectAllDocs && onDeselectAllDocs()}
                className="px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 transition-all cursor-pointer"
              >
                None
              </button>
            </div>
          </div>

          {/* Horizontal Document Toggle Chips */}
          <div className="flex flex-wrap items-center gap-1.5 max-h-20 overflow-y-auto py-0.5">
            {availableDocs.map(doc => {
              const isSelected = selectedDocIds === null || selectedDocIds.includes(doc.doc_id);
              return (
                <button
                  key={doc.doc_id}
                  onClick={() => onToggleSelectDoc && onToggleSelectDoc(doc.doc_id, allDocIds)}
                  title={`${doc.doc_name} (${doc.chunk_count} chunks) — Click to ${isSelected ? 'unselect' : 'select'} for chat context`}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11px] font-mono transition-all cursor-pointer border ${
                    isSelected
                      ? 'bg-blue-500/20 text-blue-200 border-blue-500/50 shadow-[0_0_10px_rgba(59,130,246,0.15)] font-semibold'
                      : 'bg-slate-900/60 text-slate-500 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className={`w-3.5 h-3.5 rounded flex items-center justify-center text-[10px] ${
                    isSelected ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-600'
                  }`}>
                    {isSelected ? <Check size={10} strokeWidth={3} /> : null}
                  </div>
                  <span className="max-w-[120px] truncate">{doc.doc_name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Messages Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto chat-scroll p-5 space-y-2">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-3 opacity-60">
            <div className="w-14 h-14 rounded-2xl bg-blue-500/10 flex items-center justify-center text-blue-400 border border-blue-500/20">
              <MessageSquare size={26} strokeWidth={1.5} />
            </div>
            <p className="text-xs text-center font-mono uppercase tracking-wider">
              Awaiting user audio transmission...
            </p>
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
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="flex items-start mb-4"
            >
              <div className="bg-slate-900/90 backdrop-blur-2xl rounded-[22px_22px_22px_4px] px-5 py-3.5 border border-blue-500/30 shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                  <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" style={{ animationDelay: '0.2s' }} />
                  <div className="w-2 h-2 rounded-full bg-blue-300 animate-pulse" style={{ animationDelay: '0.4s' }} />
                  <span className="text-xs font-mono text-slate-300 ml-2">Neural reasoning...</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
