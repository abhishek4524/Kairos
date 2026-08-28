/**
 * Kavya Desktop — Electron Main Process
 *
 * Responsibilities:
 *  1. Spawn the Python FastAPI backend as a managed child process
 *  2. Wait for the backend to be ready before loading the UI
 *  3. Create a frameless BrowserWindow with custom title bar
 *  4. Grant mic + audio permissions without OS prompt
 *  5. Handle IPC from the renderer (window controls, OS commands)
 *  6. Cleanly kill the backend on app quit
 */

const { app, BrowserWindow, ipcMain, shell, session } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');
const fs = require('fs');

// ── WebGL / GPU flags (must be set before app is ready) ──────────────────────
// Three.js requires hardware-accelerated WebGL. These flags prevent Electron
// from disabling the GPU context due to driver blocklists or sandbox issues.
app.commandLine.appendSwitch('enable-webgl');
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('disable-software-rasterizer');
// Allow cross-origin file:// requests for loading .vrm from dist/
app.commandLine.appendSwitch('allow-file-access-from-files');
app.commandLine.appendSwitch('disable-web-security'); // dev only; remove for production
// Fix 'Unable to move the cache: Access is denied' — point GPU cache to writable location
app.commandLine.appendSwitch('disk-cache-dir', path.join(app.getPath('userData'), 'GPUCache'));

// ── Dev mode flag ─────────────────────────────────────────────────────────────
const isDev = process.argv.includes('--dev');

// ── Resolve paths (works both in dev and packaged app) ────────────────────────
function resourcePath(...parts) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, ...parts);
  }
  return path.join(__dirname, '..', ...parts);
}

const FRONTEND_DIST = resourcePath('frontend', 'dist');
const BACKEND_DIR   = resourcePath('backend');
const MODELS_DIR    = resourcePath('models');

// ── Backend process management ────────────────────────────────────────────────
let backendProcess = null;
const BACKEND_PORT = 8000;
const BACKEND_URL  = `http://127.0.0.1:${BACKEND_PORT}`;

function getPythonPath() {
  if (process.env.KAIROS_PYTHON_PATH && fs.existsSync(process.env.KAIROS_PYTHON_PATH)) {
    return process.env.KAIROS_PYTHON_PATH;
  }
  // In packaged app, use bundled venv. In dev, use system/venv python.
  const winVenv = path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(winVenv)) return winVenv;
  const unixVenv = path.join(BACKEND_DIR, 'venv', 'bin', 'python');
  if (fs.existsSync(unixVenv)) return unixVenv;
  // Fallback to system Python
  return 'python';
}

function getBravePath() {
  if (process.env.KAIROS_BRAVE_PATH && fs.existsSync(process.env.KAIROS_BRAVE_PATH)) {
    return process.env.KAIROS_BRAVE_PATH;
  }
  if (process.platform === 'win32') {
    const candidates = [
      path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
      path.join(process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)', 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
    ];
    for (const p of candidates) {
      if (p && fs.existsSync(p)) return p;
    }
    return 'brave';
  } else if (process.platform === 'darwin') {
    const macPath = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';
    if (fs.existsSync(macPath)) return macPath;
    return 'brave';
  }
  return 'brave-browser';
}

function startBackend() {
  const python = getPythonPath();
  console.log('[Backend] Spawning Python at:', python);
  console.log('[Backend] Working dir:', BACKEND_DIR);

  const env = {
    ...process.env,
    // Pass models dir so transcriber.py can find faster-whisper models
    WHISPER_MODEL_DIR: MODELS_DIR,
    // Suppress Python buffering so logs appear in real-time
    PYTHONUNBUFFERED: '1',
    // Force UTF-8 encoding — prevents cp1252 UnicodeEncodeError when Electron
    // spawns Python without a proper UTF-8 terminal on Windows
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  };

  backendProcess = spawn(
    python,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT), '--log-level', 'warning'],
    {
      cwd: BACKEND_DIR,
      env,
      // Hide the console window on Windows in production
      windowsHide: !isDev,
    }
  );

  backendProcess.stdout.on('data', (d) => console.log('[Backend stdout]', d.toString().trim()));
  backendProcess.stderr.on('data', (d) => console.error('[Backend stderr]', d.toString().trim()));

  backendProcess.on('close', (code) => {
    console.log(`[Backend] Process exited with code ${code}`);
    backendProcess = null;
  });

  backendProcess.on('error', (err) => {
    console.error('[Backend] Failed to start:', err);
  });
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Backend] Shutting down...');
    // On Windows, kill the whole process tree
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(backendProcess.pid), '/T', '/F']);
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
  }
}

