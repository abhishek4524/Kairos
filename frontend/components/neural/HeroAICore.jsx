/**
 * HeroAICore.jsx — Main Centerpiece View: Living AI Core
 *
 * Replaces the legacy avatar view with the high-performance 3D Living AI Core.
 */

import React from 'react';
import LivingAICoreCanvas from '../../neural/LivingAICoreCanvas';

export default function HeroAICore({
  audioPlayEvent,
  userId = 'default_user',
  qualityTier = 'high',
}) {
  return (
    <div className="relative flex-1 flex flex-col items-center justify-center overflow-hidden w-full h-full bg-[#02040a]">
      {/* Real-Time 3D Neural Subsystem */}
      <LivingAICoreCanvas
        audioPlayEvent={audioPlayEvent}
        userId={userId}
        qualityTier={qualityTier}
      />
    </div>
  );
}
