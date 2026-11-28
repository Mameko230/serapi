// Static host-contract guard. Does not start Electron.
// Run: node tests/host-contract.test.js
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');

const pkg = JSON.parse(read('package.json'));
const main = read('main.js');
const preload = read('preload.js');
const workspace = read(path.join('workspace', 'index.html'));
const workspaceCss = read(path.join('workspace', 'styles.css'));
const workspaceJs = read(path.join('workspace', 'app.js'));
const enginePreload = read('engine-preload.js');
const bridgeInject = read('bridge-inject.js');
const bridgeManifest = JSON.parse(read('bridge-scripts.json'));

assert.equal(pkg.main, 'main.js', 'package main must be main.js');
assert.equal(pkg.devDependencies.electron, '30.5.1', 'Electron version is pinned for the validated host');
assert.ok(fs.existsSync(path.join(root, 'engine', 'placeholder.html')), 'engine placeholder exists');

assert.match(main, /BrowserWindow/, 'main creates a BrowserWindow');
assert.match(main, /BrowserView/, 'main creates BrowserViews');
assert.match(main, /engine:show/, 'main exposes engine:show IPC');
assert.match(main, /engine:hide/, 'main exposes engine:hide IPC');
assert.match(main, /persist:serapi/, 'both views use the persisted profile');
assert.match(main, /getUserDataPath/, 'host chooses a platform-appropriate profile path');
assert.match(main, /SERAPI_CAPTURE/, 'capture hook exists');
// macOS reopens a running app through 'activate' (the OS forbids a real second
// instance), so a hidden window must be shown there, not just re-created.
// Bodies are sliced per handler: a loose regex would match the neighbouring
// 'second-instance' showWindow() and pass even when 'activate' only recreates.
const handlerBody = (name) => {
  const after = main.split(`app.on('${name}'`)[1] || '';
  return after.split("app.on('")[0];
};
const activateBody = handlerBody('activate');
assert.ok(activateBody.length > 0, "main registers an 'activate' handler");
assert.match(activateBody, /showWindow\(\)/,
  "'activate' shows the hidden window again on macOS reopen");
assert.match(handlerBody('second-instance'), /showWindow\(\)/,
  "'second-instance' shows the hidden window again");
const showWindowBody = main.split('function showWindow()')[1].split('\nfunction ')[0];
assert.match(showWindowBody, /app\.focus\(\{ steal: true \}\)/,
  'showWindow brings the macOS app forward');
