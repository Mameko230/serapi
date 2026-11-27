// Static guard for the Electron packaging contract.
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const main = fs.readFileSync(path.join(root, 'main.js'), 'utf8');
const build = pkg.build || {};

assert.equal(pkg.main, 'main.js');
assert.equal(build.appId, 'com.serapi.app');
assert.equal(build.asar, true, 'asar must stay enabled');
assert.ok(fs.existsSync(path.join(root, 'scripts', 'build-sidecar.cjs')),
  'sidecar build script exists');
assert.ok(pkg.scripts['build:sidecar'], 'sidecar build script is wired');
assert.ok(pkg.scripts['dist:dir'], 'unpacked build script is wired');
assert.ok(pkg.scripts['dist:zip'], 'zip distributable script is wired');

const files = build.files || [];
for (const required of ['main.js', 'preload.js', 'engine-preload.js', 'workspace/**', 'engine/**']) {
  assert.ok(files.includes(required), `packaged files must include ${required}`);
}
const resources = build.extraResources || [];
assert.ok(resources.some((r) => r.to === 'app'), 'packaged app data is copied');
assert.ok(resources.some((r) => r.to === 'sidecar/serapi-sidecar.exe'), 'sidecar exe is packaged');

assert.match(main, /app\.isPackaged/, 'main switches to packaged resources');
assert.match(main, /process\.resourcesPath/, 'main resolves resources path');
assert.match(main, /serapi-sidecar\.exe/, 'main launches packaged sidecar');
console.log('PACKAGING_CONTRACT: PASS');
