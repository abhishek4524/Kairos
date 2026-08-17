import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VRMLoaderPlugin, VRMExpressionPresetName } from '@pixiv/three-vrm';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { RoomEnvironment } from './components/avatar/RoomEnvironment';

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
// Expanded emotion → raw morph target blends (layered on top of VRM presets)
// These drive Fcl_* morphs directly on the face SkinnedMesh for nuanced looks.
// Mouth/jaw morphs are zeroed during active lip-sync to protect viseme priority.
// ─────────────────────────────────────────────────────────────────────────────
const EMOTION_MORPH_LAYERS = {
  happy:           [{ m:'Fcl_EYE_Joy',   w:0.55 }, { m:'Fcl_MTH_Fun',  w:0.30 }, { m:'Fcl_BRW_Joy',       w:0.40 }],
  greeting:        [{ m:'Fcl_EYE_Joy',   w:0.60 }, { m:'Fcl_MTH_Fun',  w:0.40 }, { m:'Fcl_BRW_Joy',       w:0.50 }],
  approval:        [{ m:'Fcl_EYE_Joy',   w:0.45 }, { m:'Fcl_MTH_Fun',  w:0.25 }, { m:'Fcl_BRW_Joy',       w:0.35 }],
  comforting:      [{ m:'Fcl_EYE_Natural',w:0.40}, { m:'Fcl_BRW_Sorrow',w:0.25}, { m:'Fcl_MTH_Neutral',   w:0.20 }],
  sad:             [{ m:'Fcl_ALL_Sorrow', w:0.50 }, { m:'Fcl_EYE_Sorrow',w:0.35}, { m:'Fcl_BRW_Sorrow',   w:0.45 }],
  thinking:        [{ m:'Fcl_EYE_Natural',w:0.50}, { m:'Fcl_BRW_Fun',   w:0.20 }],
  thoughtfulness:  [{ m:'Fcl_EYE_Natural',w:0.45}, { m:'Fcl_BRW_Fun',   w:0.15 }],
  attentive:       [{ m:'Fcl_EYE_Natural',w:0.55}, { m:'Fcl_BRW_Fun',   w:0.15 }],
  focused:         [{ m:'Fcl_EYE_Natural',w:0.60}, { m:'Fcl_MTH_Neutral',w:0.30}],
  curious:         [{ m:'Fcl_BRW_Surprised',w:0.40}, { m:'Fcl_EYE_Spread',w:0.25}, { m:'Fcl_EYE_Natural', w:0.30 }],
  interestedFlash: [{ m:'Fcl_BRW_Surprised',w:0.55}, { m:'Fcl_EYE_Spread',w:0.35}],
  surprised:       [{ m:'Fcl_ALL_Surprised',w:0.65}, { m:'Fcl_EYE_Surprised',w:0.55}],
  surprise:        [{ m:'Fcl_ALL_Surprised',w:0.60}, { m:'Fcl_EYE_Surprised',w:0.50}],
  anger:           [{ m:'Fcl_ALL_Angry',  w:0.55 }, { m:'Fcl_EYE_Angry', w:0.45 }, { m:'Fcl_BRW_Angry',   w:0.50 }],
  annoyed:         [{ m:'Fcl_EYE_Angry',  w:0.35 }, { m:'Fcl_BRW_Angry', w:0.30 }, { m:'Fcl_MTH_Angry',   w:0.20 }],
  displeasure:     [{ m:'Fcl_EYE_Angry',  w:0.30 }, { m:'Fcl_BRW_Angry', w:0.25 }],
  disagreement:    [{ m:'Fcl_BRW_Angry',  w:0.40 }, { m:'Fcl_EYE_Angry', w:0.30 }],
  blushing:        [{ m:'Fcl_EYE_Joy_L',  w:0.30 }, { m:'Fcl_EYE_Joy_R', w:0.30 }, { m:'Fcl_BRW_Joy',     w:0.25 }],
  coySmile:        [{ m:'Fcl_EYE_Joy_L',  w:0.40 }, { m:'Fcl_EYE_Joy_R', w:0.40 }, { m:'Fcl_MTH_Fun',     w:0.30 }],
  jollyLaughter:   [{ m:'Fcl_ALL_Joy',    w:0.70 }, { m:'Fcl_EYE_Joy',   w:0.60 }, { m:'Fcl_MTH_Large',   w:0.50 }],
  relaxed:         [{ m:'Fcl_EYE_Natural',w:0.30}, { m:'Fcl_MTH_Neutral',w:0.15}],
  casualChat:      [{ m:'Fcl_EYE_Natural',w:0.25}],
  neutral:         [],
};
const EMOTION_MORPH_MAX = 0.42; // Cap below lip-sync weight so visemes always win


