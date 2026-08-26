import React from 'react';
import { motion } from 'framer-motion';

/**
 * RetroDial — Circular analog gauge with retro-futuristic cockpit styling.
 * 
 * @param {number} value - Current value (0 - max)
 * @param {number} max - Maximum scale value (default: 100)
 * @param {string} label - Display label below dial (e.g. "MIC LEVEL", "LATENCY")
 * @param {string} unit - Unit string (e.g. "%", "ms", "dB")
 * @param {string} variant - Color theme: "gold" | "cyan" | "violet" | "coral" | "emerald"
 * @param {number} size - Diameter in pixels (default: 110)
 */
export default function RetroDial({
  value = 0,
  max = 100,
  label = "GAUGE",
  unit = "",
  variant = "gold",
  size = 110
}) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  // Angle: -120 deg (0%) to +120 deg (100%) = 240 deg total sweep
  const sweepAngle = 240;
  const startAngle = -120;
  const currentAngle = startAngle + (percentage / 100) * sweepAngle;

  // Variant color mapping
  const colorMap = {
    gold: {
      arc: '#f5c560',
      glow: 'rgba(245, 197, 96, 0.45)',
      text: 'text-amber-300',
      needle: '#f5c560',
      bezel: 'rgba(245, 197, 96, 0.25)'
    },
    cyan: {
      arc: '#06b6d4',
      glow: 'rgba(6, 182, 212, 0.45)',
      text: 'text-cyan-300',
      needle: '#06b6d4',
      bezel: 'rgba(6, 182, 212, 0.25)'
    },
    coral: {
      arc: '#ff9e7d',
      glow: 'rgba(255, 158, 125, 0.45)',
      text: 'text-orange-300',
      needle: '#ff9e7d',
      bezel: 'rgba(255, 158, 125, 0.25)'
    },
    violet: {
      arc: '#8b5cf6',
      glow: 'rgba(139, 92, 246, 0.45)',
      text: 'text-violet-300',
      needle: '#8b5cf6',
      bezel: 'rgba(139, 92, 246, 0.25)'
    },
    emerald: {
      arc: '#10b981',
      glow: 'rgba(16, 185, 129, 0.45)',
      text: 'text-emerald-300',
      needle: '#10b981',
      bezel: 'rgba(16, 185, 129, 0.25)'
    },
    blue: {
      arc: '#3b82f6',
      glow: 'rgba(59, 130, 246, 0.45)',
      text: 'text-blue-300',
      needle: '#3b82f6',
      bezel: 'rgba(59, 130, 246, 0.25)'
    },
    sky: {
      arc: '#38bdf8',
      glow: 'rgba(56, 189, 248, 0.45)',
      text: 'text-sky-300',
      needle: '#38bdf8',
      bezel: 'rgba(56, 189, 248, 0.25)'
    }
  };

  const theme = colorMap[variant] || colorMap.blue;

  const radius = (size / 2) - 10;
  const circumference = 2 * Math.PI * radius;
  const arcLength = (sweepAngle / 360) * circumference;
  const strokeDashoffset = arcLength - (percentage / 100) * arcLength;

  return (
    <div 
      className="relative flex flex-col items-center justify-center p-2 rounded-2xl bg-gradient-to-b from-slate-900/70 to-slate-950/90 border border-[var(--border-glass)] shadow-lg shrink-0"
      style={{ width: size + 20 }}
    >
      {/* Outer Cockpit Bezel Ring */}
      <div 
        className="relative flex items-center justify-center rounded-full"
        style={{ 
          width: size, 
          height: size, 
          boxShadow: `inset 0 0 15px rgba(0,0,0,0.8), 0 0 12px ${theme.glow}` 
        }}
      >
        {/* SVG Gauge Background & Arc */}
        <svg 
          width={size} 
          height={size} 
          className="absolute inset-0 -rotate-90 pointer-events-none"
        >
          {/* Background Track Arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth="5"
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={0}
            strokeLinecap="round"
            transform={`rotate(-30 ${size / 2} ${size / 2})`}
          />

          {/* Active Value Arc */}
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={theme.arc}
            strokeWidth="5"
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform={`rotate(-30 ${size / 2} ${size / 2})`}
            initial={{ strokeDashoffset: arcLength }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            style={{ filter: `drop-shadow(0 0 4px ${theme.arc})` }}
          />
        </svg>

        {/* Dial Face Center Display */}
        <div className="flex flex-col items-center justify-center z-10 text-center">
          <div className="text-sm font-mono font-bold tracking-tight text-[var(--text-main)] leading-none">
            {typeof value === 'number' ? Math.round(value) : value}
            <span className="text-[10px] text-[var(--text-subtle)] ml-0.5">{unit}</span>
          </div>
          <div className="text-[8px] font-mono tracking-widest uppercase text-[var(--text-muted)] mt-1">
            {Math.round(percentage)}%
          </div>
        </div>

        {/* Rotating Needle */}
        <div 
          className="absolute inset-0 pointer-events-none flex items-center justify-center transition-transform duration-500 ease-out"
          style={{ transform: `rotate(${currentAngle}deg)` }}
        >
          <div 
            className="w-0.5 rounded-full"
            style={{
              height: radius - 4,
              background: theme.needle,
              boxShadow: `0 0 6px ${theme.needle}`,
              marginBottom: radius - 4
            }}
          />
        </div>

        {/* Center Brass/Gold Pivot Cap */}
        <div 
          className="absolute w-3.5 h-3.5 rounded-full border border-amber-400/60 shadow-md z-20 pointer-events-none"
          style={{ 
            background: 'radial-gradient(circle, #f5c560 0%, #8b4a3c 100%)' 
          }}
        />
      </div>

      {/* Dial Label */}
      <div className="text-[10px] font-mono tracking-wider font-semibold uppercase text-[var(--text-muted)] mt-1.5 text-center truncate max-w-full">
        {label}
      </div>
    </div>
  );
}
