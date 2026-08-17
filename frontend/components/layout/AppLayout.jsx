import React, { useMemo, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

import ChatPanel from '../chat/ChatPanel';
import HeroAvatar from '../avatar/HeroAvatar';
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
  const [theme, setTheme] = useState(() => localStorage.getItem('nanban-theme') || 'dark');
  const [zoomLevel, setZoomLevel] = useState(() => parseFloat(localStorage.getItem('nanban-zoom-level') || '50'));
  
  const [vadSensitivity, setVadSensitivity] = useState(() => localStorage.getItem('nanban-vad-sensitivity') || 'medium');
  const [isContinuousListening, setIsContinuousListening] = useState(false);
  const [lampOn, setLampOn] = useState(() => localStorage.getItem('nanban-room-lamp') !== 'false');
  const [interactionPose, setInteractionPose] = useState('standing');
  const [transientGesture, setTransientGesture] = useState(null);

  // ── Contextual Gesture Detector ────────────────────────────────────────────
  // Scans assistant response text for semantic patterns and fires a transient
  // gesture overlay. Not forced on every message — only matching intents.
  const detectContextualGesture = (text) => {
    if (!text || typeof text !== 'string') return;
    const t = text.toLowerCase();
    const fire = (name, opts = {}) => {
      setTransientGesture({ name, id: Date.now(), ...opts });
    };
    // Greetings — wave
    if (/\b(hello|hi there|hey|namaste|good morning|good evening|good afternoon|welcome)\b/.test(t))
      return fire('wave', { fadeIn: 0.2, hold: 1.8, fadeOut: 0.5 });
    // Farewell — goodbye wave
    if (/\b(bye|goodbye|see you|take care|farewell|talk soon|until next time)\b/.test(t))
      return fire('goodbye', { fadeIn: 0.2, hold: 1.8, fadeOut: 0.5 });
    // Positive confirmation — thumbs up
    if (/\b(absolutely|of course|definitely|exactly right|great|perfect|well done|congratulations|that's correct)\b/.test(t))
      return fire('thumbs_up', { fadeIn: 0.2, hold: 1.2, fadeOut: 0.4 });
    // Pointing / referencing something on screen
    if (/\b(look at (this|that|here)|check (this|that|here)|see here|here is|there it is|as you can see|over here)\b/.test(t))
      return fire('point_up', { fadeIn: 0.2, hold: 1.5, fadeOut: 0.4 });
    // Thinking / pondering
    if (/\b(hmm|let me think|interesting|that's a good question|i'm thinking|one moment|good question)\b/.test(t))
      return fire('chin_rub', { fadeIn: 0.3, hold: 2.0, fadeOut: 0.6 });
    // Explaining / open palm
    if (/\b(to explain|the reason is|basically|essentially|in other words|what (i mean|this means)|let me clarify)\b/.test(t))
      return fire('explaining', { fadeIn: 0.3, hold: 1.5, fadeOut: 0.5 });
    // Uncertainty / shrug
    if (/\b(i'm not sure|i don't know|hard to say|it depends|not certain|unclear)\b/.test(t))
      return fire('shrug', { fadeIn: 0.2, hold: 1.2, fadeOut: 0.4 });
    // Agreement / nodding reinforcement
    if (/\b(yes|yeah|agreed|right|correct|indeed|absolutely|totally)\b/.test(t))
      return fire('nodding', { fadeIn: 0.15, hold: 0.8, fadeOut: 0.3 });
  };

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
    selectedAvatar: 'avatar.vrm',
    preferredLanguage,
    onMessageReceived: (msg) => {
      // Intercept Voice & Text Theme & Room Light & Chair Sit/Stand Commands
      if (msg.role === 'user' && msg.text) {
        const lower = msg.text.toLowerCase().trim();
        if (/\b(switch to dark mode|dark mode on|set dark mode|enable dark mode|dark theme)\b/i.test(lower)) {
          setTheme('dark');
        } else if (/\b(switch to light mode|light mode on|set light mode|enable light mode|light theme)\b/i.test(lower)) {
          setTheme('light');
        } else if (/\b(switch theme|toggle theme|change theme)\b/i.test(lower)) {
          setTheme(prev => prev === 'dark' ? 'light' : 'dark');
        }

        // Room Lamp / Bulb Voice & Text Commands
        if (/\b(turn on the light|turn on the bulb|turn on the lamp|switch on the light|switch on the bulb|switch on the lamp|light on|bulb on|lamp on|roshni on|batti on|roshni chalu|batti chalu)\b/i.test(lower)) {
          setLampOn(true);
        } else if (/\b(turn off the light|turn off the bulb|turn off the lamp|switch off the light|switch off the bulb|switch off the lamp|light off|bulb off|lamp off|roshni band|batti band)\b/i.test(lower)) {
          setLampOn(false);
        } else if (/\b(toggle the light|toggle the lamp|toggle the bulb|toggle light|toggle lamp|toggle bulb)\b/i.test(lower)) {
          setLampOn(prev => !prev);
        }

        // Chair Sit & Stand Voice & Text Commands
        if (/\b(sit on the chair|sit down on the chair|sit on chair|sit down|please sit|baith jao|kursi par baith jao|take a seat)\b/i.test(lower)) {
          setInteractionPose('seated');
        } else if (/\b(stand up from the chair|stand up|get up|please stand|khade ho jao)\b/i.test(lower)) {
          setInteractionPose('standing');
        }

        // Read Books & Put Book Down Voice & Text Commands
        if (/\b(read a book|read the book|read books|go read|kitaab padho|kitab padho|pick up a book|pick up the book|go to the bookshelf)\b/i.test(lower)) {
          setInteractionPose('reading');
        } else if (/\b(put the book down|put book down|stop reading|done reading|kitaab rakh do|kitab rakh do)\b/i.test(lower)) {
          setInteractionPose('standing');
        }

        // Jump Voice & Text Commands (transient — resets after animation)
        if (/\b(jump|koodna|kudo|please jump|do a jump|jump please)\b/i.test(lower)) {
          setInteractionPose('jump');
          // Reset after animation completes (~750ms)
          setTimeout(() => setInteractionPose(prev => prev === 'jump' ? 'standing' : prev), 850);
        }
      }

      // ── Contextual gesture detection on assistant responses ──
      if (msg.role === 'assistant' && msg.text) {
        detectContextualGesture(msg.text);
      }

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
  useEffect(() => { localStorage.setItem('nanban-theme', theme); }, [theme]);
  useEffect(() => { localStorage.setItem('nanban-zoom-level', zoomLevel.toString()); }, [zoomLevel]);
  useEffect(() => { localStorage.setItem('nanban-room-lamp', lampOn.toString()); }, [lampOn]);

  // Load History (Initial)
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/history/${userId}`)
      .then(res => res.json())
      .then(data => setMessages(data || []))
      .catch(() => {});
  }, [userId]);

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  const toggleMic = () => isRecording ? stopRecording() : startRecording();

  const activeAvatarObj = { name: 'Kavya', accent: '#06b6d4' };
  const userRapportEnergy = useMemo(() => deriveUserRapportEnergy(messages), [messages]);

  return (
    <div
      className={`app-container flex flex-col md:flex-row w-screen overflow-hidden ${theme}`}
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

      {/* Character Codex / About Kavya Modal */}
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

      {/* 2. Middle: Hero Avatar View */}
      <HeroAvatar 
        audioPlayEvent={audioPlayEvent}
        emotion={emotion}
        gestureOverride={gestureOverride}
        zoomLevel={zoomLevel}
        onZoomChange={setZoomLevel}
        theme={theme}
        userRapportEnergy={userRapportEnergy}
        status={status}
        lampOn={lampOn}
        onToggleLamp={() => setLampOn(prev => !prev)}
        interactionPose={interactionPose}
        onToggleSit={() => setInteractionPose(prev => prev === 'seated' ? 'standing' : 'seated')}
        onToggleRead={() => setInteractionPose(prev => prev === 'reading' ? 'standing' : 'reading')}
        onJump={() => {
          setInteractionPose('jump');
          setTimeout(() => setInteractionPose(prev => prev === 'jump' ? 'standing' : prev), 850);
        }}
        transientGesture={transientGesture}
      />

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
          theme={theme}
          onThemeToggle={toggleTheme}
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
        KAVYA NEURAL WORKSPACE // SECURE LOCAL MEMORY
      </div>

    </div>
  );
}
