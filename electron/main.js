// Serapi Electron host — migration skeleton (step 1).
// Two WebContentsViews: local workspace UI + memoQ engine page.
// The engine View is only attached when requested; later steps load the real
// memoQ URL and inject the existing bridge.

const { app, BrowserWindow, BrowserView, ipcMain, session, Tray, Menu, nativeImage, globalShortcut } = require('electron');
const { buildBundle } = require('./bridge-inject');
const { SidecarClient } = require('./sidecar-client');
const {
  getUserDataPath,
  getFallbackLockPath,
  getPackagedSidecarPath,
  resolveDevelopmentPython,
  isExecutablePath,
} = require('./platform-paths');
const ENGINE_API = require('./engine-api-allowlist.json').methods;
const path = require('node:path');
const fs = require('node:fs');

// Keep the Chromium profile in the platform's user-data area. Windows uses
// LocalAppData; macOS/Linux use Electron's normal per-user application-data path.
const USER_DATA_PATH = getUserDataPath({
  platform: process.platform,
  env: process.env,
  appDataPath: app.getPath('appData'),
  appDir: __dirname,
});
app.setPath('userData', USER_DATA_PATH);
if (process.platform === 'win32') {
  app.commandLine.appendSwitch('disable-features', 'NetworkServiceSandbox,CalculateNativeWinOcclusion');
  app.disableHardwareAcceleration();
}

let win = null;
let workspace = null;
let engine = null;
let engineVisible = false;
let engineInjected = false;
let bridgeBundle = null;
let lastEngineEvent = null;
let engineBridgeReady = false;
let engineLastLoadOk = false;
let sidecar = null;
let sidecarReady = false;
let tray = null;
let isQuitting = false;
const SINGLE_INSTANCE_DISABLED = process.env.SERAPI_DISABLE_SINGLE_INSTANCE === '1';
const FALLBACK_LOCK = getFallbackLockPath(USER_DATA_PATH);
let fallbackLocked = false;

function acquireFallbackLock() {
  try {
    fs.mkdirSync(path.dirname(FALLBACK_LOCK), { recursive: true });
    fs.writeFileSync(FALLBACK_LOCK, String(process.pid), { encoding: 'utf8', flag: 'wx' });
    fallbackLocked = true;
    return true;
  } catch (err) {
    if (err && err.code === 'EEXIST') {
      try {
        const pid = Number(String(fs.readFileSync(FALLBACK_LOCK, 'utf8')).trim());
        if (pid && pid !== process.pid) {
          process.kill(pid, 0);
          return false;
        }
      } catch (_) {}
      try { fs.unlinkSync(FALLBACK_LOCK); } catch (_) {}
      try {
        fs.writeFileSync(FALLBACK_LOCK, String(process.pid), { encoding: 'utf8', flag: 'wx' });
        fallbackLocked = true;
        return true;
      } catch (_) {}
    }
    return false;
  }
}

let gotSingleInstanceLock = SINGLE_INSTANCE_DISABLED ? true : app.requestSingleInstanceLock();
if (!gotSingleInstanceLock && !SINGLE_INSTANCE_DISABLED) {
  // Some Windows profiles deny Chromium's singleton lock file. Fall back to a
  // plain PID lock so startup still works; second-instance focus is degraded.
  gotSingleInstanceLock = acquireFallbackLock();
  if (gotSingleInstanceLock) {
    console.log('[serapi] single-instance: fallback PID lock');
  } else {
    console.error('[serapi] single-instance lock unavailable; continuing without it');
    gotSingleInstanceLock = process.env.SERAPI_STRICT_SINGLE_INSTANCE !== '1';
  }
}
if (!gotSingleInstanceLock) app.quit();

