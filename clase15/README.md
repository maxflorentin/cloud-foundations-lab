# clase15-live-events

Servidor de analítica de eventos en tiempo real para el lab de clase 15.
Los alumnos envían números desde el celular; el dashboard proyectado muestra
el log, las métricas y el lag de cada consumidor en vivo.

## Levantar en 3 comandos

```bash
npm install
npm start
# abrir http://localhost:3000/dashboard en el proyector
# compartir http://localhost:3000 con el QR del celular
```

## Modos

```bash
npm start              # modo normal
npm run start:resume   # recupera el log desde data/events.ndjson
npm run start:simulate # 30 productores virtuales (plan B si el puerto falla)
```

## Rutas

| Ruta | Qué es |
|------|--------|
| `/` | Página del alumno (productor, mobile-first) |
| `/dashboard` | Dashboard proyectable |
| `/stream` | SSE — estado completo cada 250ms |
| `/log?from=0&limit=100` | Log crudo en JSON |
| `POST /events` | Ingesta — `{event_id, user, numero}` |
| `POST /admin/replay` | Todos los checkpoints a 0 |
| `POST /admin/idempotent` | `{enabled: true\|false}` en moda |
| `POST /admin/reset` | Vacía el log |
| `/healthz` | Ping |

## Atajos de teclado (dashboard)

| Tecla | Acción |
|-------|--------|
| `R` | Replay — recalcula todo desde offset 0 |
| `I` | Toggle idempotencia en moda |
| `L` | Mostrar/ocultar panel del log |
| `X` | Reset completo (pide confirmación) |

## Checklist T-15min

- [ ] `npm start` corriendo
- [ ] Idle timeout de Codespaces subido a 90 min
- [ ] Puerto 3000 en Público (el devcontainer lo hace solo)
- [ ] Probar desde celular con datos móviles (no wifi del aula)
- [ ] `POST /admin/reset` para arrancar con log vacío
- [ ] Dejar dashboard abierto 2 min y mandar un evento — confirmar que llega en <1s
- [ ] Generar QR con la URL pública real

## Lo que se enseña

| Pieza del lab | Equivalente en producción |
|---|---|
| Array + `events.ndjson` | Kinesis Data Stream / tópico Kafka |
| `offset` | sequence number / offset |
| `hash(user) % 3` | partition key → shard |
| `checkpoint` de cada consumidor | checkpoint en DynamoDB (KCL) / consumer group offset |
| `POST /admin/replay` | leer desde `TRIM_HORIZON` / `auto.offset.reset=earliest` |
| `Set` de `event_id` en moda | tabla de deduplicación / idempotency key |
| lag del consumidor lento | `IteratorAgeMilliseconds` / consumer lag |
| tick de 250ms | Lambda event source mapping con batch size |
