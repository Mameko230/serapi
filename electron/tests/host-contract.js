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
assert.match(workspaceCss, /--src-fr/, 'splitter drives source column width');
assert.match(workspaceCss, /--tgt-fr/, 'splitter drives target column width');
assert.match(workspaceJs, /initSplitter/, 'splitter is initialized');
assert.match(workspaceJs, /serapi:split/, 'splitter ratio is persisted');
assert.match(workspaceJs, /serapiHost\.showEngine/, 'engine button calls host API');

console.log('HOST_CONTRACT: PASS');
