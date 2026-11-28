// Platform-specific locations for the Electron host and its Python sidecar.
const path = require('node:path');

function pathForPlatform(platform) {
  return platform === 'win32' ? path.win32 : path.posix;
}

function getUserDataPath({
  platform = process.platform,
  env = process.env,
  appDataPath,
  appDir = __dirname,
} = {}) {
  const paths = pathForPlatform(platform);
  let root;
  if (platform === 'win32') {
    root = env.LOCALAPPDATA || paths.join(appDir, '.profile');
  } else if (appDataPath) {
    // Electron resolves this to ~/Library/Application Support on macOS and
    // ~/.config on Linux. Keep the product data out of the source tree.
    root = appDataPath;
  } else if (platform === 'darwin') {
    root = paths.join(env.HOME || '', 'Library', 'Application Support');
  } else if (platform === 'linux') {
    root = env.XDG_CONFIG_HOME || paths.join(env.HOME || '', '.config');
  } else {
    root = paths.join(appDir, '.profile');
  }
  return paths.join(root, 'Serapi');
}

function getFallbackLockPath(userDataPath, platform = process.platform) {
  return pathForPlatform(platform).join(userDataPath, 'instance.lock');
}

function getSidecarExecutableName(platform = process.platform) {
  return platform === 'win32' ? 'serapi-sidecar.exe' : 'serapi-sidecar';
}

function getPackagedSidecarPath(resourcesPath, platform = process.platform) {
  return pathForPlatform(platform).join(resourcesPath, 'sidecar', getSidecarExecutableName(platform));
}

function getVenvPythonPath(repoDir, platform = process.platform) {
  const paths = pathForPlatform(platform);
  const executable = platform === 'win32' ? 'python.exe' : 'python3';
  const binDir = platform === 'win32' ? 'Scripts' : 'bin';
  return paths.join(repoDir, '.venv314', binDir, executable);
}

function resolveDevelopmentPython({
  repoDir,
  platform = process.platform,
  env = process.env,
  existsSync = require('node:fs').existsSync,
} = {}) {
  if (env.SERAPI_PYTHON) return env.SERAPI_PYTHON;
  const venvPython = getVenvPythonPath(repoDir, platform);
  if (existsSync(venvPython)) return venvPython;
  // Windows keeps the baseline contract: the build and the dev host require the
  // repo venv, and a missing one must fail loudly instead of silently picking up
  // whatever `python` happens to be on PATH. macOS/Linux fall back to python3,
  // where the venv is optional (the packaged build does not need it at all).
  if (platform === 'win32') return venvPython;
  return 'python3';
}

function isExecutablePath(value, platform = process.platform) {
  const paths = pathForPlatform(platform);
  return paths.isAbsolute(value) || value.includes('/') || value.includes('\\');
}

module.exports = {
  getUserDataPath,
  getFallbackLockPath,
  getSidecarExecutableName,
  getPackagedSidecarPath,
  getVenvPythonPath,
  resolveDevelopmentPython,
  isExecutablePath,
};
