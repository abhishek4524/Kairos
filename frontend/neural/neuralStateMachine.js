/**
 * neuralStateMachine.js — Central Real-Time State Machine for Living AI Core
 *
 * Manages the 11 computational states of the AI:
 * - IDLE
 * - LISTENING
 * - PROCESSING_INPUT
 * - THINKING
 * - GENERATING
 * - MEMORY_UPDATE
 * - RAG_INGESTION
 * - RAG_RETRIEVAL
 * - TOOL_EXECUTION
 * - SUCCESS
 * - ERROR
 *
 * Provides a clean event bus with transition validation and fallback auto-recovery.
 */

export const AI_STATES = {
  IDLE: 'IDLE',
  LISTENING: 'LISTENING',
  PROCESSING_INPUT: 'PROCESSING_INPUT',
  THINKING: 'THINKING',
  GENERATING: 'GENERATING',
  MEMORY_UPDATE: 'MEMORY_UPDATE',
  RAG_INGESTION: 'RAG_INGESTION',
  RAG_RETRIEVAL: 'RAG_RETRIEVAL',
  TOOL_EXECUTION: 'TOOL_EXECUTION',
  SUCCESS: 'SUCCESS',
  ERROR: 'ERROR',
};

// Visual theme configurations per state
// Palette philosophy: deep dark steel-blue / indigo tones — rich, refined, not blinding.
// Think "deep space observatory" not "neon sign".
export const STATE_VISUAL_PROFILES = {
  IDLE: {
    primaryColor: '#1e3a5f',   // Deep Navy Blue
    secondaryColor: '#1a2744', // Dark Midnight
    coreGlow: 0.18,
    pulseSpeed: 0.6,
    rotationSpeed: 0.12,
    particleSpeed: 0.18,
    flowDirection: 'inward_slow',
    activityLevel: 0.12,
  },
  LISTENING: {
    primaryColor: '#1d4ed8',   // Royal Blue (not neon, deep)
    secondaryColor: '#1e3a5f', // Steel Navy
    coreGlow: 0.38,
    pulseSpeed: 1.8,
    rotationSpeed: 0.28,
    particleSpeed: 0.6,
    flowDirection: 'inward_fast',
    activityLevel: 0.45,
  },
  PROCESSING_INPUT: {
    primaryColor: '#2d5aa0',   // Deep Cobalt
    secondaryColor: '#3730a3', // Dark Indigo
    coreGlow: 0.52,
    pulseSpeed: 2.4,
    rotationSpeed: 0.42,
    particleSpeed: 1.0,
    flowDirection: 'inward_rapid',
    activityLevel: 0.6,
  },
  THINKING: {
    primaryColor: '#3730a3',   // Deep Indigo
    secondaryColor: '#4c1d95', // Dark Violet
    coreGlow: 0.7,
    pulseSpeed: 3.2,
    rotationSpeed: 0.65,
    particleSpeed: 1.6,
    flowDirection: 'cross_network',
    activityLevel: 0.8,
  },
  GENERATING: {
    primaryColor: '#155e75',   // Deep Cyan-Teal (not blinding)
    secondaryColor: '#1e3a5f', // Steel Navy
    coreGlow: 0.8,
    pulseSpeed: 3.0,
    rotationSpeed: 0.5,
    particleSpeed: 1.8,
    flowDirection: 'outward_radiant',
    activityLevel: 0.75,
  },
  MEMORY_UPDATE: {
    primaryColor: '#064e3b',   // Deep Emerald (subtle)
    secondaryColor: '#155e75', // Deep Teal
    coreGlow: 0.55,
    pulseSpeed: 2.0,
    rotationSpeed: 0.32,
    particleSpeed: 0.9,
    flowDirection: 'cluster_grow',
    activityLevel: 0.55,
  },
  RAG_INGESTION: {
    primaryColor: '#064e3b',   // Dark Emerald
    secondaryColor: '#78350f', // Dark Amber-Brown (subtle)
    coreGlow: 0.65,
    pulseSpeed: 2.8,
    rotationSpeed: 0.48,
    particleSpeed: 1.5,
    flowDirection: 'ingest_vortex',
    activityLevel: 0.65,
  },
  RAG_RETRIEVAL: {
    primaryColor: '#78350f',   // Deep Amber
    secondaryColor: '#3730a3', // Indigo
    coreGlow: 0.72,
    pulseSpeed: 3.2,
    rotationSpeed: 0.58,
    particleSpeed: 1.8,
    flowDirection: 'vector_beam_to_core',
    activityLevel: 0.7,
  },
  TOOL_EXECUTION: {
    primaryColor: '#7c2d12',   // Deep Burnt Orange
    secondaryColor: '#881337', // Dark Crimson
    coreGlow: 0.68,
    pulseSpeed: 3.0,
    rotationSpeed: 0.55,
    particleSpeed: 1.7,
    flowDirection: 'tool_pathway_deformation',
    activityLevel: 0.68,
  },
  SUCCESS: {
    primaryColor: '#064e3b',   // Deep Forest Green
    secondaryColor: '#155e75', // Deep Teal
    coreGlow: 0.75,
    pulseSpeed: 3.5,
    rotationSpeed: 0.35,
    particleSpeed: 1.2,
    flowDirection: 'harmonic_outward',
    activityLevel: 0.65,
  },
  ERROR: {
    primaryColor: '#7f1d1d',   // Dark Red
    secondaryColor: '#450a0a', // Very Dark Crimson
    coreGlow: 0.42,
    pulseSpeed: 1.6,
    rotationSpeed: 0.18,
    particleSpeed: 0.35,
    flowDirection: 'erratic_flicker',
    activityLevel: 0.32,
  },
};

