# Lab 13 — Arquitecturas resilientes: Multi-AZ · DR · RTO/RPO

Este lab **no tira código**. Es un **workbook de decisiones** sobre resiliencia aplicadas a tu proyecto final.

> **El punto de fondo**
> Todo falla. La pregunta no es *"cómo evito que falle"*, es *"cuánto tardo en volver cuando falla y cuántos datos puedo perder"*. Esa decisión no la toma el equipo técnico solo: la negocia con negocio, la documenta, y la revisa periódicamente.

---

## Prerequisitos

- Branch `lab-13-tuNombre` desde main
- **Leer `docs/architecture.md`** — tiene el diagrama del stack que construimos en labs 04–12. Es la base para practicar antes de aplicar al proyecto propio.
- Diagrama del proyecto final tuyo en algún formato revisable (`.excalidraw`, `.png`, link a Miro, etc.). Si aún no tenés, el ejercicio se hace primero sobre el stack del curso.
- Acceso a las docs oficiales (links al final)

No hace falta LocalStack ni ministack para este lab — es todo análisis y decisiones.

---

## Copiar el workbook

```bash
cp docs/lab-13.md docs/resilience-proyecto.md
$EDITOR docs/resilience-proyecto.md
```

Todas las Q se responden en la copia. `docs/resilience-proyecto.md` es la entrega.

---

## Parte 1 — Los 3 conceptos base

**Q1. RTO (Recovery Time Objective)**

Definición corta: **cuánto tiempo puede estar caído tu servicio antes de que sea un problema serio.**

Para tu proyecto, negocialo mentalmente con el usuario final. Marcá una opción:

- [ ] < 1 minuto (real-time crítico — trading, cirugía asistida)
- [ ] 1–15 minutos (transaccional serio — banco, e-commerce activo)
- [ ] 15 min–1 hora (SaaS estándar — dashboards, CRM)
- [ ] 1–24 horas (herramientas internas, batch)
- [ ] > 24 horas (data warehouses, reportería histórica)

**RTO acordado:** _____

Justificalo en 2 líneas: qué usuario / proceso se afecta, qué se pierde en costo/reputación si excedés ese tiempo.

**Q2. RPO (Recovery Point Objective)**

Definición corta: **cuántos datos podés perder cuando te caés** (medido en tiempo — "los últimos 5 minutos de escrituras").

Marcá:

- [ ] 0 segundos (no aceptás pérdida — replicación sincrónica)
- [ ] < 5 minutos (transaccional crítico — replicación asincrónica frecuente)
- [ ] < 1 hora (aceptable perder trabajo reciente)
- [ ] < 24 horas (backup diario alcanza)
- [ ] > 24 horas (los datos se pueden regenerar de otro lado)

**RPO acordado:** _____

Justificalo: qué tipo de dato es, qué pasa si se pierde esa ventana (reprocesamiento, disculpa al usuario, pérdida de venta).

**Q3. SPOF (Single Point of Failure)**

Definición corta: **componente sin redundancia que si se cae, deja caído todo lo que depende de él.**

Ejemplos típicos:
- Una única EC2 corriendo la app
- Una RDS Single-AZ
- Un solo Load Balancer, DNS, o certificado SSL vencido
- Un servicio externo (Stripe, un tercero) — es SPOF de él mismo

**Pregunta guía:** para cada componente en tu diagrama, preguntate *"si esto se cae 30 minutos, ¿qué dejo de tener?"* — si la respuesta es "todo", es SPOF.

---

## Parte 2 — Identificar SPOFs

Este ejercicio va en 2 pasos: primero sobre el **stack del curso** (guiado, con diagrama en `docs/architecture.md`) y después sobre **tu proyecto** (open-ended).

### Q4a — SPOFs del stack del curso

Abrí `docs/architecture.md` y mirá el diagrama. Aplicá la pregunta guía a cada componente:

> *"si esto se cae 30 minutos, ¿qué dejo de tener?"*

Completá la tabla. Apuntá al menos **5 SPOFs** — hay más de 5 en ese stack.

