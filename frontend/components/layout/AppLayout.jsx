import React, { useMemo, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

import ChatPanel from '../chat/ChatPanel';
import HeroAICore from '../neural/HeroAICore';
import VoiceDock from './VoiceDock';
import ElectronTitleBar from './ElectronTitleBar';
import AdminDashboard from '../admin/AdminDashboard';
import AboutKavya from '../info/AboutKavya';
import MemoryPanel from '../memory/MemoryPanel';
import CodeSandbox from '../sandbox/CodeSandbox';
import SettingsModal from '../settings/SettingsModal';
import HistoryList from '../chat/HistoryList';
import { useAudioStreaming } from '../../hooks/useAudioStreaming';
import { MessageSquare, Clock, X, Sparkles } from 'lucide-react';

// Detect if running inside Electron (preload exposes window.kavya)
const IS_ELECTRON = typeof window !== 'undefined' && !!window.kavya;
const TITLEBAR_HEIGHT = IS_ELECTRON ? 36 : 0;

// ── Anonymous Browser-Based User Identity ───────────────────────────────────
const getUserId = () => {
  try {
    let uid = localStorage.getItem('nanban_user_id');
    if (!uid) {
      uid = 'nanban_user_' + crypto.randomUUID().replace(/-/g, '').slice(0, 16);
      localStorage.setItem('nanban_user_id', uid);
    }
    return uid;
  } catch {
    if (!getUserId._fallback) getUserId._fallback = 'nanban_user_' + Math.random().toString(36).slice(2, 18);
    return getUserId._fallback;
  }
};

const FRIENDLY_WORDS = ['hi', 'hello', 'hey', 'thanks', 'thank', 'please', 'love', 'nice', 'great', 'awesome', 'yaar', 'dost', 'bro', 'sis'];
const EXCITED_WORDS = ['wow', 'amazing', 'haha', 'lol', 'yay', 'super', 'perfect', 'cool'];

const deriveUserRapportEnergy = (messages) => {
  const recent = messages.filter(msg => msg.role === 'user').slice(-4);
  if (!recent.length) return 0.35;

  const total = recent.reduce((score, msg) => {
    const text = String(msg.text || '').toLowerCase();
    const words = text.split(/\s+/).filter(Boolean);
    const exclamations = (text.match(/!/g) || []).length;
    const friendliness = FRIENDLY_WORDS.some(word => text.includes(word)) ? 0.22 : 0;
    const excitement = EXCITED_WORDS.some(word => text.includes(word)) ? 0.2 : 0;
    const shortWarmPing = words.length > 0 && words.length <= 8 ? 0.12 : 0;
    const punctuationLift = Math.min(exclamations * 0.08, 0.2);
    return score + 0.28 + friendliness + excitement + shortWarmPing + punctuationLift;
  }, 0);

  return Math.min(1, total / recent.length);
};

export default function AppLayout() {
  const [userId] = useState(() => getUserId());
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('nanban-session-id') || crypto.randomUUID());

  const [preferredLanguage, setPreferredLanguage] = useState(() => localStorage.getItem('nanban-language') || 'en');
  const theme = 'dark';
  
  const [vadSensitivity, setVadSensitivity] = useState(() => localStorage.getItem('nanban-vad-sensitivity') || 'medium');
  const [isContinuousListening, setIsContinuousListening] = useState(false);

  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('Idle');
  const [emotion, setEmotion] = useState('neutral');
  const [gestureOverride, setGestureOverride] = useState(null);
  const [audioPlayEvent, setAudioPlayEvent] = useState(null);
  const [micError, setMicError] = useState('');
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);
  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const [isMemoryOpen, setIsMemoryOpen] = useState(false);
  const [isSandboxOpen, setIsSandboxOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [sandboxConfig, setSandboxConfig] = useState({
    code: '',
    language: 'python',
    filename: 'main.py',
    autoRun: false
  });

  const handleOpenSandbox = ({ code = '', language = 'python', filename = 'solution.py', autoRun = false } = {}) => {
    setSandboxConfig({ code, language, filename, autoRun });
    setIsSandboxOpen(true);
  };

  // Hook logic
  const {
    isRecording,
    startRecording,
    stopRecording,
    sendTextInput,
    triggerIntro,
    updateVadSensitivity
  } = useAudioStreaming({
    sessionId,
    userId,
    preferredLanguage,
    onMessageReceived: (msg) => {
      setMessages(prev => {
        if (msg.role === 'assistant' && prev.length > 0 && prev[prev.length - 1].role === 'assistant') {
          const updated = [...prev];
          updated[updated.length - 1] = msg;
          return updated;
        }
        return [...prev, msg];
      });
    },
    onStatusChange: setStatus,
    onEmotionChange: setEmotion,
    onGestureChange: setGestureOverride,
    onAudioPlayEvent: setAudioPlayEvent,
    onMicError: setMicError
  });

  // Auto-restart recording when status goes back to Idle in continuous listening mode
  useEffect(() => {
    if (isContinuousListening && status === 'Idle' && !isRecording) {
      const timer = setTimeout(() => {
        startRecording();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isContinuousListening, status, isRecording, startRecording]);

  const handleVadSensitivityChange = (newSens) => {
    setVadSensitivity(newSens);
    localStorage.setItem('nanban-vad-sensitivity', newSens);
    updateVadSensitivity(newSens);
  };

  const handleToggleContinuousListening = () => {
    const nextVal = !isContinuousListening;
    setIsContinuousListening(nextVal);
    if (nextVal && !isRecording) {
      startRecording();
    } else if (!nextVal && isRecording) {
      stopRecording();
    }
  };

  // Persist State
  useEffect(() => { localStorage.setItem('nanban-session-id', sessionId); }, [sessionId]);
  useEffect(() => { localStorage.setItem('nanban-language', preferredLanguage); }, [preferredLanguage]);

  // Load History (Initial)
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/history/${userId}`)
      .then(res => res.json())
      .then(data => setMessages(data || []))
      .catch(() => {});
  }, [userId]);

  const toggleMic = () => isRecording ? stopRecording() : startRecording();

  const activeAvatarObj = { name: 'Kairos', accent: '#3b82f6' };
  const userRapportEnergy = useMemo(() => deriveUserRapportEnergy(messages), [messages]);

  return (
    <div
      className="app-container flex flex-col md:flex-row w-screen overflow-hidden dark"
      style={{ height: '100vh', paddingTop: TITLEBAR_HEIGHT }}
    >
      {/* Custom sci-fi title bar — only renders in Electron */}
      <ElectronTitleBar />

      {/* History Panel Overlay */}
      <AnimatePresence>
        {isHistoryOpen && (
          <motion.div 
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="absolute z-50 p-6 overflow-y-auto glass-panel border-r border-[var(--border-glass)]
              md:left-0 md:top-0 md:bottom-0 md:w-[340px] md:inset-auto
              inset-0 w-full h-full shadow-2xl"
          >
            <div className="flex justify-between items-center mb-6 pb-3 border-b border-[var(--border-glass)]">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-cyan-400" />
                <h3 className="text-xs font-mono font-bold tracking-wider uppercase text-[var(--text-main)]">
                  Session Logs
                </h3>
              </div>
              <button 
                onClick={() => setIsHistoryOpen(false)} 
                className="w-8 h-8 rounded-xl bg-[var(--surface-hover)] hover:bg-rose-500/20 hover:text-rose-400 flex items-center justify-center text-[var(--text-muted)] transition-colors cursor-pointer border border-[var(--border-glass)]"
              >
                <X size={15} />
              </button>
            </div>
            
            <HistoryList
              userId={userId}
              currentSessionId={sessionId}
              onSelectSession={(id) => {
                fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/history/${encodeURIComponent(id)}`)
                  .then(res => res.json())
                  .then(data => {
                    setMessages(data || []);
                    setIsHistoryOpen(false);
                  })
                  .catch(() => setIsHistoryOpen(false));
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Long-Term Memory Management Modal */}
      <AnimatePresence>
        {isMemoryOpen && (
          <MemoryPanel 
            onClose={() => setIsMemoryOpen(false)}
            userId={userId}
            theme={theme}
          />
        )}
      </AnimatePresence>

      {/* Character Codex / About Kairos Modal */}
      <AnimatePresence>
        {isAboutOpen && (
          <AboutKavya 
            onClose={() => setIsAboutOpen(false)}
            theme={theme}
            userRapportEnergy={userRapportEnergy}
            messageCount={messages.length}
          />
        )}
      </AnimatePresence>

      {/* Code Sandbox Modal */}
      <AnimatePresence>
        {isSandboxOpen && (
          <CodeSandbox 
            onClose={() => setIsSandboxOpen(false)}
            initialCode={sandboxConfig.code}
            initialLanguage={sandboxConfig.language}
            initialFilename={sandboxConfig.filename}
            autoRun={sandboxConfig.autoRun}
            theme={theme}
          />
        )}
      </AnimatePresence>

      {/* System Settings Modal */}
      <AnimatePresence>
        {isSettingsOpen && (
          <SettingsModal 
            onClose={() => setIsSettingsOpen(false)}
            theme={theme}
            onThemeToggle={toggleTheme}
            preferredLanguage={preferredLanguage}
            onLanguageChange={setPreferredLanguage}
            vadSensitivity={vadSensitivity}
            onVadSensitivityChange={handleVadSensitivityChange}
            isContinuousListening={isContinuousListening}
            onToggleContinuousListening={handleToggleContinuousListening}
            userId={userId}
            onOpenMemory={() => setIsMemoryOpen(true)}
          />
        )}
      </AnimatePresence>

      {/* System Dashboard Modal */}
      <AnimatePresence>
        {isDashboardOpen && (
          <AdminDashboard 
            onClose={() => setIsDashboardOpen(false)}
            theme={theme}
            userId={userId}
            sessionId={sessionId}
            status={status}
            onThemeToggle={toggleTheme}
            onOpenSandbox={() => {
              setSandboxConfig({ code: '', language: 'python', filename: 'main.py', autoRun: false });
              setIsSandboxOpen(true);
            }}
            onOpenMemory={() => setIsMemoryOpen(true)}
            onOpenSettings={() => setIsSettingsOpen(true)}
          />
        )}
      </AnimatePresence>

      {/* 2. Middle: Living AI Core 3D Neural View — z-0 so overlays are above, pointer-events-auto for canvas interaction */}
      <div className="relative flex-1 h-full z-0 pointer-events-auto">
        <HeroAICore 
          audioPlayEvent={audioPlayEvent}
          userId={userId}
          qualityTier="high"
        />
      </div>

      {/* 3. Right: Conversation Panel (Desktop standard, Mobile bottom sheet) */}
      <div className={`
        fixed md:relative inset-x-0 bottom-0 md:bottom-auto md:inset-auto z-40 md:z-auto
        transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]
        h-[80vh] md:h-full flex shrink-0
        ${isMobileChatOpen ? 'translate-y-0' : 'translate-y-[calc(100%-80px)] md:translate-y-0'}
      `}>
        {/* Mobile Drag Handle */}
        <div 
          className="md:hidden absolute top-0 inset-x-0 h-8 flex justify-center pt-3 cursor-pointer z-50 bg-transparent"
          onClick={() => setIsMobileChatOpen(!isMobileChatOpen)}
        >
          <div className="w-12 h-1.5 rounded-full bg-cyan-400/40" />
        </div>
        
        <ChatPanel 
          messages={messages}
          status={status}
          emotion={emotion}
          activeAvatar={activeAvatarObj}
          preferredLanguage={preferredLanguage}
          onLanguageChange={setPreferredLanguage}
          theme="dark"
          onHistoryClick={() => setIsHistoryOpen(!isHistoryOpen)}
          onDashboardClick={() => setIsDashboardOpen(true)}
          onAboutClick={() => setIsAboutOpen(true)}
          onMemoryClick={() => setIsMemoryOpen(true)}
          onSettingsClick={() => setIsSettingsOpen(true)}
          onSandboxClick={() => {
            setSandboxConfig({ code: '', language: 'python', filename: 'main.py', autoRun: false });
            setIsSandboxOpen(true);
          }}
          onOpenSandbox={handleOpenSandbox}
          vadSensitivity={vadSensitivity}
          onVadSensitivityChange={handleVadSensitivityChange}
        />
      </div>

      {/* 4. Bottom: Voice Dock */}
      <div className={`
        absolute left-1/2 -translate-x-1/2 transition-all duration-500 z-30 flex justify-center w-full
        ${isMobileChatOpen ? 'bottom-[80vh] md:bottom-6' : 'bottom-20 md:bottom-6'}
      `}>
        <VoiceDock 
          isRecording={isRecording}
          onToggleMic={toggleMic}
          onSendText={sendTextInput}
          status={status}
          activeAvatar={activeAvatarObj}
          isContinuousListening={isContinuousListening}
          onToggleContinuousListening={handleToggleContinuousListening}
        />
      </div>
      
      {/* Mic Error Toast */}
      <AnimatePresence>
        {micError && (
          <motion.div 
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="absolute top-12 left-1/2 -translate-x-1/2 z-50 bg-rose-950/80 border border-rose-500/60 text-rose-300 px-6 py-3 rounded-2xl backdrop-blur-xl shadow-2xl font-mono text-xs font-semibold flex items-center gap-2"
          >
            <div className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
            <span>MIC ERROR: {micError}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Telemetry Footer watermark */}
      <div className="absolute bottom-1 left-1/2 -translate-x-1/2 z-10 text-[9px] font-mono text-[var(--text-subtle)] opacity-40 pointer-events-none select-none tracking-widest uppercase">
        KAIROS NEURAL WORKSPACE // SECURE LOCAL MEMORY
      </div>

    </div>
  );
}
