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
  update_last_checked: '2026-11-27',
  custom_keep: 'ok',
}));

const rawEngine = JSON.parse(fs.readFileSync(path.join(root, 'fixtures', 'engine-rows-demo.json'), 'utf8'));
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
  { id: 6, method: 'workspace.normalize', params: { rows: rawEngine.result.rows } },
  {
    id: 7,
    method: 'workspace.normalize_segment',
    params: { segment: { ok: true, rowId: 'demo-row', rowNo: 9, locked: false,
      srcTokens: [{ t: 'text', v: '原文一行' }, { t: 'newline' }, { t: 'text', v: '原文二行' }],
      tokens: [{ t: 'text', v: '译文一行' }, { t: 'tag', name: 'mq:rxt', display: { text: 'tag1' } }, { t: 'newline' }, { t: 'text', v: '译文二行' }] } },
  },
  { id: 8, method: 'qa.config', params: {} },
  {
    id: 9,
    method: 'workspace.normalize_hits',
    params: { raw: { status: 'done',
      tm: [{ rate: 99, res: 'DEMO_TM', user: 'rev', time: '2026-11-12', srcDisp: '原文', tgtDecorated: '译文' }],
      tb: [{ s: '术语', t: '术语', res: 'DEMO_TB' }] } },
  },
  {
    id: 10,
    method: 'workspace.normalize_context',
    params: { currentNo: 3, currentText: '当前原文', rows: [
      { rowNo: 1, sourcecell: '前二' }, { rowNo: 2, sourcecell: '前一' },
      { rowNo: 3, sourcecell: '当前原文' }, { rowNo: 4, sourcecell: '后一' },
      { rowNo: 5, sourcecell: '后二' },
    ] },
  },
  { id: 11, method: 'dictionary.query', params: { word: '攻撃力' } },
  { id: 12, method: 'write.decide', params: { intent: 'save', state: { locked: false, has_row_id: true } } },
  { id: 13, method: 'write.decide', params: { intent: 'save', state: { tracking: true } } },
  { id: 14, method: 'config.update', params: { editor_font_size: 18, outer_theme: 'dark' } },
];
const result = spawnSync(python, ['-u', sidecar], {
  cwd: path.join(root, '..'),
  input: requests.map((request) => JSON.stringify(request)).join('\n') + '\n',
  encoding: 'utf8',
  timeout: 10000,
  env: { ...process.env, SERAPI_CONFIG_PATH: configPath,
    SERAPI_ASSETS_DIR: path.join(root, 'fixtures', 'assets') },
});
assert.equal(result.status, 0, result.stderr || 'sidecar exited non-zero');
const lines = result.stdout.trim().split(/\r?\n/).filter(Boolean);
assert.equal(lines.length, 14, 'expected fourteen sidecar responses');
const ping = JSON.parse(lines[0]);
const version = JSON.parse(lines[1]);
const config = JSON.parse(lines[2]);
const remember = JSON.parse(lines[3]);
const workspace = JSON.parse(lines[4]);
const normalized = JSON.parse(lines[5]);
const segment = JSON.parse(lines[6]);
const qa = JSON.parse(lines[7]);
const hits = JSON.parse(lines[8]);
const context = JSON.parse(lines[9]);
const dictionary = JSON.parse(lines[10]);
const allowed = JSON.parse(lines[11]);
const blocked = JSON.parse(lines[12]);
const updated = JSON.parse(lines[13]);
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
assert.equal(normalized.ok, true);
assert.equal(normalized.result.synthetic, false);
assert.equal(normalized.result.segments.length, 10);
assert.equal(normalized.result.segments[2].no, 3);
assert.ok(normalized.result.segments[2].srcLines.length > 1);
assert.equal(segment.ok, true);
assert.equal(segment.result.segment.srcLines.length, 2);
assert.equal(segment.result.segment.tgtLines[0], '译文一行[tag1]');
assert.equal(segment.result.segment.tgtLines[1], '译文二行');
assert.equal(qa.ok, true);
assert.equal(typeof qa.result.rules, 'object');
assert.equal(qa.result.rules.digits, true);
assert.equal(hits.ok, true);
assert.equal(hits.result.hits.length, 2);
assert.equal(hits.result.hits[0].type, 'TM');
assert.equal(hits.result.hits[0].rate, '99%');
assert.equal(hits.result.hits[1].type, 'TB');
assert.equal(context.ok, true);
assert.equal(context.result.contextLines.length, 5);
assert.equal(context.result.contextLines[1][1], '前一');
assert.equal(context.result.contextLines[2][1], '当前原文');
assert.equal(dictionary.ok, true);
assert.ok(dictionary.result.hits.length >= 1);
assert.ok(dictionary.result.hits[0].entries.length >= 1);
assert.equal(allowed.ok, true);
assert.equal(allowed.result.allowed, true);
assert.equal(blocked.ok, true);
assert.equal(blocked.result.allowed, false);
assert.ok(blocked.result.reason.includes('跟踪修改'));
assert.equal(updated.ok, true);
assert.equal(updated.result.config.editor_font_size, 18);
assert.equal(updated.result.config.outer_theme, 'dark');
const savedConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
assert.equal(savedConfig.custom_keep, 'ok');
assert.equal(savedConfig.update_last_checked, '2026-11-27');
assert.equal(JSON.parse(fs.readFileSync(configPath, 'utf8')).memoq_url,
  'https://demo.example.invalid/memoqweb');
fs.rmSync(tmpDir, { recursive: true, force: true });
console.log('SIDECAR_CONTRACT: PASS');