// ─── Emotion Visual Overlay Profiles ────────────────────────────────────────
// Each emotion subtly modulates the active STATE_VISUAL_PROFILE.
// Fields here are *deltas* applied ON TOP of the current functional state profile,
// allowing emotion to influence but never completely override the state color.
// Togglable via neuralStateMachine.emotionOverlayEnabled = false.
const EMOTION_VISUAL_OVERLAYS = {
  // Deltas: glowBoost (+/-), pulseBoost (+/-), colorTint (string|null), activityBoost (+/-)
  neutral:      { glowBoost: 0.0,   pulseBoost: 0.0,  colorTint: null,        activityBoost: 0.0  },
  excited:      { glowBoost: 0.22,  pulseBoost: 1.2,  colorTint: '#fbbf24',   activityBoost: 0.18 }, // warm gold burst
  happy:        { glowBoost: 0.15,  pulseBoost: 0.6,  colorTint: '#34d399',   activityBoost: 0.10 }, // soft emerald
  enthusiastic: { glowBoost: 0.18,  pulseBoost: 0.9,  colorTint: '#f59e0b',   activityBoost: 0.14 },
  cheerful:     { glowBoost: 0.12,  pulseBoost: 0.5,  colorTint: '#6ee7b7',   activityBoost: 0.08 },
  calm:         { glowBoost: -0.08, pulseBoost: -0.5, colorTint: '#93c5fd',   activityBoost: -0.1 }, // cool blue haze
  relaxed:      { glowBoost: -0.06, pulseBoost: -0.3, colorTint: '#a5f3fc',   activityBoost: -0.08 },
  reassuring:   { glowBoost: -0.05, pulseBoost: -0.4, colorTint: '#bfdbfe',   activityBoost: -0.07 },
  urgent:       { glowBoost: 0.30,  pulseBoost: 1.8,  colorTint: '#ef4444',   activityBoost: 0.22 }, // red pulse surge
  serious:      { glowBoost: 0.05,  pulseBoost: -0.2, colorTint: '#9ca3af',   activityBoost: 0.04 },
  focused:      { glowBoost: 0.08,  pulseBoost: 0.1,  colorTint: '#60a5fa',   activityBoost: 0.06 },
  alert:        { glowBoost: 0.25,  pulseBoost: 1.4,  colorTint: '#f97316',   activityBoost: 0.18 },
  apologetic:   { glowBoost: -0.15, pulseBoost: -0.8, colorTint: '#c4b5fd',   activityBoost: -0.12 }, // soft violet dim
  empathetic:   { glowBoost: -0.10, pulseBoost: -0.5, colorTint: '#ddd6fe',   activityBoost: -0.08 },
  comforting:   { glowBoost: -0.12, pulseBoost: -0.6, colorTint: '#e9d5ff',   activityBoost: -0.10 },
  thoughtful:   { glowBoost: -0.04, pulseBoost: -0.2, colorTint: '#a78bfa',   activityBoost: -0.04 },
  curious:      { glowBoost: 0.10,  pulseBoost: 0.4,  colorTint: '#7dd3fc',   activityBoost: 0.08 },
  surprised:    { glowBoost: 0.28,  pulseBoost: 1.5,  colorTint: '#fde68a',   activityBoost: 0.15 }, // bright amber flash
  impressed:    { glowBoost: 0.14,  pulseBoost: 0.7,  colorTint: '#fcd34d',   activityBoost: 0.10 },
  sad:          { glowBoost: -0.20, pulseBoost: -1.0, colorTint: '#6b7280',   activityBoost: -0.18 }, // grey dimming
  disappointed: { glowBoost: -0.14, pulseBoost: -0.7, colorTint: '#9ca3af',   activityBoost: -0.12 },
  confident:    { glowBoost: 0.12,  pulseBoost: 0.4,  colorTint: '#38bdf8',   activityBoost: 0.08 },
  assertive:    { glowBoost: 0.10,  pulseBoost: 0.3,  colorTint: '#0ea5e9',   activityBoost: 0.06 },
};