/**
 * Poll backend health endpoint until it responds (up to 30 s).
 */
function waitForBackend(maxWaitMs = 30000) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    function check() {
      http.get(`${BACKEND_URL}/`, (res) => {
        if (res.statusCode < 500) {
          console.log('[Backend] Ready ✅');
          resolve();
        } else {
          retry();
        }
        res.resume();
      }).on('error', retry);
    }
    function retry() {
      if (Date.now() - started > maxWaitMs) {
        reject(new Error('Backend did not start within timeout'));
      } else {
        setTimeout(check, 500);
      }
    }
    check();
  });
}

// ── Main Window ───────────────────────────────────────────────────────────────
let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    // Frameless: we draw our own sci-fi title bar in React
    frame: false,
    transparent: false,
    backgroundColor: '#0d0d12',
    show: false, // Show only after content is ready
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      // Required for Three.js to fetch ./avatar.vrm via file:// without CORS errors
      webSecurity: false,
      // Allow media (mic + speaker) without additional prompts
      allowRunningInsecureContent: false,
    },
  });

  // ── Grant mic + audio permissions automatically ────────────────────────────
  // Electron requires explicit permission grants for getUserMedia in local pages.
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowedPermissions = ['media', 'audioCapture', 'mediaKeySystem', 'geolocation', 'notifications'];
    if (allowedPermissions.includes(permission)) {
      callback(true); // Grant
    } else {
      callback(false);
    }
  });

  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    const allowedPermissions = ['media', 'audioCapture', 'mediaKeySystem'];
    return allowedPermissions.includes(permission);
  });

  // ── Load the app ──────────────────────────────────────────────────────────
  const indexPath = path.join(FRONTEND_DIST, 'index.html');
  mainWindow.loadFile(indexPath);

  // Show window smoothly once page is painted
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  // Open external links in OS browser, not Electron window
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

