import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import CharacterDock from './CharacterDock';
import ChatPanel from '../chat/ChatPanel';
import HeroAvatar from '../avatar/HeroAvatar';
import VoiceDock from './VoiceDock';
import { useAudioStreaming } from '../../hooks/useAudioStreaming';

function HistoryList({ onSelectSession, currentSessionId }) {
  const [sessions, setSessions] = useState([]);
  
  useEffect(() => {
    fetch('http://localhost:8000/api/sessions')
      .then(res => res.json())
      .then(data => setSessions(data || []))
      .catch(() => {});
  }, []);

  return (
    <>
      {sessions.map(s => (
        <button 
          key={s.session_id} 
          onClick={() => onSelectSession(s.session_id)}
          className={`text-left p-3 rounded-xl hover:bg-white/10 transition-colors text-sm ${s.session_id === currentSessionId ? 'bg-primary/20 border border-primary/50' : 'bg-white/5 border border-transparent'}`}
        >
          <div className="text-gray-200 font-medium truncate">{s.preview || "New Chat"}</div>
          <div className="text-xs text-gray-500 mt-1">{new Date(s.created_at * 1000).toLocaleString()}</div>
        </button>
      ))}
      {sessions.length === 0 && <div className="text-gray-500 text-sm text-center mt-4">No history found.</div>}
    </>
  );
}

const AVATARS = [
  { id: 'av0', file: 'avatar.vrm', name: 'Kavya', accent: '#f59e0b', emoji: '✨' },
  { id: 'av1', file: 'avatar1.vrm', name: 'Shriya', accent: '#9333ea', emoji: '😏' },
  { id: 'av2', file: 'avatar2.vrm', name: 'Kumar', accent: '#10b981', emoji: '💡' },
  { id: 'av3', file: 'avatar3.vrm', name: 'Lucy', accent: '#f43f5e', emoji: '💖' },
  { id: 'av4', file: 'avatar4.vrm', name: 'Sara', accent: '#3b82f6', emoji: '🌸' },
  { id: 'av5', file: 'avatar5.vrm', name: 'Aanya', accent: '#eab308', emoji: '🎈' },
  { id: 'av6', file: 'avatar6.vrm', name: 'Ankur', accent: '#14b8a6', emoji: '😎' },
];

// Character backgrounds: light + dark per avatar
const AVATAR_BACKGROUNDS = {
  'avatar.vrm':  { light: '/bg_kavya_light.png',  dark: '/bg_kavya_dark.png'  },
  'avatar1.vrm': { light: '/bg_shriya_light.png', dark: '/bg_shriya_dark.png' },
  'avatar2.vrm': { light: '/bg_kumar_light.png',  dark: '/bg_kumar_dark.png'  },
  // The remaining backgrounds (Lucy, Sara, Aanya, Ankur) will use the default animated background
  // until their images can be generated.
};

export default function AppLayout() {
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
    selectedAvatar,
    preferredLanguage,
    onMessageReceived: (msg) => setMessages(prev => [...prev, msg]),
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

  // Load History (Initial)
  useEffect(() => {
    fetch(`http://localhost:8000/api/history/${sessionId}`)
      .then(res => res.json())
      .then(data => setMessages(data || []))
      .catch(() => {});
  }, [sessionId]);

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
  const currentBg = AVATAR_BACKGROUNDS[selectedAvatar]?.[theme] || null;

  return (
    <div className={`app-container flex flex-col md:flex-row w-screen h-screen overflow-hidden ${theme}`}>
      
      {/* Character Background Image — fades on change */}
      <AnimatePresence mode="wait">
        {currentBg ? (
          <motion.div
            key={currentBg}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8, ease: 'easeInOut' }}
            className="absolute inset-0 z-0"
            style={{
              backgroundImage: `url(${currentBg})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
            }}
          />
        ) : (
          <motion.div key="animated-bg" className="absolute inset-0 z-0">
            <div className="animated-bg" />
            {theme === 'dark' && <div className="particles-bg" />}
          </motion.div>
        )}
      </AnimatePresence>
      {/* Overlay to darken/blend background so UI stays readable */}
      <div className={`absolute inset-0 z-[1] pointer-events-none ${
        theme === 'dark'
          ? 'bg-black/55'
          : 'bg-white/25'
      }`} />
      
      {/* 1. Left Dock: Character Selector */}
      <CharacterDock 
        avatars={AVATARS} 
        selectedAvatar={selectedAvatar} 
        onSelectAvatar={handleAvatarSelect}
        onNewChat={handleNewChat}
        onToggleHistory={() => setIsHistoryOpen(!isHistoryOpen)}
      />

      {/* History Panel Overlay */}
      <AnimatePresence>
        {isHistoryOpen && (
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="absolute z-50 p-4 overflow-y-auto bg-[#0a0a0a]/95 backdrop-blur-xl border-r border-white/10
              md:left-[120px] lg:left-[140px] md:top-0 md:bottom-0 md:w-[300px] md:inset-auto
              inset-0 w-full h-full"
          >
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-white font-bold tracking-wide">Chat History</h3>
              <button onClick={() => setIsHistoryOpen(false)} className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">✕</button>
            </div>
            <div className="flex flex-col gap-2">
              <HistoryList onSelectSession={(id) => {
                 setSessionId(id);
                 setIsHistoryOpen(false);
              }} currentSessionId={sessionId} />
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
            fetch(`http://localhost:8000/api/history/${sessionId}`)
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

    </div>
  );
}