// ─────────────────────────────────────────────────────────────────────────────
// Hand Gesture Pose Library
// ─────────────────────────────────────────────────────────────────────────────
const GESTURES = {
  // ── Core / neutral ────────────────────────────────────────────────────────────
  // Natural relaxed standing — arms hang naturally at sides, slight bend at elbow
  neutral:         { leftUpperArm: { x:0.08, y:0.00, z:-1.20 }, rightUpperArm: { x:0.08, y:0.00, z: 1.20 }, leftLowerArm: { x:0.10, y:0.00, z:-0.08 }, rightLowerArm: { x:0.10, y:0.00, z: 0.08 }, leftHand: { x:0.00, y: 0.05, z:-0.02 }, rightHand: { x:0.00, y:-0.05, z: 0.02 } },
  seated_neutral:  { leftUpperArm: { x:0.35, y: 0.12, z:-0.65 }, rightUpperArm: { x:0.35, y:-0.12, z: 0.65 }, leftLowerArm: { x:-0.60, y: 0.10, z: 0.05 }, rightLowerArm: { x:-0.60, y:-0.10, z:-0.05 }, leftHand: { x:0.00, y: 0.05, z:-0.02 }, rightHand: { x:0.00, y:-0.05, z: 0.02 } },
  reading_book:    { leftUpperArm: { x:0.35, y: 0.20, z:-0.55 }, rightUpperArm: { x:0.35, y:-0.20, z: 0.55 }, leftLowerArm: { x:-0.90, y: 0.25, z: 0.15 }, rightLowerArm: { x:-0.90, y:-0.25, z:-0.15 }, leftHand: { x:0.10, y: 0.15, z: 0.10 }, rightHand: { x:0.10, y:-0.15, z:-0.10 } },
  jump_air:        { leftUpperArm: { x:-0.40, y: 0.10, z:-0.50 }, rightUpperArm: { x:-0.40, y:-0.10, z: 0.50 }, leftLowerArm: { x:-0.50, y: 0.10, z: 0.10 }, rightLowerArm: { x:-0.50, y:-0.10, z:-0.10 }, leftHand: { x:0.00, y: 0.00, z: 0.00 }, rightHand: { x:0.00, y: 0.00, z: 0.00 } },
  
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
  thumbs_up:       { leftUpperArm: { x:0.10, y:0.00, z:-1.15 }, rightUpperArm: { x:-0.10, y:-0.08, z: 0.30 }, leftLowerArm: { x:0.18, y:0.00, z:-0.12 }, rightLowerArm: { x:-0.70, y: 0.10, z:-0.08 }, leftHand: { x:0.00, y: 0.10, z: 0.00 }, rightHand: { x: 0.10, y:-0.10, z:-0.10 } },
  
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

// ─────────────────────────────────────────────────────────────────────────────
// Finger Pose Library — curl values [proximalZ, intermediateZ, distalZ]
// Applied via VRM humanoid finger bones on top of wrist pose
// ─────────────────────────────────────────────────────────────────────────────
const FINGER_POSES = {
  open:     { index:[0.00,0.00,0.00], middle:[0.00,0.00,0.00], ring:[0.00,0.00,0.00], little:[0.00,0.00,0.00], thumb:[-0.05,0.00,0.00] },
  relaxed:  { index:[0.12,0.18,0.12], middle:[0.14,0.20,0.14], ring:[0.15,0.22,0.15], little:[0.16,0.24,0.16], thumb:[ 0.10,0.12,0.08] },
  flat:     { index:[0.06,0.08,0.06], middle:[0.06,0.08,0.06], ring:[0.06,0.08,0.06], little:[0.08,0.10,0.08], thumb:[ 0.15,0.10,0.06] },
  fist:     { index:[1.20,1.40,1.00], middle:[1.20,1.40,1.00], ring:[1.20,1.40,1.00], little:[1.20,1.40,1.00], thumb:[ 0.50,0.60,0.40] },
  pointing: { index:[0.00,0.00,0.00], middle:[1.20,1.40,1.00], ring:[1.20,1.40,1.00], little:[1.20,1.40,1.00], thumb:[ 0.40,0.50,0.30] },
  thumbsUp: { index:[1.20,1.40,1.00], middle:[1.20,1.40,1.00], ring:[1.20,1.40,1.00], little:[1.20,1.40,1.00], thumb:[-0.10,0.00,0.00] },
  peace:    { index:[0.00,0.00,0.00], middle:[0.00,0.00,0.00], ring:[1.20,1.40,1.00], little:[1.20,1.40,1.00], thumb:[ 0.40,0.50,0.30] },
  chin_cup: { index:[0.50,0.60,0.40], middle:[0.50,0.60,0.40], ring:[0.55,0.65,0.45], little:[0.55,0.65,0.45], thumb:[ 0.20,0.25,0.15] },
};

// Maps [gestureName] → [rightHandPose, leftHandPose]
const GESTURE_FINGER_POSE = {
  neutral:       ['relaxed', 'relaxed'],
  seated_neutral:['relaxed', 'relaxed'],
  reading_book:  ['flat', 'flat'],
  jump_air:      ['open', 'open'],
  namaste:       ['flat', 'flat'],
  wave:          ['open', 'relaxed'],
  goodbye:       ['open', 'relaxed'],
  salute:        ['flat', 'relaxed'],
  peace:         ['peace', 'relaxed'],
  explaining:    ['flat', 'flat'],
  palm_up:       ['flat', 'flat'],
  palm_down:     ['flat', 'flat'],
  point_up:      ['pointing', 'relaxed'],
  aanya_point:   ['pointing', 'relaxed'],
  fist_pump:     ['fist', 'relaxed'],
  thumbs_up:     ['thumbsUp', 'relaxed'],
  thinking:      ['chin_cup', 'relaxed'],
  chin_rub:      ['chin_cup', 'relaxed'],
  clapping:      ['flat', 'flat'],
  heart_hands:   ['flat', 'flat'],
  arms_crossed:  ['relaxed', 'relaxed'],
};

// Humanoid VRM bone names for each finger, [L, R], [Proximal, Intermediate, Distal]
const FINGER_JOINTS = {
  index:  { L: ['leftIndexProximal','leftIndexIntermediate','leftIndexDistal'],
             R: ['rightIndexProximal','rightIndexIntermediate','rightIndexDistal'] },
  middle: { L: ['leftMiddleProximal','leftMiddleIntermediate','leftMiddleDistal'],
             R: ['rightMiddleProximal','rightMiddleIntermediate','rightMiddleDistal'] },
  ring:   { L: ['leftRingProximal','leftRingIntermediate','leftRingDistal'],
             R: ['rightRingProximal','rightRingIntermediate','rightRingDistal'] },
  little: { L: ['leftLittleProximal','leftLittleIntermediate','leftLittleDistal'],
             R: ['rightLittleProximal','rightLittleIntermediate','rightLittleDistal'] },
  thumb:  { L: ['leftThumbMetacarpal','leftThumbProximal','leftThumbDistal'],
             R: ['rightThumbMetacarpal','rightThumbProximal','rightThumbDistal'] },
};




const getBackgroundCandidates = (theme) => {
  const mode = theme === 'dark' ? 'dark' : 'light';
  // Use relative paths — critical for Electron (file:// protocol doesn't support absolute /paths)
  return [
    `./backgrounds/kavya_${mode}.jpg`,
    `./backgrounds/kavya_${mode}.png`,
    `./bg_kavya_${mode}.png`,
    `./bg_kavya_${mode}.jpg`,
  ];
};

const GESTURE_BONES = [
  'leftUpperArm', 'rightUpperArm',
  'leftLowerArm', 'rightLowerArm',
  'leftHand',     'rightHand',
];

const selectGesture = (isSpeaking, emotionKey, override, time, rapportEnergy = 0, isSeated = false, isReading = false, isJumping = false) => {
  if (override) return override;
  
  const baseEmotion = isSpeaking ? emotionKey : 'comforting';
  
  if (isSpeaking) {
    const isHonestOpen = ['openness', 'comforting', 'casualChat', 'friendlyContact'].includes(baseEmotion);
    const isAuthoritative = ['leadership', 'confidentSpeech', 'explaining'].includes(baseEmotion);
    const isEvaluating = ['thinking', 'thoughtfulness', 'attentive'].includes(baseEmotion);

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

  if (isJumping) {
    return 'jump_air';
  }
  if (isReading && !isSpeaking) {
    return 'reading_book';
  }
  if (isSeated && !isSpeaking) {
    return 'seated_neutral';
  }

  const charSigs = { greeting: 'namaste', happy: 'kavya_open', comforting: 'kavya_open' };
  if (charSigs[baseEmotion]) {
    return charSigs[baseEmotion];
  }
  
  return GESTURES[baseEmotion] ? baseEmotion : 'neutral';
};


// ─────────────────────────────────────────────────────────────────────────────
// GesturePlayer — transient gesture overlay with fade-in / hold / fade-out
// Layers a short gesture clip on top of the base pose without replacing it.
// ─────────────────────────────────────────────────────────────────────────────
class GesturePlayer {
  constructor() {
    this._current = null;
    this.weight   = 0;
    this.name     = null;
  }

  play(name, opts = {}) {
    const fadeIn  = opts.fadeIn  ?? 0.25;
    const hold    = opts.hold    ?? 1.00;
    const fadeOut = opts.fadeOut ?? 0.40;
    this._current = { name, elapsed: 0, fadeIn, hold, fadeOut, total: fadeIn + hold + fadeOut };
    this.name   = name;
    this.weight = 0;
  }

  update(dt) {
    if (!this._current) { this.weight = 0; return; }
    this._current.elapsed += dt;
    const { elapsed, fadeIn, hold, fadeOut, total } = this._current;
    if      (elapsed < fadeIn)          this.weight = elapsed / fadeIn;
    else if (elapsed < fadeIn + hold)   this.weight = 1.0;
    else if (elapsed < total)           this.weight = 1.0 - (elapsed - fadeIn - hold) / fadeOut;
    else { this.weight = 0; this.name = null; this._current = null; }
  }

  get isActive() { return !!this._current; }
  get overlay()  { return this._current ? { name: this.name, weight: this.weight } : null; }
}

export default function AvatarCanvas({ 
  audioPlayEvent, 
  emotion = 'neutral', 
  gestureOverride = null, 
  theme = 'light', 
  zoomLevel = 50, 
  userRapportEnergy = 0.35,
  lampOn = true,
  interactionPose = 'standing',
  transientGesture = null
}) {
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

    room: null,
    keyLight: null,
    fillLight: null,
    goldRimLight: null,
    cyanRimLight: null,
    bounceLight: null,
    ambientLight: null,

    rapportTarget: 0.35,
    rapportCurrent: 0.35,
    organicNoiseSeed: rand(0, Math.PI * 2),

    // ── Locomotion & Interaction State ─────────────────────────────────────
    gesturePlayer: new GesturePlayer(),
    faceMesh: null,
    fingerLerpSpeed: 6.0,
    interactionMode: 'standing', // 'standing', 'walking_to_chair', 'sitting_down', 'seated', 'standing_up', 'walking_to_center', 'walking_to_bookshelf', 'reading_book', 'putting_book_down'
    isJumping: false,
    jumpPhase: 0,
    returnFromX: 0,
    returnFromZ: 0,
    interactionProgress: 0,
    walkPhase: 0,
    vrmPosX: 0,
    vrmPosY: 0,
    vrmPosZ: 0,
    vrmRotY: 0,
  }).current;

  // ─────────────────────────────────── Scene Setup & Master Loop ────────────
  useEffect(() => {
    if (!canvasRef.current) return;

    // Guard: prevent double-init in React Strict Mode
    let alive = true;

    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(theme === 'dark' ? 0x080a12 : 0xf7f2ea);

    // ── Stylized 3D Room Environment (Desk, Chair, Bookshelf, Interactive Lamp) ──
    const room = new RoomEnvironment(scene, theme === 'dark');
    room.setLampState(lampOn);
    S.room = room;

    const getW = () => canvasRef.current?.parentElement?.offsetWidth  ?? window.innerWidth;
    const getH = () => canvasRef.current?.parentElement?.offsetHeight ?? window.innerHeight;

    // 0.05 near plane prevents close-up facial clipping (eyelashes/nose)
    const camera = new THREE.PerspectiveCamera(28, getW() / getH(), 0.05, 35);
    cameraRef.current = camera;
    camera.position.set(0, 1.45, 1.75);
    camera.lookAt(0, 1.35, 0);

    // Reuse existing renderer if canvas is the same, else create new
    let renderer = rendererRef.current;
    if (!renderer || renderer.domElement !== canvasRef.current) {
      renderer = new THREE.WebGLRenderer({ 
        canvas: canvasRef.current, 
        antialias: true, 
        alpha: false,
        powerPreference: 'high-performance'
      });
      rendererRef.current = renderer;
    }

    // OrbitControls setup with damping and boundary limits
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 0.35; // Safe close-up limit without clipping head mesh
    controls.maxDistance = 6.0;  // Limit zoom-out distance
    controls.minPolarAngle = Math.PI * 0.15; // Prevent flipping overhead
    controls.maxPolarAngle = Math.PI * 0.82; // Prevent looking through floor
    controls.enablePan = true;
    controls.target.set(0, 1.35, 0); // Focus on head area initially
    controlsRef.current = controls;

    renderer.setSize(getW(), getH());
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;

    // Background Planes & Custom Gaussian Bokeh Depth Shader
    const bgGroup = new THREE.Group();
    bgGroup.position.set(0, 1.45, -10);
    scene.add(bgGroup);
    S.bgGroup = bgGroup;
    S.bgPlaneGeo = new THREE.PlaneGeometry(26, 14.5);
    S.bgTextureLoader = new THREE.TextureLoader();
    S.createBackgroundMaterial = (texture, opacity) => new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: texture },
        opacity: { value: opacity },
        blurSize: { value: 1.8 },
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
          vec2 texel = vec2(1.0 / resolution.x, 1.0 / resolution.y) * blurSize;
          vec4 color = vec4(0.0);
          // 9-tap weighted Gaussian distribution for soft cinematic background bokeh
          color += texture2D(tDiffuse, vUv + vec2(-2.0, -2.0) * texel) * 0.045;
          color += texture2D(tDiffuse, vUv + vec2(-1.0, -1.0) * texel) * 0.122;
          color += texture2D(tDiffuse, vUv + vec2( 0.0, -1.5) * texel) * 0.143;
          color += texture2D(tDiffuse, vUv + vec2( 1.0, -1.0) * texel) * 0.122;
          color += texture2D(tDiffuse, vUv + vec2( 2.0,  0.0) * texel) * 0.045;
          color += texture2D(tDiffuse, vUv + vec2( 0.0,  0.0) * texel) * 0.200;
          color += texture2D(tDiffuse, vUv + vec2(-1.0,  1.0) * texel) * 0.122;
          color += texture2D(tDiffuse, vUv + vec2( 0.0,  1.5) * texel) * 0.143;
          color += texture2D(tDiffuse, vUv + vec2( 1.0,  1.0) * texel) * 0.122;
          
          // Soft radial vignette falloff to emphasize the avatar as center focal point
          vec2 centerUv = (vUv - 0.5) * 1.8;
          float vignette = clamp(1.0 - dot(centerUv, centerUv) * 0.45, 0.4, 1.0);
          color.rgb *= vignette;

          gl_FragColor = color;
          gl_FragColor.a *= opacity;
        }
      `,
      transparent: true,
      depthWrite: false,
      depthTest: true
    });

    // ── Three-Point + Dual-Rim Lighting Setup ────────────────────────────────
    // 1. Key Light: Warm studio key from front-right
    const keyLight = new THREE.DirectionalLight(0xfff3e3, Math.PI * 1.05);
    keyLight.position.set(1.6, 2.2, 2.2);
    scene.add(keyLight);
    S.keyLight = keyLight;
    
    // 2. Fill Light: Soft cool fill from front-left to open up shadows
    const fillLight = new THREE.DirectionalLight(0xd4e8fc, 0.72);
    fillLight.position.set(-2.2, 1.4, 1.6);
    scene.add(fillLight);
    S.fillLight = fillLight;
    
    // 3. Gold Rim Light: Warm gold rim accent from rear-right (UI Gold harmony)
    const goldRimLight = new THREE.DirectionalLight(0xf5c560, 2.1);
    goldRimLight.position.set(1.8, 2.2, -2.4);
    scene.add(goldRimLight);
    S.goldRimLight = goldRimLight;
    
    // 4. Cyan Rim Light: Tech cyan rim accent from rear-left (UI Cyan harmony)
    const cyanRimLight = new THREE.DirectionalLight(0x06b6d4, 1.85);
    cyanRimLight.position.set(-1.8, 1.9, -2.2);
    scene.add(cyanRimLight);
    S.cyanRimLight = cyanRimLight;

    // 5. Bounce Light: Soft ground bounce under chin & neck
    const bounceLight = new THREE.DirectionalLight(0x4a3220, 0.45);
    bounceLight.position.set(0, -1.5, 0.8);
    scene.add(bounceLight);
    S.bounceLight = bounceLight;
    
    // 6. Ambient Light: Balanced base atmosphere
    const ambientLight = new THREE.AmbientLight(0x282c3c, 0.55);
    scene.add(ambientLight);
    S.ambientLight = ambientLight;

    // VRM loading
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load('./avatar.vrm', (gltf) => {
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
      // Locate face mesh with Fcl_* morph targets for expanded expression palette
      vrm.scene.traverse((obj) => {
        if (obj.isMesh && obj.morphTargetDictionary &&
            obj.morphTargetDictionary['Fcl_ALL_Joy'] !== undefined &&
            !S.faceMesh) {
          S.faceMesh = obj;
          console.log('%c[VRM] 🎭 Face mesh located with', 'color:#f9a8d4;font-weight:bold',
            Object.keys(obj.morphTargetDictionary).length, 'morph targets');
        }
      });
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
      
      const profile = { breathRate: 1.0, swayRate: 1.0, swayAmp: 1.0, blinkMin: 2.0, blinkMax: 5.0, gazeMin: 2.0, gazeMax: 5.0 }; // Kavya

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

      // ── Micro-idle head noise (ultra-subtle, prevents robotic stillness) ──
      if (!S.isSpeaking && S.interactionMode === 'standing') {
        const neckNode = getNode('neck');
        if (neckNode) {
          // Very slow organic drift — nearly imperceptible individually but alive collectively
          neckNode.rotation.x = lerp(neckNode.rotation.x,
            Math.sin(S.time * 0.19 + S.organicNoiseSeed) * 0.012 +
            Math.sin(S.time * 0.31 + S.organicNoiseSeed * 1.3) * 0.007, dt * 0.8);
          neckNode.rotation.z = lerp(neckNode.rotation.z,
            Math.sin(S.time * 0.13 + S.organicNoiseSeed * 0.7) * 0.009 +
            Math.sin(S.time * 0.23 + S.organicNoiseSeed * 1.7) * 0.005, dt * 0.8);
        }
      }

      // ── Layer 2.5: LOCOMOTION & SEATING KINEMATICS ENGINE ───────────────
      const chairTargetX = 0.85;
      const chairTargetZ = -0.50;
      const chairSitY = -0.42;
      const bookshelfTargetX = -1.10;
      const bookshelfTargetZ = -0.50;

      let isWalking = false;
      let seatProgress = 0; // 0 = standing, 1 = fully seated

      // ── Jump In-Place Physics ──
      if (S.isJumping) {
        S.jumpPhase += dt * 1.35;
        const jp = S.jumpPhase;
        if (jp < 0.2) {
          const c = Math.sin((jp / 0.2) * Math.PI * 0.5);
          S.vrmPosY = -0.09 * c;
        } else if (jp < 0.75) {
          const airP = (jp - 0.2) / 0.55;
          S.vrmPosY = Math.sin(airP * Math.PI) * 0.38;
        } else if (jp <= 1.0) {
          const landP = (jp - 0.75) / 0.25;
          S.vrmPosY = -0.06 * Math.sin((1.0 - landP) * Math.PI);
        } else {
          S.isJumping = false;
          S.jumpPhase = 0;
          S.vrmPosY = 0;
        }
      } else

      if (S.interactionMode === 'walking_to_chair') {
        isWalking = true;
        S.interactionProgress = Math.min(1, S.interactionProgress + dt * 0.72);
        const p = S.interactionProgress;
        const e = p * p * (3 - 2 * p);
        S.vrmPosX = lerp(0, chairTargetX, e);
        S.vrmPosZ = lerp(0, chairTargetZ, e);
        if (p < 0.85) {
          S.vrmRotY = lerp(S.vrmRotY, 0.45, dt * 5.0);
        } else {
          S.vrmRotY = lerp(S.vrmRotY, 0.05, dt * 6.0);
        }
        S.walkPhase += dt * 6.8;
        S.vrmPosY = Math.abs(Math.sin(S.walkPhase * 2)) * 0.025;
        if (p >= 1) {
          S.interactionMode = 'sitting_down';
          S.interactionProgress = 0;
        }
      } else if (S.interactionMode === 'sitting_down') {
        S.interactionProgress = Math.min(1, S.interactionProgress + dt * 1.15);
        const p = S.interactionProgress;
        seatProgress = p * p * (3 - 2 * p);
        S.vrmPosX = chairTargetX;
        S.vrmPosZ = chairTargetZ;
        S.vrmPosY = lerp(0, chairSitY, seatProgress);
        S.vrmRotY = lerp(S.vrmRotY, 0.05, dt * 6.0);
        if (p >= 1) {
          S.interactionMode = 'seated';
        }
      } else if (S.interactionMode === 'seated') {
        seatProgress = 1.0;
        S.vrmPosX = chairTargetX;
        S.vrmPosZ = chairTargetZ;
        S.vrmPosY = chairSitY;
        S.vrmRotY = 0.05;
      } else if (S.interactionMode === 'standing_up') {
        S.interactionProgress = Math.min(1, S.interactionProgress + dt * 1.15);
        const p = S.interactionProgress;
        seatProgress = 1.0 - (p * p * (3 - 2 * p));
        S.vrmPosX = chairTargetX;
        S.vrmPosZ = chairTargetZ;
        S.vrmPosY = lerp(0, chairSitY, seatProgress);
        S.vrmRotY = 0.05;
        if (p >= 1) {
          S.returnFromX = chairTargetX;
          S.returnFromZ = chairTargetZ;
          S.interactionMode = 'walking_to_center';
          S.interactionProgress = 0;
        }
      } else if (S.interactionMode === 'walking_to_bookshelf') {
        isWalking = true;
        S.interactionProgress = Math.min(1, S.interactionProgress + dt * 0.72);
        const p = S.interactionProgress;
        const e = p * p * (3 - 2 * p);
        S.vrmPosX = lerp(0, bookshelfTargetX, e);
        S.vrmPosZ = lerp(0, bookshelfTargetZ, e);
        S.vrmRotY = lerp(S.vrmRotY, 0.40, dt * 5.0);
        S.walkPhase += dt * 6.8;
        S.vrmPosY = Math.abs(Math.sin(S.walkPhase * 2)) * 0.025;
        if (p >= 1) {
          S.interactionMode = 'reading_book';
          S.interactionProgress = 0;
          S.room?.setHeldBookVisible(true, S.vrmPosX, 1.08, S.vrmPosZ + 0.28, 0.40);
        }
      } else if (S.interactionMode === 'reading_book') {
        S.vrmPosX = bookshelfTargetX;
        S.vrmPosZ = bookshelfTargetZ;
        S.vrmPosY = 0;
        S.vrmRotY = 0.40;
        S.room?.updateHeldBookPose(S.vrmPosX, 1.08 + Math.sin(S.time * 1.5) * 0.005, S.vrmPosZ + 0.28, 0.40);
      } else if (S.interactionMode === 'putting_book_down') {
        S.interactionProgress = Math.min(1, S.interactionProgress + dt * 1.5);
        if (S.interactionProgress >= 1) {
          S.room?.setHeldBookVisible(false);
          S.returnFromX = bookshelfTargetX;
          S.returnFromZ = bookshelfTargetZ;
          S.interactionMode = 'walking_to_center';
          S.interactionProgress = 0;
        }
      } else if (S.interactionMode === 'walking_to_center') {
        isWalking = true;
        S.interactionProgress = Math.min(1, S.interactionProgress + dt * 0.72);
        const p = S.interactionProgress;
        const e = p * p * (3 - 2 * p);
        S.vrmPosX = lerp(S.returnFromX, 0, e);
        S.vrmPosZ = lerp(S.returnFromZ, 0, e);
        S.vrmRotY = lerp(S.vrmRotY, 0, dt * 6.0);
        S.walkPhase += dt * 6.8;
        S.vrmPosY = Math.abs(Math.sin(S.walkPhase * 2)) * 0.025;
        if (p >= 1) {
          S.vrmPosX = 0;
          S.vrmPosY = 0;
          S.vrmPosZ = 0;
          S.vrmRotY = 0;
          S.interactionMode = 'standing';
        }
      } else {
        // Default standing
        S.vrmPosX = 0;
        S.vrmPosY = 0;
        S.vrmPosZ = 0;
        S.vrmRotY = 0;
      }

      vrm.scene.position.set(S.vrmPosX, S.vrmPosY, S.vrmPosZ);
      vrm.scene.rotation.y = S.vrmRotY;

      // Leg / Ankle Bone Updates
      const leftUpperLeg = getNode('leftUpperLeg');
      const rightUpperLeg = getNode('rightUpperLeg');
      const leftLowerLeg = getNode('leftLowerLeg');
      const rightLowerLeg = getNode('rightLowerLeg');
      const leftFoot = getNode('leftFoot');
      const rightFoot = getNode('rightFoot');

      if (leftUpperLeg && rightUpperLeg && leftLowerLeg && rightLowerLeg && leftFoot && rightFoot) {
        if (S.isJumping) {
          // Jump leg kinematics — 3 phases: crouch (0-0.2), air tuck (0.2-0.75), land (0.75-1.0)
          const jp = S.jumpPhase;
          let thighTarget = 0, calfTarget = 0, footTarget = 0;
          if (jp < 0.2) {
            // Crouch charge: knees bend forward
            const t = jp / 0.2;
            thighTarget = 0.40 * t;
            calfTarget = 0.70 * t;
            footTarget = -0.15 * t;
          } else if (jp < 0.75) {
            // Airborne tuck: legs lift slightly
            const t = (jp - 0.2) / 0.55;
            thighTarget = lerp(0.40, -0.22, t);
            calfTarget = lerp(0.70, 0.50, t);
            footTarget = lerp(-0.15, 0.10, t);
          } else {
            // Landing absorption
            const t = (jp - 0.75) / 0.25;
            thighTarget = lerp(-0.22, 0.28, t);
            calfTarget = lerp(0.50, 0.60, t);
            footTarget = lerp(0.10, -0.05, t);
          }
          const legSpeed = dt * 14.0;
          leftUpperLeg.rotation.x  = lerp(leftUpperLeg.rotation.x,  thighTarget, legSpeed);
          leftUpperLeg.rotation.y  = lerp(leftUpperLeg.rotation.y,  0, legSpeed);
          leftUpperLeg.rotation.z  = lerp(leftUpperLeg.rotation.z,  0, legSpeed);
          leftLowerLeg.rotation.x  = lerp(leftLowerLeg.rotation.x,  calfTarget, legSpeed);
          leftFoot.rotation.x      = lerp(leftFoot.rotation.x,      footTarget, legSpeed);
          rightUpperLeg.rotation.x = lerp(rightUpperLeg.rotation.x, thighTarget, legSpeed);
          rightUpperLeg.rotation.y = lerp(rightUpperLeg.rotation.y, 0, legSpeed);
          rightUpperLeg.rotation.z = lerp(rightUpperLeg.rotation.z, 0, legSpeed);
          rightLowerLeg.rotation.x = lerp(rightLowerLeg.rotation.x, calfTarget, legSpeed);
          rightFoot.rotation.x     = lerp(rightFoot.rotation.x,     footTarget, legSpeed);
        } else if (isWalking) {
          // Walk cycle leg swing
          const lUpper = Math.sin(S.walkPhase) * 0.52;
          const rUpper = -Math.sin(S.walkPhase) * 0.52;
          const lLower = Math.max(0, -Math.sin(S.walkPhase) * 0.60);
          const rLower = Math.max(0, Math.sin(S.walkPhase) * 0.60);
          const lFootRot = Math.sin(S.walkPhase) * 0.25;
          const rFootRot = -Math.sin(S.walkPhase) * 0.25;

          leftUpperLeg.rotation.x = lerp(leftUpperLeg.rotation.x, lUpper, dt * 8.0);
          leftUpperLeg.rotation.y = lerp(leftUpperLeg.rotation.y, 0, dt * 4.0);
          leftUpperLeg.rotation.z = lerp(leftUpperLeg.rotation.z, 0, dt * 4.0);
          leftLowerLeg.rotation.x = lerp(leftLowerLeg.rotation.x, lLower, dt * 8.0);
          leftFoot.rotation.x = lerp(leftFoot.rotation.x, lFootRot, dt * 8.0);

          rightUpperLeg.rotation.x = lerp(rightUpperLeg.rotation.x, rUpper, dt * 8.0);
          rightUpperLeg.rotation.y = lerp(rightUpperLeg.rotation.y, 0, dt * 4.0);
          rightUpperLeg.rotation.z = lerp(rightUpperLeg.rotation.z, 0, dt * 4.0);
          rightLowerLeg.rotation.x = lerp(rightLowerLeg.rotation.x, rLower, dt * 8.0);
          rightFoot.rotation.x = lerp(rightFoot.rotation.x, rFootRot, dt * 8.0);
        } else if (seatProgress > 0) {
          // Sitting pose interpolation (seatProgress: 0 = standing, 1 = seated)
          const targetThighX = -1.54 * seatProgress;
          const targetCalfX  =  1.54 * seatProgress;
          const targetThighY = -0.06 * seatProgress;
          const targetFootX  =  0.12 * seatProgress;

          leftUpperLeg.rotation.x = lerp(leftUpperLeg.rotation.x, targetThighX, dt * 6.0);
          leftUpperLeg.rotation.y = lerp(leftUpperLeg.rotation.y, targetThighY, dt * 6.0);
          leftUpperLeg.rotation.z = lerp(leftUpperLeg.rotation.z, 0, dt * 4.0);
          leftLowerLeg.rotation.x = lerp(leftLowerLeg.rotation.x, targetCalfX, dt * 6.0);
          leftFoot.rotation.x = lerp(leftFoot.rotation.x, targetFootX, dt * 6.0);

          rightUpperLeg.rotation.x = lerp(rightUpperLeg.rotation.x, targetThighX, dt * 6.0);
          rightUpperLeg.rotation.y = lerp(rightUpperLeg.rotation.y, -targetThighY, dt * 6.0);
          rightUpperLeg.rotation.z = lerp(rightUpperLeg.rotation.z, 0, dt * 4.0);
          rightLowerLeg.rotation.x = lerp(rightLowerLeg.rotation.x, targetCalfX, dt * 6.0);
          rightFoot.rotation.x = lerp(rightFoot.rotation.x, targetFootX, dt * 6.0);
        } else {
          // Default standing weight shifting
          const hipShift = S.hipRotZ;
          const shiftCycle = S.time * 0.78;
          const leftLegLift = Math.max(0, Math.sin(shiftCycle)) * 0.22;
          const rightLegLift = Math.max(0, -Math.sin(shiftCycle)) * 0.22;
          const leftLegBend = hipShift > 0 ? (hipShift * 3.5) : 0;
          const rightLegBend = hipShift <= 0 ? (-hipShift * 3.5) : 0;

          leftUpperLeg.rotation.x = lerp(leftUpperLeg.rotation.x, -leftLegLift * 0.7 - leftLegBend * 0.4, dt * 2.0);
          leftUpperLeg.rotation.y = lerp(leftUpperLeg.rotation.y, 0, dt * 2.0);
          leftUpperLeg.rotation.z = lerp(leftUpperLeg.rotation.z, -hipShift * 0.5, dt * 2.0);
          leftLowerLeg.rotation.x = lerp(leftLowerLeg.rotation.x, leftLegLift * 1.5 + leftLegBend * 1.2, dt * 2.0);
          leftFoot.rotation.x = lerp(leftFoot.rotation.x, leftLegLift * 0.8 + leftLegBend * 0.6, dt * 2.0);

          rightUpperLeg.rotation.x = lerp(rightUpperLeg.rotation.x, -rightLegLift * 0.7 - rightLegBend * 0.4, dt * 2.0);
          rightUpperLeg.rotation.y = lerp(rightUpperLeg.rotation.y, 0, dt * 2.0);
          rightUpperLeg.rotation.z = lerp(rightUpperLeg.rotation.z, -hipShift * 0.5, dt * 2.0);
          rightLowerLeg.rotation.x = lerp(rightLowerLeg.rotation.x, rightLegLift * 1.5 + rightLegBend * 1.2, dt * 2.0);
          rightFoot.rotation.x = lerp(rightFoot.rotation.x, rightLegLift * 0.8 + rightLegBend * 0.6, dt * 2.0);
        }
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

      // ── Layer 8.2: EXPANDED RAW MORPH EXPRESSION LAYERS ─────────────────
      // Drives Fcl_* morph targets directly for richer emotional nuance.
      // Mouth/jaw morphs are suppressed during active lip-sync (lipActive).
      if (S.faceMesh && S.faceMesh.morphTargetDictionary && S.faceMesh.morphTargetInfluences) {
        const morphDict = S.faceMesh.morphTargetDictionary;
        const morphInf  = S.faceMesh.morphTargetInfluences;
        const morphLayers = EMOTION_MORPH_LAYERS[S.currentEmotionKey] ?? [];
        const isLipActive = S.lipActive;

        // Determine mouth morph names to skip during lip-sync
        const mouthMorphs = new Set(['Fcl_MTH_A','Fcl_MTH_E','Fcl_MTH_I','Fcl_MTH_O','Fcl_MTH_U',
          'Fcl_MTH_Fun','Fcl_MTH_Joy','Fcl_MTH_Sorrow','Fcl_MTH_Angry','Fcl_MTH_Surprised',
          'Fcl_MTH_Close','Fcl_MTH_Large','Fcl_MTH_Small','Fcl_MTH_Neutral','Fcl_MTH_Up','Fcl_MTH_Down']);

        // Fade out all tracked morphs first (gentle decay)
        if (!S._activeMorphNames) S._activeMorphNames = new Set();
        for (const name of S._activeMorphNames) {
          const idx = morphDict[name];
          if (idx !== undefined) {
            morphInf[idx] = lerp(morphInf[idx], 0, dt * 2.5);
          }
        }
        S._activeMorphNames.clear();

        // Apply current emotion morph layers
        for (const { m, w } of morphLayers) {
          if (isLipActive && mouthMorphs.has(m)) continue; // lip-sync wins
          const idx = morphDict[m];
          if (idx === undefined) continue;
          const target = w * EMOTION_MORPH_MAX * S.emotionWeight;
          morphInf[idx] = lerp(morphInf[idx] ?? 0, target, dt * 2.0);
          S._activeMorphNames.add(m);
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

      // ── Layer 9: HAND GESTURES (Smoothness Engine + GesturePlayer overlay) ─────
      // Update transient gesture player
      S.gesturePlayer.update(dt);

      const baseGesture = selectGesture(S.isSpeaking, S.currentEmotionKey, S.gestureOverride, S.time, S.rapportCurrent, S.interactionMode === 'seated', S.interactionMode === 'reading_book', S.isJumping);
      const gpOverlay = S.gesturePlayer.overlay;

      // Blend: if GesturePlayer is active, lerp base → overlay based on weight
      const targetGesture = (gpOverlay && gpOverlay.weight > 0.05) ? gpOverlay.name : baseGesture;
      const overlayBlend  = gpOverlay ? gpOverlay.weight : 0;

      if (targetGesture !== S.currentGesture) {
        console.log(`%c[GESTURE] ${S.currentGesture} → ${targetGesture}`, 'color:#fbbf24;font-weight:bold');
        S.currentGesture = targetGesture;
        S.wavePhase      = 0;
      }

      // If overlay is fading out, use base pose blended by (1 - overlayBlend)
      const basePose    = GESTURES[baseGesture] ?? GESTURES.neutral;
      const overlayPose = GESTURES[S.currentGesture] ?? GESTURES.neutral;
      // For full overlay: use overlayPose; for base: use basePose; blend between them
      const activePose = overlayBlend > 0.05 ? overlayPose : basePose;
      const pose = activePose;

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
        thumbs_up:       3.2,
        point_up:        3.0,
        nodding:         2.4,
        head_tilt:       2.0,
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

      // ── Layer 9.5: FINGER BONE POSES ─────────────────────────────────────
      if (hum) {
        const [rPoseName, lPoseName] = GESTURE_FINGER_POSE[S.currentGesture] ?? ['relaxed', 'relaxed'];
        const rPose = FINGER_POSES[rPoseName] ?? FINGER_POSES.relaxed;
        const lPose = FINGER_POSES[lPoseName] ?? FINGER_POSES.relaxed;
        const flerpSpeed = dt * (S.fingerLerpSpeed ?? 6.0);

        for (const [finger, sides] of Object.entries(FINGER_JOINTS)) {
          const rCurl = rPose[finger];
          const lCurl = lPose[finger];
          if (rCurl && lCurl) {
            for (let i = 0; i < 3; i++) {
              const rNode = getNode(sides.R[i]);
              const lNode = getNode(sides.L[i]);
              if (rNode) rNode.rotation.z = lerp(rNode.rotation.z, rCurl[i], flerpSpeed);
              if (lNode) lNode.rotation.z = lerp(lNode.rotation.z, lCurl[i], flerpSpeed);
            }
          }
          if (finger === 'thumb') {
            const rThumbMeta = getNode('rightThumbMetacarpal');
            const lThumbMeta = getNode('leftThumbMetacarpal');
            if (rThumbMeta) rThumbMeta.rotation.x = lerp(rThumbMeta.rotation.x, (rPose?.thumb?.[0] ?? 0) > 0.3 ? -0.12 : 0.25, flerpSpeed);
            if (lThumbMeta) lThumbMeta.rotation.x = lerp(lThumbMeta.rotation.x, (lPose?.thumb?.[0] ?? 0) > 0.3 ? -0.12 : 0.25, flerpSpeed);
          }
        }
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

    // Responsive resize handler with ResizeObserver (desktop window & layout resize)
    const onResize = () => {
      const w = getW(), h = getH();
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    let resizeObserver = null;
    if (typeof ResizeObserver !== 'undefined' && canvasRef.current?.parentElement) {
      resizeObserver = new ResizeObserver(() => {
        onResize();
      });
      resizeObserver.observe(canvasRef.current.parentElement);
    }
    window.addEventListener('resize', onResize);
    setTimeout(onResize, 50);

    return () => {
      alive = false;
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', onResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
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
      if (S.room) {
        S.room.dispose();
        S.room = null;
      }
      S.keyLight = null;
      S.fillLight = null;
      S.goldRimLight = null;
      S.cyanRimLight = null;
      S.bounceLight = null;
      S.ambientLight = null;
      // Do NOT dispose renderer here — it is persistent (rendererRef)
      // Renderer is only disposed when component fully unmounts (see cleanup below)
    };
  }, []);

  // Interactive Room Lamp bulb state update
  useEffect(() => {
    if (S.room) {
      S.room.setLampState(lampOn);
    }
  }, [lampOn]);

  // Transient gesture overlay — plays a short gesture clip on top of base pose
  useEffect(() => {
    if (!transientGesture) return;
    const { name, fadeIn = 0.25, hold = 1.0, fadeOut = 0.4 } = transientGesture;
    S.gesturePlayer.play(name, { fadeIn, hold, fadeOut });
  }, [transientGesture]);

  // Navigate & Interaction triggers (Chair Sit, Bookshelf Reading, Jump)
  useEffect(() => {
    if (interactionPose === 'seated') {
      if (S.interactionMode === 'reading_book') {
        S.room?.setHeldBookVisible(false);
      }
      if (S.interactionMode === 'standing' || S.interactionMode === 'walking_to_center' || S.interactionMode === 'reading_book') {
        S.interactionMode = 'walking_to_chair';
        S.interactionProgress = 0;
      }
    } else if (interactionPose === 'reading') {
      if (S.interactionMode === 'standing' || S.interactionMode === 'walking_to_center') {
        S.interactionMode = 'walking_to_bookshelf';
        S.interactionProgress = 0;
      } else if (S.interactionMode === 'seated') {
        S.interactionMode = 'standing_up';
        S.interactionProgress = 0;
        setTimeout(() => {
          S.interactionMode = 'walking_to_bookshelf';
          S.interactionProgress = 0;
        }, 1200);
      }
    } else if (interactionPose === 'jump') {
      S.isJumping = true;
      S.jumpPhase = 0;
    } else if (interactionPose === 'standing') {
      if (S.interactionMode === 'seated' || S.interactionMode === 'sitting_down') {
        S.interactionMode = 'standing_up';
        S.interactionProgress = 0;
      } else if (S.interactionMode === 'reading_book') {
        S.interactionMode = 'putting_book_down';
        S.interactionProgress = 0;
      }
    }
  }, [interactionPose]);


  // Character/theme background image update -- independent from VRM loading.
  useEffect(() => {
    let cancelled = false;
    const candidates = getBackgroundCandidates(theme);
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
  }, [theme]);

  // Lighting follows the active theme (dark/light) with dual rim highlights
  useEffect(() => {
    const isDark = theme === 'dark';

    if (sceneRef.current) {
      sceneRef.current.background = new THREE.Color(isDark ? 0x080a12 : 0xf7f2ea);
    }
    if (S.keyLight) {
      S.keyLight.color.setHex(isDark ? 0xfff3e3 : 0xfffaed);
      S.keyLight.intensity = Math.PI * (isDark ? 1.05 : 0.90);
    }
    if (S.fillLight) {
      S.fillLight.color.setHex(isDark ? 0xd4e8fc : 0xebf4ff);
      S.fillLight.intensity = isDark ? 0.72 : 0.85;
    }
    if (S.goldRimLight) {
      S.goldRimLight.color.setHex(isDark ? 0xf5c560 : 0xd49b28);
      S.goldRimLight.intensity = isDark ? 2.1 : 1.4;
    }
    if (S.cyanRimLight) {
      S.cyanRimLight.color.setHex(isDark ? 0x06b6d4 : 0x0284c7);
      S.cyanRimLight.intensity = isDark ? 1.85 : 1.2;
    }
    if (S.bounceLight) {
      S.bounceLight.color.setHex(isDark ? 0x4a3220 : 0x6e4e35);
      S.bounceLight.intensity = isDark ? 0.45 : 0.35;
    }
    if (S.ambientLight) {
      S.ambientLight.color.setHex(isDark ? 0x282c3c : 0xfffbf5);
      S.ambientLight.intensity = isDark ? 0.55 : 0.65;
    }
  }, [theme]);

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
