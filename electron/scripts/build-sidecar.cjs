// Build the standalone Python sidecar used by the packaged Electron app.
// Requires PyInstaller in .venv314 or in the Python selected by SERAPI_PYTHON.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {
  getSidecarExecutableName,
  isExecutablePath,
  resolveDevelopmentPython,
} = require('../platform-paths');

const root = path.resolve(__dirname, '..');
const repo = path.resolve(root, '..');
const python = resolveDevelopmentPython({ repoDir: repo, platform: process.platform, env: process.env });
if (isExecutablePath(python) && !fs.existsSync(python)) {
  console.error('Python interpreter not found:', python);
  process.exit(1);
}

const vendor = path.join(root, 'vendor');
const output = path.join(vendor, 'serapi-sidecar');
fs.rmSync(output, { recursive: true, force: true });
const dataSeparator = path.delimiter;
const args = [
  '-m', 'PyInstaller',
  '--noconfirm', '--clean', '--onedir',
  '--name', 'serapi-sidecar',
  '--distpath', vendor,
  '--workpath', path.join(root, 'build', 'pyi'),
  '--specpath', path.join(root, 'build'),
  '--paths', repo,
  '--add-data', `${path.join(repo, 'app')}${dataSeparator}app`,
  '--add-data', `${path.join(root, 'fixtures')}${dataSeparator}electron/fixtures`,
  '--hidden-import', 'app.assets',
  '--hidden-import', 'app.write_policy',
  '--hidden-import', 'app.version',
  path.join(root, 'sidecar.py'),
];
const result = spawnSync(python, args, { stdio: 'inherit', cwd: root, env: process.env });
if (result.error) {
  console.error('sidecar build failed:', result.error.message);
  process.exit(1);
}
if (result.status !== 0) process.exit(result.status || 1);
const executable = path.join(output, getSidecarExecutableName(process.platform));
if (!fs.existsSync(executable)) {
  console.error('sidecar executable not produced:', executable);
  process.exit(1);
}
console.log('sidecar built:', executable);
