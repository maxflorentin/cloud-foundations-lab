'use strict';
const express    = require('express');
const crypto     = require('crypto');
const path       = require('path');
const log        = require('./log');
const consumers  = require('./consumers');
const { validate, checkRate } = require('./validate');

const PORT     = process.env.PORT || 3000;
const RESUME   = process.argv.includes('--resume');
const SIMULATE = process.argv.includes('--simulate');

if (RESUME) log.resume();

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

// ── SSE ───────────────────────────────────────────────────────────────────────
const sseClients = new Set();

function broadcast(data) {
  const msg = 'data: ' + JSON.stringify(data) + '\n\n';
  for (const res of sseClients) {
    try { res.write(msg); }
    catch (_) { sseClients.delete(res); }
  }
}

// ── Tick: consume + broadcast cada 250ms ─────────────────────────────────────
let tickCount = 0;
setInterval(() => {
  consumers.tick();
  broadcast(consumers.snapshot());
  if (++tickCount % 60 === 0) {
    // heartbeat cada 15s — imprescindible contra el proxy de Codespaces
    for (const res of sseClients) {
      try { res.write(': ping\n\n'); }
      catch (_) { sseClients.delete(res); }
    }
  }
}, 250);

// ── Rutas ─────────────────────────────────────────────────────────────────────

app.get('/',          (_, res) => res.sendFile(path.join(__dirname, '..', 'public', 'index.html')));
app.get('/dashboard', (_, res) => res.sendFile(path.join(__dirname, '..', 'public', 'dashboard.html')));

// Ingesta — el servidor NO deduplica; eso lo decide cada consumidor
app.post('/events', (req, res) => {
  const ip = (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.socket.remoteAddress;
  if (!checkRate(ip)) return res.status(429).json({ error: 'Rate limit: 5 eventos/segundo' });
  const v = validate(req.body);
  if (!v.ok) return res.status(400).json({ errors: v.errors });
  const entry = log.append({ event_id: v.event_id, user: v.user, numero: v.numero, ts: Date.now() });
  res.status(202).json({ offset: entry.offset, partition: entry.partition });
});

// SSE — estado completo cada 250ms + heartbeat cada 15s
app.get('/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('X-Accel-Buffering', 'no');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
  res.write('data: ' + JSON.stringify(consumers.snapshot()) + '\n\n');
  sseClients.add(res);
  req.on('close', () => sseClients.delete(res));
});

// Log crudo — para proyectar en clase
app.get('/log', (req, res) => {
  const from  = Math.max(0, parseInt(req.query.from)  || 0);
  const limit = Math.min(500, parseInt(req.query.limit) || 100);
  res.json({ events: log.read(from, limit), total: log.length() });
});

// Admin
app.post('/admin/replay', (_, res) => {
  consumers.replay();
  res.json({ ok: true, message: 'Checkpoints en 0 — releerán desde offset 0 en el próximo tick' });
});

app.post('/admin/idempotent', (req, res) => {
  const enabled = !!req.body.enabled;
  consumers.moda.setIdempotent(enabled);
  res.json({ ok: true, idempotent: enabled });
});

app.post('/admin/reset', (_, res) => {
  log.reset();
  consumers.replay();
  res.json({ ok: true, message: 'Log vaciado' });
});

app.get('/healthz',  (_, res) => res.json({ ok: true, events: log.length(), clients: sseClients.size }));
app.get('/snapshot', (_, res) => res.json(consumers.snapshot()));

// ── Modo simulación ───────────────────────────────────────────────────────────
// Genera 30 productores virtuales — plan B si el puerto público falla el día de clase
if (SIMULATE) {
  const NAMES = Array.from({ length: 30 }, (_, i) => `alumno${i + 1}`);
  console.log('[simulate] 30 productores virtuales activos');

  function simulateOne() {
    const user   = NAMES[Math.floor(Math.random() * NAMES.length)];
    const numero = Math.floor(Math.random() * 100) + 1;
    log.append({ event_id: crypto.randomUUID(), user, numero, ts: Date.now() });
    setTimeout(simulateOne, 400 + Math.random() * 800);
  }

  // 4 "alumnos" activos en paralelo dan ~4-5 eventos/segundo — ritmo realista
  for (let i = 0; i < 4; i++) setTimeout(simulateOne, Math.random() * 500);
}

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\nclase15-live-events en http://localhost:${PORT}`);
  console.log(`  Dashboard : http://localhost:${PORT}/dashboard`);
  console.log(`  Productor : http://localhost:${PORT}/`);
  console.log(`  Modo      : ${RESUME ? 'resume' : SIMULATE ? 'simulate' : 'normal'}\n`);
});
