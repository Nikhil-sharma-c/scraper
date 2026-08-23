// Scrape-Verse desktop shell (Electron)
// Boots the Python API server, then shows the GUI in a native window.
"use strict";
const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const PORT = process.env.SV_PORT || 8765;
const ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, "..");
let pyProc = null;
let win = null;

function startServer() {
  const python = process.platform === "win32" ? "python" : "python3";
  // -u = unbuffered so early crashes surface in our error handling
  pyProc = spawn(python, ["-m", "scrape_verse.server"], {
    cwd: ROOT,
    env: { ...process.env, SV_PORT: String(PORT), PYTHONUNBUFFERED: "1" },
    windowsHide: true,
  });
  pyProc.stdout.on("data", d => console.log(`[server] ${d}`.trimEnd()));
  pyProc.stderr.on("data", d => console.error(`[server] ${d}`.trimEnd()));
  pyProc.on("exit", code => {
    if (code && code !== 0) console.error(`[server] exited with code ${code}`);
  });
}

function waitFor(url, tries = 60, delayMs = 500) {
  return new Promise((resolve, reject) => {
    const attempt = n => {
      const req = http.get(url, res => { res.resume(); resolve(); });
      req.on("error", () => {
        if (n <= 0) return reject(new Error("server did not come up"));
        setTimeout(() => attempt(n - 1), delayMs);
      });
    };
    attempt(tries);
  });
}

async function createWindow() {
  startServer();
  try {
    await waitFor(`http://127.0.0.1:${PORT}/api/targets`);
  } catch (err) {
    console.error(err.message);
    return app.quit();
  }

  win = new BrowserWindow({
    width: 1280,
    height: 860,
    backgroundColor: "#0b1020",
    title: "Scrape-Verse",
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true },
  });

  win.loadURL(`http://127.0.0.1:${PORT}/`);
  // open external links in the real browser
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(`http://127.0.0.1:${PORT}`)) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  win.on("closed", () => { win = null; });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (pyProc) { try { pyProc.kill(); } catch (_) {} }
  if (process.platform !== "darwin") app.quit();
});
app.on("before-quit", () => { if (pyProc) { try { pyProc.kill(); } catch (_) {} } });
app.on("activate", () => { if (!win) createWindow(); });