function checkBackendRunning(port = 8000) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/`, (res) => {
      resolve(true);
      res.resume();
    });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  // 1. Check if backend is already running (e.g. started via manual uvicorn)
  const alreadyRunning = await checkBackendRunning(BACKEND_PORT);
  if (alreadyRunning) {
    console.log(`[Backend] Backend is already running on port ${BACKEND_PORT} — connected! ✅`);
  } else {
    // Start backend process
    startBackend();
    // Wait until it's healthy
    try {
      await waitForBackend();
    } catch (err) {
      console.error('[Main] Backend failed to start:', err.message);
    }
  }

  // 2. Open window
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => {
  stopBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopBackend();
    app.quit();
  }
});

// ── IPC Handlers ──────────────────────────────────────────────────────────────

// Window controls (called from custom title bar)
ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window:close', () => mainWindow?.close());

// Maximized state query (for the title bar toggle icon)
ipcMain.handle('window:is-maximized', () => mainWindow?.isMaximized() ?? false);

// OS-level command execution (for JARVIS features — opens apps, runs scripts)
ipcMain.handle('os:run-command', async (event, { command, args = [], options = {} }) => {
  return new Promise((resolve) => {
    const proc = spawn(command, args, {
      shell: true,
      windowsHide: false,
      ...options,
    });
    let stdout = '';
    let stderr = '';
    proc.stdout?.on('data', (d) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ code, stdout, stderr }));
    proc.on('error', (err) => resolve({ code: -1, stdout: '', stderr: err.message }));
  });
});

// Open a URL or file in the OS default handler
ipcMain.handle('os:open-external', async (event, url) => {
  await shell.openExternal(url);
  return { ok: true };
});

// Open a folder/file in Explorer
ipcMain.handle('os:show-in-folder', async (event, filePath) => {
  shell.showItemInFolder(filePath);
  return { ok: true };
});

// Write file into workspace folder
ipcMain.handle('os:write-file', async (event, { filename, content }) => {
  try {
    const workspaceDir = path.join(app.getPath('userData'), 'workspace');
    if (!fs.existsSync(workspaceDir)) {
      fs.mkdirSync(workspaceDir, { recursive: true });
    }
    const safeName = path.basename(filename);
    const targetPath = path.join(workspaceDir, safeName);
    fs.writeFileSync(targetPath, content, 'utf8');
    return { ok: true, path: targetPath };
  } catch (err) {
    console.error('[WriteFile] Error:', err);
    return { ok: false, error: err.message };
  }
});

// ── Agentic Desktop Skills Execution Bridge ─────────────────────────────────
ipcMain.handle('os:execute-tool', async (event, { toolName, params = {} }) => {
  console.log(`[AgenticTool] Executing tool: ${toolName}`, params);

  try {
    switch (toolName) {
      case 'open_app': {
        const appName = (params.app_name || '').toLowerCase().trim();
        const bravePath = getBravePath();
        if (appName === 'brave' || appName === 'brave browser') {
          exec(`"${bravePath}"`, { shell: true }, (err) => {
            if (err) shell.openExternal('https://brave.com');
          });
          return { ok: true, tool: 'open_app', app: params.app_name };
        }

        let cmd;
        if (process.platform === 'win32') {
          const appMap = {
            spotify: 'start spotify:',
            chrome: 'start chrome',
            notepad: 'notepad',
            calc: 'calc',
            calculator: 'calc',
            code: 'code',
            vscode: 'code',
            discord: 'start discord:',
            terminal: 'start wt || start cmd',
            cmd: 'start cmd',
            vlc: 'start vlc',
            explorer: 'explorer'
          };
          cmd = appMap[appName] || `start "" "${params.app_name}"`;
        } else if (process.platform === 'darwin') {
          cmd = `open -a "${params.app_name}"`;
        } else {
          cmd = `xdg-open "${params.app_name}" || "${params.app_name}"`;
        }

        return new Promise((resolve) => {
          exec(cmd, { shell: true }, (err, stdout, stderr) => {
            if (err) {
              console.warn(`[open_app] Standard start failed, fallback to direct run: ${err.message}`);
              exec(`"${params.app_name}"`, { shell: true }, (err2) => {
                resolve({ ok: !err2, tool: 'open_app', app: params.app_name, error: err2?.message });
              });
            } else {
              resolve({ ok: true, tool: 'open_app', app: params.app_name });
            }
          });
        });
      }

      case 'open_youtube_in_brave':
      case 'youtube_search':
      case 'search_and_play_youtube': {
        const query = params.query || '';
        const bravePath = getBravePath();
        const ytUrl = query 
          ? `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`
          : 'https://www.youtube.com';
        exec(`"${bravePath}" "${ytUrl}"`, { shell: true }, (err) => {
          if (err) shell.openExternal(ytUrl);
        });
        return { ok: true, tool: toolName, query, url: ytUrl };
      }

      case 'open_notepad_and_write_code': {
        const filename = params.filename || 'code.py';
        const code = params.code || '';
        const workspaceDir = path.join(app.getPath('userData'), 'workspace');
        if (!fs.existsSync(workspaceDir)) fs.mkdirSync(workspaceDir, { recursive: true });
        const filePath = path.join(workspaceDir, path.basename(filename));
        fs.writeFileSync(filePath, code, 'utf8');
        if (process.platform === 'win32') {
          exec(`notepad.exe "${filePath}"`, { shell: true });
        } else if (process.platform === 'darwin') {
          exec(`open -e "${filePath}"`, { shell: true });
        } else {
          exec(`xdg-open "${filePath}"`, { shell: true });
        }
        return { ok: true, tool: 'open_notepad_and_write_code', filename, filePath };
      }

      case 'open_vscode_and_write_code': {
        const filename = params.filename || 'script.py';
        const code = params.code || '';
        const workspaceDir = path.join(app.getPath('userData'), 'workspace');
        if (!fs.existsSync(workspaceDir)) {
          fs.mkdirSync(workspaceDir, { recursive: true });
        }
        const safeName = path.basename(filename);
        const filePath = path.join(workspaceDir, safeName);
        fs.writeFileSync(filePath, code, 'utf8');

        // Launch in VS Code
        exec(`code "${filePath}"`, { shell: true }, (err) => {
          if (err) {
            console.warn(`[VSCode] 'code' command failed, attempting default editor: ${err.message}`);
            shell.openPath(filePath);
          }
        });

        return { ok: true, tool: 'open_vscode_and_write_code', filename: safeName, filePath };
      }

      case 'check_whatsapp_notifications': {
        const waUrl = 'https://web.whatsapp.com';
        await shell.openExternal(waUrl);
        return { ok: true, tool: 'check_whatsapp_notifications', action: params.action || 'check_unread', url: waUrl };
      }

      default:
        return { ok: true, tool: toolName };
    }
  } catch (err) {
    console.error(`[AgenticTool] Execution error for ${toolName}:`, err);
    return { ok: false, error: err.message };
  }
});

// Query backend status
ipcMain.handle('backend:status', () => ({
  running: backendProcess !== null,
  port: BACKEND_PORT,
  url: BACKEND_URL,
}));
