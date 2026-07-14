# Lab 12 — Arquitecturas desacopladas: SNS + SQS + DLQ + cache

Este lab tiene 4 partes con preguntas numeradas — la entrega es `docs/messaging-proyecto.md` (copia de este archivo con respuestas).

> **El punto de fondo**
> El productor no sabe cuántos consumidores hay. El consumidor no sabe cuándo llegará el próximo mensaje. Ese "no saber" es lo que hace el sistema **desacoplado**: cada pieza puede caerse, escalarse o modificarse sin afectar al resto.

---

## Prerequisitos

- Branch `lab-12-tuNombre` desde main
- ministack + redis levantados: `docker compose up -d localstack redis`
- Deps Python: `pip install -r requirements.txt` (redis + boto3)
- Data disponible: `data/raw/events/github_events.jsonl` (viene del lab 02)

Verificar:
```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool | grep -iE "sqs|sns"
docker exec cloud-foundations-redis redis-cli ping   # → PONG
```

---

## Copiar el workbook

```bash
cp docs/lab-12.md docs/messaging-proyecto.md
$EDITOR docs/messaging-proyecto.md
```

Todas las Q se responden en la copia.

---

## Correr el demo (parte mecánica)

```bash
python3 scripts/messaging_demo.py --messages 5
```

Output esperado: crea DLQ + 2 queues + topic + subscriptions, publica 5 eventos, los consume con dedupe Redis, y demuestra el pipeline poison → DLQ.

Si eso no corre, no sigas — el pipeline base está roto.

---

## Parte 1 — Entender el fan-out

**Q1.** El demo publica 5 eventos al topic. Pero el consumer procesa 5 en la queue `events-analytics`. ¿Cuántos mensajes en total generaron esos 5 publish? Verificalo:

```bash
awslocal sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/events-audit \
  --attribute-names ApproximateNumberOfMessages
```

Explicá qué pasó y por qué se llama **fan-out**.

**Q2.** El `messaging_demo.py` consume de `events-analytics` pero no de `events-audit`. Después de correr el demo, ¿qué contiene `events-audit`? Recibí mensajes de ahí y verificá:

```bash
awslocal sqs receive-message \
  --queue-url http://localhost:4566/000000000000/events-audit \
  --max-number-of-messages 10 \
  --wait-time-seconds 1
```

¿Los mismos mensajes que ya consumió el analytics-consumer? ¿Por qué?

**Q3.** ¿Por qué usar **SNS + SQS** en lugar de **SQS solo con un productor que copia el mensaje a las 2 queues**? Nombrá al menos 2 razones (mirá `messaging/README.md`).

---

## Parte 2 — Criticar la queue mal-configurada

Abrí `messaging/queue-mal-configurada.json`. Tiene **3 problemas de diseño**. Aplicala y examinala:

```bash
awslocal sqs create-queue --cli-input-json file://messaging/queue-mal-configurada.json
awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/cola-legacy \
  --attribute-names All
```

**Q4.** Identificá los 3 problemas:

| # | Campo | Problema | Consecuencia en prod | Corrección |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

_Pistas:_
- Comparala con `messaging/queues.json` — ¿qué atributos tiene una queue "buena" que a esta le faltan?
- El `VisibilityTimeout` está en 5s. Si tu consumer tarda 10s en procesar, ¿qué pasa?
- El `MessageRetentionPeriod` está en 60s (1 minuto). Si un consumer se cae por 2 minutos, ¿los mensajes esperan?

---

## Parte 3 — Poison message y DLQ

Un **poison message** es un mensaje que el consumer nunca puede procesar (payload malformado, referencia a un recurso borrado, bug en el consumer). Sin DLQ, el mensaje vuelve a la queue una y otra vez, bloquea el pipeline y consume recursos.

**Q5.** El demo envía un mensaje `POISON` que el consumer nunca deletea. El pipeline lo intenta 3 veces y después lo manda a DLQ. Miralo en detalle:

