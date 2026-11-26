// 旧版 WebTrans 行状态桥接回归：只读权限/锁定不得覆盖工作流状态。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function cachedRow(id, current, locked, target) {
  return {
    id,
    guid: 'row-' + id,
    _isReadOnly: true,
    rowStatus: {
      _isReadOnly: true,
      _locked: !!locked,
      stateMachine: { stateMachine: { current: current || '' } },
    },
    sourceWebSegment: { EditorString: 'source' },
    targetWebSegment: { EditorString: target === undefined ? 'target' : target },
  };
}

function nativeRow(id, translationState, target) {
  return {
    id,
    guid: 'native-' + id,
    _isReadOnly: true,
    // 长文档分批缓存行：没有可用的 stateMachine.current，只有 memoQ 原生枚举。
    rowStatus: { translationState, _isReadOnly: true, _locked: false },
    sourceWebSegment: { EditorString: 'source' },
    targetWebSegment: { EditorString: target === undefined ? 'target' : target },
  };
}

const rows = [
  cachedRow(0, 'ManuallyConfirmed', true),
  cachedRow(1, 'Reviewer1Confirmed', false),
  // DOM 故意给泛化的 confirmed：完整缓存状态必须优先，不能降成译者确认。
  cachedRow(2, 'Reviewer2Confirmed', true),
  cachedRow(3, '', false),
  cachedRow(4, '', false, ''),
  nativeRow(5, 3),
  nativeRow(6, 7),
  nativeRow(7, 4),
  nativeRow(8, 2),
  nativeRow(9, 0, ''),
];

function domRow(no, cls, locked) {
  return {
    className: '',
    querySelector(selector) {
      if (selector === '.editor-cell') return {};
      if (selector === 'td.order') return { textContent: String(no) };
      if (selector === 'td.status-cell') return { className: cls };
      if (selector === '[data-iconkey="lock"]') return { className: locked ? 'locked' : '' };
      return null;
    },
  };
}
const domRows = [
  domRow(1, 'ico status-cell confirmed', true),
  domRow(2, 'ico status-cell r1confirmed', false),
  domRow(3, 'ico status-cell confirmed', true),
  domRow(4, 'ico status-cell r2confirmed', false),
];
const gridElement = {};
const ctrl = {
  gridContentManager: {
    rowCount: 1200,
    getAllCachedRows() { return { toArray() { return rows; } }; },
  },
};
const context = {
  console,
  URL,
  JSON,
  Date,
  location: {
    pathname: '/memoqweb/webpm/webtrans/Translation.aspx',
    href: 'https://example.test/memoqweb/webpm/webtrans/Translation.aspx',
    origin: 'https://example.test',
    host: 'example.test',
  },
  document: {
    activeElement: null,
    querySelector(selector) {
      return selector === '[ng-controller="gridCtrl"]' ? gridElement : null;
    },
    querySelectorAll(selector) { return selector === 'tr' ? domRows : []; },
    getElementById() { return null; },
  },
  angular: {
    element() { return { scope() { return { ctrl }; } }; },
  },
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) {
    callback({ objects: { mdBridge: { push() {} } } });
  },
  setInterval() { return 0; },
  fetch() { throw new Error('测试不应发起网络请求'); },
};
context.window = context;
vm.createContext(context);
const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8');
vm.runInContext(source, context, { filename: 'bridge.js' });

const result = context.__md.api.listRows();
assert.strictEqual(result.ok, true, result.err);
assert.deepStrictEqual(Array.from(result.rows, r => r.status), [
  'confirmed', 'reviewer1', 'reviewer2', 'reviewer2', 'untranslated',
  'confirmed', 'reviewer1', 'reviewer2', 'edited', 'untranslated',
]);
assert.deepStrictEqual(Array.from(result.rows, r => r.locked), [
  true, false, true, false, false, false, false, false, false, false,
]);
assert.strictEqual(result.rows[0].status, 'confirmed');
assert.strictEqual(result.rows[0].locked, true, '确认色与锁图标必须同时保留');
assert.strictEqual(result.rows[2].status, 'reviewer2', '泛化 DOM confirmed 不得覆盖缓存 R2');
assert.strictEqual(result.rows[5].status, 'confirmed', '原生枚举 3 = 译者确认');
assert.strictEqual(result.rows[6].status, 'reviewer1', '原生枚举 7 = R1');
assert.strictEqual(result.rows[7].status, 'reviewer2', '原生枚举 4 = R2/ProofRead');
assert.strictEqual(result.rows[8].status, 'edited', '原生枚举 2 = 已编辑');
console.log('STATUS_BRIDGE_TEST: PASS');
