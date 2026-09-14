/**
 * Kairos Desktop — Electron Main Process
 *
 * Responsibilities:
 *  1. Spawn the Python FastAPI backend as a managed child process
 *  2. Wait for the backend to be ready before loading the UI
 *  3. Create a frameless BrowserWindow with custom title bar
 *  4. Grant mic + audio permissions without OS prompt
 *  5. Handle IPC from the renderer (window controls, OS commands)
 *  6. System tray: minimize-to-tray, tray context menu
 *  7. Auto-start on login via app.setLoginItemSettings()
 *  8. First-run detection -> prompt renderer for auto-start preference
 *  9. Cleanly kill the backend on app quit
 */

const {
  app, BrowserWindow, ipcMain, shell, session,
  Tray, Menu, Notification, nativeImage, screen, powerMonitor,
} = require('electron');
const path = require('path');
const { spawn, exec, execFile } = require('child_process');
const http = require('http');
const fs = require('fs');

// -- WebGL / GPU flags (must be set before app is ready) ---------------------
app.commandLine.appendSwitch('enable-webgl');
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('disable-software-rasterizer');
app.commandLine.appendSwitch('allow-file-access-from-files');
app.commandLine.appendSwitch('disable-web-security');
app.commandLine.appendSwitch('disk-cache-dir', path.join(app.getPath('userData'), 'GPUCache'));

// -- Dev mode flag -----------------------------------------------------------
const isDev = process.argv.includes('--dev');

// -- Resolve paths (works both in dev and packaged app) ----------------------
function resourcePath(...parts) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, ...parts);
  }
  return path.join(__dirname, '..', ...parts);
}

const FRONTEND_DIST = resourcePath('frontend', 'dist');
const BACKEND_DIR   = resourcePath('backend');
const MODELS_DIR    = resourcePath('models');

const IS_WINDOWS = process.platform === 'win32';
const WALLPAPER_POLL_MS = 3000;

