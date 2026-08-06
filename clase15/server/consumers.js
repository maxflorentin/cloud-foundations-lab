'use strict';
const log = require('./log');

const WINDOW_MS = 10_000;

function topN(map, n = 3) {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([numero, count]) => ({ numero, count }));
}

// ── C1: últimos 12 ────────────────────────────────────────────────────────────
// Enseña: el log es una secuencia con posición, no un conjunto sin orden.
const ultimos = {
  name: 'ultimos', checkpoint: 0,
  state: { items: [] },
  handle(ev) {
    this.state.items.push({
      offset: ev.offset, user: ev.user, numero: ev.numero, partition: ev.partition,
    });
    if (this.state.items.length > 12) this.state.items.shift();
  },
  reset() { this.checkpoint = 0; this.state = { items: [] }; },
};

// ── C2: usuarios únicos ───────────────────────────────────────────────────────
// Enseña: deduplicación por clave de negocio — cuántos participantes distintos.
const usuarios = {
  name: 'usuarios', checkpoint: 0,
  state: { users: new Set(), count: 0 },
  handle(ev) {
    this.state.users.add(ev.user);
    this.state.count = this.state.users.size;
  },
  reset() { this.checkpoint = 0; this.state = { users: new Set(), count: 0 }; },
};

// ── C3: alumno más activo ─────────────────────────────────────────────────────
// Enseña: agregación por partition key — quién produjo más eventos.
const mas_activo = {
  name: 'mas_activo', checkpoint: 0,
  state: { counts: new Map(), user: null, total: 0 },
  handle(ev) {
    const c = (this.state.counts.get(ev.user) || 0) + 1;
    this.state.counts.set(ev.user, c);
    if (c > this.state.total) { this.state.user = ev.user; this.state.total = c; }
  },
  reset() { this.checkpoint = 0; this.state = { counts: new Map(), user: null, total: 0 }; },
};

// ── C4: moda (rompible por duplicados) ───────────────────────────────────────
// Enseña: no toda agregación es idempotente; el consumidor decide, no el log.
const moda = {
  name: 'moda', checkpoint: 0, idempotent: false,
  state: { counts: new Map(), seen: new Set(), top: [] },
  handle(ev) {
    if (this.idempotent && this.state.seen.has(ev.event_id)) return;
    if (this.idempotent) this.state.seen.add(ev.event_id);
    const c = (this.state.counts.get(ev.numero) || 0) + 1;
    this.state.counts.set(ev.numero, c);
    this.state.top = topN(this.state.counts);
  },
  // reset() limpia estado pero NO toca la bandera idempotent — la gestiona setIdempotent
  reset() {
    this.checkpoint = 0;
    this.state = { counts: new Map(), seen: new Set(), top: [] };
  },
  // Cambia el modo y recalcula desde offset 0 — este es el momento "ahhh" del lab
  setIdempotent(val) {
    this.idempotent = val;
    this.reset();
    const events = log.read(0);
    for (const ev of events) this.handle(ev);
    this.checkpoint = log.length();
  },
};

// ── C5: ventana tumbling 10s ──────────────────────────────────────────────────
// Enseña: ventanas de tiempo vs total acumulado; picos visibles.
const ventana = {
  name: 'ventana', checkpoint: 0,
  state: { actual: null, previas: [] },
  _wKey: null, _wEvents: [],
  handle(ev) {
    const wKey = Math.floor(ev.ts / WINDOW_MS) * WINDOW_MS;
    if (this._wKey !== null && wKey !== this._wKey) {
      // cerrar ventana actual y archivarla
      const avg = this._wEvents.reduce((s, e) => s + e.numero, 0) / this._wEvents.length;
      this.state.previas.unshift({
        desde: this._wKey,
        count: this._wEvents.length,
        avg: +avg.toFixed(1),
      });
      if (this.state.previas.length > 5) this.state.previas.pop();
      this._wEvents = [];
    }
    this._wKey = wKey;
    this._wEvents.push(ev);
    const avg = this._wEvents.reduce((s, e) => s + e.numero, 0) / this._wEvents.length;
    this.state.actual = { desde: this._wKey, count: this._wEvents.length, avg: +avg.toFixed(1) };
  },
  reset() {
    this.checkpoint = 0;
    this.state = { actual: null, previas: [] };
    this._wKey = null; this._wEvents = [];
  },
};

// ── C6: lento (400 ms por evento) ─────────────────────────────────────────────
// Enseña: lag, backpressure, desacople productor/consumidor.
// Procesa máximo 1 evento por tick (tick = 250ms), con un gap mínimo de 400ms.
const lento = {
  name: 'lento', checkpoint: 0, _nextAt: 0,
  state: { counts: new Map(), top: [] },
  handle(ev) {
    const c = (this.state.counts.get(ev.numero) || 0) + 1;
    this.state.counts.set(ev.numero, c);
    this.state.top = topN(this.state.counts);
  },
  reset() {
    this.checkpoint = 0; this._nextAt = 0;
    this.state = { counts: new Map(), top: [] };
  },
};

const all = [ultimos, usuarios, mas_activo, moda, ventana, lento];

function tick() {
  const total = log.length();
  for (const c of all) {
    if (c === lento) {
      // 400ms mínimo entre eventos — así se acumula el lag
      if (c.checkpoint < total && Date.now() >= c._nextAt) {
        const [ev] = log.read(c.checkpoint, 1);
        c.handle(ev);
        c.checkpoint++;
        c._nextAt = Date.now() + 400;
      }
    } else {
      if (c.checkpoint < total) {
        const events = log.read(c.checkpoint);
        for (const ev of events) c.handle(ev);
        c.checkpoint = total;
      }
    }
  }
}

// Replay: pone todos los checkpoints en 0 y limpia el state.
// Al siguiente tick cada consumidor releerá desde offset 0 y recalculará.
// Resultado idéntico al original — eso es lo que hace especial al log.
function replay() {
  for (const c of all) c.reset();
}

function snapshot() {
  const total = log.length();
  return {
    logLength: total,
    consumers: {
      usuarios:   { lag: total - usuarios.checkpoint,   count: usuarios.state.count },
      mas_activo: { lag: total - mas_activo.checkpoint, user: mas_activo.state.user, total: mas_activo.state.total },
      moda:       { lag: total - moda.checkpoint, idempotent: moda.idempotent, top: moda.state.top },
      ventana:    { lag: total - ventana.checkpoint, ...ventana.state },
      lento:      { lag: total - lento.checkpoint,   top: lento.state.top },
    },
    ultimos: ultimos.state.items,
  };
}

module.exports = { all, tick, replay, snapshot, moda };
