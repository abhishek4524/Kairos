import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageSquare, Settings, History, Sun, Moon, LayoutDashboard, 
  BookOpen, Brain, Copy, Check, Sparkles, Heart, Cpu, Bot, Flame, 
  Play, ExternalLink, ShieldAlert, CheckCircle2, XCircle, Code, AppWindow, Youtube, Terminal
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
        if (action.tool === 'search_and_play_youtube') {
          window.open(`https://www.youtube.com/results?search_query=${encodeURIComponent(action.params.query || '')}`, '_blank');
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
      case 'open_app': return <AppWindow size={14} className="text-cyan-400" />;
      case 'search_and_play_youtube': return <Youtube size={14} className="text-rose-400" />;
      case 'open_vscode_and_write_code': return <Code size={14} className="text-amber-400" />;
      case 'write_and_run_sandbox_code': return <Terminal size={14} className="text-amber-400" />;
      case 'check_whatsapp_notifications': return <MessageSquare size={14} className="text-emerald-400" />;
      default: return <Sparkles size={14} className="text-amber-400" />;
    }
  };

  if (action.confirmation && !executed && !denied) {
    return (
      <div className="my-2.5 p-3 rounded-2xl bg-amber-950/30 border border-amber-400/50 text-xs font-mono space-y-2">
        <div className="flex items-center gap-2 text-amber-300 font-bold">
          <ShieldAlert size={15} />
          <span>CONFIRMATION REQUIRED // {action.summary || action.tool}</span>
        </div>
        <p className="text-[11px] text-[var(--text-muted)] font-sans">
          Kavya is requesting permission to execute: <span className="text-[var(--text-main)] font-semibold">{action.summary || action.tool}</span>.
        </p>
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={handleExecute}
            disabled={executing}
            className="px-3 py-1 rounded-xl bg-amber-400/20 text-amber-300 border border-amber-400/50 hover:bg-amber-400/30 transition-all font-bold cursor-pointer"
          >
            {executing ? 'Executing...' : '✓ Approve & Run'}
          </button>
          <button
            onClick={() => setDenied(true)}
            className="px-3 py-1 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 transition-all cursor-pointer"
          >
            ✕ Decline
          </button>
        </div>
      </div>
    );
  }

  if (denied) {
    return (
      <div className="my-2 px-3 py-1.5 rounded-xl bg-rose-950/20 border border-rose-500/30 text-[11px] font-mono text-rose-300 flex items-center gap-2">
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
      className={`my-2 px-3.5 py-2 rounded-2xl glass-panel-warm border border-[var(--border-gold-glow)] text-[11px] font-mono flex items-center justify-between gap-3 shadow-md ${
        action.tool === 'write_and_run_sandbox_code' ? 'cursor-pointer hover:border-amber-400 transition-all' : ''
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <div className="p-1 rounded-lg bg-slate-900/80 border border-white/10 shrink-0">
          {getToolIcon()}
        </div>
        <span className="font-semibold text-[var(--text-main)] truncate">
          {action.summary || `Execute ${action.tool}`}
        </span>
      </div>
      <div className="flex items-center gap-1 text-emerald-400 shrink-0 font-bold text-[10px]">
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
            <div key={index} className="my-2 rounded-xl overflow-hidden border border-cyan-500/20 bg-slate-950/80">
              <div className="flex items-center justify-between px-3.5 py-1.5 bg-cyan-950/30 border-b border-cyan-500/15 text-[11px] font-mono text-cyan-400">
                <span>{lang}</span>
                <div className="flex items-center gap-2">
                  {onOpenSandbox && (
                    <button
                      onClick={() => onOpenSandbox({ code, language: lang === 'js' || lang === 'javascript' ? 'javascript' : 'python', autoRun: false })}
                      className="hover:text-amber-300 transition-colors flex items-center gap-1 cursor-pointer"
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
              <pre className="p-3 text-xs md:text-sm font-mono text-cyan-300 overflow-x-auto leading-relaxed">
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

const WARM_KEYWORDS = ['welcome', 'hello', 'hi', 'hey', 'happy', 'glad', 'pleasure', 'love', 'thank', 'thanks', 'friend', 'dost', 'yaar', 'great', 'wonderful', 'awesome', 'smile', 'enjoy', 'cheers'];
const TASK_KEYWORDS = ['done', 'function', 'code', 'error', 'command', 'terminal', 'system', 'process', 'task', 'run', 'file', 'script', 'execute'];

function deriveMessageTone(emotion, text) {
  const lower = String(text || '').toLowerCase();
  const emo = String(emotion || '').toLowerCase();
  
  if (['happy', 'comforting', 'greeting', 'openness', 'friendlyContact', 'jollyLaughter', 'coySmile'].includes(emo) || WARM_KEYWORDS.some(w => lower.includes(w))) {
    return 'warm';
  }
  if (TASK_KEYWORDS.some(w => lower.includes(w))) {
    return 'task';
  }
  if (['thinking', 'thoughtfulness', 'attentive'].includes(emo)) {
    return 'thoughtful';
  }
  return 'neutral';
}

function Bubble({ role, text, emotion, activeAvatar, onOpenSandbox }) {
  const isUser = role === 'user';
  const tone = !isUser ? deriveMessageTone(emotion, text) : 'user';
  const isWarm = tone === 'warm';
  const isTask = tone === 'task';
  const isThoughtful = tone === 'thoughtful';
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className={`flex flex-col mb-4 ${isUser ? 'items-end' : 'items-start'}`}
    >
      {!isUser && (
        <div className="flex items-center gap-1.5 mb-1.5 ml-2">
          {/* Subtle Tone Glyph */}
          {isWarm ? (
            <Sparkles size={11} className="text-amber-400 animate-pulse" />
          ) : isTask ? (
            <Cpu size={11} className="text-cyan-400" />
          ) : isThoughtful ? (
            <Bot size={11} className="text-violet-400" />
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          )}

          <span className={`text-[10px] font-mono uppercase tracking-widest ${
            isWarm ? 'text-amber-300 font-semibold' : 
            isTask ? 'text-cyan-300' : 
            isThoughtful ? 'text-violet-300' : 
            'text-[var(--text-subtle)]'
          }`}>
            {emotion || (isWarm ? 'Warm' : isTask ? 'Task' : 'Kavya')}
          </span>
        </div>
      )}
      <div 
        className={`max-w-[88%] px-5 py-3.5 text-sm md:text-base leading-relaxed ${
          isUser 
            ? 'bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-600 text-white rounded-[26px_26px_6px_26px] shadow-[0_6px_24px_rgba(6,182,212,0.25)] border border-cyan-400/30 font-normal'
            : isWarm
            ? 'bg-[var(--surface-glass)] backdrop-blur-2xl text-[var(--text-main)] rounded-[26px_26px_26px_6px] border border-amber-400/40 shadow-[0_8px_28px_rgba(245,197,96,0.12)]'
            : isThoughtful
            ? 'bg-[var(--surface-glass)] backdrop-blur-2xl text-[var(--text-main)] rounded-[26px_26px_26px_6px] border border-violet-400/35 shadow-[0_8px_28px_rgba(139,92,246,0.12)]'
            : 'bg-[var(--surface-glass)] backdrop-blur-2xl text-[var(--text-main)] rounded-[26px_26px_26px_6px] border border-cyan-400/25 shadow-[0_8px_28px_rgba(6,182,212,0.12)]'
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
  onThemeToggle,
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
  const isWarmState = emotion === 'happy' || emotion === 'comforting';

  return (
    <div className="w-full md:w-[390px] lg:w-[440px] flex flex-col h-full bg-[var(--surface-glass)] backdrop-blur-3xl border-l border-[var(--border-gold-glow)] z-20 shrink-0 relative shadow-2xl">
      
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border-gold-glow)] bg-[var(--surface)]">
        
        {/* Status Hologram Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface-hover)] border border-[var(--border-gold-glow)]">
          <div className={`w-2 h-2 rounded-full transition-all duration-300 ${
            isListening ? 'bg-cyan-400 shadow-[0_0_10px_#06b6d4] animate-pulse' :
            isThinking ? 'bg-violet-400 shadow-[0_0_10px_#8b5cf6] animate-pulse' :
            isSpeaking ? 'bg-emerald-400 shadow-[0_0_10px_#10b981] animate-pulse' :
            isWarmState ? 'bg-amber-400 shadow-[0_0_10px_#f5c560] animate-pulse' :
            'bg-amber-300/60'
          }`} />
          <span className="text-[11px] font-mono font-semibold tracking-wider uppercase text-[var(--text-main)]">
            {isThinking ? 'PROCESSING...' : status}
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5">
          {/* Language Selector */}
          <select 
            value={preferredLanguage}
            onChange={e => onLanguageChange(e.target.value)}
            className="bg-[var(--surface-hover)] border border-[var(--border-gold-glow)] text-[var(--text-main)] text-xs font-mono font-semibold rounded-xl px-2 py-1.5 outline-none cursor-pointer hover:border-amber-400 transition-all"
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
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-transparent hover:border-amber-500/30 cursor-pointer shadow-sm" 
              title="Code Sandbox (Monaco Editor)"
            >
              <Code size={15} />
            </button>
          )}

          {/* Memory Panel Button */}
          {onMemoryClick && (
            <button 
              onClick={onMemoryClick} 
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-violet-500/20 hover:text-violet-300 text-[var(--text-main)] transition-all border border-transparent hover:border-violet-500/30 cursor-pointer shadow-sm" 
              title="Long-Term Memory & Documents"
            >
              <Brain size={15} />
            </button>
          )}

          {/* Character Codex / Info Hub Button */}
          {onAboutClick && (
            <button 
              onClick={onAboutClick} 
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-transparent hover:border-amber-500/30 cursor-pointer shadow-sm" 
              title="About Kavya // Character Codex"
            >
              <BookOpen size={15} />
            </button>
          )}

          {/* Dashboard Button */}
          {onDashboardClick && (
            <button 
              onClick={onDashboardClick} 
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-transparent hover:border-amber-500/30 cursor-pointer shadow-sm" 
              title="System Dashboard"
            >
              <LayoutDashboard size={15} />
            </button>
          )}

          {/* History Button */}
          <button 
            onClick={onHistoryClick} 
            className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-transparent hover:border-amber-500/30 cursor-pointer shadow-sm" 
            title="Conversation History"
          >
            <History size={15} />
          </button>

          {/* Settings Button */}
          <button 
            onClick={onSettingsClick} 
            className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-transparent hover:border-amber-500/30 cursor-pointer shadow-sm" 
            title="Voice & App Settings"
          >
            <Settings size={15} />
          </button>

          {/* Theme Toggle Button */}
          <button 
            onClick={onThemeToggle} 
            className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-transparent hover:border-amber-500/30 cursor-pointer shadow-sm" 
            title="Toggle Dark / Light Theme"
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </div>

      {/* Settings now handled by SettingsModal via onSettingsClick */}

      {/* Messages Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto chat-scroll p-5 space-y-2">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-[var(--text-muted)] gap-3 opacity-60">
            <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 flex items-center justify-center text-cyan-400 border border-cyan-500/20">
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
              <div className="bg-[var(--surface-glass)] backdrop-blur-2xl rounded-[22px_22px_22px_4px] px-5 py-3.5 border border-violet-500/30 shadow-[0_0_20px_rgba(139,92,246,0.2)]">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
                  <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" style={{ animationDelay: '0.2s' }} />
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" style={{ animationDelay: '0.4s' }} />
                  <span className="text-xs font-mono text-[var(--text-muted)] ml-2">Neural synthesis...</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
