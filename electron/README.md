# Serapi Electron host (migration branch)

This is the Electron migration skeleton. It is **not** the shipping app yet.
The PyQt application on `main` is untouched.

## Layout

```text
electron/
├─ main.js                 BrowserWindow + Workspace/Engine BrowserViews
├─ preload.js              host API exposed to the local workspace UI
├─ engine-preload.js       placeholder for memoQ bridge injection
├─ workspace/              local web workspace UI
├─ engine/placeholder.html Engine WebView placeholder
└─ tests/host-contract.js  static host contract guard
```

## Run

```bash
cd electron
npm install
npm start
```

On the current development machine, Chromium's profile under roaming
`%APPDATA%` is rejected by the network sandbox, so the host stores its profile
under `%LOCALAPPDATA%\Serapi`. Start with `--no-sandbox` only if this machine
requires it:

```bash
npm start -- --no-sandbox
```

## Capture

```powershell
$env:SERAPI_CAPTURE="preview-electron.png"
npm start -- --no-sandbox
```

Captures the workspace View, then exits.

## Current state

- Workspace WebView loads the local UI and reports host info through preload.
- Engine BrowserView is detached until the workspace calls `serapiHost.showEngine()`
  (the toolbar’s “引擎” button).
- Both views share the `persist:serapi` profile.
- The engine page defaults to a placeholder; step 2 injects the same bridge bundle
  as `app/bridge.py` through `bridge-inject.js` + `qwebchannel-shim.js`.
- Set a server URL for the engine only through the environment at this stage:

  ```powershell
  $env:SERAPI_ENGINE_URL="https://your-server/memoqweb"
  npm start -- --no-sandbox
  ```

- Web welcome surface: server input, recent servers, connect, and “先看工作区”.
  Connect saves the URL through the sidecar, then loads it in the Engine View.
  `Ctrl+Shift+W` returns from the Engine View.
- `sidecar.py` is spawned on startup (JSON-lines RPC); `ping`, `version`,
  `config.*`, and `workspace.snapshot` are available. Workspace API:
  `serapiHost.sidecar.call(method, params)`.
- The workspace boots from `workspace.snapshot`. It first tries the real path
  (`Engine listRows` → sidecar `workspace.normalize`) and falls back to the
  synthetic fixture `fixtures/workspace-demo.json` when the Engine is not ready.
- Real-path E2E fixture: `fixtures/engine-rows-demo.json` +
  `engine/fixture-api.html`; run with `SERAPI_ENGINE_FIXTURE_API=1` and
  `SERAPI_WORKSPACE_ONLY=1` to see synthetic rows rendered through the
  Engine → sidecar → workspace chain. Selecting a row loads `readSegment`
  detail, `segmentInfo`, and runs the real `lint.js` QA engine.
- QA rules come from sidecar `qa.config` (`app/qa_rules.json`); the lint
  execution stays in the Engine page via `engine:lint`.
- TM/TB hits: Engine `tmHitsReq` + `tmHitsPoll` → sidecar
  `workspace.normalize_hits` → right-rail list and pinned detail.
- Context: `previewContextReq` + `preview-context` events are forwarded from the
  Engine through `engine:event`; sidecar `workspace.normalize_context` builds the
  five-line ribbon.
- Dictionary: selecting a word in the paired editor calls sidecar
  `dictionary.query` (reuses `app/assets.py`, personal library first, no TB).
  No full-text scan; no hit → section stays hidden.
- Write path (synthetic fixture only): `Ctrl+S` / `Ctrl+Enter` asks sidecar
  `write.decide` first, then calls Engine `writeSegment` / `confirmSegment`.
  Segments containing tags are currently blocked. Real memoQ write-back is
  **待真机验证**.
- Settings surface: theme (warm jade/dark), editor font size 12–28, line style
  (zebra/focus), shortcut hints. Persisted via sidecar `config.update`; unknown
  legacy app.json keys are preserved.
- Reverse Engine API: `serapiHost.invokeEngineApi(method, args)` → restricted
  `window.__md.api.<method>` call. The allowlist is `engine-api-allowlist.json`.
- Tests: `npm test` runs host + sidecar contract guards.

  The IPC path `serapiHost.loadEngine(url)` validates http/https and rejects
  credentials embedded in the URL. It will be wired to the Web account/welcome
  page in step 4.

## Engine smoke

The host can verify a real memoQ login page without logging its URL:

```powershell
$env:SERAPI_ENGINE_URL=$url
$env:SERAPI_ENGINE_SHOW="1"
$env:SERAPI_ENGINE_SMOKE="1"
$env:SERAPI_SMOKE_EXIT="1"
npm start -- --no-sandbox
```

Expected line: `ENGINE_SMOKE: ready (login page loaded, bridge injected)`.
Logs must not include the server origin, project GUID or page content.

## Bridge fixture

A synthetic page verifies the injection pipeline without a memoQ server:

```powershell
$env:SERAPI_ENGINE_FIXTURE="1"
$env:SERAPI_ENGINE_SHOW="1"
$env:SERAPI_CAPTURE="preview-electron.png"
$env:SERAPI_CAPTURE_ENGINE="preview-engine-fixture.png"
npm start -- --no-sandbox
```

Expected main-process log: `[serapi] engine event: bridge-ready`.
Screenshot: `preview-engine-fixture.png`.

The fixture contains no project data, credentials or real server URL.

## Not done yet

- Real memoQ login/project navigation and cookie persistence verification.
- Reverse bridge channel (main/Python calling `window.__md.api.*`).
- SSO popups, downloads, certificate errors and proxy parity.
- Python sidecar and actual data wiring.
- PyQt removal.
