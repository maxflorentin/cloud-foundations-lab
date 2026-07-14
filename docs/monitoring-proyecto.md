# Lab 11 — Operations & Reliability

Este lab **no se resuelve corriendo un script**. Tiene 3 desafíos que obligan a decidir umbrales, criticar una alarma mal diseñada, y hacer una revisión Well-Architected de tu propio stack.

> **Regla del lab:** cada respuesta requiere evidencia (número que sacaste, código que miraste, decisión que justificaste). "Está bien" o "creo que sí" no aplica.

---

## Prerequisitos

- Branch `lab-11-tuNombre` desde main
- LocalStack con `cloudwatch,logs,sns` en `SERVICES` (ya está en `compose.yaml`)
- Servicios activos: `docker compose up -d localstack`

Verificar:
```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool | grep -iE "monitoring|sns|logs"
```

> **Nota sobre el emulador**: el `compose.yaml` de esta branch usa **ministack** (fork del user con fix de IAM group policies). LocalStack 3.8.1 tiene un bug con el protocolo de CloudWatch para versiones nuevas de boto3/aws-cli, ministack lo resuelve.

Correr el demo una vez para entender el ciclo mecánicamente:
```bash
python3 scripts/monitoring_demo.py
```

Salida esperada: 3 transiciones registradas (INSUFFICIENT_DATA → ALARM → OK). Si eso no sucede, no sigas — el pipeline base tiene un problema.

---

## Copiar el workbook

```bash
cp docs/lab-11.md docs/monitoring-proyecto.md
$EDITOR docs/monitoring-proyecto.md
```

Todas las Q se responden ahí. `docs/monitoring-proyecto.md` es la entrega.

> Trabajás sobre la copia, no sobre `docs/lab-11.md` (que queda como plantilla del repo).

---

## Parte 1 — Entender la alarma que hicimos

**Q1.** Después de correr el demo, `describe-alarms` te muestra el objeto `cpu-alta-web-tier`. Copiá los 3 campos que te parezcan más importantes para operar y explicá qué informa cada uno (una frase por campo).

```bash
awslocal cloudwatch describe-alarms --alarm-names cpu-alta-web-tier
```

**Q2.** En el JSON de la alarma están `Period: 60` y `EvaluationPeriods: 3`.
- ¿Cuánto tiempo mínimo tiene que sostenerse el problema para que la alarma dispare? _segundos_
- Si el pico dura 2 minutos, ¿va a disparar? Sí / No — justificá.
- Si en lugar de 3 lo cambiás a 1, ¿qué gana y qué pierde el sistema de alarmas?

