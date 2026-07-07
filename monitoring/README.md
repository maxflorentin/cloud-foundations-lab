# `monitoring/` — Lab 11: Operations & Reliability

Tres archivos que declaran **el plan de monitoreo mínimo** del proyecto: alarma + acción + política de escalado.

## Archivos

| Archivo | Rol |
|---|---|
| `sns-topic.json` | Topic SNS `project-alerts` — destino de las alarmas (mail/PagerDuty/Slack en prod) |
| `alarm.json` | CloudWatch alarm: CPU > 70% durante 3 períodos consecutivos → publica al topic |
| `scaling-policy.json` | Target tracking del ASG: mantener CPU en 50% ajustando cantidad de instancias |

Cada archivo está en formato JSON directo de la AWS CLI (`--cli-input-json`), listo para pegar al comando correspondiente.

## Anatomía de una buena alarma

```
métrica → umbral → N períodos → acción
```

- **Métrica**: `AWS/EC2 CPUUtilization` de un ASG (dimensiones importan)
- **Umbral**: `> 70%` (accionable, no ruido)
- **N períodos**: 3 datapoints de 60s (evita falsos positivos por picos)
- **Acción**: publicar al topic SNS (que después despacha a mail / Slack / etc.)

La regla: **una alarma buena es accionable**. Si dispara y no sabés qué hacer, no es alarma — es ruido.

## Estados de una alarma

```
        no hay datos
         ↓
   INSUFFICIENT_DATA
         ↓
   ┌─────────────┐
   │      OK     │←──────┐
   └─────────────┘       │
         ↓ superó umbral │ volvió bajo umbral
         ↓ N períodos    │ N períodos
   ┌─────────────┐       │
   │    ALARM    │───────┘
   └─────────────┘
         ↓ dispara AlarmActions
     SNS / Auto Scaling / Lambda
```

`set-alarm-state` sirve para forzar cualquier estado desde la CLI — clave para probar el pipeline sin esperar que la métrica real cruce el umbral.

## De target tracking a "auto scaling automático"

La política del `scaling-policy.json` es simple pero potente:

> "Mantené el CPU promedio del ASG en 50%. Si sube, agregá instancias. Si baja, sacá."

AWS calcula automáticamente cuántas instancias sumar/restar. No hace falta que definas alarmas manuales para scale-out y scale-in — target tracking las crea solo.

## LocalStack Community

| Acción | Estado |
|---|---|
| `sns create-topic` + subscribe | ✅ real |
| `cloudwatch put-metric-data` | ✅ real |
| `cloudwatch put-metric-alarm` | ✅ real |
| `cloudwatch set-alarm-state` | ✅ real |
| `cloudwatch describe-alarms` | ✅ real |
| SNS actúa como `AlarmAction` (publica al topic al disparar) | ⚠️ parcial |
| Auto Scaling group real que escala por la alarma | ❌ (ASG API existe pero no ejecuta) |

El **ciclo métrica → alarma → estado → SNS** se practica completo. El escalado end-to-end (alarma → ASG suma instancia real) requiere AWS real.