// Win32 WorkerW bridge -------------------------------------------------------
// This uses PowerShell Add-Type to compile a tiny C# P/Invoke shim at runtime
// instead of adding node-ffi-napi/electron-as-wallpaper. That keeps packaging
// simple and avoids ABI rebuilds for Electron. The fragile bit is still the
// undocumented 0x052C Progman message, which may change in future Windows
// builds; every caller treats failure as "wallpaper mode unavailable".
const WIN32_WALLPAPER_SCRIPT = `
param(
  [string]$Action,
  [string]$Hwnd,
  [int]$X = 0,
  [int]$Y = 0,
  [int]$Width = 0,
  [int]$Height = 0,
  [int]$ScreenX = 0,
  [int]$ScreenY = 0,
  [int]$ScreenWidth = 0,
  [int]$ScreenHeight = 0
)

$ErrorActionPreference = "Stop"

$source = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class NativeWallpaper {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
  }

  [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
  public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

  [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
  public static extern IntPtr FindWindowEx(IntPtr parentHandle, IntPtr childAfter, string className, string windowTitle);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam, uint flags, uint timeout, out IntPtr result);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

  [DllImport("user32.dll", EntryPoint = "GetWindowLongPtr", SetLastError = true)]
  public static extern IntPtr GetWindowLongPtr64(IntPtr hWnd, int nIndex);

  [DllImport("user32.dll", EntryPoint = "SetWindowLongPtr", SetLastError = true)]
  public static extern IntPtr SetWindowLongPtr64(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

  [DllImport("user32.dll", EntryPoint = "GetWindowLong", SetLastError = true)]
  public static extern int GetWindowLong32(IntPtr hWnd, int nIndex);

  [DllImport("user32.dll", EntryPoint = "SetWindowLong", SetLastError = true)]
  public static extern int SetWindowLong32(IntPtr hWnd, int nIndex, int dwNewLong);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern IntPtr GetForegroundWindow();

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool IsZoomed(IntPtr hWnd);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool IsWindowVisible(IntPtr hWnd);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

  [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
  public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

  public static IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex) {
    return IntPtr.Size == 8 ? GetWindowLongPtr64(hWnd, nIndex) : new IntPtr(GetWindowLong32(hWnd, nIndex));
  }

  public static IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong) {
    return IntPtr.Size == 8 ? SetWindowLongPtr64(hWnd, nIndex, dwNewLong) : new IntPtr(SetWindowLong32(hWnd, nIndex, dwNewLong.ToInt32()));
  }
}
"@

if (-not ("NativeWallpaper" -as [type])) {
  Add-Type -TypeDefinition $source
}

function Out-Result($obj) {
  $obj | ConvertTo-Json -Compress
}

function To-Hwnd([string]$value) {
  if ([string]::IsNullOrWhiteSpace($value)) { return [IntPtr]::Zero }
  return [IntPtr]([UInt64]::Parse($value))
}

function Get-ClassName([IntPtr]$handle) {
  if ($handle -eq [IntPtr]::Zero) { return "" }
  $builder = New-Object System.Text.StringBuilder 256
  [void][NativeWallpaper]::GetClassName($handle, $builder, $builder.Capacity)
  return $builder.ToString()
}

function Get-WorkerW {
  $progman = [NativeWallpaper]::FindWindow("Progman", "Program Manager")
  if ($progman -eq [IntPtr]::Zero) {
    return @{ ok = $false; error = "Progman window not found" }
  }

  # Undocumented Explorer message used by Wallpaper Engine/Lively-style desktop embedding.
  $result = [IntPtr]::Zero
  [void][NativeWallpaper]::SendMessageTimeout($progman, 0x052C, [IntPtr]::Zero, [IntPtr]::Zero, 0, 1000, [ref]$result)
  Start-Sleep -Milliseconds 150

  $worker = [IntPtr]::Zero
  $callback = [NativeWallpaper+EnumWindowsProc]{
    param([IntPtr]$topHandle, [IntPtr]$lParam)
    $defView = [NativeWallpaper]::FindWindowEx($topHandle, [IntPtr]::Zero, "SHELLDLL_DefView", $null)
    if ($defView -ne [IntPtr]::Zero) {
      $script:worker = [NativeWallpaper]::FindWindowEx([IntPtr]::Zero, $topHandle, "WorkerW", $null)
    }
    return $true
  }
  [void][NativeWallpaper]::EnumWindows($callback, [IntPtr]::Zero)

  if ($worker -eq [IntPtr]::Zero) {
    return @{ ok = $false; error = "WorkerW window not found after Progman 0x052C" }
  }
  return @{ ok = $true; progman = $progman.ToInt64(); workerw = $worker.ToInt64() }
}

try {
  if ($Action -eq "Attach") {
    $child = To-Hwnd $Hwnd
    $target = Get-WorkerW
    if (-not $target.ok) { Out-Result $target; exit 0 }
    $parent = [IntPtr]$target.workerw

    $GWL_STYLE = -16
    $GWL_EXSTYLE = -20
    $WS_CHILD = 0x40000000L
    $WS_VISIBLE = 0x10000000L
    $WS_CAPTION = 0x00C00000L
    $WS_THICKFRAME = 0x00040000L
    $WS_SYSMENU = 0x00080000L
    $WS_MINIMIZEBOX = 0x00020000L
    $WS_MAXIMIZEBOX = 0x00010000L
    $WS_EX_APPWINDOW = 0x00040000L
    $WS_EX_TOOLWINDOW = 0x00000080L
    $WS_EX_NOACTIVATE = 0x08000000L
    $SWP_NOACTIVATE = 0x0010
    $SWP_FRAMECHANGED = 0x0020
    $SWP_SHOWWINDOW = 0x0040

    [void][NativeWallpaper]::SetParent($child, $parent)
    $style = [NativeWallpaper]::GetWindowLongPtr($child, $GWL_STYLE).ToInt64()
    $style = ($style -bor $WS_CHILD -bor $WS_VISIBLE) -band (-bnot ($WS_CAPTION -bor $WS_THICKFRAME -bor $WS_SYSMENU -bor $WS_MINIMIZEBOX -bor $WS_MAXIMIZEBOX))
    [void][NativeWallpaper]::SetWindowLongPtr($child, $GWL_STYLE, [IntPtr]$style)

    $exStyle = [NativeWallpaper]::GetWindowLongPtr($child, $GWL_EXSTYLE).ToInt64()
    $exStyle = ($exStyle -bor $WS_EX_TOOLWINDOW -bor $WS_EX_NOACTIVATE) -band (-bnot $WS_EX_APPWINDOW)
    [void][NativeWallpaper]::SetWindowLongPtr($child, $GWL_EXSTYLE, [IntPtr]$exStyle)
    [void][NativeWallpaper]::SetWindowPos($child, [IntPtr]::Zero, $X, $Y, $Width, $Height, $SWP_NOACTIVATE -bor $SWP_FRAMECHANGED -bor $SWP_SHOWWINDOW)

    Out-Result @{ ok = $true; workerw = $target.workerw; progman = $target.progman }
  } elseif ($Action -eq "Detach") {
    $child = To-Hwnd $Hwnd
    [void][NativeWallpaper]::SetParent($child, [IntPtr]::Zero)
    Out-Result @{ ok = $true }
  } elseif ($Action -eq "DesktopVisible") {
    $foreground = [NativeWallpaper]::GetForegroundWindow()
    $className = Get-ClassName $foreground
    if ($foreground -eq [IntPtr]::Zero -or $className -eq "Progman" -or $className -eq "WorkerW" -or $className -eq "SHELLDLL_DefView") {
      Out-Result @{ ok = $true; desktopVisible = $true; reason = "desktop_foreground"; foregroundClass = $className }
      exit 0
    }

    $rect = New-Object NativeWallpaper+RECT
    $hasRect = [NativeWallpaper]::GetWindowRect($foreground, [ref]$rect)
    $coversPrimary = $false
    if ($hasRect) {
      $coveredWidth = [Math]::Min($rect.Right, $ScreenX + $ScreenWidth) - [Math]::Max($rect.Left, $ScreenX)
      $coveredHeight = [Math]::Min($rect.Bottom, $ScreenY + $ScreenHeight) - [Math]::Max($rect.Top, $ScreenY)
      $coverage = 0
      if ($coveredWidth -gt 0 -and $coveredHeight -gt 0 -and $ScreenWidth -gt 0 -and $ScreenHeight -gt 0) {
        $coverage = ($coveredWidth * $coveredHeight) / ($ScreenWidth * $ScreenHeight)
      }
      $coversPrimary = $coverage -ge 0.92
    }
    $maximized = [NativeWallpaper]::IsZoomed($foreground)
    $hidden = $maximized -or $coversPrimary
    Out-Result @{ ok = $true; desktopVisible = (-not $hidden); reason = $(if ($hidden) { "covered_by_foreground" } else { "desktop_partially_visible" }); foregroundClass = $className; maximized = $maximized; coversPrimary = $coversPrimary }
  } else {
    Out-Result @{ ok = $false; error = "Unknown action: $Action" }
  }
} catch {
  Out-Result @{ ok = $false; error = $_.Exception.Message }
}
`;

