# Lab 15 — Streaming: append-only log, consumidores y lag

**Clase:** 15 · **Tiempo estimado:** 45–60 min · **Entregable:** `NombreApellido.md`

> **Objetivo:** entender el modelo de log distribuido que subyace a Kafka y Kinesis
> observando en vivo cómo múltiples consumidores independientes leen el mismo log
> a distintas velocidades, con distintas semánticas de deduplicación.
>
> Al terminar tenés que poder responder con evidencia:
> 1. ¿Por qué todos los eventos de un mismo usuario siempre caen en la misma partición?
> 2. ¿Qué pasa cuando un consumidor se reinicia desde offset 0 (replay)?
> 3. ¿Qué es el lag y cómo se traduce a `IteratorAgeMilliseconds` en Kinesis?
> 4. ¿Qué diferencia hay entre que el servidor deduplique vs que lo haga el consumidor?

---

## Contexto del sistema

El servidor de clase expone un **log append-only** — el mismo primitivo que usa
Kafka (topic/offset) o Kinesis (stream/sequence-number).

```
POST /events  →  append al log  →  fan-out a 5 consumidores independientes
                                    ├── usuarios    (usuarios únicos)
                                    ├── mas_activo  (quién mandó más)
                                    ├── moda        (número más elegido — rompible)
                                    ├── ventana     (tumbling window 10s)
                                    └── lento       (simula 400ms por evento)
```

Cada consumidor tiene su propio **checkpoint** (offset hasta donde leyó).
El lag es `logLength - checkpoint`.

---

## Paso 1 — Conectarte como productor

Abrí en el celular (o en una pestaña del navegador) la URL que te va a dar el
profesor. Es la página del productor.

Completá tu nombre y elegí un número entre 1 y 100. Enviá un evento con **ENVIAR**.

En el feedback vas a ver:

```
offset 5
particion 2 · id …a3f8c2d1
```

Anotá en el entregable:
- Tu offset
- Tu partición

Enviá un segundo evento con un número distinto. ¿Cambió la partición? ¿Por qué sí o no?

> El servidor calcula `particion = hash(nombre) % 3`. El hash de tu nombre es
> siempre el mismo → todos tus eventos van al mismo shard. En Kinesis esto se
> llama *partition key*.

---

## Paso 2 — Observar el log en el dashboard

El profesor va a proyectar el dashboard. Mirá el panel izquierdo (el log) y
buscá tus eventos por nombre. Debería aparecer con el mismo color de partición
que te indicó el celular.

Pregunta para el entregable: ¿los eventos de distintos usuarios están mezclados
en el log? ¿Y dentro de tu partición — qué orden tienen?

---

## Paso 3 — Duplicado e idempotencia

Apretá **ENVIAR DUPLICADO** en tu celular (usa el mismo `event_id` dos veces).

Observá en el dashboard el panel **Más elegido (moda)**:
- ¿Subió el conteo del número que enviaste?
- ¿Lo hizo una vez o dos?

Ahora el profesor va a activar **Idempotencia** (`I` en el dashboard o badge amarillo).

Apretá **ENVIAR DUPLICADO** de nuevo. ¿Qué pasó con el conteo esta vez?

Para el entregable respondé:
- ¿Quién decidió ignorar el duplicado: el log, el servidor de ingesta, o el consumidor?
- ¿Cómo lo hizo técnicamente? (pista: `event_id`)
- ¿En qué se parece esto a una tabla de idempotency keys en DynamoDB?

---

## Paso 4 — Ráfaga y lag

Apretá **RAFAGA x10** (manda 10 eventos del mismo número en rápida sucesión).

Mirá en el dashboard la barra inferior (**lag indicators**):

- `usuarios`, `mas_activo`, `moda`, `ventana` → deberían tener lag ≈ 0 (alcanzaron el final del log casi instantáneamente)
- `lento` → va a tener lag > 0 (simula un consumidor que tarda 400ms por evento)

Esperá hasta que el punto de `lento` vuelva a verde (lag = 0).

Para el entregable respondé:
- ¿El log esperó a que `lento` terminara antes de aceptar nuevos eventos? ¿Por qué no?
- ¿Qué pasa con los datos mientras `lento` tiene lag? ¿Se pierden?
- En Kinesis, ¿cómo se llama la métrica que mide este lag?

---

## Paso 5 — Replay

El profesor va a presionar **Replay** (`R`).

Todos los consumidores van a resetear su checkpoint a 0 y releer el log
completo desde el principio. Observá en el dashboard cómo se reconstruyen
los números, la moda y los conteos.

Para el entregable respondé:
- ¿El resultado final fue idéntico al original?
- ¿Qué propiedad del log hace posible el replay?
- ¿Cómo se llama esta operación en Kinesis? ¿Y en Kafka?

---

## Paso 6 — Consultar el log crudo (opcional)

Podés ver el log crudo completo con:

```bash
curl "URL_DEL_SERVIDOR/log?from=0&limit=50"
```

Buscá tus propios eventos por nombre. Verificá que el campo `partition`
coincide con lo que viste en el celular.

También podés ver el estado actual de todos los consumidores:

```bash
curl "URL_DEL_SERVIDOR/snapshot"
```

---

## Entregable — `NombreApellido.md`

1. Tu primer evento: offset y partición recibidos.
2. Respuesta a: ¿por qué el mismo usuario siempre va a la misma partición?
3. Observación del duplicado — comportamiento antes y después de activar idempotencia.
4. Observación del lag en `lento` — ¿cuánto tiempo tardó en recuperarse aproximadamente?
5. Respuesta a: ¿qué pasa con los datos de un consumidor con lag si el servidor se reinicia?
6. Observación del replay — ¿el estado final fue idéntico?
7. Tres líneas de cierre:
   - Una diferencia entre este log en memoria y Kinesis/Kafka real.
   - ¿En qué caso necesitarías idempotencia en un pipeline de producción?
   - ¿Por qué el lag del consumidor lento no afectó a los demás?

### Criterios de corrección

| # | Criterio | Peso |
|---|---|---|
| 1 | Observación propia del log con offset y partición propios | 20% |
| 2 | Explicación correcta de particionado por partition key | 20% |
| 3 | Diferencia observada con/sin idempotencia + explicación de cómo funciona | 25% |
| 4 | Explicación de lag y desacople productor/consumidor | 20% |
| 5 | Replay — propiedad del log que lo hace posible + equivalente en prod | 15% |

---

## Equivalencias con producción

| Pieza del lab | Equivalente en producción |
|---|---|
| Array + `events.ndjson` | Kinesis Data Stream / tópico Kafka |
| `offset` | sequence number / offset |
| `hash(user) % 3` | partition key → shard |
| `checkpoint` de cada consumidor | checkpoint en DynamoDB (KCL) / consumer group offset |
| Replay desde offset 0 | `TRIM_HORIZON` en Kinesis / `auto.offset.reset=earliest` en Kafka |
| `Set` de `event_id` en moda | tabla de deduplicación / idempotency key |
| lag del consumidor lento | `IteratorAgeMilliseconds` / consumer lag |
| tick de 250ms | Lambda event source mapping con batch size |

---

## Referencias

- Kinesis Data Streams: https://docs.aws.amazon.com/streams/latest/dev/introduction.html
- Kinesis consumer lag (`IteratorAgeMilliseconds`): https://docs.aws.amazon.com/streams/latest/dev/monitoring-with-cloudwatch.html
- Kafka consumer group offsets: https://kafka.apache.org/documentation/#intro_consumers
- Idempotent consumers: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