class NeuralStateMachine {
  constructor() {
    this.currentState = AI_STATES.IDLE;
    this.previousState = AI_STATES.IDLE;
    this.stateData = {};
    this.listeners = new Set();
    this.autoResetTimer = null;
    this.history = [];

    // ── Emotion overlay ───────────────────────────────────────────────────
    // Set emotionOverlayEnabled = false to revert to flat functional-state-only visuals.
    this.currentEmotion = 'neutral';
    this.emotionOverlayEnabled = true;   // togglable via settings
    this.emotionResetTimer = null;       // auto-clear emotion after response finishes

    this.metrics = {
      tokensGenerated: 0,
      ragRetrievalsCount: 0,
      memoriesCount: 0,
      toolsExecutedCount: 0,
      lastLatencyMs: 0,
      tokenRate: 0,
    };
  }

  getState() {
    return this.currentState;
  }

  /**
   * Returns the visual profile for the current state, optionally blended with
   * the emotion overlay if emotionOverlayEnabled is true.
   * Overlay deltas are clamped to keep values in safe ranges.
   */
  getProfile() {
    const base = { ...(STATE_VISUAL_PROFILES[this.currentState] || STATE_VISUAL_PROFILES.IDLE) };
    if (!this.emotionOverlayEnabled || this.currentEmotion === 'neutral') {
      return base;
    }
    const overlay = EMOTION_VISUAL_OVERLAYS[this.currentEmotion] || EMOTION_VISUAL_OVERLAYS.neutral;

    // Apply deltas — clamp to reasonable bounds
    const blended = {
      ...base,
      coreGlow:      Math.max(0.1, Math.min(1.0, base.coreGlow      + overlay.glowBoost)),
      pulseSpeed:    Math.max(0.5, Math.min(6.0, base.pulseSpeed    + overlay.pulseBoost)),
      activityLevel: Math.max(0.1, Math.min(1.0, base.activityLevel + overlay.activityBoost)),
      // Inject emotion tint as emotionColor so renderers can optionally use it
      emotionColor:  overlay.colorTint || base.primaryColor,
      emotionLabel:  this.currentEmotion,
    };
    return blended;
  }

  getStateData() {
    return this.stateData;
  }

  getMetrics() {
    return this.metrics;
  }

  subscribe(listener) {
    this.listeners.add(listener);
    // Immediately notify initial state
    listener(this.currentState, this.stateData, this.getProfile());
    return () => this.listeners.delete(listener);
  }

  _notify() {
    const profile = this.getProfile();
    for (const listener of this.listeners) {
      try {
        listener(this.currentState, this.stateData, profile);
      } catch (err) {
        console.error('[NeuralStateMachine] Listener error:', err);
      }
    }
  }

  /**
   * Called when the backend emits an emotion_update WebSocket event.
   * Updates currentEmotion and re-notifies all subscribers.
   * Auto-resets to 'neutral' after 8 seconds (the typical response duration).
   *
   * @param {string} emotion - Emotion label from tts_emotion_profiles.EMOTION_PROFILES
   */
  onEmotionUpdate(emotion = 'neutral') {
    const validEmotions = new Set(Object.keys(EMOTION_VISUAL_OVERLAYS));
    const resolved = validEmotions.has(emotion) ? emotion : 'neutral';

    if (this.emotionResetTimer) {
      clearTimeout(this.emotionResetTimer);
      this.emotionResetTimer = null;
    }

    this.currentEmotion = resolved;
    this._notify();

    // Auto-reset after 8 seconds so a stale emotion doesn't persist into next IDLE state
    this.emotionResetTimer = setTimeout(() => {
      this.currentEmotion = 'neutral';
      this._notify();
    }, 8000);
  }

