// Serapi Electron host — migration skeleton (step 1).
// Two WebContentsViews: local workspace UI + memoQ engine page.
// The engine View is only attached when requested; later steps load the real
// memoQ URL and inject the existing bridge.

const { app, BrowserWindow, BrowserView, ipcMain, session } = require('electron');
const { buildBundle } = require('./bridge-inject');
const { SidecarClient } = require('./sidecar-client');
const ENGINE_API = require('./engine-api-allowlist.json').methods;
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
let sidecar = null;
let sidecarReady = false;

const PRELOAD = path.join(__dirname, 'preload.js');
const WORKSPACE_ENTRY = path.join(__dirname, 'workspace', 'index.html');
const ENGINE_ENTRY = path.join(__dirname, 'engine', 'placeholder.html');
const ENGINE_FIXTURE = path.join(__dirname, 'engine', 'fixture.html');
const ENGINE_FIXTURE_API = path.join(__dirname, 'engine', 'fixture-api.html');
const APP_DIR = path.join(__dirname, '..', 'app');
const ENGINE_URL = String(process.env.SERAPI_ENGINE_URL || '').trim();
const ENGINE_FIXTURE_MODE = process.env.SERAPI_ENGINE_FIXTURE === '1';
const ENGINE_FIXTURE_API_MODE = process.env.SERAPI_ENGINE_FIXTURE_API === '1';
const ENGINE_SHOW_ON_START = process.env.SERAPI_ENGINE_SHOW === '1';
const ENGINE_API_ALLOWED = new Set(ENGINE_API);

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
  if (process.env.SERAPI_DEBUG === '1') {
    workspace.webContents.on('console-message', (_event, level, message, line, source) => {
      console.log('[workspace console]', level, String(message).slice(0, 300), line || '', source || '');
    });
  }
  workspace.webContents.loadFile(WORKSPACE_ENTRY,
    process.env.SERAPI_WORKSPACE_ONLY === '1' ? { query: { workspace: '1' } } : undefined);
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
    engine.webContents.loadFile(ENGINE_FIXTURE_API_MODE ? ENGINE_FIXTURE_API : (ENGINE_FIXTURE_MODE ? ENGINE_FIXTURE : ENGINE_ENTRY));
  }
  engine.webContents.on('dom-ready', () => injectBridge());
  if (ENGINE_FIXTURE_API_MODE) {
    // The synthetic Engine fixture does not run the bridge bundle, but QA needs
    // the same pure lint.js engine as the real page.
    engine.webContents.executeJavaScript(
      fs.readFileSync(path.join(APP_DIR, 'lint.js'), 'utf8'), true
    ).catch((err) => console.error('[serapi] fixture lint injection failed:', err));
  }
  engine.webContents.on('before-input-event', (event, input) => {
    if (input.type === 'keyDown' && input.control && input.shift
        && String(input.key || '').toLowerCase() === 'w') {
      event.preventDefault();
      setEngineVisible(false);
    }
  });
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
    let safeOrigin = '';
    try { safeOrigin = new URL(url).origin; } catch (_e) { safeOrigin = 'unknown-origin'; }
    console.log('[serapi] engine bridge injected:', safeOrigin);
    const smokeApi = process.env.SERAPI_ENGINE_INVOKE;
    if (smokeApi) {
      const result = await invokeEngineApi(smokeApi, []);
      console.log('[serapi] engine invoke', smokeApi, JSON.stringify(result).slice(0, 300));
    }
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
    if (!captureEngine && process.env.SERAPI_CAPTURE_WRITE === '1') {
      try {
        const result = await workspace.webContents.executeJavaScript(`(async () => {
          const el = document.querySelector('#codePane .target-text');
          if (!el) return { ok: false, error: 'no-target' };
          el.textContent = el.textContent + 'X';
          el.dispatchEvent(new Event('input', { bubbles: true }));
          await saveCurrentSegment(false);
          return { ok: true };
        })()`, true);
        console.log('[serapi] capture write:', JSON.stringify(result));
        await new Promise((resolve) => setTimeout(resolve, 700));
      } catch (err) {
        console.error('[serapi] capture write failed:', err);
      }
    }
    if (!captureEngine && process.env.SERAPI_CAPTURE_SELECT === '1') {
      try {
        await workspace.webContents.executeJavaScript(`(() => {
          const el = document.querySelector('#codePane .source-text');
          if (!el || !el.firstChild) return '';
          const range = document.createRange();
          range.setStart(el.firstChild, 0);
          range.setEnd(el.firstChild, Math.min(3, el.firstChild.textContent.length));
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          document.dispatchEvent(new Event('selectionchange'));
          return selection.toString();
        })()`, true);
        await new Promise((resolve) => setTimeout(resolve, 800));
      } catch (err) {
        console.error('[serapi] capture selection failed:', err);
      }
    }
    const image = await targetView.webContents.capturePage();
    fs.writeFileSync(targetPath, image.toPNG());
    console.log('[serapi] capture:', targetPath, image.getSize());
  } catch (err) {
    console.error('[serapi] capture failed:', err);
  } finally {
    app.quit();
  }
}


