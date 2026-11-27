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

- `sidecar.py` is spawned on startup (JSON-lines RPC); `ping`/`version` are the
  first methods. Workspace API: `serapiHost.sidecar.call(method, params)`.
- Reverse Engine API: `serapiHost.invokeEngineApi(method, args)` → restricted
  `window.__md.api.<method>` call. The allowlist is `engine-api-allowlist.json`.
- Tests: `npm test` runs host + sidecar contract guards.

  The IPC path `serapiHost.loadEngine(url)` validates http/https and rejects
  credentials embedded in the URL. It will be wired to the Web account/welcome
  page in step 4.

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
