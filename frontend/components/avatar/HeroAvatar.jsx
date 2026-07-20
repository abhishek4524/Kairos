import React from 'react';
import AvatarCanvas from '../../AvatarCanvas';
import { Maximize2, Minimize2 } from 'lucide-react';

export default function HeroAvatar({ 
  audioPlayEvent, 
  emotion, 
  gestureOverride, 
  selectedAvatar, 
  zoomLevel, 
  onZoomChange, 
  theme = 'dark' 
}) {
  return (
    <div className="relative flex-1 flex flex-col items-center justify-center overflow-hidden w-full h-full">
      {/* Dynamic atmospheric background based on emotion */}
      <div className={`absolute inset-0 z-0 transition-opacity duration-1000 ${
        emotion === 'thinking' ? 'bg-purple-900/10' : 
        emotion === 'happy' ? 'bg-emerald-900/10' : 'bg-transparent'
      }`} />
      
      {/* 3D Canvas */}
      <div className="relative z-10 w-full h-full">
        <AvatarCanvas 
          audioPlayEvent={audioPlayEvent} 
          emotion={emotion} 
          gestureOverride={gestureOverride} 
          avatarUrl={`/${selectedAvatar}`} 
          theme={theme} 
          zoomLevel={zoomLevel} 
        />
      </div>
      
      {/* Cinematic Vignette */}
      <div className="avatar-vignette pointer-events-none" />

      {/* Floating Zoom Controls — visible on all screens */}
      <div className="absolute top-4 right-4 md:top-6 md:right-6 z-20 flex items-center gap-2 md:gap-4 px-3 md:px-6 py-2 md:py-3 rounded-full glass-panel">
        <Minimize2 size={14} className="text-white/40" />
        <input
          type="range"
          min="0" max="100"
          value={zoomLevel}
          onChange={(e) => onZoomChange(parseFloat(e.target.value))}
          className="w-24 md:w-32 accent-primary cursor-pointer h-1.5 bg-white/10 rounded-full appearance-none"
        />
        <Maximize2 size={14} className="text-white/40" />
      </div>
    </div>
  );
}
