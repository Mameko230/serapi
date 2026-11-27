# Serapi Electron migration — handoff

Branch: `electron-migration` (main untouched)

## Done

- Electron 30.5.1 host with Workspace + Engine BrowserViews
- Real memoQ login-page bridge injection verified (`bridge-ready`)
- Web welcome/account surface, server history, config persistence
- Web settings: theme, editor font size, line style
- Workspace real-data path: listRows → sidecar normalize
- Current segment detail: readSegment → token normalization
- QA via existing `lint.js`, segment info, TM/TB hits, context, selected-word dictionary
- Write path skeleton: `Ctrl+S` / `Ctrl+Enter` → sidecar WritePolicy → Engine writeSegment
- Python sidecar with JSON-lines RPC; no PyQt imports
- PyInstaller one-file sidecar; packaged app launches and talks to it
- Electron builder `--dir` and zip; unsigned zip ~111 MB
- Single instance, tray, global `Ctrl+Shift+W`
- Host / sidecar / packaging contract tests; L0 75/75; L1 PASS

## Only remaining before PyQt removal

1. Real memoQ login and open a document.
2. Validate real `listRows` / `readSegment` / `segmentInfo` / `tmHits` / context shapes.
3. Validate real save → confirm → reload; session expiry, tracking, read-only.
4. Validate SSO popups, cookies across restart, refresh injection.
5. Validate tray / close-to-tray / second-instance on a normal desktop.
6. Then delete the PyQt entry point and keep legacy only as a temporary fallback.

## Run

```powershell
cd electron
npm install
npm run build:sidecar
npm run dist:zip
# or
npm start -- --no-sandbox
```

This machine needs `SERAPI_DISABLE_SINGLE_INSTANCE=1` for capture/dev because
the LocalAppData singleton lock file is denied by ACLs.

## Safety

- No real server URL, GUID, account or text is committed or logged.
- Real-project captures must not be committed.
- The synthetic fixtures are marked `synthetic: true`.
