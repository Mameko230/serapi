const assert = require('node:assert/strict');
const path = require('node:path');
const {
  getUserDataPath,
  getFallbackLockPath,
  getSidecarExecutableName,
  getPackagedSidecarPath,
  getVenvPythonPath,
  resolveDevelopmentPython,
  isExecutablePath,
} = require('../platform-paths');

assert.equal(
  getUserDataPath({ platform: 'win32', env: { LOCALAPPDATA: 'C:\\Users\\tester\\AppData\\Local' }, appDir: 'C:\\repo' }),
  path.win32.join('C:\\Users\\tester\\AppData\\Local', 'Serapi'),
  'Windows profile remains in LocalAppData',
);
assert.equal(
  getUserDataPath({ platform: 'win32', env: {}, appDir: 'C:\\repo\\electron' }),
  path.win32.join('C:\\repo\\electron', '.profile', 'Serapi'),
  'Windows has a source-tree fallback when LocalAppData is unavailable',
);
assert.equal(
  getUserDataPath({ platform: 'darwin', env: { HOME: '/Users/tester' } }),
  '/Users/tester/Library/Application Support/Serapi',
  'macOS profile uses Library/Application Support',
);
assert.equal(
  getUserDataPath({ platform: 'darwin', appDataPath: '/Users/tester/Library/Application Support' }),
  '/Users/tester/Library/Application Support/Serapi',
  'Electron appData path is used on macOS',
);
assert.equal(
  getUserDataPath({ platform: 'linux', env: { HOME: '/home/tester', XDG_CONFIG_HOME: '/tmp/config' } }),
  '/tmp/config/Serapi',
  'Linux respects XDG_CONFIG_HOME',
);
assert.equal(
  getFallbackLockPath('/Users/tester/Library/Application Support/Serapi', 'darwin'),
  '/Users/tester/Library/Application Support/Serapi/instance.lock',
);

assert.equal(getSidecarExecutableName('win32'), 'serapi-sidecar.exe');
assert.equal(getSidecarExecutableName('darwin'), 'serapi-sidecar');
assert.equal(getPackagedSidecarPath('/Applications/Serapi.app/Contents/Resources', 'darwin'),
  '/Applications/Serapi.app/Contents/Resources/sidecar/serapi-sidecar');
assert.equal(getPackagedSidecarPath('C:\\Serapi\\resources', 'win32'),
  'C:\\Serapi\\resources\\sidecar\\serapi-sidecar.exe');
assert.equal(getVenvPythonPath('/repo', 'darwin'), '/repo/.venv314/bin/python3');
assert.equal(getVenvPythonPath('C:\\repo', 'win32'), 'C:\\repo\\.venv314\\Scripts\\python.exe');
assert.equal(resolveDevelopmentPython({ repoDir: '/repo', platform: 'darwin', env: {}, existsSync: () => false }), 'python3');
// Windows must not fall back to PATH: the baseline build fails when the repo venv is missing.
assert.equal(resolveDevelopmentPython({ repoDir: 'C:\\repo', platform: 'win32', env: {}, existsSync: () => false }),
  'C:\\repo\\.venv314\\Scripts\\python.exe');
assert.equal(resolveDevelopmentPython({ repoDir: '/repo', platform: 'darwin', env: {}, existsSync: () => true }), '/repo/.venv314/bin/python3');
assert.equal(resolveDevelopmentPython({ repoDir: '/repo', platform: 'darwin', env: { SERAPI_PYTHON: 'python-custom' } }), 'python-custom');
assert.equal(isExecutablePath('python3', 'darwin'), false);
assert.equal(isExecutablePath('/usr/bin/python3', 'darwin'), true);
assert.equal(isExecutablePath('C:\\Python\\python.exe', 'win32'), true);

console.log('PLATFORM_PATHS: PASS');
