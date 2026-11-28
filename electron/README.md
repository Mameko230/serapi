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

## Launch the packaged app

On this machine use the launcher, not `Serapi.exe` directly:

```text
repo\start-electron.cmd
```

or:

```text
repo\electron\dist\win-unpacked\run-serapi.cmd
```

If you unzip `electron\dist\Serapi-0.1.0-win.zip`, run `run-serapi.cmd` inside
the extracted folder. `Serapi.exe` needs `--no-sandbox` on this Windows profile;
the launcher supplies it and clears `ELECTRON_RUN_AS_NODE`.

## Build

Windows:

```powershell
npm install
npm run build:sidecar   # one-directory Python sidecar (requires .venv314 + pyinstaller)
npm run dist:dir        # unpacked app in dist/win-unpacked
npm run dist:zip        # unsigned distributable zip
```

macOS (arm64, built and smoke-tested on Apple silicon):

```bash
python3 -m venv .venv314          # repo-root venv; .venv314/bin/python3 is auto-detected
.venv314/bin/python3 -m pip install pyinstaller
cd electron
npm install
npm run dist:mac:dir   # unpacked dist/mac-arm64/Serapi.app
npm run dist:mac       # dist/Serapi-<version>-arm64-mac.dmg + .zip
```

To start the unpacked app from Finder, double-click the repository-root
`start-serapi.command` (already `chmod +x`). For source development, `npm start`
works on macOS without `--no-sandbox` or `SERAPI_DISABLE_SINGLE_INSTANCE=1`.

The sidecar binary is platform-specific: `serapi-sidecar.exe` on Windows,
extension-less Mach-O on macOS. PyInstaller data paths use the host platform
separator. macOS builds are unsigned (no Developer ID certificate); Gatekeeper
requires right-click → Open on first launch of the zip/dmg build.

Packaged layout:

```text
resources/
├─ app/                    bridge scripts + page_rules
├─ sidecar/                one-directory Python sidecar
│  └─ serapi-sidecar(.exe)
└─ app.asar                workspace/engine/main/preload
```

### Icon assets

There is one Serapi mark: `workspace/icon-a.svg` (the same file the in-app brand
and the design prototype use). Everything else is derived from it, so the Dock
icon, the menu bar icon and the brand inside the window cannot drift apart:

| file | derived from | used by |
|---|---|---|
| `assets/Serapi.icns` | `icon-a.svg` at 16…1024 | macOS bundle icon (`build.mac.icon`) |
| `assets/tray-mac-22.png`, `tray-mac-44.png` | same, at 22 and 44 px | macOS status item |
| `assets/icon-32.png`, `icon-64.png`, `icon-256.png` | upstream raster set | Windows tray + Windows packaging |

Regenerating the macOS icons after an artwork change (repo-root `.venv314` has
PyQt6, which renders the SVG):

```bash
.venv314/bin/python3 - <<'PY'
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
import sys
app = QGuiApplication(sys.argv[:1])
r = QSvgRenderer('electron/workspace/icon-a.svg')
for size in (16, 32, 64, 128, 256, 512, 1024, 22, 44):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img); r.render(p); p.end()
    img.save(f'/tmp/icon-{size}.png', 'PNG')
PY
# build the iconset (16…512 plus @2x) and convert it
then: iconutil -c icns /tmp/Serapi.iconset -o electron/assets/Serapi.icns
```

Do not add a second artwork set: the earlier macOS bundle icon was a different
design, and having two identities in one binary is what made the tray and the
Dock icon disagree.

The Windows NSIS portable target is currently blocked by an NSIS mmap
failure; use the zip target for now.

## Profile locations

`electron/platform-paths.js` picks the per-user data directory per platform
and `tests/platform-paths.test.js` guards the mapping:

- Windows: `%LOCALAPPDATA%\Serapi` (roaming AppData is rejected by Chromium's
  network sandbox on the development machine)
- macOS: `~/Library/Application Support/Serapi`
- Linux: `$XDG_CONFIG_HOME/Serapi` or `~/.config/Serapi`

## Host shell

- Single-instance lock; the second instance focuses the existing window.
  If Chromium/PID lock creation is denied (ACL-limited profile), startup falls
  back to running without a lock and logs a warning; `SERAPI_STRICT_SINGLE_INSTANCE=1`
  forces strict refusal instead.
- System tray: workspace / memoQ engine / settings / quit.
- Closing the window hides it to the tray; “退出 Serapi” is the explicit exit.
- Global `Ctrl+Shift+W` toggles workspace ↔ engine.
- On this machine the Electron singleton lock file is denied by AppData ACLs;
  smoke/capture runs with `SERAPI_DISABLE_SINGLE_INSTANCE=1`. Normal user
  environments should not need it. Tray/second-instance interaction still needs
  a real-desktop check.

## Bridge fixture

A synthetic page verifies the injection pipeline without a memoQ server:

```bash
SERAPI_ENGINE_FIXTURE=1 SERAPI_ENGINE_SHOW=1 SERAPI_ENGINE_SMOKE=1 \
SERAPI_SMOKE_EXIT=1 SERAPI_CAPTURE=preview-electron.png npm start
```

Expected main-process log: `[serapi] engine event: bridge-ready` and
`ENGINE_SMOKE: ready`. On the Windows dev machine append `--no-sandbox`;
macOS does not need it.

The fixture contains no project data, credentials or real server URL.

## Not done yet

- Real memoQ login/project navigation and cookie persistence verification.
- SSO popups, downloads, certificate errors and proxy parity.
- macOS tray / second-instance / close-to-tray interaction on a real desktop.
- Signed macOS builds (dmg/zip are unsigned; no auto-update path yet).
- PyQt removal.
