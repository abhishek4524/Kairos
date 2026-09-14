/**
 * Kairos Desktop -- Electron Preload Script
 *
 * Runs in the renderer context but with access to Node.js/Electron APIs.
 * Uses contextBridge to expose a safe, typed API to React code via window.kavya.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kavya', {
  // -- Platform detection ---------------------------------------------------
  platform: 'electron',

  // -- Window controls ------------------------------------------------------
  minimize:    () => ipcRenderer.send('window:minimize'),
  maximize:    () => ipcRenderer.send('window:maximize'),
  close:       () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),

  onMaximizeChange: (callback) => {
    ipcRenderer.on('window:maximized',   () => callback(true));
    ipcRenderer.on('window:unmaximized', () => callback(false));
  },

  // -- OS-level command execution -------------------------------------------
  runCommand:   (command, args = [], options = {}) => ipcRenderer.invoke('os:run-command', { command, args, options }),
  openExternal: (url)              => ipcRenderer.invoke('os:open-external', url),
  showInFolder: (filePath)         => ipcRenderer.invoke('os:show-in-folder', filePath),
  writeFile:    (filename, content) => ipcRenderer.invoke('os:write-file', { filename, content }),
  executeTool:  (toolName, params = {}) => ipcRenderer.invoke('os:execute-tool', { toolName, params }),

  // -- Backend info ---------------------------------------------------------
  backendStatus: () => ipcRenderer.invoke('backend:status'),

  // -- Auto-start on Windows login ------------------------------------------
  /** Set whether Kairos should open automatically when the user logs in. */
  setLoginItem: (enabled) => ipcRenderer.invoke('app:set-login-item', enabled),
  /** Returns true if auto-start is currently enabled. */
  getLoginItem: () => ipcRenderer.invoke('app:get-login-item'),

  // -- Close-to-tray setting ------------------------------------------------
  /** Set whether closing the window minimizes to tray (true) or quits (false). */
  setCloseToTray: (enabled) => ipcRenderer.invoke('app:set-close-to-tray', enabled),
  /** Returns current close-to-tray preference. */
  getCloseToTray: () => ipcRenderer.invoke('app:get-close-to-tray'),

  // -- Live Wallpaper Mode --------------------------------------------------
  /** Enables/disables the Windows WorkerW live wallpaper renderer. */
  setLiveWallpaper: (enabled) => ipcRenderer.invoke('wallpaper:set-enabled', enabled),
  /** Returns availability, enabled/active state, pause state, and last error. */
  getLiveWallpaperState: () => ipcRenderer.invoke('wallpaper:get-state'),
  /** Returns whether the wallpaper renderer is currently throttled/paused. */
  getWallpaperPauseState: () => ipcRenderer.invoke('wallpaper:get-paused'),
  /** Fires whenever the main process auto-pauses/resumes wallpaper rendering. */
  onWallpaperPaused: (callback) => {
    const handler = (_event, paused, reason) => callback(!!paused, reason || '');
    ipcRenderer.on('wallpaper:set-paused', handler);
    return () => ipcRenderer.removeListener('wallpaper:set-paused', handler);
  },
  /** Fires whenever the wallpaper toggle or attach state changes. */
  onLiveWallpaperStateChange: (callback) => {
    const handler = (_event, state) => callback(state);
    ipcRenderer.on('wallpaper:state-changed', handler);
    return () => ipcRenderer.removeListener('wallpaper:state-changed', handler);
  },

  // -- App lifecycle --------------------------------------------------------
  /** Force-quit the app (bypasses close-to-tray). */
  quitApp: () => ipcRenderer.send('app:quit'),

  // -- First-run event ------------------------------------------------------
  /** Registers a callback fired exactly once on first install. */
  onFirstRun: (callback) => ipcRenderer.once('app:first-run', callback),

  // -- Tray relay events ----------------------------------------------------
  /** Fires when tray "Pause Listening" is clicked. */
  onTrayPauseListening:  (callback) => ipcRenderer.on('tray:pause-listening',  callback),
  /** Fires when tray "Resume Listening" is clicked. */
  onTrayResumeListening: (callback) => ipcRenderer.on('tray:resume-listening', callback),
  /** Tell the main process the current listening state (for tray menu label). */
  notifyListeningPaused:  () => ipcRenderer.send('tray:pause-listening'),
  notifyListeningResumed: () => ipcRenderer.send('tray:resume-listening'),

  /** Fires when the tray menu asks to open Settings. */
  onTrayOpenSettings: (callback) => ipcRenderer.on('tray:open-settings', callback),
});