const PRELOAD = path.join(__dirname, 'preload.js');
const WORKSPACE_ENTRY = path.join(__dirname, 'workspace', 'index.html');
const ENGINE_ENTRY = path.join(__dirname, 'engine', 'placeholder.html');
const ENGINE_FIXTURE = path.join(__dirname, 'engine', 'fixture.html');
const ENGINE_FIXTURE_API = path.join(__dirname, 'engine', 'fixture-api.html');
const APP_DIR = app.isPackaged ? path.join(process.resourcesPath, 'app') : path.join(__dirname, '..', 'app');
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
  engine.webContents.on('did-finish-load', () => { engineLastLoadOk = true; maybeFinishSmoke(); });
  engine.webContents.on('did-fail-load', (_e, code, desc) => {
    engineLastLoadOk = false;
    console.error('[serapi] engine load failed:', code, String(desc || '').slice(0, 80));
  });
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
  engine.webContents.on('did-start-navigation', () => { engineInjected = false; engineBridgeReady = false; });
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
    console.log('[serapi] engine bridge injected');
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
    if (!captureEngine && process.env.SERAPI_CAPTURE_SETTINGS === '1') {
      try {
        await workspace.webContents.executeJavaScript(
          "document.querySelector('[data-action=\"设置\"]')?.click(); true", true);
        await new Promise((resolve) => setTimeout(resolve, 350));
      } catch (err) {
        console.error('[serapi] capture settings failed:', err);
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



function maybeFinishSmoke() {
  if (process.env.SERAPI_ENGINE_SMOKE !== '1') return;
  if (!engineLastLoadOk || !engineBridgeReady) return;
  if (global.__serapiSmokeDone) return;
  global.__serapiSmokeDone = true;
  console.log('[serapi] ENGINE_SMOKE: ready (login page loaded, bridge injected)');
  if (process.env.SERAPI_SMOKE_EXIT === '1') {
    setTimeout(() => app.quit(), 800);
  }
}

function startSidecar() {
  if (app.isPackaged) {
    const executable = getPackagedSidecarPath(process.resourcesPath, process.platform);
    if (!fs.existsSync(executable)) {
      console.error('[serapi] packaged sidecar not found:', executable);
      return;
    }
    sidecar = new SidecarClient({
      python: executable,
      args: [],
      cwd: path.dirname(executable),
      onLog: (line) => console.log(line),
    });
    sidecar.start();
    console.log('[serapi] sidecar: packaged');
  } else {
    const repoDir = path.join(__dirname, '..');
    const python = resolveDevelopmentPython({
      repoDir,
      platform: process.platform,
      env: process.env,
    });
    if (isExecutablePath(python) && !fs.existsSync(python)) {
      console.error('[serapi] sidecar python not found:', python);
      return;
    }
    sidecar = new SidecarClient({
      python,
      script: path.join(__dirname, 'sidecar.py'),
      cwd: repoDir,
      onLog: (line) => console.log(line),
    });
  }
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

function showWindow() {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
  // macOS needs the app itself brought forward; on Windows/Linux the window
  // focus above is enough and stealing app focus would fight the OS.
  if (process.platform === 'darwin') {
    try { app.focus({ steal: true }); } catch (_err) {}
  }
}

function showWorkspace() {
  showWindow();
  setEngineVisible(false);
}

function showEngine() {
  showWindow();
  setEngineVisible(true);
}

function trayIcon() {
  // macOS draws the status item at 22pt. Both files below are the Serapi mark
  // rendered from workspace/icon-a.svg, the same artwork the bundle icon and the
  // in-app brand use, so nothing here can drift into a second identity.
  // Windows keeps the original 32px tile, which matches its app icon.
  if (process.platform !== 'darwin') {
    return nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon-32.png'));
  }
  const icon = nativeImage.createFromPath(path.join(__dirname, 'assets', 'tray-mac-22.png'));
  const hi = nativeImage.createFromPath(path.join(__dirname, 'assets', 'tray-mac-44.png'));
  if (!hi.isEmpty()) icon.addRepresentation({ scaleFactor: 2, buffer: hi.toPNG() });
  return icon;
}

function createTray() {
  try {
    const icon = trayIcon();
    tray = new Tray(icon);
    tray.setToolTip('Serapi');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: '显示工作区', click: showWorkspace },
      { label: '显示 memoQ 引擎', click: showEngine },
      { type: 'separator' },
      { label: '设置', click: () => {
        showWorkspace();
        workspace.webContents.executeJavaScript(
          'document.querySelector("[data-action=\"设置\"]")?.click(); true', true
        ).catch(() => {});
      } },
      { type: 'separator' },
      { label: '退出 Serapi', click: () => { isQuitting = true; app.quit(); } },
    ]));
    tray.on('click', () => {
      if (win && win.isVisible() && !win.isMinimized()) win.hide();
      else showWindow();
    });
  } catch (err) {
    console.error('[serapi] tray failed:', err);
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
  win.on('close', (event) => {
    if (!isQuitting) { event.preventDefault(); win.hide(); }
  });
  createTray();
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
    if (parsed.type === 'bridge-ready') {
      engineBridgeReady = true;
      console.log('[serapi] engine bridge ready');
      maybeFinishSmoke();
    }
    if (process.env.SERAPI_DEBUG === '1') console.log('[serapi] engine event:', lastEngineEvent.type);
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
    const r = result && result.value;
    const shape = {
      ok: !!(result && result.ok),
      valueOk: !!(r && r.ok),
      rows: r && Array.isArray(r.rows) ? r.rows.length : -1,
      error: result && result.error ? String(result.error).slice(0, 80) : '',
      valueType: typeof r,
      valueKeys: r && typeof r === 'object' ? Object.keys(r).slice(0, 8) : [],
      valueErr: r && r.err ? String(r.err).slice(0, 80) : '',
    };
    console.log('[serapi] engine api', String(name || ''), JSON.stringify(shape));
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
  engineBridgeReady,
  sidecarReady,
}));
ipcMain.handle('host:capture', async (_event, target) => {
  if (!target) return false;
  const image = await win.capturePage();
  fs.writeFileSync(target, image.toPNG());
  return true;
});

app.whenReady().then(() => {
  if (!gotSingleInstanceLock) return;
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
  try {
    globalShortcut.register('CommandOrControl+Shift+W', () => {
      if (engineVisible) setEngineVisible(false);
      else setEngineVisible(true);
    });
  } catch (err) {
    console.error('[serapi] global shortcut failed:', err);
  }
  app.on('activate', () => {
    // macOS single-instance is enforced by the OS: launching the app again
    // while it runs does not spawn a second process and does not fire
    // 'second-instance', it just activates this one. Closing the window only
    // hides it, so a reopen has to show it back or the app looks dead.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else showWindow();
  });
});

app.on('window-all-closed', () => {
  // Keep the host alive in the tray; explicit Quit is the only exit.
});
app.on('second-instance', () => {
  // Launching again means "bring it back", not "reset my view": keep whatever
  // the window showed before it was hidden.
  showWindow();
});
app.on('will-quit', () => {
  if (fallbackLocked) {
    try { fs.unlinkSync(FALLBACK_LOCK); } catch (_) {}
    fallbackLocked = false;
  }
  try { globalShortcut.unregisterAll(); } catch (_) {}
  if (tray) { try { tray.destroy(); } catch (_) {} tray = null; }
});
app.on('before-quit', () => {
  isQuitting = true;
  if (sidecar) sidecar.close();
});
