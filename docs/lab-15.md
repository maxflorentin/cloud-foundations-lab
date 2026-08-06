# Lab 15 — Event-driven: EventBridge, Kafka y cuándo usar qué

**Clase:** 15 · **Tiempo estimado:** 50–65 min · **Entregable:** `NombreApellido.md`

> **Objetivo:** producir y consumir eventos usando EventBridge y Kafka/Redpanda,
> entender la diferencia entre cola (SQS) y log (Kafka/Kinesis), y saber
> elegir el servicio correcto para cada patrón de integración.
>
> Al terminar tenés que poder responder con evidencia:
> 1. ¿Qué pasa con un mensaje de SQS después de que lo lés? ¿Y con un evento de Kafka?
> 2. ¿Cómo EventBridge filtra eventos antes de entregarlos?
> 3. ¿Por qué dos consumer groups distintos pueden leer el mismo topic Kafka de forma independiente?
> 4. ¿En qué caso elegirías Kinesis/Kafka sobre EventBridge? ¿Y sobre SQS?

---

## Prerrequisitos

```bash
docker compose up -d localstack redpanda
```

Verificar:

```bash
awslocal events list-event-buses       # debe listar "default"
rpk cluster health                     # debe mostrar "Healthy: true"
```

> **Si `awslocal` no está disponible**, usá `aws --endpoint-url=http://localhost:4566 --region us-east-1`
> en lugar de `awslocal` en todos los comandos del lab.

---

## Parte A — EventBridge

EventBridge es un **event bus administrado**: los productores publican eventos
con `put-events` y EventBridge los enruta a targets (SQS, Lambda, etc.) según
reglas con filtros de patrón JSON.

### Paso A1 — Bus de eventos y regla con filtro

```bash
# Bus personalizado
awslocal events create-event-bus --name lab-bus

# Cola SQS destino (target)
awslocal sqs create-queue --queue-name eventos-eb

# Regla: solo eventos de source "tienda" con detail-type "Pedido"
awslocal events put-rule \
  --name regla-pedidos \
  --event-bus-name lab-bus \
  --event-pattern '{"source":["tienda"],"detail-type":["Pedido"]}' \
  --state ENABLED

# Conectar la regla a la cola SQS
awslocal events put-targets \
  --rule regla-pedidos \
  --event-bus-name lab-bus \
  --targets '[{"Id":"1","Arn":"arn:aws:sqs:us-east-1:000000000000:eventos-eb"}]'
```

Verificar que la regla quedó activa:

```bash
awslocal events list-rules --event-bus-name lab-bus
```

> **Para el entregable:** ¿qué tiene que cumplir un evento para que la regla lo capture?
> ¿Qué pasa con un evento que NO cumple el patrón?

### Paso A2 — Publicar eventos y observar filtrado

Publicar un evento que **sí** cumple el patrón:

```bash
awslocal events put-events \
  --entries '[{
    "Source": "tienda",
    "DetailType": "Pedido",
    "Detail": "{\"id\":\"P-001\",\"monto\":1500,\"usuario\":\"sofia\"}",
    "EventBusName": "lab-bus"
  }]'
```

Verificar que llegó a la cola:

```bash
awslocal sqs receive-message \
  --queue-url http://localhost:4566/000000000000/eventos-eb \
  --attribute-names All
```

Publicar un evento que **no** cumple el patrón (source distinto):

```bash
awslocal events put-events \
  --entries '[{
    "Source": "sistema-interno",
    "DetailType": "Pedido",
    "Detail": "{\"id\":\"X-001\"}",
    "EventBusName": "lab-bus"
  }]'
```

Revisá la cola de nuevo. ¿Llegó el segundo evento?

> **Para el entregable:** pegá el JSON que devolvió `receive-message` para el primer evento.
> Comparalo con el payload original — ¿qué campos agrega EventBridge?

### Paso A3 — Cuándo usar EventBridge

EventBridge es ideal para **integrar servicios** con filtrado declarativo.
Lo que **no** es: un log replayable ni una cola de alta throughput.

Completá en el entregable:

| Caso | ¿EventBridge? | Alternativa si no |
|---|---|---|
| Notificar a 5 servicios cuando se crea un usuario | | |
| Procesar 50.000 clicks/segundo con replay | | |
| Reaccionar a eventos de otros servicios AWS (ej: S3 object created) | | |
| Cola de trabajo con reintentos y DLQ | | |

---

## Parte B — Kafka / Redpanda

Kafka es un **log distribuido**: los mensajes se persisten en el broker y
múltiples consumidores pueden leerlos de forma independiente, con replay.
Redpanda es 100% compatible con la API Kafka.

### Paso B1 — Crear topic con particiones

```bash
# Topic con 3 particiones — equivalente a 3 shards en Kinesis
rpk topic create cloud-events --partitions 3 --replicas 1

rpk topic list
rpk topic describe cloud-events
```

Anotá en el entregable:
- ¿Cuántas particiones tiene el topic?
- ¿Qué relación tiene la cantidad de particiones con el paralelismo de consumo?

### Paso B2 — Producir con partition key

```bash
python3 scripts/produce_kafka.py
```

El script usa el campo `actor` del evento como **partition key**.
Todos los eventos del mismo actor van a la misma partición — garantiza orden por actor.

> Equivalente en Kinesis: `PartitionKey` en `put_record()`.
> Equivalente en lo que viste en el live de clase: `hash(user) % 3`.

Mirá la salida del script: ¿el offset sube de forma monotónica?

### Paso B3 — Consumir y verificar offsets

```bash
python3 scripts/consume_kafka.py --from-beginning
```

