// Engine preload placeholder. Later this loads the bridge injection and
// exposes a controlled API to the host; for step 1 it only marks readiness.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('serapiEngine', {
  ready: true,
  host: 'electron-migration',
});
