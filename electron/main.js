// Serapi Electron host — migration skeleton (step 1).
// Two WebContentsViews: local workspace UI + memoQ engine page.
// The engine View is only attached when requested; later steps load the real
// memoQ URL and inject the existing bridge.

const { app, BrowserWindow, BrowserView, ipcMain, session } = require('electron');
const { buildBundle } = require('./bridge-inject');
const path = require('node:path');
const fs = require('node:fs');

// The profile must live under LocalAppData. On this machine the roaming
// AppData profile cannot be used by Chromium's network sandbox (access denied),
// which crashed the host before the window appeared.
app.setPath('userData', path.join(process.env.LOCALAPPDATA || path.join(__dirname, '.profile'), 'Serapi'));
app.commandLine.appendSwitch('disable-features', 'NetworkServiceSandbox,CalculateNativeWinOcclusion');
app.disableHardwareAcceleration();

let win = null;
let workspace = null;
let engine = null;
let engineVisible = false;
let engineInjected = false;
let bridgeBundle = null;
let lastEngineEvent = null;

const PRELOAD = path.join(__dirname, 'preload.js');
const WORKSPACE_ENTRY = path.join(__dirname, 'workspace', 'index.html');
const ENGINE_ENTRY = path.join(__dirname, 'engine', 'placeholder.html');
const ENGINE_FIXTURE = path.join(__dirname, 'engine', 'fixture.html');
const APP_DIR = path.join(__dirname, '..', 'app');
const ENGINE_URL = String(process.env.SERAPI_ENGINE_URL || '').trim();
const ENGINE_FIXTURE_MODE = process.env.SERAPI_ENGINE_FIXTURE === '1';
const ENGINE_SHOW_ON_START = process.env.SERAPI_ENGINE_SHOW === '1';

function viewBounds() {
  const [width, height] = win.getContentSize();
  return { x: 0, y: 0, width, height };
}

function resizeViews() {
  if (!win || win.isDestroyed()) return;
  const bounds = viewBounds();
  if (workspace) workspace.setBounds(bounds);
  if (engine) engine.setBounds(engineVisible ? bounds : { x: -10000, y: -10000, width: 1, height: 1 });
}

function createViews() {
  workspace = new BrowserView({
    webPreferences: {
      preload: PRELOAD,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      partition: 'persist:serapi',
    },
  });
  workspace.webContents.loadFile(WORKSPACE_ENTRY);
  win.addBrowserView(workspace);

  engine = new BrowserView({
    webPreferences: {
      preload: path.join(__dirname, 'engine-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      partition: 'persist:serapi',
    },
  });
  if (ENGINE_URL) {
    engine.webContents.loadURL(ENGINE_URL);
  } else {
    engine.webContents.loadFile(ENGINE_FIXTURE_MODE ? ENGINE_FIXTURE : ENGINE_ENTRY);
  }
  engine.webContents.on('dom-ready', () => injectBridge());
  engine.webContents.on('did-start-navigation', () => { engineInjected = false; });
  // Do not attach the engine view until needed; keeps it out of the workspace.
  resizeViews();
}


function shouldInject(url) {
  if (ENGINE_FIXTURE_MODE && url.startsWith('file:')) return true;
  return /^https?:\/\//.test(url);
}

async function injectBridge() {
  if (!engine || engineInjected) return;
  const url = engine.webContents.getURL();
  if (!shouldInject(url)) return;
  engineInjected = true;
  try {
    if (!bridgeBundle) bridgeBundle = buildBundle(APP_DIR);
    await engine.webContents.executeJavaScript(bridgeBundle, true);
    console.log('[serapi] engine bridge injected:', url.replace(/\?.*$/, ''));
  } catch (err) {
    engineInjected = false;
    console.error('[serapi] engine bridge injection failed:', err);
  }
}

function setEngineVisible(visible) {
  if (!win || win.isDestroyed() || !engine) return;
  visible = Boolean(visible);
  if (visible === engineVisible) return;
  engineVisible = visible;
  if (visible) {
    win.addBrowserView(engine);
    engine.setBounds(viewBounds());
    engine.webContents.focus();
  } else {
    engine.setBounds({ x: -10000, y: -10000, width: 1, height: 1 });
    win.removeBrowserView(engine);
    workspace.webContents.focus();
  }
}

async function captureAndQuit(target) {
  try {
    const captureEngine = process.env.SERAPI_CAPTURE_ENGINE;
    const targetView = captureEngine ? engine : workspace;
    const targetPath = captureEngine ? captureEngine : target;
    if (targetView.webContents.isLoading()) {
      await new Promise((resolve) => targetView.webContents.once('did-finish-load', resolve));
    }
    await new Promise((resolve) => setTimeout(resolve, 900));
    const image = await targetView.webContents.capturePage();
    fs.writeFileSync(targetPath, image.toPNG());
    console.log('[serapi] capture:', targetPath, image.getSize());
  } catch (err) {
    console.error('[serapi] capture failed:', err);
  } finally {
    app.quit();
  }
}

function createWindow() {
  win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    backgroundColor: '#e9e3d8',
    title: 'Serapi',
    autoHideMenuBar: true,
  });
  win.setMenuBarVisibility(false);
  createViews();
  if (ENGINE_SHOW_ON_START) setEngineVisible(true);
  win.on('resize', resizeViews);
  win.webContents.on('did-finish-load', () => {});
  win.once('ready-to-show', () => {
    win.show();
    const target = process.env.SERAPI_CAPTURE;
    if (target) captureAndQuit(path.resolve(target));
  });
  // The workspace is shown first; the engine view remains detached until login.
  workspace.webContents.once('did-finish-load', () => {
    if (!win.isVisible()) win.show();
  });
}

ipcMain.handle('engine:show', () => { setEngineVisible(true); return true; });
ipcMain.on('engine:bridge', (_event, payload) => {
  try {
    const parsed = JSON.parse(String(payload));
    lastEngineEvent = { type: parsed.type || '', time: Date.now() };
    console.log('[serapi] engine event:', lastEngineEvent.type);
  } catch (_err) {
    console.error('[serapi] invalid engine bridge payload');
  }
});
ipcMain.handle('engine:hide', () => { setEngineVisible(false); return true; });
ipcMain.handle('engine:load', (_event, rawUrl) => {
  const url = String(rawUrl || '').trim();
  let parsed;
  try { parsed = new URL(url); } catch (_e) { return { ok: false, error: 'invalid-url' }; }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { ok: false, error: 'http-only' };
  }
  if (parsed.username || parsed.password) return { ok: false, error: 'credentials-in-url' };
  engine.webContents.loadURL(url);
  setEngineVisible(true);
  return { ok: true, url };
});
ipcMain.handle('host:info', () => ({
  mode: 'electron-migration',
  version: app.getVersion(),
  engineVisible,
  engineUrl: engine ? engine.webContents.getURL() : '',
  lastEngineEvent,
}));
ipcMain.handle('host:capture', async (_event, target) => {
  if (!target) return false;
  const image = await win.capturePage();
  fs.writeFileSync(target, image.toPNG());
  return true;
});

app.whenReady().then(() => {
  // A dedicated, persisted profile is the Electron equivalent of the
  // QWebEngineProfile used by the current PyQt app. It will be shared by the
  // workspace and the memoQ engine View.
  const profile = session.fromPartition('persist:serapi');
  profile.setUserAgent(
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
  );
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
