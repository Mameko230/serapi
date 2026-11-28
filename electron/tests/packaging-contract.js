// Static guard for the Electron packaging contract.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { getPackagedSidecarPath } = require('../platform-paths');

const root = path.join(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const main = fs.readFileSync(path.join(root, 'main.js'), 'utf8');
const sidecarBuild = fs.readFileSync(path.join(root, 'scripts', 'build-sidecar.cjs'), 'utf8');
const build = pkg.build || {};

assert.equal(pkg.main, 'main.js');
assert.equal(build.appId, 'com.serapi.app');
assert.equal(build.asar, true, 'asar must stay enabled');
assert.ok(pkg.scripts['build:sidecar'], 'sidecar build script is wired');
assert.ok(pkg.scripts['dist:dir'], 'Windows unpacked build script is wired');
assert.ok(pkg.scripts['dist:zip'], 'Windows zip distributable script is wired');
assert.ok(pkg.scripts['dist:mac:dir'], 'macOS app-directory build script is wired');
assert.ok(pkg.scripts['dist:mac'], 'macOS dmg and zip build script is wired');
const launcher = path.join(root, '..', 'start-serapi.command');
assert.ok(fs.existsSync(launcher), 'macOS launcher exists');
assert.ok(fs.statSync(launcher).mode & 0o111, 'macOS launcher is executable');

const files = build.files || [];
for (const required of ['main.js', 'platform-paths.js', 'preload.js', 'engine-preload.js', 'workspace/**', 'engine/**', 'assets/**']) {
  assert.ok(files.includes(required), `packaged files must include ${required}`);
}
const resources = build.extraResources || [];
assert.ok(resources.some((resource) => resource.to === 'app'), 'packaged app data is copied');
assert.ok(resources.some((resource) => resource.to === 'sidecar'), 'sidecar folder is packaged');

assert.ok(build.win.target.includes('portable'), 'Windows portable target remains available');
assert.ok(build.win.extraFiles.some((file) => file.from === 'extra/run-serapi.cmd'),
  'Windows launcher remains Windows-only');
assert.ok(build.mac.target.includes('dmg') && build.mac.target.includes('zip'),
  'macOS dmg and zip targets are configured');
assert.ok(fs.existsSync(path.join(root, build.mac.icon)), 'macOS app icon exists');
assert.match(build.mac.artifactName, /\$\{arch\}/, 'macOS artifact names distinguish CPU architecture');

assert.match(main, /app\.isPackaged/, 'main switches to packaged resources');
assert.match(main, /process\.resourcesPath/, 'main resolves packaged resources');
assert.match(main, /getPackagedSidecarPath/, 'main resolves the sidecar for the current platform');
assert.equal(getPackagedSidecarPath('/resources', 'win32'), path.win32.join('/resources', 'sidecar', 'serapi-sidecar.exe'));
assert.equal(getPackagedSidecarPath('/resources', 'darwin'), '/resources/sidecar/serapi-sidecar');
assert.match(sidecarBuild, /path\.delimiter/, 'PyInstaller data paths use the host platform separator');
assert.match(sidecarBuild, /--onedir/, 'sidecar is built as an onedir resource bundle');

console.log('PACKAGING_CONTRACT: PASS');
