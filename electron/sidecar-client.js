// Newline-delimited JSON-RPC client for the Python sidecar.
const { spawn } = require('node:child_process');

class SidecarClient {
  constructor({ python, script, args, cwd, onLog }) {
    this.python = python;
    this.script = script || null;
    this.args = Array.isArray(args) ? args : null;
    this.cwd = cwd;
    this.onLog = onLog || (() => {});
    this.child = null;
    this.pending = new Map();
    this.nextId = 1;
    this.buffer = '';
  }

  start() {
    if (this.child) return;
    const argv = this.args ? this.args : ['-u', this.script];
    this.child = spawn(this.python, argv, {
      cwd: this.cwd,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    this.child.stdout.setEncoding('utf8');
    this.child.stderr.setEncoding('utf8');
    this.child.stdout.on('data', (chunk) => this._onData(chunk));
    this.child.stderr.on('data', (chunk) => this.onLog('[sidecar] ' + String(chunk).trim()));
    this.child.on('exit', (code, signal) => {
      this.onLog(`[sidecar] exited code=${code} signal=${signal}`);
      for (const entry of this.pending.values()) entry.reject(new Error('sidecar-exited'));
      this.pending.clear();
      this.child = null;
    });
    this.onLog(`[sidecar] started ${this.python}`);
  }

  _onData(chunk) {
    this.buffer += chunk;
    let index;
    while ((index = this.buffer.indexOf('\n')) >= 0) {
      const line = this.buffer.slice(0, index).trim();
      this.buffer = this.buffer.slice(index + 1);
      if (!line) continue;
      let message;
      try { message = JSON.parse(line); } catch (err) {
        this.onLog('[sidecar] bad-json: ' + line.slice(0, 200));
        continue;
      }
      const entry = this.pending.get(message.id);
      if (!entry) continue;
      this.pending.delete(message.id);
      if (message.ok) entry.resolve(message.result);
      else entry.reject(new Error(message.error || 'sidecar-error'));
    }
  }

  call(method, params = {}, timeoutMs = 5000) {
    this.start();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('sidecar-timeout'));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (value) => { clearTimeout(timer); resolve(value); },
        reject: (err) => { clearTimeout(timer); reject(err); },
      });
      try {
        this.child.stdin.write(JSON.stringify({ id, method, params }) + '\n');
      } catch (err) {
        this.pending.delete(id);
        clearTimeout(timer);
        reject(err);
      }
    });
  }

  close() {
    if (!this.child) return;
    try { this.child.stdin.write(JSON.stringify({ id: 0, method: '_shutdown' }) + '\n'); } catch (_) {}
    try { this.child.kill(); } catch (_) {}
    this.child = null;
  }
}

module.exports = { SidecarClient };
