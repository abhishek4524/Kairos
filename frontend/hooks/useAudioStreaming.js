import { useState, useEffect, useRef, useCallback } from 'react';
import { neuralStateMachine } from '../neural/neuralStateMachine';

// Resample helper
function downsampleBuffer(input, fromRate, toRate = 16000) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const idx = i * ratio;
    const lo = Math.floor(idx), hi = Math.min(lo + 1, input.length - 1);
    out[i] = input[lo] * (1 - (idx - lo)) + input[hi] * (idx - lo);
  }
  return out;
}

export function useAudioStreaming({
  sessionId,
  userId,
  selectedAvatar,
  preferredLanguage,
  onMessageReceived, // (msg) => void
  onStatusChange,    // (status) => void (Idle, Listening, Thinking, Speaking)
  onEmotionChange,   // (emotion) => void
  onGestureChange,   // (gesture) => void
  onAudioPlayEvent,  // (event) => void
  onMicError,        // (error) => void
  onModeChange,      // (mode) => void — 'gf' | 'assistant'
}) {
  const [isRecording, setIsRecording] = useState(false);
  
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const processorRef = useRef(null);
  const sourceRef = useRef(null);
  const gainRef = useRef(null);
  const streamRef = useRef(null);
  const isRecordingRef = useRef(false);
  
  const currentAudioSourceRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingAudioRef = useRef(false);

  const selectedAvatarRef = useRef(selectedAvatar);
  const preferredLanguageRef = useRef(preferredLanguage);
  const userIdRef = useRef(userId);
  const callbacksRef = useRef({ onMessageReceived, onStatusChange, onEmotionChange, onGestureChange, onAudioPlayEvent, onMicError, onModeChange });
  
  useEffect(() => {
    callbacksRef.current = { onMessageReceived, onStatusChange, onEmotionChange, onGestureChange, onAudioPlayEvent, onMicError, onModeChange };
  });

  useEffect(() => { userIdRef.current = userId; }, [userId]);

  useEffect(() => {
    selectedAvatarRef.current = selectedAvatar;
  }, [selectedAvatar]);
  
  useEffect(() => {
    preferredLanguageRef.current = preferredLanguage;
  }, [preferredLanguage]);

  const stopAndClearAudio = useCallback(() => {
    audioQueueRef.current = [];
    if (currentAudioSourceRef.current) {
      try {
        currentAudioSourceRef.current.stop();
        currentAudioSourceRef.current.disconnect();
      } catch (e) {}
      currentAudioSourceRef.current = null;
    }
    isPlayingAudioRef.current = false;
    if (callbacksRef.current.onAudioPlayEvent) callbacksRef.current.onAudioPlayEvent(null);
  }, []);

  const processAudioQueue = useCallback(async () => {
    if (isPlayingAudioRef.current || audioQueueRef.current.length === 0) return;
    
    isPlayingAudioRef.current = true;
    const arrayBuffer = audioQueueRef.current.shift();

    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    const actx = audioCtxRef.current;
    if (actx.state === 'suspended') await actx.resume();

    try {
      const buf = await actx.decodeAudioData(arrayBuffer.slice(0));
      const source = actx.createBufferSource();
      const analyser = actx.createAnalyser();
      analyser.fftSize = 256;
      
      source.buffer = buf;
      source.connect(analyser);
      analyser.connect(actx.destination);
      const startTime = actx.currentTime;

      if (callbacksRef.current.onAudioPlayEvent) {
        callbacksRef.current.onAudioPlayEvent({ startTime, duration: buf.duration, actx, analyser });
      }
      currentAudioSourceRef.current = source;
      source.start(startTime);

      source.onended = () => {
        if (currentAudioSourceRef.current === source) {
          if (callbacksRef.current.onAudioPlayEvent) callbacksRef.current.onAudioPlayEvent(null);
          currentAudioSourceRef.current = null;
          isPlayingAudioRef.current = false;
          
          if (audioQueueRef.current.length > 0) {
            processAudioQueue();
          } else {
            if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Idle');
            neuralStateMachine.onCompleted();
          }
        }
      };
    } catch (err) {
      console.error('[Audio decode error]', err);
      isPlayingAudioRef.current = false;
      if (audioQueueRef.current.length > 0) processAudioQueue();
      else {
        if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Idle');
        neuralStateMachine.onCompleted();
      }
    }
  }, []);

  const pendingIntroRef = useRef(null);

  // Initialize WebSocket
  useEffect(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      wsRef.current.close();
    }

    let wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
    if (window.location.protocol === 'https:' && wsUrl.startsWith('ws://')) {
      wsUrl = wsUrl.replace('ws://', 'wss://');
    }
    const ws = new WebSocket(`${wsUrl}/ws/audio?session_id=${sessionId}`);
    ws.binaryType = 'arraybuffer';
    
    ws.onopen = () => {
      // Send config + user identity on connect
      // Backend will key all memory/history to this user_id
      ws.send(JSON.stringify({
        type: 'config_update',
        avatar: selectedAvatarRef.current,
        language: preferredLanguageRef.current,
        user_id: userIdRef.current,
      }));
      
      if (pendingIntroRef.current) {
        const { introPayload, gesture } = pendingIntroRef.current;
        pendingIntroRef.current = null;
        setTimeout(() => {
          ws.send(JSON.stringify(introPayload));
          if (callbacksRef.current.onEmotionChange) callbacksRef.current.onEmotionChange('thinking');
          if (callbacksRef.current.onGestureChange) callbacksRef.current.onGestureChange(gesture);
          setTimeout(() => { if (callbacksRef.current.onGestureChange) callbacksRef.current.onGestureChange(null); }, 4000);
        }, 200);
      }
    };

    ws.onmessage = async (ev) => {
      if (typeof ev.data === 'string') {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }

        if (msg.type === 'neural_event') {
          // Real-time Living AI Core Event Bus
          const ev = msg.event;
          if (ev === 'AI_PROCESSING_STARTED') neuralStateMachine.onProcessingInput();
          else if (ev === 'AI_THINKING_STARTED') neuralStateMachine.onThinking(msg);
          else if (ev === 'RAG_SEARCH_COMPLETED') neuralStateMachine.onRagResultsFound(msg.results || []);
          else if (ev === 'AI_GENERATION_STARTED') neuralStateMachine.onGenerating(0);
          else if (ev === 'AI_GENERATION_TOKEN') neuralStateMachine.onGenerating(msg.tokenCount || 1);
          else if (ev === 'TOOL_STARTED') neuralStateMachine.onToolExecution(msg.toolName, msg.params);
          else if (ev === 'TOOL_COMPLETED') neuralStateMachine.onToolCompleted(msg.toolName, msg.success, msg.message);
          else if (ev === 'AI_COMPLETED') {
            // Only transition to completed/idle if audio queue has finished playing
            if (!isPlayingAudioRef.current && audioQueueRef.current.length === 0) {
              neuralStateMachine.onCompleted();
            }
          }
          else if (ev === 'AI_ERROR') neuralStateMachine.onError(msg.error);
        } else if (msg.type === 'emotion_update') {
          // Emotion overlay: modulate neural core visuals to reflect LLM emotional tone
          neuralStateMachine.onEmotionUpdate(msg.emotion || 'neutral');
        } else if (msg.type === 'transcription') {
          if (callbacksRef.current.onMessageReceived) callbacksRef.current.onMessageReceived(msg);
          if (msg.role === 'user') {
            neuralStateMachine.onProcessingInput();
            if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Thinking');
          }
        } else if (msg.type === 'barge_in') {
          stopAndClearAudio();
          neuralStateMachine.onCompleted();
        } else if (msg.type === 'mode_changed') {
          if (callbacksRef.current.onModeChange) callbacksRef.current.onModeChange(msg.mode);
        }
      } else {
        if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Speaking');
        neuralStateMachine.onGenerating(1);
        audioQueueRef.current.push(ev.data);
        processAudioQueue();
      }
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [sessionId, processAudioQueue, stopAndClearAudio]);

  const startRecording = async () => {
    if (isRecordingRef.current) return;
    onMicError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      if (!audioCtxRef.current)
        audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
      const actx = audioCtxRef.current;
      if (actx.state === 'suspended') await actx.resume();

      const nativeRate = actx.sampleRate;
      const source = actx.createMediaStreamSource(stream);
      const processor = actx.createScriptProcessor(4096, 1, 1);
      const silentGain = actx.createGain();
      silentGain.gain.value = 0;

      sourceRef.current = source;
      processorRef.current = processor;
      gainRef.current = silentGain;

      processor.onaudioprocess = (e) => {
        if (!isRecordingRef.current) return;
        const raw = e.inputBuffer.getChannelData(0);
        const resampled = downsampleBuffer(raw, nativeRate, 16000);
        if (wsRef.current?.readyState === WebSocket.OPEN)
          wsRef.current.send(resampled.buffer.slice(0));
      };

      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(actx.destination);

      isRecordingRef.current = true;
      setIsRecording(true);
      neuralStateMachine.onUserInputStarted('voice');
      if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Listening');
    } catch (err) {
      const msg = err.name === 'NotAllowedError' ? 'Microphone permission denied.'
                : err.name === 'NotFoundError'   ? 'No microphone found.'
                : `Mic error: ${err.message}`;
      if (callbacksRef.current.onMicError) callbacksRef.current.onMicError(msg);
    }
  };

  const stopRecording = () => {
    isRecordingRef.current = false;
    setIsRecording(false);
    if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Idle'); // Or keep listening if we are waiting for response, handled by caller
    processorRef.current?.disconnect(); processorRef.current = null;
    sourceRef.current?.disconnect();    sourceRef.current = null;
    gainRef.current?.disconnect();
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  };
  
  const sendTextInput = (text) => {
    if (!text.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    
    // Immediately show the user's message in the chat (same behaviour as audio input)
    if (callbacksRef.current.onMessageReceived) {
      callbacksRef.current.onMessageReceived({
        type: 'transcription',
        role: 'user',
        text: text.trim(),
      });
    }

    stopAndClearAudio();
    neuralStateMachine.onUserInputStarted('text');
    if (callbacksRef.current.onStatusChange) callbacksRef.current.onStatusChange('Thinking');
    if (callbacksRef.current.onEmotionChange) callbacksRef.current.onEmotionChange('thinking');

    wsRef.current.send(JSON.stringify({
      type: 'text_input',
      text: text.trim(),
      language: preferredLanguage,
      user_id: userIdRef.current,
    }));
  };
  
  const triggerIntro = (avatarFile, gesture) => {
    const introPayload = {
      type: 'intro_trigger',
      text: "Do not give a long introduction. Briefly show your unique personality, state your name, and greet the user. If you already know the user's name from memory, say their name. If you don't know their name, ask for it. Keep it to 1-2 lines. Use a relevant gesture tag at the very beginning.",
      language: preferredLanguageRef.current,
      user_id: userIdRef.current,
    };

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'config_update', avatar: avatarFile }));
      setTimeout(() => {
        wsRef.current.send(JSON.stringify(introPayload));
        if (callbacksRef.current.onEmotionChange) callbacksRef.current.onEmotionChange('thinking');
        if (callbacksRef.current.onGestureChange) callbacksRef.current.onGestureChange(gesture);
        setTimeout(() => { if (callbacksRef.current.onGestureChange) callbacksRef.current.onGestureChange(null); }, 4000);
      }, 100);
    } else {
      pendingIntroRef.current = { introPayload, gesture };
    }
  };

  const updateVadSensitivity = (sensitivity) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'config_update',
        vad_sensitivity: sensitivity,
        user_id: userIdRef.current,
      }));
    }
  };

  const updateSelectedDocs = (docIds) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'update_selected_docs',
        selected_doc_ids: docIds,
        user_id: userIdRef.current,
      }));
    }
  };

  // Send any config_update payload to backend (mode switch, language change, etc.)
  const sendConfigUpdate = (payload) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'config_update',
        user_id: userIdRef.current,
        ...payload,
      }));
    }
  };

  return {
    isRecording,
    startRecording,
    stopRecording,
    sendTextInput,
    stopAndClearAudio,
    triggerIntro,
    updateVadSensitivity,
    updateSelectedDocs,
    sendConfigUpdate,
  };
}
