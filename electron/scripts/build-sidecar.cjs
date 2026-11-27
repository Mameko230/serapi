// Build the standalone Python sidecar used by the packaged Electron app.
// Requires PyInstaller in the repo venv:
//   .venv314/Scripts/python.exe -m pip install pyinstaller
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const repo = path.resolve(root, '..');
const python = process.env.SERAPI_PYTHON
  || path.join(repo, '.venv314', 'Scripts', 'python.exe');
const pyinstaller = path.join(repo, '.venv314', 'Scripts', 'pyinstaller.exe');
if (!fs.existsSync(pyinstaller)) {
  console.error('pyinstaller not found:', pyinstaller);
  process.exit(1);
}
const args = [
  '--noconfirm', '--clean', '--onefile',
  '--name', 'serapi-sidecar',
  '--distpath', path.join(root, 'vendor'),
  '--workpath', path.join(root, 'build', 'pyi'),
  '--specpath', path.join(root, 'build'),
  '--paths', repo,
  '--add-data', path.join(repo, 'app') + ';app',
  '--add-data', path.join(root, 'fixtures') + ';electron/fixtures',
  '--hidden-import', 'app.assets',
  '--hidden-import', 'app.write_policy',
  '--hidden-import', 'app.version',
  path.join(root, 'sidecar.py'),
];
const result = spawnSync(pyinstaller, args, { stdio: 'inherit', cwd: root, env: process.env });
if (result.status !== 0) process.exit(result.status || 1);
console.log('sidecar built:', path.join(root, 'vendor', 'serapi-sidecar.exe'));
