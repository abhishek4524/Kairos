import React, { useState, useEffect } from 'react';

/**
 * ElectronTitleBar — Custom sci-fi frameless window title bar.
 *
 * Only renders when running inside Electron (window.kavya is defined).
 * Provides: drag region, app title, minimize / maximize / close buttons.
 */
export default function ElectronTitleBar() {
  const isElectron = typeof window !== 'undefined' && !!window.kavya;
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (!isElectron) return;
    // Sync initial state
    window.kavya.isMaximized().then(setIsMaximized);
    // Listen for changes from main process
    window.kavya.onMaximizeChange(setIsMaximized);
  }, [isElectron]);

  if (!isElectron) return null;

  return (
    <div
      id="electron-titlebar"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '36px',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        // WebkitAppRegion makes the whole bar draggable
        WebkitAppRegion: 'drag',
        background: 'linear-gradient(90deg, rgba(7,9,19,0.98) 0%, rgba(13,17,31,0.98) 100%)',
        borderBottom: '1px solid rgba(6,182,212,0.18)',
        backdropFilter: 'blur(20px)',
        padding: '0 12px 0 16px',
        userSelect: 'none',
      }}
    >
      {/* Left: App identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Glowing orb */}
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: '#06b6d4',
          boxShadow: '0 0 10px 2px rgba(6,182,212,0.8)',
          animation: 'kavya-pulse 2.5s ease-in-out infinite',
        }} />
        <span style={{
          fontSize: '11px',
          fontWeight: '700',
          letterSpacing: '0.18em',
          color: 'rgba(241,245,249,0.75)',
          fontFamily: "'Space Grotesk', system-ui, sans-serif",
        }}>
          KAVYA // PERSONAL AI ASSISTANT
        </span>
      </div>

      {/* Right: Window controls — NOT draggable */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '4px', WebkitAppRegion: 'no-drag' }}
      >
        <TitleBarButton
          title="Minimize"
          onClick={() => window.kavya.minimize()}
          hoverBg="rgba(255,255,255,0.08)"
        >
          <MinimizeIcon />
        </TitleBarButton>

        <TitleBarButton
          title={isMaximized ? 'Restore' : 'Maximize'}
          onClick={() => window.kavya.maximize()}
          hoverBg="rgba(255,255,255,0.08)"
        >
          {isMaximized ? <RestoreIcon /> : <MaximizeIcon />}
        </TitleBarButton>

        <TitleBarButton
          title="Close"
          onClick={() => window.kavya.close()}
          hoverBg="rgba(239,68,68,0.75)"
        >
          <CloseIcon />
        </TitleBarButton>
      </div>

      {/* Pulse animation keyframes injected inline */}
      <style>{`
        @keyframes kavya-pulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 8px 2px rgba(168,85,247,0.7); }
          50% { opacity: 0.6; box-shadow: 0 0 4px 1px rgba(168,85,247,0.3); }
        }
      `}</style>
    </div>
  );
}

function TitleBarButton({ children, onClick, title, hoverBg }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      title={title}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '32px',
        height: '28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: 'none',
        borderRadius: '6px',
        background: hovered ? hoverBg : 'transparent',
        cursor: 'pointer',
        transition: 'background 0.15s ease',
        outline: 'none',
        WebkitAppRegion: 'no-drag',
      }}
    >
      {children}
    </button>
  );
}

function MinimizeIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
      <rect y="4.5" width="10" height="1" fill="rgba(255,255,255,0.6)" />
    </svg>
  );
}

function MaximizeIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
      <rect x="0.5" y="0.5" width="9" height="9" stroke="rgba(255,255,255,0.6)" strokeWidth="1" fill="none" />
    </svg>
  );
}

function RestoreIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
      <rect x="2" y="0" width="8" height="8" stroke="rgba(255,255,255,0.6)" strokeWidth="1" fill="none" />
      <rect x="0" y="2" width="8" height="8" stroke="rgba(255,255,255,0.6)" strokeWidth="1" fill="white" fillOpacity="0.05" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
      <line x1="1" y1="1" x2="9" y2="9" stroke="rgba(255,255,255,0.8)" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="9" y1="1" x2="1" y2="9" stroke="rgba(255,255,255,0.8)" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}
