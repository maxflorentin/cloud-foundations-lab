# `messaging/` — Lab 12: Arquitecturas desacopladas

Cuatro archivos que declaran el pipeline SNS → 2 SQS + DLQ + una cola mal-configurada para criticar.

## Arquitectura del lab

```
             ┌──────────────┐
             │ github_events│ (json lines)
             │  producer    │
             └──────┬───────┘
                    │ publish
                    ▼
             ┌──────────────┐
             │ SNS topic    │  events-topic
             │  events-topic│
             └──────┬───────┘
              fan-out (2 subs)
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│ events-       │       │ events-       │
│  analytics    │       │  audit        │
│  (SQS queue)  │       │  (SQS queue)  │
└───────┬───────┘       └───────┬───────┘
        │                       │
        │ consumer (con Redis dedupe)   │
        ▼                       ▼
   procesamiento        auditoría / log

     Si el consumer falla 3 veces:
        │                       │
        └───────────┬───────────┘
                    ▼
             ┌──────────────┐
             │ events-dlq   │  ← poison messages
             └──────────────┘
```

## Archivos

| Archivo | Rol |
|---|---|
| `queues.json` | DLQ + 2 queues principales + policy de `maxReceiveCount` |
| `topic.json` | SNS topic para fan-out |
| `queue-mal-configurada.json` | Cola con 3 problemas de diseño — worksheet Q4 |

## Decisiones documentadas en `queues.json`

- **`MessageRetentionPeriod: 345600`** (4 días) — un consumer caído tiene 4 días para volver antes de perder mensajes
- **`VisibilityTimeout: 30`** — el consumer tiene 30s para procesar antes de que el mensaje vuelva a la cola
- **`maxReceiveCount: 3`** — un mensaje se intenta procesar 3 veces; después va al DLQ
- **DLQ separada** (`events-dlq`) — los poison messages se aíslan para análisis

## Por qué SNS + SQS y no SQS solo

Con **solo SQS**: un mensaje va a UNA cola, un tipo de consumidor lo procesa. Si mañana querés que otro sistema también reaccione al mismo evento, tenés que modificar el productor.

Con **SNS + SQS (fan-out)**: el productor publica una vez al topic. Cada subscriber (cola) recibe una copia. Agregar un nuevo consumer es agregar una subscription — el productor no cambia.

Es **desacople real**: productor no sabe cuántos consumers hay.