// -- Persistent settings (stored in userData so they survive updates) ---------
const SETTINGS_PATH = path.join(app.getPath('userData'), 'kairos-settings.json');

function loadSettings() {
  try {
    if (fs.existsSync(SETTINGS_PATH)) {
      return JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8'));
    }
  } catch (_) {}
  return null; // null means first run
}

function saveSettings(updates) {
  try {
    const current = loadSettings() || {};
    const merged = { ...current, ...updates };
    fs.writeFileSync(SETTINGS_PATH, JSON.stringify(merged, null, 2), 'utf8');
    return merged;
  } catch (e) {
    console.error('[Settings] Failed to save:', e);
    return null;
  }
}

function getLiveWallpaperEnabledSetting() {
  const s = loadSettings();
  return !!(s && s.liveWallpaperEnabled);
}

function getPrimaryWallpaperBounds() {
  const display = screen.getPrimaryDisplay();
  return display.bounds;
}

function getNativeHwndString(win) {
  const handle = win.getNativeWindowHandle();
  if (handle.length >= 8) return handle.readBigUInt64LE(0).toString();
  return BigInt(handle.readUInt32LE(0)).toString();
}

function getWallpaperScriptPath() {
  const scriptPath = path.join(app.getPath('userData'), 'win32-wallpaper-workerw.ps1');
  try {
    fs.writeFileSync(scriptPath, WIN32_WALLPAPER_SCRIPT, 'utf8');
  } catch (err) {
    console.error('[Wallpaper] Failed to write Win32 helper:', err);
  }
  return scriptPath;
}

function runWin32WallpaperAction(action, params = {}) {
  if (!IS_WINDOWS) {
    return Promise.resolve({ ok: false, error: 'Live Wallpaper Mode is only implemented on Windows.' });
  }

  const args = [
    '-NoProfile',
    '-NonInteractive',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    getWallpaperScriptPath(),
    '-Action',
    action,
  ];

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    args.push('-' + key, String(value));
  }

  return new Promise((resolve) => {
    execFile('powershell.exe', args, { windowsHide: true, timeout: 5000 }, (error, stdout, stderr) => {
      if (error) {
        resolve({ ok: false, error: error.message, stderr });
        return;
      }
      const trimmed = String(stdout || '').trim();
      if (!trimmed) {
        resolve({ ok: false, error: stderr || 'No Win32 helper output' });
        return;
      }
      try {
        resolve(JSON.parse(trimmed.split(/\r?\n/).filter(Boolean).pop()));
      } catch (parseErr) {
        resolve({ ok: false, error: parseErr.message, stdout: trimmed, stderr });
      }
    });
  });
}

