'use strict';
const fs = require('fs');
const path = require('path');
const EventEmitter = require('events');

const DATA_DIR = path.resolve(__dirname, '..', 'data');
const NDJSON = path.join(DATA_DIR, 'events.ndjson');
const PARTITIONS = 3;

const bus = new EventEmitter();
bus.setMaxListeners(50);

let _log = [];
let _ws = null;

// djb2-variant hash — deterministic partition per user
function _hashUser(user) {
  let h = 5381;
  for (let i = 0; i < user.length; i++) {
    h = (((h << 5) + h) ^ user.charCodeAt(i)) >>> 0;
  }
  return h % PARTITIONS;
}

function _openStream() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  _ws = fs.createWriteStream(NDJSON, { flags: 'a' });
}

/**
 * Asigna offset, persiste y notifica. Devuelve la entrada canónica.
 */
function append(event) {
  const entry = {
    offset:    _log.length,
    event_id:  event.event_id,
    user:      event.user,
    numero:    event.numero,
    ts:        event.ts || Date.now(),
    partition: _hashUser(event.user),
  };
  _log.push(entry);
  if (_ws) _ws.write(JSON.stringify(entry) + '\n');
  bus.emit('append', entry);
  return entry;
}

/**
 * Lectura por offset. No consume, no borra.
 * Diez consumidores pueden leer el mismo offset — esta es la diferencia con una cola.
 */
function read(fromOffset = 0, limit) {
  const start = Math.max(0, fromOffset);
  return limit !== undefined ? _log.slice(start, start + limit) : _log.slice(start);
}

function length() {
  return _log.length;
}

/**
 * Vacía el log completamente. Usa antes de empezar la clase.
 */
function reset() {
  _log = [];
  if (_ws) { _ws.end(); _ws = null; }
  if (fs.existsSync(NDJSON)) fs.truncateSync(NDJSON, 0);
  _openStream();
  bus.emit('reset');
}

/**
 * Rehidrata desde events.ndjson. Llamar con --resume al arrancar.
 */
function resume() {
  if (!fs.existsSync(NDJSON)) { _openStream(); return; }
  const lines = fs.readFileSync(NDJSON, 'utf8').trim().split('\n').filter(Boolean);
  for (const line of lines) {
    try { _log.push(JSON.parse(line)); } catch (_) {}
  }
  console.log(`[log] resumed: ${_log.length} eventos desde ${NDJSON}`);
  _openStream();
}

_openStream();

module.exports = { append, read, length, reset, resume, on: bus.on.bind(bus) };
