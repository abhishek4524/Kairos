# Auto-Start & System Tray Integration QA Checklist & Platform Notes

This document provides a manual QA validation checklist for verifying the Windows auto-start and system tray features, followed by notes on how to implement equivalent auto-start mechanisms on macOS and Linux.

---

## Part 1: Windows Manual QA Checklist

Since OS-level startup items and system tray interactions cannot be easily tested in standard unit tests, use the following manual checklist to verify correct behavior:

- [ ] **1. First-Run Preference Prompt**
  - Delete `kairos-settings.json` from `%APPDATA%\Kairos` to simulate a clean install.
  - Run the application.
  - Verify that the glassmorphic modal "Welcome to Kairos - Start automatically on login?" appears.
  - Click **"No thanks"** and check that `kairos-settings.json` is created with `"closeToTray": true`.
  - Re-simulate, click **"Yes, start on login"**, and check that the registry startup entry is added.

- [ ] **2. Windows Registry Validation**
  - Open `regedit` or run `reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
  - Verify that a `Kairos` key exists pointing to the path of the Kairos executable.

- [ ] **3. Settings Toggle Sync (Auto-Start)**
  - Open Settings Modal → **Desktop App** tab.
  - Toggle **"Start on Login"** to OFF and click **Save Desktop Settings**.
  - Verify the `reg query` output again; the `Kairos` key should now be removed.
  - Toggle it back to ON, save, and verify it is re-added.

- [ ] **4. Settings Toggle Sync (Close Behavior)**
  - Open Settings Modal → **Desktop App** tab.
  - Toggle **"Minimize to System Tray"** to ON and click **Save**.
  - Click the window's close button (X).
  - Verify the window hides, but the application does not quit (verify the icon remains in the system tray and the python backend is still running in the Task Manager).

- [ ] **5. System Tray Balloon Alert**
  - Verify that a one-time balloon tip/notification is shown in the tray explaining that Kairos is running in the background when first minimizing to tray.

- [ ] **6. Tray Context Menu Actions**
  - Right-click the Kairos tray icon.
  - Click **"Pause Voice Listening"**; check that the UI voice indicator changes state to paused/disabled.
  - Click **"Resume Voice Listening"**; check that the UI voice indicator switches back to listening.
  - Click **"Settings"**; check that the settings modal is shown.
  - Click **"Open Kairos"**; check that the window restores and focuses.

- [ ] **7. Explicit Quit**
  - Right-click the tray icon and click **"Quit Kairos"**.
  - Verify that all windows close, the system tray icon disappears, and both the Electron process and the python backend process (Task Manager) terminate cleanly.

- [ ] **8. Reboot Integration Test**
  - Turn **"Start on Login"** to ON in settings.
  - Restart the PC.
  - Verify that the PC boots, no command terminal windows show up, the tray icon appears, and a Windows notification toast appears saying: *"Kairos is ready — Running quietly in the system tray. Click the icon to open."*

---

## Part 2: macOS & Linux Autostart Mechanisms

While Windows uses Electron's native `app.setLoginItemSettings()` API (which writes to the registry), the production build architecture is portable to other platforms. Below are the equivalent autostart configurations.

### macOS (LaunchAgent plist)

To auto-start Kairos on macOS, create a plist file under `~/Library/LaunchAgents/com.abhishek.kairos.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.abhishek.kairos</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Kairos.app/Contents/MacOS/Kairos</string>
        <string>--hidden</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

Enable it using `launchctl`:
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.abhishek.kairos.plist
```

### Linux (.desktop file or systemd user service)

#### Option A: Autostart Desktop Entry
Create a file at `~/.config/autostart/kairos.desktop`:

```ini
[Desktop Entry]
Type=Application
Version=1.0
Name=Kairos
Comment=Kairos Personal AI Assistant
Exec=/usr/bin/kairos --hidden
Icon=kairos
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
```

#### Option B: systemd User Service
Create a file at `~/.config/systemd/user/kairos.service`:

```ini
[Unit]
Description=Kairos AI Assistant Service
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/kairos --hidden
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable it using:
```bash
systemd --user enable kairos.service
```
