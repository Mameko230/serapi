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
assert.match(main, /process\.env\.LOCALAPPDATA/, 'profile avoids roaming AppData');
assert.match(main, /SERAPI_CAPTURE/, 'capture hook exists');
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
assert.match(workspaceJs, /workspace\.snapshot/, 'workspace boots from the sidecar snapshot');
assert.match(workspaceJs, /loadEngineSnapshot/, 'workspace tries real Engine rows first');
assert.match(workspaceJs, /workspace\.normalize/, 'workspace normalizes Engine rows in the sidecar');
assert.match(workspaceJs, /loadSegmentDetail/, 'workspace loads per-segment detail from the Engine');
assert.match(workspaceJs, /workspace\.normalize_segment/, 'workspace normalizes segment tokens in the sidecar');
assert.match(workspaceJs, /lintEngine/, 'workspace runs QA through the Engine lint engine');
assert.match(workspaceJs, /qa\.config/, 'workspace reads QA rules from the sidecar');
assert.match(workspaceJs, /loadHitsForSegment/, 'workspace loads TM/TB hits');
assert.match(workspaceJs, /workspace\.normalize_hits/, 'workspace normalizes hits in the sidecar');
assert.match(workspaceJs, /tmHitsPoll/, 'TM/TB polling is wired through engine API');
assert.match(main, /engine:lint/, 'main exposes engine:lint IPC');

console.log('HOST_CONTRACT: PASS');