```bash
# Ver mensajes en la DLQ
awslocal sqs receive-message \
  --queue-url http://localhost:4566/000000000000/events-dlq \
  --attribute-names ApproximateReceiveCount \
  --max-number-of-messages 10
```

¿Qué valor tiene `ApproximateReceiveCount`? ¿Qué significa ese número?

**Q6.** Si tu consumer real falla al procesar un mensaje, tenés 4 opciones:
- **A**: `delete` el mensaje (perdés el evento — bad)
- **B**: No hacer nada (deja que la queue lo re-entregue después del VisibilityTimeout)
- **C**: `change-message-visibility` para adelantar el reintento (útil si sabés que fue error transient)
- **D**: `send-message` a la DLQ manualmente y `delete` (raro, deja que el RedrivePolicy lo haga solo)

Elegí la mejor y justificá. ¿En qué escenario usarías `C`?

---

## Parte 4 — Aplicá al proyecto

**Q7.** Elegí un caso de tu proyecto final donde tenga sentido SNS + SQS. Ejemplos:
- Un `order-created` que dispara: (a) email de confirmación, (b) actualización de inventario, (c) analytics
- Un `user-signup` que dispara: (a) welcome email, (b) crear default settings, (c) audit log

Escribí en 5-6 líneas: qué evento, qué queues (subscribers), qué hace cada consumer, por qué SNS+SQS y no otra cosa.

**Q8.** Para ese caso: ¿qué es un **poison message** posible? Ej: consumer de "envío de email" que falla porque el email es inválido. ¿Qué querés que pase con ese mensaje? ¿DLQ? ¿Log y descartar? ¿Alertar?

---

## Documentar en `decisions.md`

```
### 014 — Fan-out con SNS + SQS y DLQ para poison messages

Decision: usar SNS como topic de eventos y SQS como cola por cada consumer.
Cada queue tiene DLQ con maxReceiveCount=3.

Contexto: si el productor escribe directamente en las queues, agregar un nuevo
consumer requiere modificar el productor. Con SNS, el productor publica una vez
y cada consumer suscribe su propia queue.

Alternativas: SQS solo (productor escribe a cada queue), EventBridge (más
schema-aware pero más ceremonia), Kafka/Redpanda (ordenamiento y retención más
fuerte, más operación).

Tradeoff: SNS+SQS es simple y encaja para eventos fire-and-forget. Si necesitás
orden estricto o replay histórico, mirar Kafka. Si necesitás routing por
attributes complejos, EventBridge.

Resultado: SNS `events-topic` + SQS `events-analytics` y `events-audit`.
DLQ compartida con maxReceiveCount=3. Redis para dedupe en el consumer.
```

---

## Checkpoint

- [ ] `messaging_demo.py` corrió y la DLQ recibió el poison message
- [ ] Q1-Q3 respondidas (fan-out entendido con evidencia)
- [ ] Q4 respondida con los 3 problemas identificados
- [ ] Q5-Q6 respondidas (DLQ + estrategias de fallo)
- [ ] Q7-Q8 respondidas (caso real del proyecto)
- [ ] Decisión 014 en `decisions.md`

---

## Para llevar: ministack vs AWS real

| Acción | Ministack | AWS real |
|---|---|---|
| SQS create + attributes | ✅ | ✅ |
| SNS topic + subscribe | ✅ | ✅ |
| Fan-out SNS → SQS | ✅ | ✅ |
| RedrivePolicy + DLQ | ✅ | ✅ |
| `set-alarm-state` sobre queue depth | ⚠️ ver lab-11 | ✅ |
| SNS entrega a email/SMS/HTTP endpoints reales | ❌ | ✅ |
| Lambda triggered by SQS | ⚠️ parcial | ✅ |

El pipeline SNS + SQS + DLQ es indistinguible entre ministack y AWS real hasta que necesitás **efectos secundarios reales** (emails, notificaciones push, invocación de Lambda con concurrencia).
