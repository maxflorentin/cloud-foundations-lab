'use strict';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SAFE_USER_RE = /^[\w\s\-\.]{1,20}$/;

// Sliding-window rate limiter: 5 eventos/segundo por IP
const _rl = new Map();
setInterval(() => {
  const cutoff = Date.now() - 2000;
  for (const [ip, times] of _rl) {
    if (!times.length || times[times.length - 1] < cutoff) _rl.delete(ip);
  }
}, 10_000);

function checkRate(ip) {
  const now = Date.now();
  const times = (_rl.get(ip) || []).filter(t => now - t < 1000);
  times.push(now);
  _rl.set(ip, times);
  return times.length <= 5;
}

function validate(body) {
  const errs = [];
  const rawUser = typeof body.user === 'string' ? body.user.trim().slice(0, 20) : '';
  if (!rawUser || !SAFE_USER_RE.test(rawUser)) errs.push('user: 1-20 caracteres alfanuméricos');
  const numero = Number(body.numero);
  if (!Number.isInteger(numero) || numero < 1 || numero > 100) errs.push('numero: entero entre 1 y 100');
  if (!UUID_RE.test(body.event_id || '')) errs.push('event_id: UUID v4 requerido');
  if (errs.length) return { ok: false, errors: errs };
  return { ok: true, user: rawUser, numero, event_id: body.event_id };
}

module.exports = { validate, checkRate };
