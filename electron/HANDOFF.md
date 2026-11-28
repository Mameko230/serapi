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
- macOS arm64 packaging: dmg + zip, `Serapi.icns`, `.command` launcher, platform-specific profile and extension-less Mach-O sidecar; four Electron contract guards PASS, packaged sidecar ping/version PASS on Python 3.14.10.

## Only remaining

1. Real memoQ login and open a document.
2. Validate real `listRows` / `readSegment` / `segmentInfo` / `tmHits` / context shapes.
3. Validate real save → confirm → reload; session expiry, tracking, read-only.
4. Validate SSO popups, cookies across restart, refresh injection.
5. Validate tray / close-to-tray / second-instance on a normal desktop.
6. Validate unsigned macOS dmg/zip first launch, Gatekeeper flow, and signing/notarization needs.

PyQt/Qt source is intentionally kept in this branch as the legacy fallback and
test baseline. The packaged Electron artifact does not depend on it.

## Run

Use the launcher (this machine needs `--no-sandbox`):

```text
repo\start-electron.cmd
```

Or the packaged launcher:

```text
repo\electron\dist\win-unpacked\run-serapi.cmd
```

Development:

```powershell
cd electron
npm install
npm run build:sidecar
npm run dist:zip
npm start -- --no-sandbox
```

Development on macOS:

```bash
python3 -m venv .venv314
.venv314/bin/python3 -m pip install pyinstaller
cd electron
npm install
npm start               # no --no-sandbox / singleton workaround needed
npm run dist:mac
```

This Windows machine needs `SERAPI_DISABLE_SINGLE_INSTANCE=1` for capture/dev because
the LocalAppData singleton lock file is denied by ACLs.

## Safety

- No real server URL, GUID, account or text is committed or logged.
- Real-project captures must not be committed.
- The synthetic fixtures are marked `synthetic: true`.
