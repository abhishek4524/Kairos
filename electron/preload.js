/**
 * Kavya Desktop — Electron Preload Script
 *
 * Runs in the renderer's context but with access to Node.js/Electron APIs.
 * Uses contextBridge to expose a safe, typed API to React code via window.kavya.
 *
 * Security model:
 *  - contextIsolation: true (renderer cannot access Node directly)
 *  - Only explicitly listed channels are bridged
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kavya', {
  // ── Platform detection ────────────────────────────────────────────────────
  platform: 'electron',

  // ── Window controls ───────────────────────────────────────────────────────
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close:    () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),

  // ── Listen for window state changes ──────────────────────────────────────
  onMaximizeChange: (callback) => {
    ipcRenderer.on('window:maximized',   () => callback(true));
    ipcRenderer.on('window:unmaximized', () => callback(false));
  },

  // ── OS-level command execution (JARVIS features) ──────────────────────────
  /**
   * Run a system command.
   * @param {string} command - e.g. 'notepad.exe', 'start', 'python'
   * @param {string[]} args  - command arguments
   * @param {object} options - spawn options override
   * @returns {Promise<{code: number, stdout: string, stderr: string}>}
   */
  runCommand: (command, args = [], options = {}) =>
    ipcRenderer.invoke('os:run-command', { command, args, options }),

  /**
   * Open a URL in the OS default browser or a file in its default handler.
   */
  openExternal: (url) => ipcRenderer.invoke('os:open-external', url),

  /**
   * Reveal a file or folder in Windows Explorer.
   */
  showInFolder: (filePath) => ipcRenderer.invoke('os:show-in-folder', filePath),

  /**
   * Execute an agentic desktop skill (open_app, search_and_play_youtube, open_vscode_and_write_code, check_whatsapp_notifications)
   */
  executeTool: (toolName, params = {}) =>
    ipcRenderer.invoke('os:execute-tool', { toolName, params }),

  /**
   * Write file to user workspace directory.
   */
  writeFile: (filename, content) =>
    ipcRenderer.invoke('os:write-file', { filename, content }),

  // ── Backend info ──────────────────────────────────────────────────────────
  backendStatus: () => ipcRenderer.invoke('backend:status'),
});
