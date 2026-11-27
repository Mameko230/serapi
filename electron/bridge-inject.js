// Build the same document-level script bundle that app/bridge.py injects via
// QWebEngineScript, but for Electron's main world.
const fs = require('node:fs');
const path = require('node:path');
const manifest = require('./bridge-scripts.json');

function readRequired(file) {
  try { return fs.readFileSync(file, 'utf8'); } catch (err) {
    throw new Error(`bridge injection: missing ${file}: ${err.message}`);
  }
}

function buildBundle(appDir) {
  const shim = readRequired(path.join(__dirname, 'qwebchannel-shim.js'));
  const pageRules = readRequired(path.join(appDir, 'page_rules.json'));
  const parts = [
    '/* serapi electron bridge bundle */',
    shim,
    `window.__MD_PAGE_RULES = ${pageRules};`,
  ];
  manifest.scripts.forEach((name) => {
    const source = readRequired(path.join(appDir, name));
    parts.push(`/* ---- ${name} ---- */`);
    parts.push('try {');
    parts.push(source);
    parts.push(`} catch (e) { try { console.error('[serapi:inject] ${name} ' + (e && e.message)); } catch (_) {} }`);
  });
  parts.push('window.__serapiBridgeInjected = true;');
  return parts.join('\n');
}

module.exports = { buildBundle };
