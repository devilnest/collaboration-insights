#!/usr/bin/env node
// collab-progress dashboard server: a tiny read-only web app for viewers that cannot run
// scripts on file:// pages (for example an IDE's or desktop app's built-in browser).
//
//   node serve.mjs [--port 4785] [--data DATA_DIR] [--open]
//
// Node standard library only. Binds to 127.0.0.1, answers GET/HEAD for the dashboard files
// and nothing else, never writes, and reads files fresh on each request, so a new
// `progress.py snapshot` shows up on reload. Exit codes: 0 stopped, 1 error, 2 not configured.
import http from 'node:http';
import fs from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const SKILL_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                '.json': 'application/json; charset=utf-8', '.md': 'text/markdown; charset=utf-8' };
// Only what the dashboard page loads. The tracker database, inbox packets, coaching notes
// and config are never served.
const ROUTES = new Map([['/', 'dashboard.html'], ['/dashboard.html', 'dashboard.html'],
                        ['/dashboard.js', 'dashboard.js'], ['/dashboard-data.js', 'dashboard-data.js']]);

// Same resolution order as progress.py (core.locate_data): --data, COLLAB_PROGRESS_HOME, config.json.
export function locateData(explicit, env = process.env, skillDir = SKILL_DIR) {
  if (explicit) return { dir: path.resolve(explicit), how: '--data' };
  if (env.COLLAB_PROGRESS_HOME) return { dir: path.resolve(env.COLLAB_PROGRESS_HOME), how: 'env:COLLAB_PROGRESS_HOME' };
  const config = path.join(skillDir, 'config.json');
  if (existsSync(config)) {
    const value = JSON.parse(readFileSync(config, 'utf8')).data_dir;
    if (value) return { dir: path.resolve(skillDir, value), how: 'config:' + config };
  }
  return { dir: null, how: 'unconfigured' };
}

export function createServer(reportsDir, { port } = {}) {
  return http.createServer(async (req, res) => {
    const send = (status, body, type = 'text/plain; charset=utf-8') => {
      res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                              'Referrer-Policy': 'no-referrer', 'Cross-Origin-Resource-Policy': 'same-origin' });
      res.end(req.method === 'HEAD' ? undefined : body);
    };
    // Refuse other hosts so a web page cannot reach this server through DNS rebinding.
    const host = (req.headers.host || '').toLowerCase();
    const actual = port ?? req.socket.localPort;
    if (![`127.0.0.1:${actual}`, `localhost:${actual}`].includes(host)) return send(403, 'Forbidden host\n');
    if (req.method !== 'GET' && req.method !== 'HEAD') return send(405, 'Read-only\n');
    const name = ROUTES.get(new URL(req.url, 'http://x').pathname);
    if (!name) return send(404, 'Not found\n');
    try {
      const body = await fs.readFile(path.join(reportsDir, name));
      send(200, body, TYPES[path.extname(name)]);
    } catch (error) {
      if (error.code !== 'ENOENT') return send(500, 'Read error\n');
      send(404, name === 'dashboard.html' || name === 'dashboard-data.js'
        ? `${name} has not been generated yet. Run: progress.py snapshot (or progress.py dashboard)\n` : 'Not found\n');
    }
  });
}

function parseArgs(argv) {
  const args = { port: 4785, data: null, open: false };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === '--port') args.port = Number(argv[++i]);
    else if (flag === '--data') args.data = argv[++i];
    else if (flag === '--open') args.open = true;
    else if (flag === '--help' || flag === '-h') args.help = true;
    else throw new Error('Unknown option ' + flag);
  }
  if (!Number.isInteger(args.port) || args.port < 0 || args.port > 65535) throw new Error('--port must be 0-65535');
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { console.log('node serve.mjs [--port 4785] [--data DATA_DIR] [--open]'); return; }
  const { dir, how } = locateData(args.data);
  if (!dir) {
    console.error(JSON.stringify({ error: 'Data location not chosen; run progress.py setup first', needs_setup: true }));
    process.exit(2);
  }
  const reports = path.join(dir, 'reports');
  if (!existsSync(path.join(reports, 'dashboard.html'))) console.warn('No dashboard yet in ' + reports + ' - run progress.py snapshot');
  const server = createServer(reports, { port: args.port || undefined });
  server.on('error', error => {
    console.error(JSON.stringify({ error: error.code === 'EADDRINUSE' ? `Port ${args.port} is busy; pass --port N (0 picks a free one)` : error.message }));
    process.exit(1);
  });
  server.listen(args.port, '127.0.0.1', () => {
    const url = `http://127.0.0.1:${server.address().port}/`;
    console.log(JSON.stringify({ url, reports, data_chosen_by: how, stop: 'Ctrl+C' }));
    if (args.open) {
      const [cmd, extra] = process.platform === 'win32' ? ['cmd', ['/c', 'start', '', url]] : [process.platform === 'darwin' ? 'open' : 'xdg-open', [url]];
      import('node:child_process').then(({ spawn }) => spawn(cmd, extra, { stdio: 'ignore', detached: true }).unref());
    }
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(JSON.stringify({ error: error.message })); process.exit(1); });
}
