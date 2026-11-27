// Sidecar smoke test: spawn the Python sidecar, send requests, verify JSON.
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..');
const sidecar = path.join(root, 'sidecar.py');
const candidates = [
  process.env.SERAPI_PYTHON,
  path.join(root, '..', '.venv314', 'Scripts', 'python.exe'),
  'python',
].filter(Boolean);
const python = candidates.find((candidate) => candidate === 'python' || fs.existsSync(candidate));
assert.ok(python, 'no Python interpreter found (set SERAPI_PYTHON)');

const tmpDir = fs.mkdtempSync(path.join(root, '.sidecar-test-'));
const configPath = path.join(tmpDir, 'app.json');
fs.writeFileSync(configPath, JSON.stringify({
  memoq_url: '',
  server_history: ['https://demo.example.invalid/memoqweb'],
  server_names: { 'https://demo.example.invalid/memoqweb': '演示服务器' },
  outer_theme: 'teal',
  editor_theme: 'green',
}));

const requests = [
  { id: 1, method: 'ping', params: {} },
  { id: 2, method: 'version', params: {} },
  { id: 3, method: 'config.get', params: {} },
  {
    id: 4,
    method: 'config.remember_server',
    params: { url: 'https://demo.example.invalid/memoqweb', name: '演示服务器' },
  },
  { id: 5, method: 'workspace.snapshot', params: {} },
];
const result = spawnSync(python, ['-u', sidecar], {
  cwd: path.join(root, '..'),
  input: requests.map((request) => JSON.stringify(request)).join('\n') + '\n',
  encoding: 'utf8',
  timeout: 10000,
  env: { ...process.env, SERAPI_CONFIG_PATH: configPath },
});
assert.equal(result.status, 0, result.stderr || 'sidecar exited non-zero');
const lines = result.stdout.trim().split(/\r?\n/).filter(Boolean);
assert.equal(lines.length, 5, 'expected five sidecar responses');
const ping = JSON.parse(lines[0]);
const version = JSON.parse(lines[1]);
const config = JSON.parse(lines[2]);
const remember = JSON.parse(lines[3]);
const workspace = JSON.parse(lines[4]);
assert.equal(ping.ok, true);
assert.equal(ping.result.ok, true);
assert.equal(version.ok, true);
assert.equal(typeof version.result.version, 'string');
assert.equal(config.ok, true);
assert.equal(config.result.memoq_url, '');
assert.equal(config.result.server_history.length, 1);
assert.equal(remember.ok, true);
assert.equal(remember.result.ok, true);
assert.equal(remember.result.config.memoq_url, 'https://demo.example.invalid/memoqweb');
assert.equal(workspace.ok, true);
assert.equal(workspace.result.synthetic, true);
assert.ok(workspace.result.segments.length >= 10);
assert.equal(JSON.parse(fs.readFileSync(configPath, 'utf8')).memoq_url,
  'https://demo.example.invalid/memoqweb');
fs.rmSync(tmpDir, { recursive: true, force: true });
console.log('SIDECAR_CONTRACT: PASS');
