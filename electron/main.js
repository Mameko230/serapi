// Serapi Electron host — migration skeleton (step 1).
// Two WebContentsViews: local workspace UI + memoQ engine page.
// The engine View is only attached when requested; later steps load the real
// memoQ URL and inject the existing bridge.

const { app, BrowserWindow, BrowserView, ipcMain, session } = require('electron');
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

const PRELOAD = path.join(__dirname, 'preload.js');
const WORKSPACE_ENTRY = path.join(__dirname, 'workspace', 'index.html');
const ENGINE_ENTRY = path.join(__dirname, 'engine', 'placeholder.html');

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
  engine.webContents.loadFile(ENGINE_ENTRY);
  // Do not attach the engine view until needed; keeps it out of the workspace.
  resizeViews();
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
    if (workspace.webContents.isLoading()) {
      await new Promise((resolve) => workspace.webContents.once('did-finish-load', resolve));
    }
    await new Promise((resolve) => setTimeout(resolve, 900));
    const image = await workspace.webContents.capturePage();
    fs.writeFileSync(target, image.toPNG());
    console.log('[serapi] capture:', target, image.getSize());
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
ipcMain.handle('engine:hide', () => { setEngineVisible(false); return true; });
ipcMain.handle('host:info', () => ({
  mode: 'electron-migration',
  version: app.getVersion(),
  engineVisible,
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
