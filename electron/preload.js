// Workspace preload: the only host API exposed to the local Web UI.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('serapiHost', {
  showEngine: () => ipcRenderer.invoke('engine:show'),
  hideEngine: () => ipcRenderer.invoke('engine:hide'),
  loadEngine: (url) => ipcRenderer.invoke('engine:load', String(url)),
  invokeEngineApi: (method, args) => ipcRenderer.invoke('engine:api', String(method), args || []),
  lintEngine: (payload) => ipcRenderer.invoke('engine:lint', payload || {}),
  sidecar: {
    call: (method, params) => ipcRenderer.invoke('sidecar:call', String(method), params || {}),
  },
  onEngineEvent: (handler) => {
    if (typeof handler !== 'function') return () => {};
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on('engine:event', listener);
    return () => ipcRenderer.removeListener('engine:event', listener);
  },
  info: () => ipcRenderer.invoke('host:info'),
});
