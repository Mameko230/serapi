// Workspace preload: the only host API exposed to the local Web UI.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('serapiHost', {
  showEngine: () => ipcRenderer.invoke('engine:show'),
  hideEngine: () => ipcRenderer.invoke('engine:hide'),
  info: () => ipcRenderer.invoke('host:info'),
});