// -- Backend process management ----------------------------------------------
let backendProcess = null;
const BACKEND_PORT = 8000;
const BACKEND_URL  = 'http://127.0.0.1:' + BACKEND_PORT;

function getPythonPath() {
  if (process.env.KAIROS_PYTHON_PATH && fs.existsSync(process.env.KAIROS_PYTHON_PATH)) {
    return process.env.KAIROS_PYTHON_PATH;
  }
  // In packaged app, use bundled venv. In dev, use system/venv python.
  const winVenv = path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(winVenv)) return winVenv;
  const unixVenv = path.join(BACKEND_DIR, 'venv', 'bin', 'python');
  if (fs.existsSync(unixVenv)) return unixVenv;
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

/**
 * Start the Python backend.
 * - Dev mode: backend must be started manually (uvicorn --reload). We just poll for it.
 * - Production: spawn the bundled venv Python running uvicorn directly.
 */
function startBackend() {
  if (isDev) {
    console.log('[Backend] Dev mode -- expecting manually-started uvicorn on port', BACKEND_PORT);
    return;
  }

  const python = getPythonPath();
  console.log('[Backend] Spawning Python at:', python);
  console.log('[Backend] Working dir:', BACKEND_DIR);

  const env = {
    ...process.env,
    WHISPER_MODEL_DIR: MODELS_DIR,
    PYTHONUNBUFFERED: '1',
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  };

  backendProcess = spawn(
    python,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT), '--log-level', 'warning'],
    { cwd: BACKEND_DIR, env, windowsHide: true }
  );

  backendProcess.stdout.on('data', (d) => console.log('[Backend]', d.toString().trim()));
  backendProcess.stderr.on('data', (d) => console.error('[Backend]', d.toString().trim()));
  backendProcess.on('close', (code) => {
    console.log('[Backend] Exited with code', code);
    backendProcess = null;
  });
  backendProcess.on('error', (err) => console.error('[Backend] Failed to start:', err));
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Backend] Shutting down...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(backendProcess.pid), '/T', '/F']);
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
  }
}

/** Poll backend health until ready or timeout. */
function waitForBackend(maxWaitMs) {
  maxWaitMs = maxWaitMs || (isDev ? 30000 : 45000);
  return new Promise((resolve, reject) => {
    const started = Date.now();
    function check() {
      http.get(BACKEND_URL + '/', (res) => {
        if (res.statusCode < 500) { console.log('[Backend] Ready'); resolve(); }
        else retry();
        res.resume();
      }).on('error', retry);
    }
    function retry() {
      if (Date.now() - started > maxWaitMs) reject(new Error('Backend timeout'));
      else setTimeout(check, 500);
    }
    check();
  });
}

function checkBackendRunning(port) {
  port = port || 8000;
  return new Promise((resolve) => {
    const req = http.get('http://127.0.0.1:' + port + '/', (res) => { resolve(true); res.resume(); });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => { req.destroy(); resolve(false); });
  });
}

// -- System Tray -------------------------------------------------------------
let tray = null;
let trayListeningPaused = false;
let liveWallpaperEnabled = false;

function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'icon.ico');
  let icon;
  try {
    icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch (_) {
    icon = nativeImage.createEmpty();
  }
  tray = new Tray(icon);
  tray.setToolTip('Kairos -- Personal AI Assistant');
  rebuildTrayMenu();

  // Single-click: show window
  tray.on('click', () => showWindow());
}

function rebuildTrayMenu() {
  if (!tray) return;
  const contextMenu = Menu.buildFromTemplate([
    { label: '  Open Kairos', click: () => showWindow() },
    {
      label: trayListeningPaused ? '  Resume Voice Listening' : '  Pause Voice Listening',
      click: () => {
        trayListeningPaused = !trayListeningPaused;
        mainWindow && mainWindow.webContents.send(
          trayListeningPaused ? 'tray:pause-listening' : 'tray:resume-listening'
        );
        rebuildTrayMenu();
      },
    },
    { type: 'separator' },
    {
      label: liveWallpaperEnabled ? '  Disable Live Wallpaper' : '  Enable Live Wallpaper',
      enabled: IS_WINDOWS,
      click: async () => {
        await setLiveWallpaperEnabled(!liveWallpaperEnabled);
      },
    },
    { type: 'separator' },
    {
      label: '  Settings',
      click: () => { showWindow(); setTimeout(() => mainWindow && mainWindow.webContents.send('tray:open-settings'), 300); },
    },
    { type: 'separator' },
    {
      label: '  Quit Kairos',
      click: () => { appIsQuitting = true; stopBackend(); app.quit(); },
    },
  ]);
  tray.setContextMenu(contextMenu);
}

