// Engine preload: controlled transport between the memoQ page and Electron main.
// The bridge bundle is injected into the main world by main.js.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('serapiEngine', {
  ready: true,
  host: 'electron-migration',
  push: (payload) => ipcRenderer.send('engine:bridge', String(payload)),
});