  transition(newState, payload = {}) {
    if (!AI_STATES[newState]) {
      console.warn(`[NeuralStateMachine] Unknown state: ${newState}`);
      return;
    }

    if (this.autoResetTimer) {
      clearTimeout(this.autoResetTimer);
      this.autoResetTimer = null;
    }

    this.previousState = this.currentState;
    this.currentState = newState;
    this.stateData = {
      ...payload,
      timestamp: Date.now(),
      fromState: this.previousState,
    };

    this.history.push({
      state: newState,
      timestamp: Date.now(),
      payload,
    });
    if (this.history.length > 50) this.history.shift();

    // Auto-recovery timers for transient states
    if (newState === AI_STATES.SUCCESS) {
      this.autoResetTimer = setTimeout(() => this.transition(AI_STATES.IDLE), 1600);
    } else if (newState === AI_STATES.ERROR) {
      this.autoResetTimer = setTimeout(() => this.transition(AI_STATES.IDLE), 3000);
    } else if (newState === AI_STATES.MEMORY_UPDATE) {
      this.autoResetTimer = setTimeout(() => this.transition(AI_STATES.IDLE), 2400);
    } else if (newState === AI_STATES.RAG_INGESTION) {
      this.autoResetTimer = setTimeout(() => this.transition(AI_STATES.IDLE), 3500);
    } else if (newState === AI_STATES.THINKING) {
      // Safety watchdog: recover to IDLE if stuck for > 45 seconds
      this.autoResetTimer = setTimeout(() => {
        if (this.currentState === AI_STATES.THINKING) {
          console.warn('[NeuralStateMachine] Watchdog timeout: resetting from THINKING to IDLE');
          this.transition(AI_STATES.IDLE);
        }
      }, 45000);
    } else if (newState === AI_STATES.TOOL_EXECUTION) {
      // Tool execution watchdog (15s max)
      this.autoResetTimer = setTimeout(() => {
        if (this.currentState === AI_STATES.TOOL_EXECUTION) {
          this.transition(AI_STATES.THINKING);
        }
      }, 15000);
    }

    this._notify();
  }

  // Helper event triggers directly mapped to application events
  onUserInputStarted(type = 'text') {
    this.transition(type === 'voice' ? AI_STATES.LISTENING : AI_STATES.PROCESSING_INPUT, { inputType: type });
  }

  onProcessingInput() {
    this.transition(AI_STATES.PROCESSING_INPUT);
  }

  onThinking(metadata = {}) {
    this.transition(AI_STATES.THINKING, metadata);
  }

  onGenerating(tokenCount = 0) {
    this.metrics.tokensGenerated += tokenCount;
    this.transition(AI_STATES.GENERATING, { tokenCount });
  }

  onRagSearchStarted(query) {
    this.transition(AI_STATES.RAG_RETRIEVAL, { query, phase: 'searching' });
  }

  onRagResultsFound(results = []) {
    this.metrics.ragRetrievalsCount += 1;
    this.transition(AI_STATES.RAG_RETRIEVAL, {
      results,
      retrievalCount: results.length,
      topScore: results[0]?.score || 0.85,
      phase: 'illuminating',
    });
  }

  onToolExecution(toolName, params = {}) {
    this.metrics.toolsExecutedCount += 1;
    this.transition(AI_STATES.TOOL_EXECUTION, { toolName, params });
  }

  onToolCompleted(toolName, success = true, message = '') {
    this.transition(success ? AI_STATES.SUCCESS : AI_STATES.ERROR, { toolName, success, message });
  }

  onMemoryUpdate(type = 'created', factText = '') {
    this.metrics.memoriesCount += (type === 'created' ? 1 : (type === 'deleted' ? -1 : 0));
    this.transition(AI_STATES.MEMORY_UPDATE, { updateType: type, text: factText });
  }

  onRagIngestion(docName, chunkCount = 0) {
    this.transition(AI_STATES.RAG_INGESTION, { docName, chunkCount });
  }

  onCompleted() {
    this.transition(AI_STATES.IDLE);
  }

  onError(errorMsg = '') {
    this.transition(AI_STATES.ERROR, { error: errorMsg });
  }
}

// Global Singleton Instance
export const neuralStateMachine = new NeuralStateMachine();