function startSidecar() {
  const python = process.env.SERAPI_PYTHON
    || path.join(__dirname, '..', '.venv314', 'Scripts', 'python.exe');
  if (!fs.existsSync(python)) {
    console.error('[serapi] sidecar python not found:', python);
    return;
  }
  sidecar = new SidecarClient({
    python,
    script: path.join(__dirname, 'sidecar.py'),
    cwd: path.join(__dirname, '..'),
    onLog: (line) => console.log(line),
  });
  sidecar.start();
  sidecar.call('ping', {}, 5000)
    .then((result) => {
      sidecarReady = true;
      console.log('[serapi] sidecar ping:', JSON.stringify(result));
      if (process.env.SERAPI_SIDECAR_SMOKE === '1') {
        sidecar.call('version', {}, 5000).then((v) => {
          console.log('[serapi] sidecar version:', JSON.stringify(v));
        }).catch((err) => console.error('[serapi] sidecar version failed:', err));
      }
    })
    .catch((err) => {
      sidecarReady = false;
      console.error('[serapi] sidecar ping failed:', err.message);
    });
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
    if (workspace && !workspace.webContents.isDestroyed()) {
      workspace.webContents.send('engine:event', parsed);
    }
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
async function invokeEngineLint(payload) {
  if (!engine) return { ok: false, error: 'engine-not-ready' };
  let safe;
  try { safe = JSON.parse(JSON.stringify(payload || {})); } catch (_e) { return { ok: false, error: 'bad-payload' }; }
  if (JSON.stringify(safe).length > 1_500_000) return { ok: false, error: 'payload-too-large' };
  const expr = `(function () {
    try {
      if (!window.__mdLint || typeof window.__mdLint.analyze !== 'function') {
        return { ok: false, error: 'missing-lint' };
      }
      return window.__mdLint.analyze(${JSON.stringify(safe)});
    } catch (e) {
      return { ok: false, error: String(e && e.message || e) };
    }
  })()`;
  try {
    const result = await engine.webContents.executeJavaScript(expr, true);
    return { ok: true, result };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}
async function invokeEngineApi(name, args) {
  const method = String(name || '');
  if (!ENGINE_API_ALLOWED.has(method)) return { ok: false, error: 'method-not-allowed' };
  if (!engine) return { ok: false, error: 'engine-not-ready' };
  let argv = Array.isArray(args) ? args : [];
  try { argv = JSON.parse(JSON.stringify(argv)); } catch (_e) { return { ok: false, error: 'bad-args' }; }
  const expr = `(async () => {
    const api = window.__md && window.__md.api;
    const fn = api && api[${JSON.stringify(method)}];
    if (typeof fn !== 'function') return { ok: false, error: 'missing-api' };
    try { return { ok: true, value: await fn(...${JSON.stringify(argv)}) }; }
    catch (e) { return { ok: false, error: String(e && e.message || e) }; }
  })()`;
  try {
    const result = await engine.webContents.executeJavaScript(expr, true);
    return result || { ok: false, error: 'empty-result' };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}
ipcMain.handle('engine:api', async (_event, name, args) => {
  const result = await invokeEngineApi(name, args);
  if (process.env.SERAPI_DEBUG === '1') {
    console.log('[serapi] engine api', String(name || ''), result && result.ok ? 'ok' : 'fail',
      result && result.error ? result.error : '');
  }
  return result;
});
ipcMain.handle('engine:lint', (_event, payload) => invokeEngineLint(payload));
ipcMain.handle('sidecar:call', async (_event, method, params) => {
  const name = String(method || '');
  if (!sidecar) return { ok: false, error: 'sidecar-not-started' };
  try {
    const result = await sidecar.call(name, params || {});
    if (process.env.SERAPI_DEBUG === '1') console.log('[serapi] sidecar call', name, result && result.ok === false ? 'fail' : 'ok');
    return { ok: true, result };
  } catch (err) {
    if (process.env.SERAPI_DEBUG === '1') console.log('[serapi] sidecar call', name, 'error', String(err.message || err));
    return { ok: false, error: String(err.message || err) };
  }
});
ipcMain.handle('host:info', () => ({
  mode: 'electron-migration',
  version: app.getVersion(),
  engineVisible,
  engineUrl: engine ? engine.webContents.getURL() : '',
  lastEngineEvent,
  sidecarReady,
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
  startSidecar();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('before-quit', () => {
  if (sidecar) sidecar.close();
});
