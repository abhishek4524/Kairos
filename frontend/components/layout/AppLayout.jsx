import React, { useMemo, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import CharacterDock from './CharacterDock';
import ChatPanel from '../chat/ChatPanel';
import HeroAvatar from '../avatar/HeroAvatar';
import VoiceDock from './VoiceDock';
import { useAudioStreaming } from '../../hooks/useAudioStreaming';

// ── Anonymous Browser-Based User Identity ───────────────────────────────────
// No login/signup required. A unique ID is generated once per browser and
// stored in localStorage. Same browser = same identity, fresh browser = new.
const getUserId = () => {
  try {
    let uid = localStorage.getItem('nanban_user_id');
    if (!uid) {
      uid = 'nanban_user_' + crypto.randomUUID().replace(/-/g, '').slice(0, 16);
      localStorage.setItem('nanban_user_id', uid);
    }
    return uid;
  } catch {
    // localStorage disabled (e.g. private browsing) — use in-memory fallback
    if (!getUserId._fallback) getUserId._fallback = 'nanban_user_' + Math.random().toString(36).slice(2, 18);
    return getUserId._fallback;
  }
};

function HistoryList({ userId, onSelectSession, currentUserId }) {
  const [sessions, setSessions] = useState([]);
  
  useEffect(() => {
    // fetch sessions from backend to find previous avatars
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/sessions?user_id=${encodeURIComponent(userId)}`)
      .then(res => res.json())
      .then(data => setSessions(data || []))
      .catch(() => {});
  }, [userId]);

  return (
    <>
      {sessions.map(s => (
        <button 
          key={s.session_id} 
          onClick={() => onSelectSession(s.session_id)}
          className={`text-left p-3 rounded-xl hover:bg-[var(--surface-hover)] transition-colors text-sm ${
            s.session_id === currentUserId 
              ? 'bg-primary/20 border border-primary/50' 
              : 'bg-[var(--surface)] border border-transparent'
          }`}
        >
          <div className="text-[var(--text-main)] font-medium truncate">{s.preview || 'New Chat'}</div>
          <div className="text-xs text-[var(--text-muted)] mt-1">{new Date(s.created_at * 1000).toLocaleString()}</div>
        </button>
      ))}
      {sessions.length === 0 && (
        <div className="text-[var(--text-muted)] text-sm text-center mt-8 opacity-60">
          No conversations yet.
        </div>
      )}
    </>
  );
}

const AVATARS = [
  { id: 'av0', file: 'avatar.vrm', name: 'Kavya', bgName: 'kavya', accent: '#f59e0b' },
  { id: 'av1', file: 'avatar1.vrm', name: 'Shriya', bgName: 'shriya', accent: '#9333ea' },
  { id: 'av2', file: 'avatar2.vrm', name: 'Kumar', bgName: 'kumar', accent: '#10b981' },
  { id: 'av3', file: 'avatar3.vrm', name: 'Lucy', bgName: 'lucy', accent: '#f43f5e' },
  { id: 'av4', file: 'avatar4.vrm', name: 'Sara', bgName: 'sara', accent: '#3b82f6' },
  { id: 'av5', file: 'avatar5.vrm', name: 'Aanya', bgName: 'aanya', accent: '#eab308' },
  { id: 'av6', file: 'avatar6.vrm', name: 'Ankur', bgName: 'ankur', accent: '#14b8a6' },
];

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

// Three.js handles the room backgrounds directly in AvatarCanvas.jsx.

export default function AppLayout() {
  // ── User Identity (anonymous, browser-local) ─────────────────────────────
  const [userId] = useState(() => getUserId());

  // State
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('nanban-session-id') || crypto.randomUUID());
  const [selectedAvatar, setSelectedAvatar] = useState(() => localStorage.getItem('nanban-selected-character') || 'avatar.vrm');
  const [preferredLanguage, setPreferredLanguage] = useState(() => localStorage.getItem('nanban-language') || 'en');
  const [theme, setTheme] = useState(() => localStorage.getItem('nanban-theme') || 'dark');
  const [zoomLevel, setZoomLevel] = useState(() => parseFloat(localStorage.getItem('nanban-zoom-level') || '50'));
  
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('Idle'); // Idle, Listening, Thinking, Speaking
  const [emotion, setEmotion] = useState('neutral');
  const [gestureOverride, setGestureOverride] = useState(null);
  const [audioPlayEvent, setAudioPlayEvent] = useState(null);
  const [micError, setMicError] = useState('');
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  // Hook logic
  const {
    isRecording,
    startRecording,
    stopRecording,
    sendTextInput,
    triggerIntro
  } = useAudioStreaming({
    sessionId,
    userId,
    selectedAvatar,
    preferredLanguage,
    onMessageReceived: (msg) => setMessages(prev => {
      // For assistant messages: update the last assistant entry in-place
      // instead of appending a new one (prevents duplicate display).
      if (msg.role === 'assistant' && prev.length > 0 && prev[prev.length - 1].role === 'assistant') {
        const updated = [...prev];
        updated[updated.length - 1] = msg;
        return updated;
      }
      return [...prev, msg];
    }),
    onStatusChange: setStatus,
    onEmotionChange: setEmotion,
    onGestureChange: setGestureOverride,
    onAudioPlayEvent: setAudioPlayEvent,
    onMicError: setMicError
  });

  // Persist State
  useEffect(() => { localStorage.setItem('nanban-session-id', sessionId); }, [sessionId]);
  useEffect(() => { localStorage.setItem('nanban-selected-character', selectedAvatar); }, [selectedAvatar]);
  useEffect(() => { localStorage.setItem('nanban-language', preferredLanguage); }, [preferredLanguage]);
  useEffect(() => { localStorage.setItem('nanban-theme', theme); }, [theme]);
  useEffect(() => { localStorage.setItem('nanban-zoom-level', zoomLevel.toString()); }, [zoomLevel]);

  // Load History (Initial) — keyed by userId so history persists across sessions
  useEffect(() => {
    // Fetch history using anonymous user ID
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/history/${userId}`)
      .then(res => res.json())
      .then(data => setMessages(data || []))
      .catch(() => {});
  }, [userId]);

  const handleAvatarSelect = (file) => {
    if (file === selectedAvatar) return;
    setSelectedAvatar(file);
    
    const introGestures = {
      'avatar.vrm': 'greeting', 'avatar1.vrm': 'casualChat', 'avatar2.vrm': 'explaining',
      'avatar3.vrm': 'jollyLaughter', 'avatar4.vrm': 'receptive', 'avatar5.vrm': 'happy', 'avatar6.vrm': 'relaxed',
    };
    triggerIntro(file, introGestures[file] || 'greeting');
  };

  const handleNewChat = () => {
    const newSession = crypto.randomUUID();
    setSessionId(newSession);
    setMessages([]);
    localStorage.setItem('nanban-session-id', newSession);
    
    const introGestures = {
      'avatar.vrm': 'greeting', 'avatar1.vrm': 'casualChat', 'avatar2.vrm': 'explaining',
      'avatar3.vrm': 'jollyLaughter', 'avatar4.vrm': 'receptive', 'avatar5.vrm': 'happy', 'avatar6.vrm': 'relaxed',
    };
    triggerIntro(selectedAvatar, introGestures[selectedAvatar] || 'greeting');
  };

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  const toggleMic = () => isRecording ? stopRecording() : startRecording();

  const activeAvatarObj = AVATARS.find(a => a.file === selectedAvatar);
  const userRapportEnergy = useMemo(() => deriveUserRapportEnergy(messages), [messages]);

  return (
    <div className={`app-container flex flex-col md:flex-row w-screen h-screen overflow-hidden ${theme}`}>
      
      {/* The background is fully handled by Three.js in AvatarCanvas.jsx */}
      {/* 1. Left Dock: Character Selector */}
      <CharacterDock 
        avatars={AVATARS} 
        selectedAvatar={selectedAvatar} 
        onSelectAvatar={handleAvatarSelect}
        onNewChat={handleNewChat}
        onToggleHistory={() => setIsHistoryOpen(!isHistoryOpen)}
        theme={theme}
      />

      {/* History Panel Overlay */}
      <AnimatePresence>
        {isHistoryOpen && (
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="absolute z-50 p-4 overflow-y-auto bg-[var(--background)] backdrop-blur-xl border-r border-[var(--border-glass)]
              md:left-[120px] lg:left-[140px] md:top-0 md:bottom-0 md:w-[300px] md:inset-auto
              inset-0 w-full h-full"
          >
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-[var(--text-main)] font-bold tracking-wide">Chat History</h3>
              <button onClick={() => setIsHistoryOpen(false)} className="w-8 h-8 rounded-full bg-[var(--surface)] hover:bg-[var(--surface-hover)] flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-main)] transition-colors">✕</button>
            </div>
            <div className="flex flex-col gap-2">
              <HistoryList
                userId={userId}
                currentUserId={userId}
                onSelectSession={(id) => {
                  // refetch history for this newly activated session
                  fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/history/${encodeURIComponent(id)}`)
                    .then(res => res.json())
                    .then(data => {
                      setMessages(data || []);
                      setIsHistoryOpen(false);
                    })
                    .catch(() => setIsHistoryOpen(false));
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 2. Middle: Hero Avatar View */}
      <HeroAvatar 
        audioPlayEvent={audioPlayEvent}
        emotion={emotion}
        gestureOverride={gestureOverride}
        selectedAvatar={selectedAvatar}
        zoomLevel={zoomLevel}
        onZoomChange={setZoomLevel}
        theme={theme}
        userRapportEnergy={userRapportEnergy}
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
          <div className="w-12 h-1.5 rounded-full bg-white/20" />
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
          onHistoryClick={() => {
            // Fetch history for new character using generic user ID
            fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/history/${userId}`)
              .then(res => res.json())
              .then(data => setMessages(data || []));
          }}
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
        />
      </div>
      
      {/* Mic Error Toast */}
      <AnimatePresence>
        {micError && (
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="absolute top-6 left-1/2 -translate-x-1/2 z-50 bg-danger/20 border border-danger/50 text-rose-300 px-6 py-3 rounded-xl backdrop-blur-md shadow-lg font-semibold text-sm"
          >
            {micError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Subtle data-locality notice */}
      <div className="absolute bottom-1 left-1/2 -translate-x-1/2 z-10 text-[9px] text-[var(--text-muted)] opacity-30 pointer-events-none select-none whitespace-nowrap">
        Data stored locally in this browser
      </div>

    </div>
  );
}