| # | Componente | Ubicación | Qué depende de él | ¿Aceptable? |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

_Tip:_ mirá cada capa (Identidad, Cómputo, Red, Data, Messaging, Monitoring). Cada una tiene al menos un SPOF.

_Después de contestar, podés desplegar la lista de SPOFs candidatos que dejé en `docs/architecture.md` para chequearte._

### Q4b — SPOFs de tu proyecto

Ahora aplicá la misma lente a tu **proyecto final**. Listá los SPOFs específicos:

| # | Componente | Ubicación | Qué depende de él | ¿Aceptable? |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

_No hace falta llegar a "cero SPOF"._ Es casi imposible sin gasto absurdo. El objetivo es **saber cuáles existen y decidir a conciencia**.

---

## Parte 3 — Matriz SPOF → estrategia de DR

**Q5.** Para **cada SPOF que NO aceptás** (de Q4), completá la tabla siguiente. Los que sí aceptás como riesgo, saltealos con una fila en Q7 justificando.

### SPOF #1: _nombre_

| Aspecto | Decisión |
|---|---|
| **Ubicación** | EC2 / RDS / Load Balancer / DNS / Storage / otro |
| **Zona(s) actual** | Single-AZ / Multi-AZ / Multi-región |
| **RTO acordado** | _minutos / horas_ (de Q1) |
| **RPO acordado** | _minutos / datos_ (de Q2) |
| **Impacto si falla** | qué usuarios/procesos/data se afectan |
| **Estrategia elegida** | Backup & restore / Pilot light / Warm standby / Multi-site active-active |
| **Costo relativo** | Bajo / Medio / Alto |
| **Decisión concreta** | ej. *"RDS Multi-AZ con failover automático + backup retention 7 días"* |
| **Justificación** | por qué esta estrategia y no otra |

Copiá y completá esta tabla **una vez por SPOF** que quieras mitigar.

**Las 4 estrategias de DR de AWS** (referencia rápida):

| Estrategia | RTO típico | RPO típico | Costo | Cuándo elegirla |
|---|---|---|---|---|
| **Backup & Restore** | horas–días | horas–día | $ | RTO/RPO holgados; presupuesto ajustado |
| **Pilot Light** | 10 min–horas | minutos–hora | $$ | Infra mínima pre-arrancada, escala on-demand |
| **Warm Standby** | minutos | segundos–min | $$$ | Réplica corriendo a menor capacidad, listo para escalar |
| **Multi-site active-active** | segundos | ~0 | $$$$ | RTO/RPO cercanos a cero; tráfico repartido |

Fuente: [AWS — Disaster recovery options in the cloud](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)

---

**Q6.** Sumá las estrategias elegidas y el costo relativo:

| Componente | Estrategia | Costo |
|---|---|---|
| SPOF #1 | | |
| SPOF #2 | | |
| SPOF #3 | | |
| **Total esperado** | | Bajo / Medio / Alto |

¿El total de costo se banca en el budget del proyecto (recordar lab 10)? Si no, ¿qué estrategias hay que bajar?

---

## Parte 4 — Los SPOFs que sí aceptás

**Q7.** Listá los SPOFs que decidís **NO mitigar** y justificá cada uno:

| SPOF | Por qué NO se mitiga |
|---|---|
| _ej. Certificado SSL en un solo emisor_ | _Costo del multi-emisor mayor que el riesgo (renovación automática cubre el escenario común)_ |
| | |

**Regla:** "no lo mitigo porque no quiero" no es respuesta. "No lo mitigo porque el costo supera el impacto esperado, y tengo un plan manual documentado" sí.

---

## Parte 5 — Al proyecto real

**Q8.** Al final del workbook, resumí en 3–5 líneas:

- Total de SPOFs identificados: _X_
- SPOFs mitigados con Multi-AZ / redundancia zonal: _Y_
- SPOFs mitigados con Multi-región: _Z_ (si aplica)
- SPOFs aceptados como riesgo consciente: _W_
- Estrategia dominante elegida: _Backup & Restore / Pilot Light / Warm Standby / Multi-site_
- Costo relativo total agregado al proyecto: _Bajo / Medio / Alto_