**Q3.** El campo `TreatMissingData` está en `"notBreaching"`. Buscá en la [doc de AWS](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html#alarms-and-missing-data) qué significa. ¿Por qué eligimos ese valor y no `breaching`?

---

## Parte 2 — Criticar una alarma mal diseñada

Abrí `monitoring/alarm-mal-disenada.json`. Tiene **4 problemas de diseño**. Aplicala en LocalStack para ver cómo se comporta:

```bash
awslocal cloudwatch put-metric-alarm --cli-input-json file://monitoring/alarm-mal-disenada.json
awslocal cloudwatch describe-alarms --alarm-names alarma-cpu
```

**Q4.** Identificá los 4 problemas. Para cada uno:
- Cuál es el problema
- Qué pasaría en producción si esta alarma se deja así
- Cómo lo corregirías

| # | Campo | Problema | Consecuencia en prod | Corrección |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

_Pistas para revisar (mirar de a uno):_
- ¿La alarma tiene destinatario? ¿Qué pasa si dispara?
- ¿El umbral tiene sentido físico? (¿puede CPU pasar 100%?)
- ¿Un solo período de 10 segundos es suficiente evidencia?
- ¿`TreatMissingData: breaching` genera falsos positivos?

---

## Parte 3 — Diseñar UNA alarma para tu proyecto

**Q5.** Elegí UN servicio real de tu proyecto (RDS, EC2, ALB, S3, Lambda...). Escribí la alarma en `monitoring/mi-alarma.json` completando la plantilla `alarm.template.json`:

```bash
cp monitoring/alarm.template.json monitoring/mi-alarma.json
$EDITOR monitoring/mi-alarma.json
```

Cada TODO tiene que quedar resuelto con una decisión.

**Q6.** Justificá las 4 decisiones clave que tomaste:

- **Métrica** (`Namespace` + `MetricName`): ¿Por qué esta métrica y no otra? Debe ser algo **accionable** — si sube, ya sabés qué hay que revisar/hacer.
- **Umbral**: ¿De dónde salió el número? (Baseline observado / SLO / documentación / criterio del negocio)
- **Período + EvaluationPeriods**: ¿Cuánto tiempo tolerás el problema antes de despertar a alguien?
- **TreatMissingData**: ¿Ausencia de datos = problema o = normal para esta métrica?

**Q7.** Aplicala y probala con `set-alarm-state`:
```bash
awslocal cloudwatch put-metric-alarm --cli-input-json file://monitoring/mi-alarma.json
awslocal cloudwatch set-alarm-state --alarm-name TU-NOMBRE --state-value ALARM --state-reason "test"
awslocal cloudwatch describe-alarm-history --alarm-name TU-NOMBRE --history-item-type StateUpdate
```

Copiá acá los 2 últimos items del history — es la evidencia de que la alarma responde.

---

## Parte 4 — Revisión Well-Architected (los 6 pilares)

**Q8.** Completá `docs/well-architected.md` con los 6 pilares aplicados a **tu stack**.

Copiá el archivo primero:
```bash
cp docs/well-architected.md docs/well-architected-proyecto.md
```

**Regla del pilar:** cada hallazgo tiene que citar **evidencia** — un archivo, un número, una decisión de `docs/decisions.md`. "Está bien la seguridad" no vale. "Rol de instancia con inline `s3:GetObject` sobre `raw/*` (ver `iam/s3_read_policy.json`), no hay access keys en código (grep pasado en CI)" — eso sí.

**Q9.** Al final del archivo, elegí **los 3 pilares críticos** para tu proyecto y justificá por qué son 3 y no los otros. No hay respuesta correcta — hay respuestas defendibles.

---

## Parte 5 — La política de scaling

El archivo `monitoring/scaling-policy.json` describe una política de target tracking sobre un ASG que **no lanzamos** en este lab (ASGs reales requieren AWS real). Pero la política es una decisión de diseño igual — la política decide antes de la carga cuánto se puede escalar.

**Q10.** Mirá el archivo. Explicá:
- ¿Qué mide la métrica de target tracking?
- ¿Por qué el target es 50% y no 30% o 80%?
- ¿Qué pasaría si `DisableScaleIn` fuera `true`?

**Q11.** ¿En qué escenario la target tracking **NO** sería la política correcta? Nombrá al menos uno donde convendría step scaling o scheduled scaling en su lugar.

---

## Paso final — Documentar en `decisions.md`

```
### 013 — Alarma accionable y revisión Well-Architected

Decision: definir al menos una alarma con criterio (ver monitoring/mi-alarma.json),
hacer revisión Well-Architected priorizando 3 pilares (ver docs/well-architected-proyecto.md),
y declarar la política de scaling (target tracking) del ASG.

Contexto: sin observabilidad accionable, la operación es reactiva. Sin revisión
de pilares, las decisiones son tácitas. Sin política de scaling declarada, la
capacidad la ajusta alguien a mano cuando algo se rompe.

Alternativas: solo dashboards (no accionable), monitorear por Slack (frágil),
alarmas genéricas (ruido).

Tradeoff: cada alarma pide un runbook y un destinatario. Sin eso, se convierte
en ruido y se ignora — peor que no tenerla.

Resultado: N alarmas activas, 3 pilares priorizados, política de scaling declarada.
```

---

## Checkpoint

- [ ] `monitoring_demo.py` corrió y muestra las 3 transiciones (evidencia mecánica)
- [ ] Q1-Q3 respondidas (entender la alarma de ejemplo)
- [ ] Q4 respondida con los 4 problemas identificados
- [ ] Q5-Q7 respondidas: alarma tuya escrita, aplicada, testeada con `set-alarm-state`
- [ ] Q8-Q9 respondidas: 6 pilares con evidencia + 3 priorizados con justificación
- [ ] Q10-Q11 respondidas: política de scaling entendida y su límite reconocido
- [ ] Decisión 013 en `decisions.md`
- [ ] `docs/monitoring-proyecto.md` y `docs/well-architected-proyecto.md` como entregables

---

## Para llevar: LocalStack/ministack vs AWS real

| Acción | Comunidad (ministack) | AWS real |
|---|---|---|
| Ciclo métrica → alarma → estado → SNS | ✅ modelado | ✅ |
| SNS entrega el mensaje al topic | ✅ (queda en la queue interna) | ✅ dispara subscriptions reales |
| Auto Scaling responde a la alarma | ⚠️ ASG existe pero no crea instancias reales | ✅ end-to-end |
| Métricas reales de EC2/RDS con datos vivos | ⚠️ parcial | ✅ |
| CloudWatch Dashboards visuales | ❌ | ✅ |

El **pipeline** se practica completo en local. La respuesta automática (Auto Scaling levanta EC2) y los dashboards con gráficos se validan en AWS real.