// -- Main Window -------------------------------------------------------------
let mainWindow = null;
let wallpaperWindow = null;
let wallpaperWorkerW = null;
let wallpaperPauseTimer = null;
let wallpaperPaused = false;
let wallpaperLocked = false;
let appIsQuitting = false;

function showWindow() {
  if (!mainWindow) { createWindow(); return; }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    transparent: false,
    backgroundColor: '#0d0d12',
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
      allowRunningInsecureContent: false,
    },
  });

  // Grant mic + audio permissions
  session.defaultSession.setPermissionRequestHandler((wc, permission, callback) => {
    callback(['media', 'audioCapture', 'mediaKeySystem', 'geolocation', 'notifications'].includes(permission));
  });
  session.defaultSession.setPermissionCheckHandler((wc, permission) => {
    return ['media', 'audioCapture', 'mediaKeySystem'].includes(permission);
  });

  mainWindow.loadFile(path.join(FRONTEND_DIST, 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('maximize',   () => mainWindow && mainWindow.webContents.send('window:maximized'));
  mainWindow.on('unmaximize', () => mainWindow && mainWindow.webContents.send('window:unmaximized'));

  // Close-to-tray: intercept unless we are actually quitting
  mainWindow.on('close', (event) => {
    if (appIsQuitting) return;
    const settings = loadSettings();
    const closeToTray = settings ? (settings.closeToTray !== false) : true; // default ON
    if (closeToTray && tray) {
      event.preventDefault();
      mainWindow.hide();
      // One-time balloon hint
      if (settings && !settings.shownTrayHint) {
        if (tray.displayBalloon) {
          tray.displayBalloon({ title: 'Kairos', content: 'Still running in the system tray. Right-click to quit.', iconType: 'info' });
        }
        saveSettings({ shownTrayHint: true });
      }
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// -- Live Wallpaper Window ---------------------------------------------------
function createWallpaperWindow() {
  if (!IS_WINDOWS) {
    return Promise.resolve({ ok: false, error: 'Live Wallpaper Mode is only available on Windows.' });
  }
  if (wallpaperWindow && !wallpaperWindow.isDestroyed()) {
    return attachWallpaperWindow();
  }

  const bounds = getPrimaryWallpaperBounds();
  wallpaperWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    transparent: false,
    backgroundColor: '#02040a',
    show: false,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    closable: true,
    focusable: false,
    skipTaskbar: true,
    title: 'Kairos Live Wallpaper',
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
      allowRunningInsecureContent: false,
    },
  });

  wallpaperWindow.setMenuBarVisibility(false);
  wallpaperWindow.loadFile(path.join(FRONTEND_DIST, 'index.html'), {
    query: { wallpaper: '1' },
  });

  wallpaperWindow.on('closed', () => {
    wallpaperWindow = null;
    wallpaperWorkerW = null;
    stopWallpaperPauseMonitor();
  });

  return new Promise((resolve) => {
    wallpaperWindow.once('ready-to-show', async () => {
      wallpaperWindow.setBounds(bounds);
      wallpaperWindow.showInactive();
      const result = await attachWallpaperWindow();
      resolve(result);
    });
  });
}

async function attachWallpaperWindow() {
  if (!wallpaperWindow || wallpaperWindow.isDestroyed()) {
    return { ok: false, error: 'Wallpaper renderer is not available.' };
  }
  const bounds = getPrimaryWallpaperBounds();
  wallpaperWindow.setBounds(bounds);
  const hwnd = getNativeHwndString(wallpaperWindow);
  const result = await runWin32WallpaperAction('Attach', {
    Hwnd: hwnd,
    X: 0,
    Y: 0,
    Width: bounds.width,
    Height: bounds.height,
  });

  if (!result.ok) {
    console.error('[Wallpaper] WorkerW attach failed:', result.error);
    liveWallpaperEnabled = false;
    saveSettings({ liveWallpaperEnabled: false });
    rebuildTrayMenu();
    if (mainWindow) mainWindow.webContents.send('wallpaper:state-changed', getWallpaperState(result.error));
    if (wallpaperWindow && !wallpaperWindow.isDestroyed()) wallpaperWindow.close();
    return result;
  }

  wallpaperWorkerW = result.workerw;
  wallpaperWindow.setIgnoreMouseEvents(true, { forward: true });
  startWallpaperPauseMonitor();
  setWallpaperPaused(false, 'visible');
  return result;
}

async function setLiveWallpaperEnabled(enabled) {
  if (enabled && !IS_WINDOWS) {
    return getWallpaperState('Live Wallpaper Mode is only implemented on Windows.');
  }

  if (enabled) {
    liveWallpaperEnabled = true;
    saveSettings({ liveWallpaperEnabled: true });
    rebuildTrayMenu();
    const result = await createWallpaperWindow();
    if (!result.ok) {
      return getWallpaperState(result.error || 'Failed to attach wallpaper renderer.');
    }
  } else {
    liveWallpaperEnabled = false;
    saveSettings({ liveWallpaperEnabled: false });
    rebuildTrayMenu();
    stopWallpaperPauseMonitor();
    await detachAndCloseWallpaperWindow();
  }

  const state = getWallpaperState();
  if (mainWindow) mainWindow.webContents.send('wallpaper:state-changed', state);
  return state;
}

async function detachAndCloseWallpaperWindow() {
  if (!wallpaperWindow || wallpaperWindow.isDestroyed()) {
    wallpaperWindow = null;
    wallpaperWorkerW = null;
    return;
  }

  try {
    const hwnd = getNativeHwndString(wallpaperWindow);
    await runWin32WallpaperAction('Detach', { Hwnd: hwnd });
  } catch (err) {
    console.warn('[Wallpaper] Detach failed while closing:', err);
  }

  if (wallpaperWindow && !wallpaperWindow.isDestroyed()) {
    wallpaperWindow.close();
  }
  wallpaperWindow = null;
  wallpaperWorkerW = null;
}

function getWallpaperState(error = '') {
  return {
    available: IS_WINDOWS,
    enabled: liveWallpaperEnabled,
    active: !!(wallpaperWindow && !wallpaperWindow.isDestroyed() && wallpaperWorkerW),
    paused: wallpaperPaused,
    pauseReason: wallpaperPaused ? lastWallpaperPauseReason : '',
    primaryMonitorOnly: true,
    error,
  };
}

let lastWallpaperPauseReason = '';

function setWallpaperPaused(paused, reason) {
  wallpaperPaused = !!paused;
  lastWallpaperPauseReason = wallpaperPaused ? reason : '';
  if (wallpaperWindow && !wallpaperWindow.isDestroyed()) {
    wallpaperWindow.webContents.send('wallpaper:set-paused', wallpaperPaused, reason || '');
  }
  if (mainWindow) {
    mainWindow.webContents.send('wallpaper:state-changed', getWallpaperState());
  }
}

function startWallpaperPauseMonitor() {
  stopWallpaperPauseMonitor();
  checkWallpaperPauseState();
  wallpaperPauseTimer = setInterval(checkWallpaperPauseState, WALLPAPER_POLL_MS);
}

function stopWallpaperPauseMonitor() {
  if (wallpaperPauseTimer) {
    clearInterval(wallpaperPauseTimer);
    wallpaperPauseTimer = null;
  }
  setWallpaperPaused(false, '');
}

async function checkWallpaperPauseState() {
  if (!liveWallpaperEnabled || !wallpaperWindow || wallpaperWindow.isDestroyed()) return;

  if (wallpaperLocked) {
    setWallpaperPaused(true, 'screen_locked');
    return;
  }

  try {
    if (powerMonitor.isOnBatteryPower && powerMonitor.isOnBatteryPower()) {
      setWallpaperPaused(true, 'on_battery');
      return;
    }
  } catch (_) {}

  const bounds = getPrimaryWallpaperBounds();
  const result = await runWin32WallpaperAction('DesktopVisible', {
    ScreenX: bounds.x,
    ScreenY: bounds.y,
    ScreenWidth: bounds.width,
    ScreenHeight: bounds.height,
  });

  if (!result.ok) {
    setWallpaperPaused(true, 'visibility_check_failed');
    return;
  }

  setWallpaperPaused(!result.desktopVisible, result.reason || 'desktop_hidden');
}

// -- App lifecycle -----------------------------------------------------------
app.whenReady().then(async () => {
  const settings = loadSettings();
  const isFirstRun = (settings === null);
  liveWallpaperEnabled = !!(settings && settings.liveWallpaperEnabled);

  // Create tray first so app stays alive even if window is hidden
  createTray();

  // Connect to or spawn backend
  const alreadyRunning = await checkBackendRunning(BACKEND_PORT);
  if (alreadyRunning) {
    console.log('[Backend] Already running -- connected!');
  } else {
    startBackend();
    try { await waitForBackend(); } catch (e) { console.error('[Main] Backend start failed:', e.message); }
  }

  // Startup tray notification when launched at login
  try {
    const loginInfo = app.getLoginItemSettings();
    if (loginInfo.wasOpenedAtLogin && Notification.isSupported()) {
      new Notification({
        title: 'Kairos is ready',
        body: 'Running quietly in the system tray. Click the icon to open.',
        icon: path.join(__dirname, 'assets', 'icon.ico'),
      }).show();
    }
  } catch (_) {}

  createWindow();

  if (liveWallpaperEnabled && IS_WINDOWS) {
    createWallpaperWindow().then((result) => {
      if (!result.ok) {
        console.error('[Wallpaper] Restore-on-start failed:', result.error);
      }
    });
  }

  // First-run: emit event to renderer after it loads
  if (isFirstRun) {
    // Initialize default settings
    saveSettings({ closeToTray: true, shownTrayHint: false, liveWallpaperEnabled: false });
    const sendFirstRun = () => {
      setTimeout(() => {
        if (mainWindow) mainWindow.webContents.send('app:first-run');
      }, 2000);
    };
    if (mainWindow) {
      mainWindow.webContents.once('did-finish-load', sendFirstRun);
    }
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });

  powerMonitor.on('lock-screen', () => {
    wallpaperLocked = true;
    setWallpaperPaused(true, 'screen_locked');
  });
  powerMonitor.on('unlock-screen', () => {
    wallpaperLocked = false;
    checkWallpaperPauseState();
  });
  powerMonitor.on('on-battery', () => {
    setWallpaperPaused(true, 'on_battery');
  });
  powerMonitor.on('on-ac', () => {
    checkWallpaperPauseState();
  });
});

app.on('before-quit', () => {
  appIsQuitting = true;
  stopWallpaperPauseMonitor();
  stopBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    const settings = loadSettings();
    const closeToTray = settings ? (settings.closeToTray !== false) : true;
    if (!closeToTray || !tray) {
      stopBackend();
      app.quit();
    }
    // If close-to-tray is on, app stays alive in the tray -- do NOT quit here.
  }
});

