import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VRMLoaderPlugin, VRMExpressionPresetName } from '@pixiv/three-vrm';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────
const lerp  = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const rand  = (lo, hi) => Math.random() * (hi - lo) + lo;

// ─────────────────────────────────────────────────────────────────────────────
// Viseme → VRM Expression
// ─────────────────────────────────────────────────────────────────────────────
const RHUBARB_TO_VRM = {
  A: null,                             B: VRMExpressionPresetName.Aa,
  C: VRMExpressionPresetName.Ih,       D: VRMExpressionPresetName.Aa,
  E: VRMExpressionPresetName.Oh,       F: VRMExpressionPresetName.Ou,
  G: VRMExpressionPresetName.Ee,       H: VRMExpressionPresetName.Oh,
  X: null,
};
const MOUTH_PRESETS = [
  VRMExpressionPresetName.Aa, VRMExpressionPresetName.Ih,
  VRMExpressionPresetName.Ou, VRMExpressionPresetName.Ee,
  VRMExpressionPresetName.Oh,
];

// ─────────────────────────────────────────────────────────────────────────────
// Gesture/Emotion → VRM face expression (max 0.65 so lip-sync can override)
// ─────────────────────────────────────────────────────────────────────────────
const EMOTION_PRESET = {
  // Classic emotions
  happy:           VRMExpressionPresetName.Happy,
  sad:             VRMExpressionPresetName.Sad,
  surprised:       VRMExpressionPresetName.Surprised,
  thinking:        VRMExpressionPresetName.Relaxed,
  neutral:         null,
  // 20 gesture-tags mapped to closest VRM face preset
  greeting:        VRMExpressionPresetName.Happy,
  activeListening: VRMExpressionPresetName.Relaxed,
  confidentSpeech: VRMExpressionPresetName.Happy,
  leadership:      VRMExpressionPresetName.Happy,
  disagreement:    VRMExpressionPresetName.Angry,
  opposition:      VRMExpressionPresetName.Angry,
  comforting:      VRMExpressionPresetName.Sad,
  surprise:        VRMExpressionPresetName.Surprised,
  casualChat:      VRMExpressionPresetName.Relaxed,
  relaxed:         VRMExpressionPresetName.Relaxed,
  annoyed:         VRMExpressionPresetName.Angry,
  negotiation:     null,
  presentation:    VRMExpressionPresetName.Happy,
  explaining:      null,
  thoughtfulness:  VRMExpressionPresetName.Relaxed,
  approval:        VRMExpressionPresetName.Happy,
  anger:           VRMExpressionPresetName.Angry,
  displeasure:     VRMExpressionPresetName.Angry,
  openness:        VRMExpressionPresetName.Happy,
  farewell:        VRMExpressionPresetName.Happy,
  // Charming / social gesture tags (Image 2)
  eyeContact:      VRMExpressionPresetName.Happy,
  interestedFlash: VRMExpressionPresetName.Surprised,
  receptive:       VRMExpressionPresetName.Happy,
  engaged:         VRMExpressionPresetName.Happy,
  attentive:       VRMExpressionPresetName.Relaxed,
  blushing:        VRMExpressionPresetName.Happy,
  coySmile:        VRMExpressionPresetName.Happy,
  preening:        VRMExpressionPresetName.Happy,
  fidgeting:       VRMExpressionPresetName.Relaxed,
  focused:         null,
  synchrony:       VRMExpressionPresetName.Happy,
  jollyLaughter:   VRMExpressionPresetName.Happy,
  friendlyContact: VRMExpressionPresetName.Happy,
  gazeShift:       null,
  sharedFocus:     VRMExpressionPresetName.Happy,
  openPosture:     VRMExpressionPresetName.Happy,
};
const EMOTION_WEIGHT_MAX = 0.65;

