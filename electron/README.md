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
- The engine page is a placeholder; step 2 replaces it with the real memoQ URL
  and the existing bridge injection.

See [docs/electron-migration.md](../docs/electron-migration.md) for the phased plan.