// -- IPC: Window controls ---------------------------------------------------
ipcMain.on('window:minimize', () => mainWindow && mainWindow.minimize());
ipcMain.on('window:maximize', () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on('window:close', () => mainWindow && mainWindow.close());
ipcMain.handle('window:is-maximized', () => (mainWindow ? mainWindow.isMaximized() : false));

// -- IPC: Auto-start on login -----------------------------------------------
ipcMain.handle('app:set-login-item', (_, enabled) => {
  app.setLoginItemSettings({ openAtLogin: !!enabled, openAsHidden: true });
  return { ok: true, openAtLogin: !!enabled };
});

ipcMain.handle('app:get-login-item', () => {
  try { return app.getLoginItemSettings().openAtLogin; } catch (_) { return false; }
});

// -- IPC: Close-to-tray setting ---------------------------------------------
ipcMain.handle('app:set-close-to-tray', (_, enabled) => {
  saveSettings({ closeToTray: !!enabled });
  return { ok: true, closeToTray: !!enabled };
});

ipcMain.handle('app:get-close-to-tray', () => {
  const s = loadSettings();
  return s ? (s.closeToTray !== false) : true;
});

// -- IPC: Live Wallpaper Mode ------------------------------------------------
ipcMain.handle('wallpaper:set-enabled', async (_, enabled) => {
  return setLiveWallpaperEnabled(!!enabled);
});

ipcMain.handle('wallpaper:get-state', () => getWallpaperState());

ipcMain.handle('wallpaper:get-paused', () => ({
  paused: wallpaperPaused,
  reason: lastWallpaperPauseReason,
}));

// -- IPC: Quit / pause relay ------------------------------------------------
ipcMain.on('app:quit', () => { appIsQuitting = true; stopWallpaperPauseMonitor(); stopBackend(); app.quit(); });
ipcMain.on('tray:pause-listening',  () => { trayListeningPaused = true;  rebuildTrayMenu(); });
ipcMain.on('tray:resume-listening', () => { trayListeningPaused = false; rebuildTrayMenu(); });

// -- IPC: OS-level tools ----------------------------------------------------
ipcMain.handle('os:run-command', async (event, { command, args = [], options = {} }) => {
  return new Promise((resolve) => {
    const proc = spawn(command, args, { shell: true, windowsHide: false, ...options });
    let stdout = '', stderr = '';
    proc.stdout && proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.stderr && proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ code, stdout, stderr }));
    proc.on('error', (err) => resolve({ code: -1, stdout: '', stderr: err.message }));
  });
});

