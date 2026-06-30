# Lab 04 — Streaming: Redpanda / Kafka

**Clase:** 15 · **Tiempo estimado:** 30-40 min

Objetivo: entender la diferencia entre cola (queue) y stream, producir y consumir mensajes en un topic Kafka local con Redpanda.

## Queue vs Stream — diferencia clave

| Queue (SQS)                        | Stream (Kafka / Redpanda)              |
|------------------------------------|----------------------------------------|
| Mensaje leído → desaparece         | Mensaje leído → sigue en el log        |
| Un consumidor por mensaje          | Múltiples consumer groups              |
| Ideal para trabajo distribuido     | Ideal para replay, múltiples lectores  |
| Retención: mientras no se procese  | Retención: configurable (horas/días)   |

## Prerrequisitos

- `docker compose up -d redpanda`
- `pip install kafka-python-ng` (o ya en `requirements.txt`)

## Paso 1 — Levantar Redpanda

```bash
docker compose up -d redpanda
docker compose ps redpanda
```

Esperar a que el healthcheck muestre `healthy` (puede tardar 30-40 segundos).

## Paso 2 — Crear el topic

```bash
docker exec cloud-foundations-redpanda \
  rpk topic create cloud-events --partitions 1 --replicas 1
```

Listar topics:

```bash
docker exec cloud-foundations-redpanda rpk topic list
```

## Paso 3 — Producir eventos

```bash
python scripts/produce_kafka.py
```

El script lee `data/raw/events.jsonl` y publica cada evento como mensaje en el topic `cloud-events`.

Salida esperada:

```
Topic: cloud-events @ localhost:9092
Publicado: signup  | user_id=1 (offset=0)
Publicado: login   | user_id=1 (offset=1)
Publicado: signup  | user_id=2 (offset=2)
...
Total publicados: 8 mensajes
```

## Paso 4 — Consumir en tiempo real

En una terminal separada (o con `&`):

```bash
python scripts/consume_kafka.py
```

Salida esperada:

```
Consumidor 'analytics-group' en cloud-events @ localhost:9092
[offset=0] signup  | user_id=1, country=AR
[offset=1] login   | user_id=1
...
Esperando mensajes... (Ctrl+C para salir)
```

## Paso 5 — Replay desde el inicio

La diferencia clave: podés releer todos los mensajes desde el offset 0.

```bash
python scripts/consume_kafka.py --from-beginning
```

Esto demuestra que Kafka/Redpanda no destruye los mensajes al consumirlos.

## Paso 6 — Explorar con rpk (CLI)

```bash
# Ver mensajes directamente
docker exec cloud-foundations-redpanda \
  rpk topic consume cloud-events --num 5

# Ver estado del cluster
docker exec cloud-foundations-redpanda rpk cluster health
```

---

## Entregable de clase

Al finalizar deberías poder mostrar:

- Salida de `produce_kafka.py` con offsets asignados
- Salida de `consume_kafka.py` leyendo los mensajes
- Demostración de replay con `--from-beginning`
- Diferencia queue/stream explicada en tus palabras

---

## Conexión conceptual (AWS)

| Local                              | AWS equivalente                    |
|------------------------------------|------------------------------------|
| Redpanda / Kafka                   | Amazon Kinesis o Amazon MSK        |
| Topic `cloud-events`               | Kinesis stream o MSK topic         |
| `rpk topic create`                 | `aws kinesis create-stream`        |
| Consumer group                     | Kinesis shard iterator             |
| Offset (replay desde 0)            | Kinesis sequence number / AT_TIMESTAMP |
| Retención configurable             | Kinesis: 24h-365d; MSK: configurable |