Observá que cada mensaje muestra `offset=N`. El broker recuerda hasta dónde
leyó este consumer group en un campo llamado **committed offset** (checkpoint).

Interrumpí con `Ctrl+C` a mitad de la lectura. Volvé a correr sin `--from-beginning`:

```bash
python3 scripts/consume_kafka.py
```

¿Qué pasó? ¿Leyó los mensajes desde el principio o desde donde quedó?

> En SQS el mensaje se elimina al ser leído (o al expirar la visibility window).
> En Kafka el mensaje **sigue en el log** — el consumer solo avanza su offset.

### Paso B4 — Dos consumer groups independientes

Los consumer groups son la forma en que Kafka aísla el progreso de distintos consumidores.
Cada grupo tiene su propio offset committado — no interfieren entre sí.

En una terminal, corré el consumidor analytics:

```bash
KAFKA_GROUP_ID=analytics-group python3 scripts/consume_kafka.py --from-beginning
```

En otra terminal, corré un segundo consumidor con group distinto:

```bash
KAFKA_GROUP_ID=audit-group python3 scripts/consume_kafka.py --from-beginning
```

Ambos leen los mismos mensajes. En SQS con una cola, el primer consumidor
que lee el mensaje se lo "lleva" — el segundo no lo vería.

> **Para el entregable:** describí con tus palabras por qué esto es imposible en SQS
> pero natural en Kafka/Kinesis.

### Paso B5 — Replay desde offset 0

Con `--from-beginning` el consumidor usa `auto.offset.reset=earliest`,
lo que es equivalente a `TRIM_HORIZON` en Kinesis.

```bash
KAFKA_GROUP_ID=replay-test python3 scripts/consume_kafka.py --from-beginning
```

Contá cuántos mensajes leyó. Volvé a correr el mismo comando:
¿leyó los mismos mensajes de nuevo? ¿Por qué?

> En SQS no existe replay: un mensaje consumido se elimina de la cola.
> En Kafka/Kinesis el log se retiene por un período configurable (default 7 días en Kinesis).

---

## Parte C — Tabla de decisión

Completá en el entregable la siguiente tabla para cada escenario:

| Escenario | Servicio elegido | Razón principal |
|---|---|---|
| Fan-out: un evento → 5 microservicios reaccionan | | |
| Pipeline de ML: re-entrenar el modelo desde datos históricos | | |
| Cola de trabajo: procesar pagos con reintentos y DLQ | | |
| 100k eventos/s de clickstream con múltiples consumidores | | |
| Reaccionar al evento `aws.s3` de un bucket | | |
| Microservicios en la misma cuenta que se notifican entre sí | | |

---

## Paso C1 — Limpieza

```bash
# EventBridge
awslocal events remove-targets --rule regla-pedidos --event-bus-name lab-bus --ids 1
awslocal events delete-rule --name regla-pedidos --event-bus-name lab-bus
awslocal events delete-event-bus --name lab-bus
awslocal sqs delete-queue --queue-url http://localhost:4566/000000000000/eventos-eb

# Kafka
rpk topic delete cloud-events
```

---

## Entregable — `NombreApellido.md`

1. Output de `list-rules` con la regla creada.
2. JSON de `receive-message` del primer evento y comparación con el payload original.
3. Tabla A3 completa (cuándo usar EventBridge).
4. Output de `describe cloud-events` con las 3 particiones.
5. Observación de `consume_kafka.py` interrumpido y reiniciado — ¿desde dónde retomó?
6. Explicación (3–5 líneas) de por qué dos consumer groups son independientes en Kafka pero no en SQS.
7. Tabla de decisión C completa con justificaciones.

### Criterios de corrección

| # | Criterio | Peso |
|---|---|---|
| 1 | EventBridge: regla activa, evento filtrado correctamente y observación de evento que no matchea | 25% |
| 2 | Kafka: topic creado, offsets visibles al consumir, checkpoint correcto al reiniciar | 25% |
| 3 | Diferencia Kafka vs SQS: consumer groups y log retention explicados con evidencia | 25% |
| 4 | Tabla de decisión razonada (no alcanza con nombrar el servicio, hay que justificar) | 25% |

---

## Kinesis: la versión managed de Kafka en AWS

En este lab usamos Kafka/Redpanda localmente porque es más fácil de levantar sin cuenta AWS.
En producción, Kinesis Data Streams ofrece la misma semántica con una API distinta:

| Concepto Kafka | Equivalente Kinesis |
|---|---|
| Topic | Stream |
| Partición | Shard |
| `PartitionKey` | `PartitionKey` en `put_record` |
| Consumer group offset | Checkpoint en DynamoDB (KCL) |
| `auto.offset.reset=earliest` | `TRIM_HORIZON` |
| `--from-beginning` | Iterator type `TRIM_HORIZON` |
| Retención configurable | 24h default, hasta 365 días |

Precio: Kinesis cobra por **shard-hour** ($0.015/shard/hora) más por **payload** ($0.014 por millón de PUT).
Un stream de 1 shard activo todo el mes = ~$11/mes antes de datos.

Para volúmenes medianos-altos con equipo con expertise Kafka: Amazon MSK.
Para integración entre servicios AWS con lógica de enrutamiento: EventBridge.
Para cola simple con reintentos y DLQ: SQS.

---

## Referencias

- EventBridge patterns: https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html
- Kinesis vs SQS vs EventBridge: https://aws.amazon.com/blogs/compute/choosing-between-messaging-services-for-serverless-workloads/
- Kafka consumer groups: https://kafka.apache.org/documentation/#intro_consumers
- Redpanda docs: https://docs.redpanda.com/current/get-started/quick-start/
- Kinesis pricing: https://aws.amazon.com/kinesis/data-streams/pricing/