ipcMain.handle('os:open-external',  async (_, url) => { await shell.openExternal(url); return { ok: true }; });
ipcMain.handle('os:show-in-folder', async (_, fp)  => { shell.showItemInFolder(fp); return { ok: true }; });

ipcMain.handle('os:write-file', async (_, { filename, content }) => {
  try {
    const dir = path.join(app.getPath('userData'), 'workspace');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const fp = path.join(dir, path.basename(filename));
    fs.writeFileSync(fp, content, 'utf8');
    return { ok: true, path: fp };
  } catch (e) { return { ok: false, error: e.message }; }
});

// -- IPC: Agentic tool bridge -----------------------------------------------
ipcMain.handle('os:execute-tool', async (_, { toolName, params = {} }) => {
  console.log('[AgenticTool] Executing tool:', toolName, params);
  try {
    switch (toolName) {
      case 'open_app': {
        const appName = (params.app_name || '').toLowerCase().trim();
        const bravePath = getBravePath();
        if (appName === 'brave' || appName === 'brave browser') {
          exec('"' + bravePath + '"', { shell: true }, (err) => { if (err) shell.openExternal('https://brave.com'); });
          return { ok: true, tool: 'open_app', app: params.app_name };
        }
        let cmd;
        if (process.platform === 'win32') {
          const appMap = { spotify:'start spotify:', chrome:'start chrome', notepad:'notepad', calc:'calc',
            calculator:'calc', code:'code', vscode:'code', discord:'start discord:',
            terminal:'start wt || start cmd', cmd:'start cmd', vlc:'start vlc', explorer:'explorer' };
          cmd = appMap[appName] || 'start "" "' + params.app_name + '"';
        } else if (process.platform === 'darwin') {
          cmd = 'open -a "' + params.app_name + '"';
        } else {
          cmd = 'xdg-open "' + params.app_name + '" || "' + params.app_name + '"';
        }
        return new Promise((resolve) => {
          exec(cmd, { shell: true }, (err) => {
            if (err) exec('"' + params.app_name + '"', { shell: true }, (e2) => resolve({ ok: !e2, tool: 'open_app', app: params.app_name, error: e2 && e2.message }));
            else resolve({ ok: true, tool: 'open_app', app: params.app_name });
          });
        });
      }
      case 'open_youtube_in_brave':
      case 'youtube_search':
      case 'search_and_play_youtube': {
        const q = params.query || '';
        const ytUrl = q ? 'https://www.youtube.com/results?search_query=' + encodeURIComponent(q) : 'https://www.youtube.com';
        exec('"' + getBravePath() + '" "' + ytUrl + '"', { shell: true }, (err) => { if (err) shell.openExternal(ytUrl); });
        return { ok: true, tool: toolName, query: q, url: ytUrl };
      }
      case 'open_notepad_and_write_code': {
        const fn = params.filename || 'code.py';
        const dir = path.join(app.getPath('userData'), 'workspace');
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const fp = path.join(dir, path.basename(fn));
        fs.writeFileSync(fp, params.code || '', 'utf8');
        exec((process.platform === 'win32' ? 'notepad.exe' : process.platform === 'darwin' ? 'open -e' : 'xdg-open') + ' "' + fp + '"', { shell: true });
        return { ok: true, tool: 'open_notepad_and_write_code', filename: fn, filePath: fp };
      }
      case 'open_vscode_and_write_code': {
        const fn = path.basename(params.filename || 'script.py');
        const dir = path.join(app.getPath('userData'), 'workspace');
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const fp = path.join(dir, fn);
        fs.writeFileSync(fp, params.code || '', 'utf8');
        exec('code "' + fp + '"', { shell: true }, (err) => { if (err) shell.openPath(fp); });
        return { ok: true, tool: 'open_vscode_and_write_code', filename: fn, filePath: fp };
      }
      case 'check_whatsapp_notifications': {
        await shell.openExternal('https://web.whatsapp.com');
        return { ok: true, tool: 'check_whatsapp_notifications', url: 'https://web.whatsapp.com' };
      }
      default:
        return { ok: true, tool: toolName };
    }
  } catch (err) {
    console.error('[AgenticTool] Error for ' + toolName + ':', err);
    return { ok: false, error: err.message };
  }
});

// Backend status query
ipcMain.handle('backend:status', () => ({ running: backendProcess !== null, port: BACKEND_PORT, url: BACKEND_URL }));