---

## Ejemplo de referencia (no solución al tuyo)

E-commerce simple con todo en `us-east-1a`:

### SPOF: Zona de disponibilidad completa

| Aspecto | Decisión |
|---|---|
| Ubicación | EC2 + RDS + Load Balancer (los 3 en us-east-1a) |
| Zona actual | Single-AZ |
| RTO acordado | 15 minutos |
| RPO acordado | 5 minutos |
| Impacto si falla | 100% de los usuarios sin servicio; pedidos en vuelo pueden perderse |
| Estrategia elegida | Warm Standby: EC2 en 2 AZs + RDS Multi-AZ + ALB regional |
| Costo relativo | Medio |
| Decisión concreta | Auto Scaling Group multi-AZ (min=2), RDS con `--multi-az`, ALB regional con health checks |
| Justificación | RTO de 15min exige failover automático; manual no da. RDS Multi-AZ es sync → cumple RPO 5min. ALB regional distribuye entre las AZ. Costo de duplicación de compute + réplica DB es aceptable vs. costo comercial del downtime. |

---

## Documentar en `decisions.md`

```
### 015 — Estrategia de resiliencia por componente

Decision: cada componente del stack tiene un análisis SPOF documentado con
RTO/RPO acordado y una estrategia de DR elegida (backup & restore, pilot
light, warm standby o multi-site) o una justificación explícita de por qué
se acepta el riesgo.

Contexto: sin este análisis, los SPOFs quedan invisibles hasta el incidente.
La resiliencia no se decide durante el fuego — se decide antes.

Alternativas: multi-región para todo (caro), single-AZ para todo (frágil),
ad-hoc caso por caso (inconsistente).

Tradeoff: el análisis toma tiempo y requiere números del negocio (RTO/RPO
reales). A cambio: decisiones defensibles, costo previsible, y saber qué se
rompe cuando algo falla.

Resultado: matriz SPOF → estrategia en docs/resilience-proyecto.md.
Estrategia dominante: [warm standby / pilot light / etc.]. Costo relativo
total: [bajo / medio / alto].
```

---

## Checkpoint

- [ ] Q1: RTO acordado con justificación
- [ ] Q2: RPO acordado con justificación
- [ ] Q3: entendés qué es un SPOF y podés detectarlo mirando el diagrama
- [ ] Q4a: mínimo 5 SPOFs del stack del curso (con base en `docs/architecture.md`)
- [ ] Q4b: mínimo 3 SPOFs de tu proyecto
- [ ] Q5: matriz completa para cada SPOF mitigado
- [ ] Q6: costo total estimado y ajuste al budget
- [ ] Q7: SPOFs aceptados con justificación
- [ ] Q8: resumen ejecutivo (3-5 líneas)
- [ ] Decisión 015 en `decisions.md`

---

## Criterio del curso

- **No hace falta cero SPOF.** Es casi imposible sin costo absurdo. El objetivo es **conocerlos, documentarlos, y decidir a conciencia cuáles aceptás**.
- **RTO/RPO lo define el negocio**, no el equipo técnico. Si no tenés los números, preguntá.
- **Fuente oficial siempre.** Este lab depende de docs oficiales — no invente números.

---

## Referencias

- **AWS** — [Well-Architected: Reliability pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- **AWS** — [DR options in the cloud (whitepaper)](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- **AWS** — [RDS Multi-AZ deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- **GCP** — [Disaster Recovery planning guide](https://cloud.google.com/architecture/disaster-recovery)
- **Excalidraw** (para diagramar) — https://excalidraw.com

---

## Después de esta clase

Esta matriz alimenta al entregable final (clase 18). Las clases 14–17 agregan:
- **14**: Serverless (afecta RTO — Lambda cold start)
- **15**: Event-driven (afecta RPO — eventual consistency)
- **16**: Analytics (data lakes con retenciones distintas)
- **17**: Arquitectura integradora local-first

Cada clase agrega una capa de decisión. Resiliencia es la capa de *"qué tan rápido volvés y cuánto perdés cuando algo se cae"*.
