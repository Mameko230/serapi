// Sidecar smoke test: spawn the Python sidecar, send two requests, verify JSON.
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

const stdout = JSON.stringify({
  id: 1, method: 'ping', params: {},
}) + '\n' + JSON.stringify({
  id: 2, method: 'version', params: {},
}) + '\n';
const result = spawnSync(python, ['-u', sidecar], {
  cwd: path.join(root, '..'),
  input: stdout,
  encoding: 'utf8',
  timeout: 10000,
});
assert.equal(result.status, 0, result.stderr || 'sidecar exited non-zero');
const lines = result.stdout.trim().split(/\r?\n/).filter(Boolean);
assert.equal(lines.length, 2, 'expected two sidecar responses');
const ping = JSON.parse(lines[0]);
const version = JSON.parse(lines[1]);
assert.equal(ping.id, 1);
assert.equal(ping.ok, true);
assert.equal(ping.result.ok, true);
assert.equal(version.id, 2);
assert.equal(version.ok, true);
assert.equal(typeof version.result.version, 'string');
console.log('SIDECAR_CONTRACT: PASS');