assert.match(preload, /contextBridge\.exposeInMainWorld\('serapiHost'/, 'workspace host API is exposed');
assert.match(preload, /showEngine/, 'host API can show the engine view');
assert.match(preload, /loadEngine/, 'host API can load a memoQ URL');
assert.match(preload, /invokeEngineApi/, 'host API can call the engine API');
assert.match(preload, /sidecar/, 'host API exposes the sidecar');
assert.ok(fs.existsSync(path.join(root, 'sidecar.py')), 'sidecar script exists');
assert.ok(fs.existsSync(path.join(root, 'sidecar-client.js')), 'sidecar client exists');
assert.ok(Array.isArray(require(path.join(root, 'engine-api-allowlist.json')).methods),
  'engine API allowlist exists');
assert.match(main, /sidecar:call/, 'main exposes sidecar:call IPC');
assert.match(main, /engine:api/, 'main exposes engine:api IPC');
assert.match(main, /invokeEngineApi/, 'engine API calls are guarded by one helper');
assert.match(main, /startSidecar/, 'sidecar is started with the host');
assert.match(main, /SERAPI_ENGINE_INVOKE/, 'engine API has a smoke hook');
assert.match(main, /SERAPI_SIDECAR_SMOKE/, 'sidecar has a smoke hook');
assert.match(enginePreload, /engine:bridge/, 'engine preload forwards bridge events');
assert.match(main, /engine:bridge/, 'main receives bridge events');
assert.match(main, /injectBridge/, 'main injects the bridge bundle');
assert.match(main, /engine:load/, 'main validates engine URL loading');
assert.ok(Array.isArray(bridgeManifest.scripts) && bridgeManifest.scripts.length >= 30,
  'bridge manifest covers the memoQ page bundles');
assert.match(bridgeInject, /qwebchannel-shim/, 'bridge injector uses the QWebChannel shim');
assert.match(bridgeInject, /page_rules\.json/, 'bridge injector carries page rules');

assert.match(workspace, /id="codePane"/, 'workspace has paired code rows');
assert.match(workspace, /id="colResizer"/, 'workspace has a source/target splitter');
assert.match(workspace, /id="welcome"/, 'workspace has a Web welcome surface');
assert.match(workspaceCss, /--src-fr/, 'splitter drives source column width');
assert.match(workspaceCss, /--tgt-fr/, 'splitter drives target column width');
assert.match(workspaceJs, /initSplitter/, 'splitter is initialized');
assert.match(workspaceJs, /serapi:split/, 'splitter ratio is persisted');
assert.match(workspaceJs, /serapiHost\.showEngine/, 'engine button calls host API');
assert.match(workspaceJs, /config\.get/, 'welcome reads config from the sidecar');
assert.match(workspaceJs, /config\.remember_server/, 'welcome saves the server through the sidecar');
assert.match(workspaceJs, /initSettings/, 'workspace has a Web settings surface');
assert.match(workspaceJs, /config\.update/, 'settings persist through the sidecar');
assert.match(workspaceJs, /applyUiConfig/, 'UI preferences are applied to the workspace');
assert.match(workspaceJs, /workspace\.snapshot/, 'workspace boots from the sidecar snapshot');
assert.match(workspaceJs, /loadEngineSnapshot/, 'workspace tries real Engine rows first');
assert.match(workspaceJs, /workspace\.normalize/, 'workspace normalizes Engine rows in the sidecar');
assert.match(workspaceJs, /loadSegmentDetail/, 'workspace loads per-segment detail from the Engine');
assert.match(workspaceJs, /workspace\.normalize_segment/, 'workspace normalizes segment tokens in the sidecar');
assert.match(workspaceJs, /lintEngine/, 'workspace runs QA through the Engine lint engine');
assert.match(workspaceJs, /qa\.config/, 'workspace reads QA rules from the sidecar');
assert.match(workspaceJs, /loadHitsForSegment/, 'workspace loads TM/TB hits');
assert.match(workspaceJs, /workspace\.normalize_hits/, 'workspace normalizes hits in the sidecar');
assert.match(workspaceJs, /initEngineEvents/, 'workspace listens to forwarded Engine events');
assert.match(workspaceJs, /workspace\.normalize_context/, 'workspace normalizes context in the sidecar');
assert.match(workspaceJs, /dictionary\.query/, 'workspace queries the local dictionary');
assert.match(workspaceJs, /initDictionarySelection/, 'workspace looks up only the selected word');
assert.match(workspaceJs, /lookupSelectedWord/, 'dictionary lookup is selection-driven');
assert.match(workspaceJs, /saveCurrentSegment/, 'workspace has a save/confirm path');
assert.match(workspaceJs, /write\.decide/, 'workspace asks the sidecar WritePolicy before writing');
assert.match(workspaceJs, /writeSegment/, 'workspace calls Engine writeSegment');
assert.match(main, /SERAPI_CAPTURE_WRITE/, 'write path has a fixture smoke hook');
assert.match(main, /requestSingleInstanceLock/, 'host owns a single-instance lock');
assert.match(main, /new Tray/, 'host creates a system tray');
assert.match(main, /globalShortcut/, 'host owns a global workspace shortcut');
assert.ok(fs.existsSync(path.join(root, 'assets', 'icon-32.png')), 'tray icon exists');
// macOS status item must use the same artwork as the bundle icon and the in-app brand
// (a second artwork set reads as two different products).
assert.ok(fs.existsSync(path.join(root, 'assets', 'tray-mac-22.png')), 'macOS tray icon (1x) exists');
assert.ok(fs.existsSync(path.join(root, 'assets', 'tray-mac-44.png')), 'macOS tray icon (2x) exists');
const trayIconBody = (main.split('function trayIcon()')[1] || '').split('\nfunction ')[0];
assert.ok(trayIconBody.length > 0, 'main has a trayIcon() helper');
assert.match(trayIconBody, /platform !== 'darwin'/,
  'windows keeps the original tray artwork');
assert.match(trayIconBody, /tray-mac-22\.png/, 'darwin tray uses the app artwork');
assert.match(trayIconBody, /scaleFactor: 2/, 'darwin tray ships a Retina representation');
assert.match(preload, /onEngineEvent/, 'preload exposes Engine event forwarding');
assert.match(main, /engine:event/, 'main forwards Engine events to the workspace');
assert.match(workspaceJs, /tmHitsPoll/, 'TM/TB polling is wired through engine API');
assert.match(main, /engine:lint/, 'main exposes engine:lint IPC');

console.log('HOST_CONTRACT: PASS');