// ─────────────────────────────────────────────────────────────────────────────
// Hand Gesture Pose Library
// ─────────────────────────────────────────────────────────────────────────────
const GESTURES = {
  // ── Core / neutral ────────────────────────────────────────────────────────────
  // Natural relaxed standing — arms hang naturally at sides, slight bend at elbow
  neutral:         { leftUpperArm: { x:0.08, y:0.00, z:-1.20 }, rightUpperArm: { x:0.08, y:0.00, z: 1.20 }, leftLowerArm: { x:0.10, y:0.00, z:-0.08 }, rightLowerArm: { x:0.10, y:0.00, z: 0.08 }, leftHand: { x:0.00, y: 0.05, z:-0.02 }, rightHand: { x:0.00, y:-0.05, z: 0.02 } },
  
  // ── Greeting Gestures ────────────────────────────────────────────────────────
  namaste:         { leftUpperArm: { x:0.10, y: 0.20, z:-0.60 }, rightUpperArm: { x:0.10, y:-0.20, z: 0.60 }, leftLowerArm: { x:-1.00, y:-0.10, z: 0.10 }, rightLowerArm: { x:-1.00, y: 0.10, z:-0.10 }, leftHand: { x:0.10, y: 0.10, z: 0.10 }, rightHand: { x:0.10, y:-0.10, z:-0.10 } },
  wave:            { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.45, y:-0.10, z:-0.28 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.95, y:0.00, z: 0.00 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.20, z: 0.00 } },
  salute:          { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.20, y:-0.15, z:-0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.40, y: 0.20, z: 0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.10, z: 0.00 } },
  peace:           { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.10, y:-0.10, z:-0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.00, y: 0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z:-0.20 } },
  
  // ── Expressive / Emphasis ───────────────────────────────────────────────────
  explaining:      { leftUpperArm: { x:0.20, y: 0.25, z:-0.85 }, rightUpperArm: { x:0.20, y:-0.25, z: 0.85 }, leftLowerArm: { x:0.50, y:-0.10, z: 0.15 }, rightLowerArm: { x:0.50, y: 0.10, z:-0.15 }, leftHand: { x:-0.10, y: 0.25, z:-0.05 }, rightHand: { x:-0.10, y:-0.25, z: 0.05 } },
  point_up:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.10, y:-0.10, z: 0.30 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.80, y: 0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:-0.10, y:-0.20, z: 0.00 } },
  counting:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.20, y:-0.15, z: 0.40 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.90, y: 0.00, z: 0.00 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:-0.10, y: 0.10, z:-0.10 } },
  air_quotes:      { leftUpperArm: { x:0.30, y: 0.20, z:-0.60 }, rightUpperArm: { x:0.30, y:-0.20, z: 0.60 }, leftLowerArm: { x:-1.20, y: 0.10, z: 0.10 }, rightLowerArm: { x:-1.20, y:-0.10, z:-0.10 }, leftHand: { x:0.10, y: 0.00, z: 0.00 }, rightHand: { x:0.10, y: 0.00, z: 0.00 } },
  thinking:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.05, y:-0.12, z: 0.45 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.80, y: 0.12, z: 0.08 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.12, y: 0.00, z:-0.20 } },
  head_scratch:    { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.20, y:-0.15, z:-0.80 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.30, y: 0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.20, z: 0.10 } },
  shrug:           { leftUpperArm: { x:0.10, y: 0.10, z:-0.70 }, rightUpperArm: { x:0.10, y:-0.10, z: 0.70 }, leftLowerArm: { x:-0.30, y: 0.10, z: 0.10 }, rightLowerArm: { x:-0.30, y:-0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  facepalm:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.20, y:-0.15, z:-0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.40, y: 0.20, z: 0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.10, y: 0.00, z: 0.10 } },
  palm_up:         { leftUpperArm: { x:0.20, y: 0.15, z:-0.60 }, rightUpperArm: { x:0.20, y:-0.15, z: 0.60 }, leftLowerArm: { x:-0.30, y:-0.30, z: 0.10 }, rightLowerArm: { x:-0.30, y: 0.30, z:-0.10 }, leftHand: { x:-0.10, y: 0.10, z:-0.60 }, rightHand: { x:-0.10, y:-0.10, z: 0.60 } },
  palm_down:       { leftUpperArm: { x:0.20, y: 0.15, z:-0.60 }, rightUpperArm: { x:0.20, y:-0.15, z: 0.60 }, leftLowerArm: { x:-0.30, y:-0.30, z: 0.10 }, rightLowerArm: { x:-0.30, y: 0.30, z:-0.10 }, leftHand: { x:-0.10, y: 0.10, z: 0.60 }, rightHand: { x:-0.10, y:-0.10, z:-0.60 } },
  
  // ── Emotional ───────────────────────────────────────────────────────────────
  excited_jump:    { leftUpperArm: { x:-0.20, y: 0.20, z:-0.40 }, rightUpperArm: { x:-0.20, y:-0.20, z: 0.40 }, leftLowerArm: { x:-0.60, y: 0.10, z: 0.10 }, rightLowerArm: { x:-0.60, y:-0.10, z:-0.10 }, leftHand: { x:-0.10, y: 0.10, z: 0.00 }, rightHand: { x:-0.10, y:-0.10, z: 0.00 } },
  clasped_hands:   { leftUpperArm: { x:0.10, y: 0.15, z:-0.80 }, rightUpperArm: { x:0.10, y:-0.15, z: 0.80 }, leftLowerArm: { x:-0.40, y:-0.05, z: 0.10 }, rightLowerArm: { x:-0.40, y: 0.05, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y: 0.10, z: 0.00 } },
  chill_lean:      { leftUpperArm: { x:0.10, y: 0.00, z:-1.15 }, rightUpperArm: { x:0.10, y:-0.10, z: 0.90 }, leftLowerArm: { x:0.10, y:0.00, z:-0.10 }, rightLowerArm: { x:-0.10, y: 0.10, z: 0.00 }, leftHand: { x:0.00, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  arms_crossed:    { leftUpperArm: { x:0.10, y: 0.30, z:-0.50 }, rightUpperArm: { x:0.10, y:-0.30, z: 0.50 }, leftLowerArm: { x:-0.80, y:-0.20, z: 0.20 }, rightLowerArm: { x:-0.80, y: 0.20, z:-0.20 }, leftHand: { x:0.00, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  bouncy_hop:      { leftUpperArm: { x:0.10, y: 0.20, z:-0.90 }, rightUpperArm: { x:0.10, y:-0.20, z: 0.90 }, leftLowerArm: { x:0.10, y: 0.10, z:-0.10 }, rightLowerArm: { x:0.10, y:-0.10, z: 0.10 }, leftHand: { x:0.00, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  heart_hands:     { leftUpperArm: { x:0.30, y: 0.20, z:-0.60 }, rightUpperArm: { x:0.30, y:-0.20, z: 0.60 }, leftLowerArm: { x:-0.80, y: 0.10, z: 0.10 }, rightLowerArm: { x:-0.80, y:-0.10, z:-0.10 }, leftHand: { x:-0.10, y: 0.10, z: 0.10 }, rightHand: { x:-0.10, y:-0.10, z:-0.10 } },
  wink_gun:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.20, y:-0.15, z: 0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.40, y: 0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:-0.20, y: 0.10, z: 0.00 } },
  eye_roll:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.10, y:-0.10, z:-0.60 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.10, y: 0.10, z: 0.00 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.10, y:-0.10, z: 0.10 } },
  clapping:        { leftUpperArm: { x:0.30, y: 0.20, z:-0.50 }, rightUpperArm: { x:0.30, y:-0.20, z: 0.50 }, leftLowerArm: { x:-0.80, y:-0.10, z: 0.10 }, rightLowerArm: { x:-0.80, y: 0.10, z:-0.10 }, leftHand: { x:-0.10, y: 0.10, z: 0.10 }, rightHand: { x:-0.10, y:-0.10, z:-0.10 } },
  fist_pump:       { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.50, y:-0.10, z:-0.40 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.50, y: 0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.10, y:-0.10, z: 0.00 } },
  
  // ── Listening / Reactive ────────────────────────────────────────────────────
  nodding:         { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:0.10, y:0.00, z: 1.15 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:0.18, y:0.00, z: 0.12 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.10, z: 0.00 } },
  head_tilt:       { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:0.10, y:0.00, z: 1.15 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:0.18, y:0.00, z: 0.12 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.10, z: 0.00 } },
  hand_on_chest:   { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.20, y:-0.20, z:-0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.40, y: 0.10, z: 0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.10, y:-0.10, z:-0.10 } },
  chin_rub:        { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.15, y:-0.15, z:-0.55 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.30, y: 0.15, z: 0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.15, y: 0.00, z:-0.10 } },
  
  // ── Idle Micro-Gestures ──────────────────────────────────────────────────────
  hair_touch:      { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.10, y:-0.20, z:-0.80 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.30, y: 0.10, z: 0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.10, z: 0.10 } },
  stretch:         { leftUpperArm: { x:-0.30, y: 0.10, z:-0.50 }, rightUpperArm: { x:-0.30, y:-0.10, z: 0.50 }, leftLowerArm: { x:-0.20, y: 0.10, z: 0.00 }, rightLowerArm: { x:-0.20, y:-0.10, z: 0.00 }, leftHand: { x:-0.10, y: 0.00, z: 0.00 }, rightHand: { x:-0.10, y: 0.00, z: 0.00 } },
  look_nails:      { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.20, y:-0.15, z: 0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.00, y: 0.20, z:-0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.20, y:-0.10, z: 0.10 } },
  adjust_collar:   { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.20, y:-0.20, z:-0.40 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.20, y: 0.15, z: 0.10 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.10, y:-0.10, z: 0.00 } },
  
  // ── Special Personality ─────────────────────────────────────────────────────
  aanya_point:     { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.20, y:-0.15, z: 0.40 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.30, y: 0.10, z: 0.00 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:-0.10, y: 0.00, z: 0.00 } },
  kumar_glasses:   { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.25, y:-0.10, z:-0.60 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-1.40, y: 0.15, z: 0.00 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.10, y:-0.10, z:-0.15 } },
  sara_gentle:     { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x: 0.15, y:-0.15, z: 0.50 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.80, y: 0.10, z:-0.05 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:-0.05, y: 0.00, z: 0.00 } },
  lucy_spin:       { leftUpperArm: { x:0.20, y: 0.20, z:-0.70 }, rightUpperArm: { x:0.20, y:-0.20, z: 0.70 }, leftLowerArm: { x:-0.20, y:-0.10, z: 0.10 }, rightLowerArm: { x:-0.20, y: 0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  kavya_open:      { leftUpperArm: { x:0.14, y: 0.08, z:-0.98 }, rightUpperArm: { x:0.14, y:-0.08, z: 0.98 }, leftLowerArm: { x:0.08, y: 0.10, z: 0.02 }, rightLowerArm: { x:0.08, y:-0.10, z:-0.02 }, leftHand: { x:-0.06, y: 0.08, z:-0.12 }, rightHand: { x:-0.06, y:-0.08, z: 0.12 } },
  shriya_smirk:    { leftUpperArm: { x:0.15, y: 0.00, z:-0.80 }, rightUpperArm: { x:0.05, y: 0.00, z: 1.15 }, leftLowerArm: { x:-0.70, y:-0.10, z: 0.00 }, rightLowerArm: { x:0.18, y:0.00, z: 0.12 }, leftHand: { x:0.10, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  goodbye:         { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.40, y:-0.15, z:-0.30 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.90, y:0.00, z: 0.00 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x:0.00, y:-0.20, z: 0.00 } },
};

const DEFAULT_EMOTIONS = {
  '/avatar.vrm': 'comforting',
  '/avatar1.vrm': 'casualChat',
  '/avatar2.vrm': 'explaining',
  '/avatar3.vrm': 'jollyLaughter',
  '/avatar4.vrm': 'attentive',
  '/avatar5.vrm': 'happy',
  '/avatar6.vrm': 'relaxed',
};

const CHARACTER_SIGNATURES = {
  '/avatar.vrm':  { greeting: 'namaste', happy: 'kavya_open', comforting: 'kavya_open' },
  '/avatar1.vrm': { casualChat: 'shriya_sarcastic', annoyed: 'eye_roll', disapproval: 'shriya_smirk' },
  '/avatar2.vrm': { explaining: 'kumar_glasses', presentation: 'kumar_glasses' },
  '/avatar3.vrm': { jollyLaughter: 'lucy_spin', happy: 'lucy_spin', surprise: 'excited_jump', greeting: 'salute' },
  '/avatar4.vrm': { attentive: 'sara_gentle', relaxed: 'sara_gentle', comforting: 'sara_gentle' },
  '/avatar5.vrm': { happy: 'bouncy_hop', surprise: 'aanya_point', greeting: 'bouncy_hop' },
  '/avatar6.vrm': { relaxed: 'chill_lean', casualChat: 'chill_lean', greeting: 'peace', flirt: 'wink_gun' },
};

const CHARACTER_PROFILES = {
  '/avatar.vrm': { breathRate: 1.0, swayRate: 1.0, swayAmp: 1.0, blinkMin: 2.0, blinkMax: 5.0, gazeMin: 2.0, gazeMax: 5.0 }, // Kavya
  '/avatar1.vrm':{ breathRate: 0.9, swayRate: 0.9, swayAmp: 0.8, blinkMin: 1.5, blinkMax: 4.0, gazeMin: 1.5, gazeMax: 4.0 }, // Shriya
  '/avatar2.vrm':{ breathRate: 0.7, swayRate: 0.6, swayAmp: 0.5, blinkMin: 3.0, blinkMax: 6.0, gazeMin: 3.0, gazeMax: 6.0 }, // Kumar
  '/avatar3.vrm':{ breathRate: 1.8, swayRate: 2.2, swayAmp: 1.8, blinkMin: 1.0, blinkMax: 3.0, gazeMin: 1.0, gazeMax: 3.0 }, // Lucy
  '/avatar4.vrm':{ breathRate: 0.5, swayRate: 0.4, swayAmp: 0.4, blinkMin: 4.0, blinkMax: 8.0, gazeMin: 4.0, gazeMax: 8.0 }, // Sara
  '/avatar5.vrm':{ breathRate: 1.4, swayRate: 1.6, swayAmp: 1.5, blinkMin: 1.5, blinkMax: 3.5, gazeMin: 1.0, gazeMax: 3.0 }, // Aanya
  '/avatar6.vrm':{ breathRate: 0.7, swayRate: 0.6, swayAmp: 0.7, blinkMin: 3.0, blinkMax: 7.0, gazeMin: 3.0, gazeMax: 6.0 }, // Ankur
};

const AVATAR_NAMES = {
  '/avatar.vrm': 'kavya',
  '/avatar1.vrm': 'shriya',
  '/avatar2.vrm': 'kumar',
  '/avatar3.vrm': 'lucy',
  '/avatar4.vrm': 'sara',
  '/avatar5.vrm': 'aanya',
  '/avatar6.vrm': 'ankur',
};

const BACKGROUND_FALLBACKS = {
  kavya: ['jpg', 'png'],
  shriya: ['jpg', 'png'],
  kumar: ['jpg', 'png'],
  lucy: ['jpg', 'png'],
  sara: ['jpg', 'png'],
  aanya: ['jpg', 'png'],
  ankur: ['jpg', 'png'],
};

const BACKGROUND_LIGHTING = {
  kavya:  { keyDark: 0xffd0a0, keyLight: 0xffe8c0, fillDark: 0x8a7060, fillLight: 0xd8c5b2 },
  shriya: { keyDark: 0xd7c4ff, keyLight: 0xf0dcff, fillDark: 0x66527f, fillLight: 0xcab4e8 },
  kumar:  { keyDark: 0xc8e7d9, keyLight: 0xe1fff1, fillDark: 0x536f63, fillLight: 0xb9dacb },
  lucy:   { keyDark: 0xffb8c8, keyLight: 0xffdbe3, fillDark: 0x8a5363, fillLight: 0xe7adbb },
  sara:   { keyDark: 0xbfd9ff, keyLight: 0xe7f1ff, fillDark: 0x506987, fillLight: 0xb8d3ef },
  aanya:  { keyDark: 0xffdda2, keyLight: 0xffedc7, fillDark: 0x8a7450, fillLight: 0xe4cc9c },
  ankur:  { keyDark: 0xffc69a, keyLight: 0xffe4c2, fillDark: 0x8a6450, fillLight: 0xddb49b },
};

const getBackgroundCandidates = (avatarUrl, theme) => {
  const avatarName = AVATAR_NAMES[avatarUrl] || 'kavya';
  const mode = theme === 'dark' ? 'dark' : 'light';
  const exts = BACKGROUND_FALLBACKS[avatarName] || ['jpg', 'png'];
  return [
    ...exts.map(ext => `/backgrounds/${avatarName}_${mode}.${ext}`),
    `/bg_${avatarName}_${mode}.png`,
    `/bg_${avatarName}_${mode}.jpg`,
  ];
};

const GESTURE_BONES = [
  'leftUpperArm', 'rightUpperArm',
  'leftLowerArm', 'rightLowerArm',
  'leftHand',     'rightHand',
];

const selectGesture = (isSpeaking, emotionKey, override, avatarUrl, time, rapportEnergy = 0) => {
  if (override) return override;
  
  const baseEmotion = isSpeaking ? emotionKey : (DEFAULT_EMOTIONS[avatarUrl] || 'neutral');
  
  // Allan Pease Book Enhancements: Map core states to micro-gestures dynamically
  if (isSpeaking) {
    const isHonestOpen = ['openness', 'comforting', 'casualChat', 'friendlyContact'].includes(baseEmotion);
    const isAuthoritative = ['leadership', 'confidentSpeech', 'explaining'].includes(baseEmotion);
    const isEvaluating = ['thinking', 'thoughtfulness', 'attentive'].includes(baseEmotion);

    // Seed pseudo-randomness with time to dynamically inject micro-gestures
    const p = Math.sin(time * 0.5); 
    
    if (isEvaluating && p > 0.78) return 'chin_rub';
    if (isEvaluating && p < -0.78) return 'thinking';
    
    if (isHonestOpen && p > 0.52) return 'palm_up';
    if (isAuthoritative && p > 0.62) return 'palm_down';
  } else if (rapportEnergy > 0.68) {
    const p = Math.sin(time * 0.38 + rapportEnergy * Math.PI);
    if (p > 0.84) return 'synchrony';
    if (p < -0.88) return 'openPosture';
  }

  // Intercept with character-specific signature if it exists
  const charSigs = CHARACTER_SIGNATURES[avatarUrl];
  if (charSigs && charSigs[baseEmotion]) {
    return charSigs[baseEmotion];
  }
  
  return GESTURES[baseEmotion] ? baseEmotion : 'neutral';
};

const loadVRM = (url, scene, S, onLoaded) => {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  loader.load(url, (gltf) => {
    const vrm = gltf.userData.vrm;
    if (!vrm) { console.error('[VRM] No VRM data.'); return; }
    scene.add(vrm.scene);
    vrm.scene.rotation.y = 0;
    const hum = vrm.humanoid;
    vrm.scene.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(vrm.scene);
    const height = box.max.y - box.min.y;
    let headY = height * 0.85;
    if (hum) {
      const headNode = hum.getNormalizedBoneNode('head');
      if (headNode) {
        const headPos = new THREE.Vector3();
        headNode.getWorldPosition(headPos);
        headY = headPos.y;
      }
    }
    S.avatarHeight  = height;
    S.avatarHeadY   = headY;
    S.avatarCenterY = (box.max.y + box.min.y) / 2;
    console.log(`%c[VRM] Calibration: Height=${height.toFixed(2)}m, HeadY=${headY.toFixed(2)}m`, 'color:#a78bfa;font-weight:bold');
    if (vrm.expressionManager) {
      console.log('%c[VRM] ✅ Expressions:', 'color:#44ff88;font-weight:bold', Object.keys(vrm.expressionManager.expressionMap ?? {}));
    }
    onLoaded(vrm);
  }, undefined, (err) => console.error('[VRM] Load error:', err));
};

export default function AvatarCanvas({ audioPlayEvent, emotion = 'neutral', gestureOverride = null, avatarUrl = '/avatar.vrm', theme = 'light', zoomLevel = 50, userRapportEnergy = 0.35 }) {
  const canvasRef = useRef(null);
  const vrmRef    = useRef(null);
  const sceneRef  = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const prevBgTextureRef = useRef(null);
  const currentBgTextureRef = useRef(null);
  const currentBgUrlRef = useRef(null);
  const controlsRef = useRef(null);
  
  // Single mutable state object — updated every frame, never triggers re-renders
  const S = useRef({
    time: 0,

    // ── Face / Head ───────────────────────────────────────────────────────
    breathPhase: 0,
    swayPhaseX:  rand(0, Math.PI * 2),
    swayPhaseY:  rand(0, Math.PI * 2),
    headRotX: 0, headRotY: 0, headRotZ: 0,
    nodPhase: 0,
    // Multi-axis speaking head bob
    speakBobPhaseX: rand(0, Math.PI * 2),
    speakBobPhaseY: rand(0, Math.PI * 2),
    speakBobPhaseZ: rand(0, Math.PI * 2),

    blinkTimer: rand(1, 4), isBlinking: false,
    blinkProgress: 0, blinkWeight: 0,
    // Double blink state
    doubleBlink: false, doubleBlinkTimer: 0,

    gazeTimer:    rand(2, 5), isLookingAway: false,
    gazeTargetX:  0, gazeTargetY:  0,
    gazeCurrentX: 0, gazeCurrentY: 0,
    // Speaking gaze saccade
    speakGazeTimer: rand(0.4, 1.2),
    speakGazeX: 0, speakGazeY: 0,

    emotionPreset: null, emotionWeight: 0, emotionTarget: 0,
    currentEmotionKey: 'neutral',
    
    microTimer: rand(1, 4), microWeight: 0, microTarget: 0,

    // ── Body / Gesture ────────────────────────────────────────────────────
    hipSwayPhase: rand(0, Math.PI * 2),
    hipRotZ: 0,
    hipRotY: 0,          // NEW: forward-back rock while speaking
    spineTargetX: 0,
    spineRotY: 0,        // NEW: gentle torso twist while speaking
    // Idle micro-fidget
    fidgetTimer: rand(6, 14), isFidgeting: false,
    fidgetPhase: 0, fidgetBone: 'rightLowerArm',
    // Speaking weight shift — hip shifts with speech rhythm
    speakWeightPhase: rand(0, Math.PI * 2),
    speakLeanTarget: 0,   // forward lean when speaking
    speakLeanCurrent: 0,

    currentGesture: 'neutral',
    gestureOverride: null,
    wavePhase: 0,

    // ── Audio / Lip Sync ──────────────────────────────────────────────────
    isSpeaking:   false,
    lipActive:    false, lipStartTime: 0, lipDuration: 0,
    lipCues:      [], lipActx: null, lipLastPreset: null,
    analyser:     null, audioDataArray: new Uint8Array(128),
    currentVolume: 0,
    zoomTarget: 50,
    zoomCurrent: 50,
    avatarHeight: 1.6,
    avatarHeadY: 1.45,
    avatarCenterY: 0.8,

    bgGroup: null,
    bgPlaneGeo: null,
    bgTextureLoader: null,
    bgActiveMesh: null,
    bgActiveMat: null,
    bgOldMesh: null,
    oldBgMat: null,
    newBgMat: null,
    bgFadeProgress: 1,
    createBackgroundMaterial: null,

    keyLight: null,
    fillLight: null,
    rimLight: null,
    ambientLight: null,

    rapportTarget: 0.35,
    rapportCurrent: 0.35,
    organicNoiseSeed: rand(0, Math.PI * 2),
  }).current;

  // ─────────────────────────────────── Scene Setup & Master Loop ────────────
  useEffect(() => {
    if (!canvasRef.current) return;

    // Guard: prevent double-init in React Strict Mode
    let alive = true;

    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x000000); // Base dark void

    const getW = () => canvasRef.current?.parentElement?.offsetWidth  ?? window.innerWidth;
    const getH = () => canvasRef.current?.parentElement?.offsetHeight ?? window.innerHeight;

    const camera = new THREE.PerspectiveCamera(28, getW() / getH(), 0.1, 25);
    cameraRef.current = camera;
    camera.position.set(0, 1.45, 1.75);
    camera.lookAt(0, 1.35, 0);

    // Reuse existing renderer if canvas is the same, else create new
    let renderer = rendererRef.current;
    if (!renderer || renderer.domElement !== canvasRef.current) {
      renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current, antialias: true, alpha: false });
      rendererRef.current = renderer;
    }

    // OrbitControls setup for full 3D viewport control
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 0.3; // Allow close zoom-in on face
    controls.maxDistance = 10.0; // Don't zoom out too far
    controls.enablePan = true;  // Allow panning (right click drag / multi-finger swipe)
    controls.target.set(0, 1.35, 0); // Focus on head area initially
    controlsRef.current = controls;
    renderer.setSize(getW(), getH());
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;

    // Background Planes & Custom Blur Shader
    const bgGroup = new THREE.Group();
    bgGroup.position.set(0, 1.45, -10); // Far behind avatar
    scene.add(bgGroup);
    S.bgGroup = bgGroup;
    S.bgPlaneGeo = new THREE.PlaneGeometry(24, 13.5); // Wide enough to cover frustum shifts
    S.bgTextureLoader = new THREE.TextureLoader();
    S.createBackgroundMaterial = (texture, opacity) => new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: texture },
        opacity: { value: opacity },
        blurSize: { value: 1.65 },
        resolution: { value: new THREE.Vector2(texture.image?.width || 1024, texture.image?.height || 1024) }
      },
      vertexShader: `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform float opacity;
        uniform vec2 resolution;
        uniform float blurSize;
        varying vec2 vUv;
        void main() {
          vec2 texel = vec2(1.0 / resolution.x, 1.0 / resolution.y);
          vec4 color = vec4(0.0);
          float total = 0.0;
          for(float x = -2.0; x <= 2.0; x++) {
            for(float y = -2.0; y <= 2.0; y++) {
              color += texture2D(tDiffuse, vUv + vec2(x, y) * texel * blurSize);
              total += 1.0;
            }
          }
          gl_FragColor = color / total;
          gl_FragColor.a *= opacity;
        }
      `,
      transparent: true,
      depthWrite: false,
      depthTest: true
    });

    // Lighting: Dynamic sync with character/background vibe
    const keyLight = new THREE.DirectionalLight(0xffffff, Math.PI * 0.9);
    keyLight.position.set(1.5, 2.5, 2);
    scene.add(keyLight);
    S.keyLight = keyLight;
    
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.6);
    fillLight.position.set(-2, 1, -1);
    scene.add(fillLight);
    S.fillLight = fillLight;
    
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.3);
    rimLight.position.set(0, 3, -3);
    scene.add(rimLight);
    S.rimLight = rimLight;
    
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.35);
    scene.add(ambientLight);
    S.ambientLight = ambientLight;

    // VRM loading
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(avatarUrl, (gltf) => {
      if (!alive) return; // Abort if effect was cleaned up
      const vrm = gltf.userData.vrm;
      if (!vrm) { console.error('[VRM] No VRM data.'); return; }
      vrmRef.current = vrm;
      scene.add(vrm.scene);
      vrm.scene.rotation.y = 0;

      const em  = vrm.expressionManager;
      const hum = vrm.humanoid;

      // ── Dynamic Avatar Calibration for Camera Framing ──
      vrm.scene.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(vrm.scene);
      const height = box.max.y - box.min.y;
      let headY = 1.45;
      if (hum) {
        const headNode = hum.getNormalizedBoneNode('head');
        if (headNode) {
          const headPos = new THREE.Vector3();
          headNode.getWorldPosition(headPos);
          headY = headPos.y;
        } else {
          headY = height * 0.85;
        }
      }
      S.avatarHeight = height;
      S.avatarHeadY = headY;
      S.avatarCenterY = (box.max.y + box.min.y) / 2;
      console.log(`%c[VRM] Calibration: Height=${height.toFixed(2)}m, HeadY=${headY.toFixed(2)}m`, 'color:#a78bfa;font-weight:bold');
      
      // Calibrate initial OrbitControls targeting
      if (controlsRef.current) {
        const controls = controlsRef.current;
        const targetY = headY;
        controls.target.set(0, targetY, 0);
        camera.position.set(0, targetY, 0.7); // Focus closely on face
        controls.update();
      }
      // ──────────────────────────────────────────────────

      if (em) {
        console.log('%c[VRM] ✅ Expressions:', 'color:#44ff88;font-weight:bold',
          Object.keys(em.expressionMap ?? {}));
      }
      if (hum) {
        const bonesToCheck = [
          'hips', 'spine', 'chest', 'upperChest',
          'leftShoulder', 'rightShoulder',
          'leftUpperArm', 'rightUpperArm',
          'leftLowerArm', 'rightLowerArm',
          'leftHand', 'rightHand',
        ];
        const found    = bonesToCheck.filter(b => hum.getNormalizedBoneNode?.(b));
        const missing  = bonesToCheck.filter(b => !hum.getNormalizedBoneNode?.(b));
        console.log('%c[VRM] Bones found:', 'color:#44ff88', found);
        if (missing.length) console.warn('[VRM] Bones missing:', missing);
      }
    }, undefined, (err) => console.error('[VRM] Load error:', err));

    // ─────────────────────────────────────── MASTER ANIMATION LOOP ────────
    const clock = new THREE.Clock();
    let rafId;

    const safe  = (em, preset, val) => {
      if (!preset || !em) return;
      try { em.setValue(preset, clamp(val, 0, 1)); } catch {}
    };
    const resetMouth = (em) => MOUTH_PRESETS.forEach(p => safe(em, p, 0));

    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.05);
      S.time += dt;

      const vrm = vrmRef.current;
      if (!vrm) { renderer.render(scene, camera); return; }

      const em      = vrm.expressionManager;
      const hum     = vrm.humanoid;
      const getNode = (name) => hum?.getNormalizedBoneNode?.(name) ?? null;

      // ── Layer 0: AUDIO VOLUME (Voice-reactive) ───────────────────────────
      if (S.isSpeaking && S.analyser) {
        S.analyser.getByteFrequencyData(S.audioDataArray);
        let sum = 0;
        for (let i = 0; i < 32; i++) sum += S.audioDataArray[i]; // check low/mid frequencies
        const avg = sum / 32.0;
        // Map 0-255 to 0-1, with slight boost
        S.currentVolume = lerp(S.currentVolume, clamp((avg / 128.0), 0, 1.5), dt * 10);
      } else {
        S.currentVolume = lerp(S.currentVolume, 0, dt * 5);
      }
      const volBoost = S.currentVolume; // ranges ~0 to 1.5
      
      const profile = CHARACTER_PROFILES[avatarUrl] || CHARACTER_PROFILES['/avatar.vrm'];

      // ── Natural Timing Jitter (Allan Pease 'organic movement' rule) ──────
      const jitter = Math.sin(S.time * 2.5 + S.organicNoiseSeed) * 0.05 + Math.sin(S.time * 4.1 + S.organicNoiseSeed * 0.7) * 0.03;
      S.rapportCurrent = lerp(S.rapportCurrent, S.rapportTarget, dt * 1.2);
      const mirrorLift = 1 + S.rapportCurrent * 0.28;

      // ── Layer 1: BREATHING ───────────────────────────────────────────────
      const breathRate = (S.currentEmotionKey === 'surprised' ? 0.45 : 0.32) * profile.breathRate;
      S.breathPhase += (dt + dt * jitter) * breathRate * (0.96 + S.rapportCurrent * 0.12);
      const breathVal = (Math.sin(S.breathPhase) + 1) * 0.5;   // 0..1

      const chestNode = getNode('upperChest') ?? getNode('chest');
      if (chestNode) chestNode.rotation.x = breathVal * 0.018;

      // Shoulders rise/fall with breath + emotion (Territorial/Open posture)
      const lShoulder = getNode('leftShoulder');
      const rShoulder = getNode('rightShoulder');
      const isConfident = ['leadership', 'confidentSpeech', 'openness', 'openPosture'].includes(S.currentEmotionKey) || S.rapportCurrent > 0.72;
      const isDefensive = ['sad', 'tired', 'displeasure', 'opposition'].includes(S.currentEmotionKey);
      
      const shoulderRaise = S.currentEmotionKey === 'happy' ? -0.05 : (isDefensive ? 0.05 : 0);
      const shoulderOpen = isConfident ? 0.1 : (isDefensive ? -0.1 : 0); // Allan Pease chest open/close

      if (lShoulder) { lShoulder.rotation.z = breathVal * 0.04 + shoulderRaise; lShoulder.rotation.y = shoulderOpen; }
      if (rShoulder) { rShoulder.rotation.z = -breathVal * 0.04 - shoulderRaise; rShoulder.rotation.y = -shoulderOpen; }

      // ── Layer 2: HIP WEIGHT SHIFT (Mirroring user energy) ────────────────
      // While speaking: hips subtly shift side-to-side with speech rhythm (natural weight transfer)
      S.hipSwayPhase += (dt + dt * jitter) * (S.isSpeaking ? (0.80 + volBoost * 0.5) : 0.45 * mirrorLift) * profile.swayRate;
      const hipTarget = Math.sin(S.hipSwayPhase) * (S.isSpeaking ? 0.018 : 0.022 * (0.9 + S.rapportCurrent * 0.25)) * profile.swayAmp;
      S.hipRotZ = lerp(S.hipRotZ, hipTarget, dt * 1.8);

      // Speaking: subtle forward-back weight rock (heel to toe) — very human
      if (S.isSpeaking) {
        S.speakWeightPhase += dt * (1.1 + volBoost * 0.4);
        const fwdRock = Math.sin(S.speakWeightPhase * 0.7) * 0.006 * (0.8 + volBoost * 0.5);
        S.hipRotY = lerp(S.hipRotY, fwdRock, dt * 2.0);
      } else {
        S.hipRotY = lerp(S.hipRotY, 0, dt * 1.5);
      }

      // Speaking forward lean — avatar leans slightly into conversation
      S.speakLeanTarget = S.isSpeaking ? (-0.018 - volBoost * 0.012) : 0;
      S.speakLeanCurrent = lerp(S.speakLeanCurrent, S.speakLeanTarget, dt * 1.2);

      const hipsNode = getNode('hips');
      if (hipsNode) {
        hipsNode.rotation.z = S.hipRotZ;
        hipsNode.rotation.x = breathVal * 0.005 + S.speakLeanCurrent;
        hipsNode.rotation.y = S.hipRotY;
      }

      // ── Layer 2.5: NATURAL LOWER BODY ANIMATION (Weight shift + heel/leg bobbing) ──
      const leftUpperLeg = getNode('leftUpperLeg');
      const rightUpperLeg = getNode('rightUpperLeg');
      const leftLowerLeg = getNode('leftLowerLeg');
      const rightLowerLeg = getNode('rightLowerLeg');
      const leftFoot = getNode('leftFoot');
      const rightFoot = getNode('rightFoot');

      if (leftUpperLeg && rightUpperLeg && leftLowerLeg && rightLowerLeg && leftFoot && rightFoot) {
        // Hips shift sways the weight.
        const hipShift = S.hipRotZ; // sways between ~-0.025 and 0.025
        
        // Cyclic weight shifting rhythm (every ~8 seconds, shifting weight left to right)
        const shiftCycle = S.time * 0.78;
        const leftLegLift = Math.max(0, Math.sin(shiftCycle)) * 0.22;  // bent and lifted slightly (heel raise)
        const rightLegLift = Math.max(0, -Math.sin(shiftCycle)) * 0.22;
        
        const leftLegBend = hipShift > 0 ? (hipShift * 3.5) : 0;
        const rightLegBend = hipShift <= 0 ? (-hipShift * 3.5) : 0;

        // Apply natural knee bends, thigh rotations, and ankle rotations to simulate natural shifting
        leftUpperLeg.rotation.x = lerp(leftUpperLeg.rotation.x, -leftLegLift * 0.7 - leftLegBend * 0.4, dt * 2.0);
        leftUpperLeg.rotation.z = lerp(leftUpperLeg.rotation.z, -hipShift * 0.5, dt * 2.0);
        leftLowerLeg.rotation.x = lerp(leftLowerLeg.rotation.x, leftLegLift * 1.5 + leftLegBend * 1.2, dt * 2.0);
        leftFoot.rotation.x = lerp(leftFoot.rotation.x, leftLegLift * 0.8 + leftLegBend * 0.6, dt * 2.0);

        rightUpperLeg.rotation.x = lerp(rightUpperLeg.rotation.x, -rightLegLift * 0.7 - rightLegBend * 0.4, dt * 2.0);
        rightUpperLeg.rotation.z = lerp(rightUpperLeg.rotation.z, -hipShift * 0.5, dt * 2.0);
        rightLowerLeg.rotation.x = lerp(rightLowerLeg.rotation.x, rightLegLift * 1.5 + rightLegBend * 1.2, dt * 2.0);
        rightFoot.rotation.x = lerp(rightFoot.rotation.x, rightLegLift * 0.8 + rightLegBend * 0.6, dt * 2.0);
      }

      // ── Layer 3: SPINE LEAN (Emotion-driven Posture) ─────────────────────
      const POSTURE_OFFSETS = {
        surprised: -0.06, happy: -0.04, confidentSpeech: -0.07, leadership: -0.06, openness: -0.05, jollyLaughter: -0.05, // Open/Confident
        sad: 0.06, comforting: 0.03, attentive: 0.02, tired: 0.05, // Closed/Evaluating
        anger: -0.02, // rigid
        relaxed: 0.01,
      };
      
      S.spineTargetX = (POSTURE_OFFSETS[S.currentEmotionKey] ?? (S.isSpeaking ? 0.02 : 0.01)) + S.speakLeanCurrent * 0.6;

      // Speaking torso twist — natural lateral spine rotation while talking
      if (S.isSpeaking) {
        S.spineRotY = lerp(S.spineRotY, Math.sin(S.hipSwayPhase * 0.5) * 0.025 * profile.swayAmp, dt * 1.2);
      } else {
        S.spineRotY = lerp(S.spineRotY, 0, dt * 1.0);
      }

      const spineNode = getNode('spine');
      if (spineNode) {
        // Apply emotion posture + subtle breath curve + speaking torso twist
        spineNode.rotation.x = lerp(spineNode.rotation.x, S.spineTargetX + breathVal * 0.008, dt * 1.5);
        spineNode.rotation.y = lerp(spineNode.rotation.y, S.spineRotY, dt * 1.5);
      }

      // ── Layer 4: HEAD IDLE SWAY & TILT ───────────────────────────────────
      // Idle: gentle, slow sway. Speaking: reduced sway (head is actively moving with speech)
      S.swayPhaseX += (dt + dt * jitter * 0.5) * (S.isSpeaking ? 0.12 : 0.10 * mirrorLift) * profile.swayRate;
      S.swayPhaseY += (dt + dt * jitter * 0.5) * (S.isSpeaking ? 0.10 : 0.08 * mirrorLift) * profile.swayRate;
      const swayAmp = (S.isSpeaking ? 0.004 : 0.013 * (0.88 + S.rapportCurrent * 0.28)) * profile.swayAmp;
      S.headRotX = lerp(S.headRotX, Math.sin(S.swayPhaseX) * swayAmp, dt * 1.8);
      S.headRotY = lerp(S.headRotY, Math.sin(S.swayPhaseY) * swayAmp * 0.6, dt * 1.8);
      
      // Thinking head tilt — slight head tilt when pondering
      let targetHeadZ = (S.currentEmotionKey === 'thinking') ? -0.08 : 0;
      S.headRotZ = lerp(S.headRotZ, targetHeadZ, dt * 2.0);

      // ── Layer 5: HUMAN-LIKE SPEAKING HEAD MOTION ──────────────────────────
      // Real humans move head in 3 axes while speaking: nod (X), side-to-side (Y), slight roll (Z)
      // This replaces the old single-axis nod with a richer multi-axis motion.
      let speakX = 0, speakY = 0, speakZ = 0;
      if (S.isSpeaking) {
        // Advance all three independent oscillators at slightly different rates
        S.speakBobPhaseX += dt * (1.8 + volBoost * 0.9);
        S.speakBobPhaseY += dt * (1.3 + volBoost * 0.5);
        S.speakBobPhaseZ += dt * (0.9 + volBoost * 0.3);

        const bobAmpBase = 0.022 + volBoost * 0.018;
        // X: primary nod up-down (most visible)
        speakX = Math.sin(S.speakBobPhaseX) * bobAmpBase;
        // Y: side lean — like tilting head while making a point
        speakY = Math.sin(S.speakBobPhaseY) * (bobAmpBase * 0.45);
        // Z: subtle roll — adds organic feel, prevents robotic look
        speakZ = Math.sin(S.speakBobPhaseZ) * (bobAmpBase * 0.18);
        // Emphasis on loud syllables — snap head forward briefly
        if (volBoost > 0.7) {
          speakX += (volBoost - 0.7) * 0.04;
        }
      } else {
        // Smoothly return bob phases to 0 influence
        speakX = speakY = speakZ = 0;
      }

      const headNode = getNode('head');
      const neckNode = getNode('neck');
      if (headNode) {
        // Neck/Head turns slightly with the gaze direction (natural visual tracking)
        const gazeHeadX = -S.gazeCurrentY * 0.22; // tilt head up/down slightly when looking up/down
        const gazeHeadY = S.gazeCurrentX * 0.30;  // turn head left/right slightly when looking left/right
        headNode.rotation.x = lerp(headNode.rotation.x, S.headRotX + speakX + gazeHeadX, dt * 4.0);
        headNode.rotation.y = lerp(headNode.rotation.y, S.headRotY + speakY + gazeHeadY, dt * 4.0);
        headNode.rotation.z = lerp(headNode.rotation.z, S.headRotZ + speakZ, dt * 4.0);
      }
      if (neckNode) {
        // Neck echoes head at ~40% amplitude for natural chain movement + gaze tracking
        const gazeNeckX = -S.gazeCurrentY * 0.08;
        const gazeNeckY = S.gazeCurrentX * 0.12;
        neckNode.rotation.x = lerp(neckNode.rotation.x, (S.headRotX + speakX) * 0.40 + gazeNeckX, dt * 3.5);
        neckNode.rotation.y = lerp(neckNode.rotation.y, (S.headRotY + speakY) * 0.40 + gazeNeckY, dt * 3.5);
        neckNode.rotation.z = lerp(neckNode.rotation.z, speakZ * 0.30, dt * 3.5);
      }

      // ── Layer 6: BLINKING STATE MACHINE (Flutter-Free) ───────────────────
      // Speaking increases blink rate naturally
      const blinkRateMultiplier = S.isSpeaking ? 1.3 : 1.0;
      if (!S.isBlinking) {
        if (S.doubleBlinkTimer > 0) {
          // Count down double-blink delay with eyes open
          S.doubleBlinkTimer -= dt;
          if (S.doubleBlinkTimer <= 0) {
            S.isBlinking = true;
            S.blinkProgress = 0;
            S.doubleBlink = false; // complete second blink trigger
          }
        } else {
          S.blinkTimer -= dt * blinkRateMultiplier;
          if (S.blinkTimer <= 0) {
            S.isBlinking = true;
            S.blinkProgress = 0;
            // 15% chance to schedule a second blink (double-blink)
            if (Math.random() < 0.15) {
              S.doubleBlink = true;
              S.doubleBlinkTimer = rand(0.16, 0.28);
            }
            S.blinkTimer = rand(profile.blinkMin, profile.blinkMax);
          }
        }
      }
      if (S.isBlinking) {
        S.blinkProgress += dt * 13; // blink speed
        if (S.blinkProgress >= 1) {
          S.isBlinking = false;
          S.blinkProgress = 0;
        }
      }
      // Surprised emotion: eyes open wider (negative blink = widened eyes)
      const isWidened = ['surprised', 'surprise', 'interestedFlash'].includes(S.currentEmotionKey);
      const blinkTarget = S.isBlinking ? Math.sin(S.blinkProgress * Math.PI) : (isWidened ? -0.12 : 0);
      S.blinkWeight = lerp(S.blinkWeight, blinkTarget, dt * 22);
      safe(em, VRMExpressionPresetName.Blink, clamp(S.blinkWeight, 0, 1));

      // ── Layer 7: GAZE (Dynamic wandering + Speaking saccades) ────────────
      // Idle gaze: wander naturally, look away occasionally, hold eye contact
      S.gazeTimer -= dt;
      if (S.gazeTimer <= 0) {
        if (S.isLookingAway) {
           // Look back at user
           S.gazeTargetX = rand(-0.02, 0.02);
           S.gazeTargetY = rand(-0.02, 0.02);
           S.gazeTimer = rand(profile.gazeMin, profile.gazeMax) * 1.5; 
           S.isLookingAway = false;
        } else {
           const isEngaged = ['interestedFlash', 'engaged', 'attentive', 'activeListening', 'eyeContact', 'comforting', 'casualChat'].includes(S.currentEmotionKey) || S.rapportCurrent > 0.65;
           const lookAwayProb = isEngaged ? 0.08 : 0.35;

           if (Math.random() < lookAwayProb) {
               S.gazeTargetX = rand(-0.35, 0.35);
               S.gazeTargetY = rand(-0.15, 0.15);
               S.gazeTimer = rand(profile.gazeMin * 0.3, profile.gazeMax * 0.3);
               S.isLookingAway = true;
           } else {
               S.gazeTargetX = rand(-0.05, 0.05);
               S.gazeTargetY = rand(-0.03, 0.03);
               S.gazeTimer = rand(profile.gazeMin * 0.5, profile.gazeMax * 0.5);
           }
        }
      }

      // Speaking saccades — while talking, eyes make small rapid darts (very human!)
      // Real speakers look slightly left/right while retrieving words from memory.
      let speakGazeOffX = 0, speakGazeOffY = 0;
      if (S.isSpeaking) {
        S.speakGazeTimer -= dt;
        if (S.speakGazeTimer <= 0) {
          // Quick saccade: look slightly away then back — mimics word retrieval
          const isThinking = ['thinking', 'thoughtfulness', 'attentive'].includes(S.currentEmotionKey);
          S.speakGazeX = isThinking ? rand(-0.20, 0.20) : rand(-0.08, 0.08);
          S.speakGazeY = isThinking ? rand(-0.10, 0.08) : rand(-0.05, 0.05);
          S.speakGazeTimer = rand(0.3, 1.1);
        }
        speakGazeOffX = lerp(speakGazeOffX, S.speakGazeX, dt * 6.0);
        speakGazeOffY = lerp(speakGazeOffY, S.speakGazeY, dt * 6.0);
      } else {
        S.speakGazeX = lerp(S.speakGazeX, 0, dt * 3.0);
        S.speakGazeY = lerp(S.speakGazeY, 0, dt * 3.0);
        speakGazeOffX = S.speakGazeX;
        speakGazeOffY = S.speakGazeY;
      }

      S.gazeCurrentX = lerp(S.gazeCurrentX, S.gazeTargetX + speakGazeOffX, dt * (S.isLookingAway ? 4.0 : 2.0));
      S.gazeCurrentY = lerp(S.gazeCurrentY, S.gazeTargetY + speakGazeOffY, dt * (S.isLookingAway ? 4.0 : 2.0));
      if (vrm.lookAt) {
        vrm.lookAt.yaw   = S.gazeCurrentX * 30;
        vrm.lookAt.pitch = S.gazeCurrentY * 20;
      }

      // Direct Eye Bone Rotation Fallback (Guarantees visible gaze shifts even if lookAt API is not working)
      const leftEyeNode = getNode('leftEye');
      const rightEyeNode = getNode('rightEye');
      if (leftEyeNode && rightEyeNode) {
        // Clamp eye rotation range to look natural (not too extreme/cross-eyed)
        const eyeGazeX = clamp(S.gazeCurrentX, -0.22, 0.22);
        const eyeGazeY = clamp(S.gazeCurrentY, -0.12, 0.12);
        
        leftEyeNode.rotation.y = lerp(leftEyeNode.rotation.y, eyeGazeX, dt * 8.0);
        leftEyeNode.rotation.x = lerp(leftEyeNode.rotation.x, eyeGazeY, dt * 8.0);
        
        rightEyeNode.rotation.y = lerp(rightEyeNode.rotation.y, eyeGazeX, dt * 8.0);
        rightEyeNode.rotation.x = lerp(rightEyeNode.rotation.x, eyeGazeY, dt * 8.0);
      }

      // ── Layer 8: EMOTION & MICRO-EXPRESSIONS ─────────────────────────────
      S.microTimer -= dt;
      if (S.microTimer <= 0) {
        S.microTarget = Math.random() < 0.4 ? rand(0.1, 0.25) : 0; // Occasional twitch/smile
        S.microTimer = rand(1, 4);
      }
      S.microWeight = lerp(S.microWeight, S.microTarget, dt * 4);

      if (em) {
        if (S.emotionPreset) {
          S.emotionWeight = lerp(S.emotionWeight, S.emotionTarget, dt * 1.5);
          safe(em, S.emotionPreset, S.emotionWeight * EMOTION_WEIGHT_MAX);
        }
        // Apply micro-expression (subtle relaxed/smile) when not overridden heavily
        if (!S.emotionPreset || S.currentEmotionKey === 'neutral') {
          safe(em, VRMExpressionPresetName.Relaxed, S.microWeight);
        }
      }

      // ── Layer 8.5: IDLE MICRO-FIDGET SYSTEM ──────────────────────────────
      // Real humans standing still don't freeze — they occasionally shift weight,
      // adjust clothing, touch hair etc. This adds random subtle idle micro-movements.
      if (!S.isSpeaking) {
        S.fidgetTimer -= dt;
        if (S.fidgetTimer <= 0) {
          S.isFidgeting = !S.isFidgeting;
          if (S.isFidgeting) {
            // Pick a random subtle fidget bone
            const fidgetBones = ['rightLowerArm', 'leftLowerArm', 'rightHand', 'leftHand'];
            S.fidgetBone = fidgetBones[Math.floor(Math.random() * fidgetBones.length)];
            S.fidgetPhase = 0;
            S.fidgetTimer = rand(1.5, 3.0);  // fidget lasts 1.5-3s
          } else {
            S.fidgetTimer = rand(5.0, 12.0); // next fidget in 5-12s
          }
        }
        if (S.isFidgeting) S.fidgetPhase += dt;
      } else {
        // Reset fidget when speaking starts
        S.isFidgeting = false;
        S.fidgetTimer = rand(6.0, 14.0);
      }

      // ── Layer 9: HAND GESTURES (Smoothness Engine) ─────────────────────
      const targetGesture = selectGesture(S.isSpeaking, S.currentEmotionKey, S.gestureOverride, avatarUrl, S.time, S.rapportCurrent);

      if (targetGesture !== S.currentGesture) {
        console.log(`%c[GESTURE] ${S.currentGesture} → ${targetGesture}`, 'color:#fbbf24;font-weight:bold');
        S.currentGesture = targetGesture;
        S.wavePhase      = 0; // reset wave on any gesture change
      }

      const pose = GESTURES[S.currentGesture] ?? GESTURES.neutral;

      // Per-gesture lerp speed — slow gestures feel heavy/intentional, fast feel reactive
      const GESTURE_LERP_SPEED = {
        neutral:         1.8,
        greeting:        3.5,   // snappy raise
        farewell:        3.0,
        activeListening: 2.0,
        confidentSpeech: 2.5,
        leadership:      2.2,
        disagreement:    3.8,   // fast, assertive
        opposition:      4.0,
        comforting:      1.5,   // slow, gentle
        surprise:        5.0,   // instant shock reaction
        surprised:       5.0,
        casualChat:      2.0,
        relaxed:         1.2,   // very slow drift
        annoyed:         2.8,
        negotiation:     2.0,
        presentation:    2.5,
        explaining:      2.2,
        thoughtfulness:  1.8,
        approval:        3.0,
        anger:           4.5,   // fast, tense
        displeasure:     3.5,
        openness:        2.0,
        happy:           2.5,
        sad:             1.0,   // slowest — heavy sadness
        thinking:        1.8,
        // Charming gestures
        eyeContact:      1.5,   // very slow, confident stillness
        interestedFlash: 4.2,   // quick flash reaction
        receptive:       2.0,
        engaged:         2.2,
        attentive:       1.8,
        blushing:        1.4,   // slow, shy
        coySmile:        1.8,
        preening:        2.2,
        fidgeting:       2.8,   // slightly nervous, faster
        focused:         1.2,   // very deliberate
        synchrony:       2.2,
        jollyLaughter:   3.8,   // bouncy and quick
        friendlyContact: 2.5,
        gazeShift:       2.0,
        sharedFocus:     2.2,
        openPosture:     1.8,
      };
      const gLerpSpeed = dt * (GESTURE_LERP_SPEED[S.currentGesture] ?? 2.0);

      S.wavePhase += dt;

      for (const boneName of GESTURE_BONES) {
        const boneNode = getNode(boneName);
        const target   = pose[boneName];
        if (!boneNode || !target) continue;

        let tx = target.x, ty = target.y, tz = target.z;

        // ── Per-gesture organic micro-animations ─────────────────────────
        const isLeft  = boneName.startsWith('left');
        const side    = isLeft ? 0 : Math.PI;  // phase offset between sides
        const t       = S.time;

        // Greeting: right hand waving fast
        if (S.currentGesture === 'greeting' && boneName === 'rightHand') {
          tz += Math.sin(S.wavePhase * 5.0) * 0.55;
        }
        // Farewell: right hand gentle wave
        if (S.currentGesture === 'farewell' && boneName === 'rightHand') {
          tz += Math.sin(S.wavePhase * 4.0) * 0.4;
          tx += Math.sin(S.wavePhase * 2.0) * 0.05;
        }
        // Explaining: both arms sway in anti-phase (natural human motion)
        if (S.currentGesture === 'explaining' || S.currentGesture === 'confidentSpeech') {
          if (boneName.includes('LowerArm') || boneName.includes('Hand')) {
            const amp = 0.06 + volBoost * 0.08;
            tx += Math.sin(t * 2.1 + side) * amp;
            ty += Math.sin(t * 1.7 + side + 1.0) * amp * 0.5;
          }
        }
        // Negotiation: hands rock side to side
        if (S.currentGesture === 'negotiation') {
          if (boneName.includes('Hand') || boneName.includes('LowerArm')) {
            ty += Math.sin(t * 1.8 + side) * 0.07;
            tx += Math.sin(t * 1.2) * 0.04;
          }
        }
        // Thoughtfulness / activeListening: slight finger tremor on right hand
        if ((S.currentGesture === 'thoughtfulness' || S.currentGesture === 'activeListening') && boneName === 'rightHand') {
          ty += Math.sin(t * 4.5) * 0.025;
          tz += Math.sin(t * 3.1) * 0.02;
        }
        // Disagreement / opposition: hands quiver with tension
        if (S.currentGesture === 'disagreement' || S.currentGesture === 'opposition') {
          if (boneName.includes('Hand')) {
            tx += Math.sin(t * 8.0 + side) * 0.03;
            ty += Math.sin(t * 9.0 + side) * 0.025;
          }
        }
        // Anger / displeasure: rigid micro-tension in arms
        if (S.currentGesture === 'anger' || S.currentGesture === 'displeasure') {
          if (boneName.includes('Arm')) {
            tx += Math.sin(t * 10.0 + side) * 0.015;
            tz += Math.sin(t * 12.0) * 0.012;
          }
        }
        // Approval: slight up-down bounce on right arm
        if (S.currentGesture === 'approval' && (boneName === 'rightLowerArm' || boneName === 'rightHand')) {
          tx += Math.sin(t * 3.0) * 0.05;
        }
        // Openness: arms gently float up-down like breathing
        if (S.currentGesture === 'openness') {
          if (boneName.includes('UpperArm')) {
            tz += Math.sin(t * 1.2 + side) * 0.04;
          }
        }
        // Surprise: arms tremble with shock
        if ((S.currentGesture === 'surprise' || S.currentGesture === 'surprised') && boneName.includes('LowerArm')) {
          tx += Math.sin(t * 6.0 + side) * 0.035;
        }
        // Relaxed: slow natural drift on raised arm
        if (S.currentGesture === 'relaxed' && boneName === 'rightLowerArm') {
          tx += Math.sin(t * 0.8) * 0.03;
        }
        // Leadership / Presentation: pointing arm holds steady with minor natural sway
        if ((S.currentGesture === 'leadership' || S.currentGesture === 'presentation') && boneName === 'rightLowerArm') {
          ty += Math.sin(t * 1.5) * 0.02;
        }
        // CasualChat: relaxed oscillation on both forearms
        if (S.currentGesture === 'casualChat' && boneName.includes('LowerArm')) {
          tz += Math.sin(t * 1.3 + side) * 0.04;
        }
        // Comforting: slow gentle forward drift on right arm
        if (S.currentGesture === 'comforting' && boneName === 'rightLowerArm') {
          tx += Math.sin(t * 1.0) * 0.03;
        }

        // ── Charming gesture micro-animations ────────────────────────────────
        // Eye contact: ultra-slow confident breathing sway
        if (S.currentGesture === 'eyeContact' && boneName.includes('UpperArm')) {
          tz += Math.sin(t * 0.9 + side) * 0.012;
        }
        // Interested flash: quick pulse on raised right hand
        if (S.currentGesture === 'interestedFlash' && (boneName === 'rightLowerArm' || boneName === 'rightHand')) {
          tx += Math.sin(t * 4.5) * 0.04;
          ty += Math.sin(t * 3.8) * 0.02;
        }
        // Receptive: gentle bilateral float on forearms
        if (S.currentGesture === 'receptive' && boneName.includes('LowerArm')) {
          tx += Math.sin(t * 1.1 + side) * 0.035;
          ty += Math.sin(t * 0.9 + side + 0.5) * 0.02;
        }
        // Engaged: slight lean-in pulse on upper arms
        if (S.currentGesture === 'engaged' && boneName.includes('UpperArm')) {
          tz += Math.sin(t * 1.4 + side) * 0.025;
          tx += Math.sin(t * 1.0) * 0.015;
        }
        // Attentive: tiny chin-hand finger tap tremor
        if (S.currentGesture === 'attentive' && boneName === 'rightHand') {
          ty += Math.sin(t * 3.8) * 0.022;
          tz += Math.sin(t * 2.6) * 0.018;
        }
        // Blushing: shy inward oscillation — arms gently hug and release
        if (S.currentGesture === 'blushing' && boneName.includes('LowerArm')) {
          tx += Math.sin(t * 1.3 + side) * 0.03;
          ty += Math.sin(t * 0.8) * 0.02;
        }
        // Coy smile: gentle sway with slight shy arm drift
        if (S.currentGesture === 'coySmile' && (boneName === 'rightLowerArm' || boneName === 'rightHand')) {
          tx += Math.sin(t * 1.5) * 0.025;
          ty += Math.sin(t * 1.1) * 0.015;
        }
        // Preening: smooth up-down stroke hair motion
        if (S.currentGesture === 'preening') {
          if (boneName === 'rightLowerArm') { tx += Math.sin(t * 1.8) * 0.04; tz += Math.sin(t * 1.2) * 0.02; }
          if (boneName === 'rightHand')     { ty += Math.sin(t * 2.2) * 0.03; }
        }
        // Fidgeting: hands intertwine — opposing oscillations
        if (S.currentGesture === 'fidgeting' && boneName.includes('Hand')) {
          tx += Math.sin(t * 5.5 + side) * 0.035;
          ty += Math.sin(t * 4.2 + side + 1.0) * 0.025;
          tz += Math.sin(t * 6.0 + side) * 0.02;
        }
        // Focused: almost frozen — tiniest breathing sway only
        if (S.currentGesture === 'focused' && boneName.includes('UpperArm')) {
          tz += Math.sin(t * 0.7 + side) * 0.008;
        }
        // Synchrony: mirroring natural anti-phase arm sway
        if (S.currentGesture === 'synchrony' && (boneName.includes('LowerArm') || boneName.includes('Hand'))) {
          const syncAmp = 0.05 + volBoost * 0.06;
          tx += Math.sin(t * 2.0 + side) * syncAmp;
          ty += Math.sin(t * 1.6 + side + 0.8) * syncAmp * 0.4;
        }
        // Jolly laughter: bouncy full-body arm bounce
        if (S.currentGesture === 'jollyLaughter' && boneName.includes('Arm')) {
          tx += Math.sin(t * 4.0) * 0.06;
          tz += Math.sin(t * 4.0 + side) * 0.04;
        }
        // Friendly contact: warm forward reach pulse on right arm
        if (S.currentGesture === 'friendlyContact' && (boneName === 'rightLowerArm' || boneName === 'rightHand')) {
          tx += Math.sin(t * 1.6) * 0.03;
        }
        // Gaze shift: very slow side-lean of whole arm posture
        if (S.currentGesture === 'gazeShift' && boneName.includes('UpperArm')) {
          ty += Math.sin(t * 0.8) * 0.025;
        }
        // Shared focus: pointing arm holds with minor natural sway
        if (S.currentGesture === 'sharedFocus' && boneName === 'rightLowerArm') {
          ty += Math.sin(t * 1.3) * 0.018;
          tz += Math.sin(t * 0.9) * 0.012;
        }
        // Open posture: arms breathe wide — subtle float like wings
        if (S.currentGesture === 'openPosture' && boneName.includes('UpperArm')) {
          tz += Math.sin(t * 1.0 + side) * 0.038;
          tx += Math.sin(t * 0.75) * 0.015;
        }

        // ── Idle micro-fidget overlay (only when not speaking, on specific bone) ──
        if (!S.isSpeaking && S.isFidgeting && boneName === S.fidgetBone) {
          const fp = S.fidgetPhase;
          // Gentle, non-repeating micro-movement (dampened sine)
          const dampening = Math.max(0, 1.0 - fp * 0.6); // fades out
          tx += Math.sin(fp * 3.2) * 0.025 * dampening;
          ty += Math.sin(fp * 2.1 + 0.8) * 0.018 * dampening;
          tz += Math.sin(fp * 4.0 + 1.5) * 0.015 * dampening;
        }

        // ── Universal: voice-reactive amplitude boost ─────────────────────
        if (S.isSpeaking) {
          tx += (tx > 0 ? volBoost * 0.04 : -volBoost * 0.04);
          ty += (ty > 0 ? volBoost * 0.03 : -volBoost * 0.03);
          tz += Math.sin(t * 7.3 + side) * (0.008 + volBoost * 0.03);
        }

        boneNode.rotation.x = lerp(boneNode.rotation.x, tx, gLerpSpeed);
        boneNode.rotation.y = lerp(boneNode.rotation.y, ty, gLerpSpeed);
        boneNode.rotation.z = lerp(boneNode.rotation.z, tz, gLerpSpeed);
      }

      // ── Layer 10: LIP SYNC ───────────────────────────────────────────────
      if (em && S.lipActive && S.lipActx) {
        const t = S.lipActx.currentTime - S.lipStartTime;
        if (t > S.lipDuration + 0.1) {
          resetMouth(em);
          S.lipActive = false; S.isSpeaking = false; S.lipLastPreset = null;
        } else {
          let activeCue = null;
          for (let i = S.lipCues.length - 1; i >= 0; i--) {
            if (t >= S.lipCues[i].start) { activeCue = S.lipCues[i]; break; }
          }
          const tp = activeCue ? (RHUBARB_TO_VRM[activeCue.value] ?? null) : null;
          if (tp !== S.lipLastPreset) {
            resetMouth(em);
            if (tp) safe(em, tp, 1.0);
            S.lipLastPreset = tp;
          }
        }
      }

      // ── Layer 11: CAMERA ZOOM (OrbitControls Update) ──────────────────────
      if (controlsRef.current) {
        controlsRef.current.update();
      }

      // ── Layer 12: BACKGROUND DEPTH & PARALLAX (Billboard Alignment) ────────
      if (S.bgGroup) {
        if (S.oldBgMat && S.newBgMat) {
          S.bgFadeProgress += dt * 2.4; // ~420ms fade
          const fade = clamp(S.bgFadeProgress, 0, 1);
          S.oldBgMat.uniforms.opacity.value = 1.0 - fade;
          S.newBgMat.uniforms.opacity.value = fade;
          if (fade >= 1.0) {
            if (S.bgOldMesh) {
              S.bgGroup.remove(S.bgOldMesh);
              S.bgOldMesh.geometry?.dispose?.();
              S.bgOldMesh = null;
            }
            S.oldBgMat.dispose?.();
            S.oldBgMat = null;
            S.newBgMat.uniforms.opacity.value = 1.0;
            prevBgTextureRef.current = currentBgTextureRef.current;
          }
        } else if (S.newBgMat && !S.oldBgMat) {
          S.newBgMat.uniforms.opacity.value = 1.0;
          prevBgTextureRef.current = currentBgTextureRef.current;
        }

        // Parallax depth effect: the far plane follows camera motion, staying perpendicular (billboard)
        if (cameraRef.current) {
          const target = controlsRef.current ? controlsRef.current.target : new THREE.Vector3(0, 1.35, 0);
          const dir = new THREE.Vector3().copy(cameraRef.current.position).sub(target).normalize();
          S.bgGroup.position.copy(target).addScaledVector(dir, -10.0);
          S.bgGroup.quaternion.copy(cameraRef.current.quaternion);
        }
      }

      // ── VRM physics (spring bones, etc.) ─────────────────────────────────
      vrm.update(dt);
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = getW(), h = getH();
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);
    setTimeout(onResize, 50);

    return () => {
      alive = false;
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', onResize);
      // Dispose OrbitControls
      if (controlsRef.current) {
        controlsRef.current.dispose();
        controlsRef.current = null;
      }
      // Remove old VRM from scene when avatar changes
      if (vrmRef.current) {
        sceneRef.current?.remove(vrmRef.current.scene);
        vrmRef.current = null;
      }
      S.bgGroup = null;
      S.bgActiveMesh = null;
      S.bgActiveMat = null;
      S.bgOldMesh = null;
      S.oldBgMat = null;
      S.newBgMat = null;
      S.keyLight = null;
      S.fillLight = null;
      S.rimLight = null;
      S.ambientLight = null;
      // Do NOT dispose renderer here — it is persistent (rendererRef)
      // Renderer is only disposed when component fully unmounts (see cleanup below)
    };
  }, [avatarUrl]);


  // Character/theme background image update -- independent from VRM loading.
  useEffect(() => {
    let cancelled = false;
    const candidates = getBackgroundCandidates(avatarUrl, theme);
    if (currentBgUrlRef.current && candidates.includes(currentBgUrlRef.current) && S.bgActiveMesh) return;

    const loadCandidate = (index = 0) => {
      if (cancelled || !S.bgGroup || !S.bgPlaneGeo || !S.bgTextureLoader || !S.createBackgroundMaterial) return;
      if (index >= candidates.length) {
        console.warn('[BG] Background image not found:', candidates);
        return;
      }

      const url = candidates[index];
      S.bgTextureLoader.load(url, (texture) => {
        if (cancelled || !S.bgGroup) {
          texture.dispose?.();
          return;
        }

        texture.colorSpace = THREE.SRGBColorSpace;
        const hadBackground = Boolean(S.bgActiveMesh || prevBgTextureRef.current);
        let oldMesh = S.bgActiveMesh;
        let oldMat = S.bgActiveMat;

        if (!oldMesh && prevBgTextureRef.current) {
          oldMat = S.createBackgroundMaterial(prevBgTextureRef.current, 1.0);
          oldMesh = new THREE.Mesh(S.bgPlaneGeo, oldMat);
          oldMesh.position.z = 0.1;
          oldMesh.renderOrder = -101;
          oldMesh.frustumCulled = false;
          S.bgGroup.add(oldMesh);
        }

        const newMat = S.createBackgroundMaterial(texture, hadBackground ? 0.0 : 1.0);
        const newMesh = new THREE.Mesh(S.bgPlaneGeo, newMat);
        newMesh.position.z = 0;
        newMesh.renderOrder = -100;
        newMesh.frustumCulled = false;
        S.bgGroup.add(newMesh);

        S.bgOldMesh = oldMesh;
        S.oldBgMat = oldMat;
        S.newBgMat = newMat;
        S.bgActiveMesh = newMesh;
        S.bgActiveMat = newMat;
        S.bgFadeProgress = hadBackground ? 0 : 1;
        currentBgTextureRef.current = texture;
        currentBgUrlRef.current = url;
        if (!hadBackground) prevBgTextureRef.current = texture;
      }, undefined, () => loadCandidate(index + 1));
    };

    loadCandidate();
    return () => { cancelled = true; };
  }, [avatarUrl, theme]);

  // Lighting follows the active character room and light/dark mode.
  useEffect(() => {
    const avatarName = AVATAR_NAMES[avatarUrl] || 'kavya';
    const mood = BACKGROUND_LIGHTING[avatarName] || BACKGROUND_LIGHTING.kavya;
    const isDark = theme === 'dark';

    if (sceneRef.current) {
      sceneRef.current.background = new THREE.Color(isDark ? 0x080a12 : 0xf7f2ea);
    }
    if (S.keyLight) {
      S.keyLight.color.setHex(isDark ? mood.keyDark : mood.keyLight);
      S.keyLight.intensity = Math.PI * (isDark ? 0.95 : 0.82);
    }
    if (S.fillLight) {
      S.fillLight.color.setHex(isDark ? mood.fillDark : mood.fillLight);
      S.fillLight.intensity = isDark ? 0.58 : 0.72;
    }
    if (S.rimLight) {
      S.rimLight.color.setHex(isDark ? 0xdbeafe : 0xffffff);
      S.rimLight.intensity = isDark ? 0.36 : 0.24;
    }
    if (S.ambientLight) {
      S.ambientLight.color.setHex(isDark ? 0xd7ddff : 0xfff7ed);
      S.ambientLight.intensity = isDark ? 0.34 : 0.42;
    }
  }, [avatarUrl, theme]);

  // Frontend-only mirroring signal from recent user text.
  useEffect(() => {
    S.rapportTarget = clamp(userRapportEnergy, 0, 1);
  }, [userRapportEnergy]);
  // True unmount cleanup — dispose renderer
  useEffect(() => {
    return () => {
      if (rendererRef.current) {
        try { rendererRef.current.dispose(); } catch {}
        rendererRef.current = null;
      }
    };
  }, []); // empty deps = runs only on TRUE unmount

  // Emotion prop → animation state
  useEffect(() => {
    const em     = vrmRef.current?.expressionManager;
    const preset = EMOTION_PRESET[emotion] ?? null;
    if (S.emotionPreset && S.emotionPreset !== preset && em) {
      try { em.setValue(S.emotionPreset, 0); } catch {}
    }
    S.emotionPreset    = preset;
    S.emotionTarget    = preset ? 1 : 0;
    S.emotionWeight    = 0;
    S.currentEmotionKey = emotion;
  }, [emotion]);

  // Gesture override prop → animation state
  useEffect(() => {
    S.gestureOverride = gestureOverride;
    if (gestureOverride) {
      console.log(`%c[GESTURE] Override set → ${gestureOverride}`, 'color:#fbbf24;font-weight:bold');
    }
  }, [gestureOverride]);


  // Zoom update driven by React prop slider
  useEffect(() => {
    S.zoomTarget = zoomLevel;
    if (controlsRef.current) {
      const controls = controlsRef.current;
      const normalizedZoom = zoomLevel / 100.0;
      
      const headY = S.avatarHeadY || 1.45;
      const centerY = S.avatarCenterY || 0.8;
      const fullHeight = S.avatarHeight || 1.6;

      const targetY = lerp(headY, centerY, normalizedZoom);
      const targetDistance = lerp(0.7, fullHeight * 2.3, normalizedZoom);

      controls.target.set(0, targetY, 0);
      
      const dir = new THREE.Vector3().copy(controls.object.position).sub(controls.target).normalize();
      controls.object.position.copy(controls.target).addScaledVector(dir, targetDistance);
      controls.update();
    }
  }, [zoomLevel]);

  // Lip sync trigger
  useEffect(() => {
    S.lipActive = false; S.isSpeaking = false; S.lipLastPreset = null;
    const em = vrmRef.current?.expressionManager;
    if (em) MOUTH_PRESETS.forEach(p => { try { em.setValue(p, 0); } catch {} });

    if (!audioPlayEvent) return;
    const { startTime, duration, visemes, actx } = audioPlayEvent;

    if (!visemes?.mouthCues?.length) {
      console.warn('[LIP-SYNC] No mouthCues — skipping.');
      return;
    }

    console.log(
      `%c[LIP-SYNC] 🎬 ${visemes.mouthCues.length} cues, ${duration.toFixed(2)}s`,
      'color:#ff88ff;font-weight:bold'
    );

    S.lipActive    = true;
    S.lipStartTime = startTime;
    S.lipDuration  = duration;
    S.lipCues      = visemes.mouthCues;
    S.lipActx      = actx;
    S.analyser     = audioPlayEvent.analyser || null;
    S.isSpeaking   = true;

    return () => { S.lipActive = false; S.isSpeaking = false; };
  }, [audioPlayEvent]);

  return (
    <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
  );
}
