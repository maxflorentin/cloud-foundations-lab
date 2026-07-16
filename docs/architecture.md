# Arquitectura del stack — labs 04 a 12

Este archivo documenta **qué recursos existen en el ministack** después de correr todos los demos de labs 04 a 12 en orden. Es la base para el análisis de resiliencia del **lab 13**.

Stack local-first: **ministack** (drop-in de LocalStack, incluye engine SQL real vía container postgres) + **postgres/redis/minio** en compose.

---

## Diagrama del stack

```
                              ┌───────────────────────────────────────────┐
                              │  IDENTIDAD (lab 04)                       │
                              │  - Role: app-role  (assume by EC2)        │
                              │  - Instance profile: app-instance-profile │
                              │  - Group: bigdata-read + user: lab-user   │
                              │  - Managed policy: S3ReadOnlyLab          │
                              │  - Secret: app/db (Secrets Manager)       │
                              └────────────────┬──────────────────────────┘
                                               │ credencial + rol
                                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           VPC course-vpc  10.0.0.0/16  (lab 07)          │
│                                                                          │
│  ┌────────────────────────┐         ┌────────────────────────────────┐   │
│  │ Subnet PÚBLICA         │         │ Subnet PRIVADA                 │   │
│  │ 10.0.1.0/24 · 1a       │         │ 10.0.2.0/24 · 1b               │   │
│  │                        │         │                                │   │
│  │  SG web-public-sg      │         │  SG app-private-sg             │   │
│  │  (80 desde Internet)   │         │  (8080 solo desde web-public)  │   │
│  │        │               │         │        │                       │   │
│  │        ▼               │         │        ▼                       │   │
│  │  ┌──────────────┐      │         │  ┌──────────────┐              │   │
│  │  │ EC2 lab05-web│──────┼─────────┼─▶│  App (mock)  │              │   │
│  │  │ (t3.micro)   │      │         │  │              │              │   │
│  │  │ user-data:   │      │         │  │  reads secret│              │   │
│  │  │  bajar de S3 │      │         │  │  from SM     │              │   │
│  │  └──────────────┘      │         │  └──────┬───────┘              │   │
│  │                        │         │         │ 5432                 │   │
│  │                        │         │         ▼                      │   │
│  │                        │         │  ┌──────────────────────────┐  │   │
│  │                        │         │  │ RDS app-db (postgres 16) │  │   │
│  │                        │         │  │ SG db-sg (5432 desde     │  │   │
│  │                        │         │  │           app-private-sg)│  │   │
│  │                        │         │  │ Schemas: public+analytics│  │   │
│  │                        │         │  └──────────────────────────┘  │   │
│  └────────┬───────────────┘         └──────────────────┬─────────────┘   │
│           │                                            │                 │
│    Route Table pública                        Route Table privada        │
│    0.0.0.0/0 → IGW                            + VPC endpoint → S3        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
           │                                            │
           ▼                                            ▼
┌──────────────────────┐                     ┌────────────────────────────┐
│ Internet Gateway     │                     │ VPC endpoint (Gateway)     │
│ course-igw           │                     │ com.amazonaws.us-east-1.s3 │
└──────────────────────┘                     └────────────────────────────┘
                                                        │
                                                        ▼
                       ┌────────────────────────────────────────────────┐
                       │  S3 course-data-lake  (lab 06)                 │
                       │  - BPA ON · SSE-S3 · Versioning ON             │
                       │  - Bucket policy: app-role → GetObject         │
                       │  - Prefijos: raw/olist/, raw/events/, processed│
                       └────────────────────────────────────────────────┘

                       ┌────────────────────────────────────────────────┐
                       │  MESSAGING (lab 12)                            │
                       │  SNS events-topic ──┬── SQS events-analytics   │
                       │                     └── SQS events-audit       │
                       │                         │                      │
                       │              (RedrivePolicy → events-dlq)      │
                       │  Redis dedupe (docker: cloud-foundations-redis)│
                       └────────────────────────────────────────────────┘

                       ┌────────────────────────────────────────────────┐
                       │  MONITORING (lab 11)                           │
                       │  CloudWatch alarm cpu-alta-web-tier            │
                       │       │ AlarmActions                           │
                       │       ▼                                        │
                       │  SNS project-alerts                            │
                       └────────────────────────────────────────────────┘
```

---

## Inventario por lab

### Lab 04 — Identidad (IAM)
- **Role** `app-role` — trust policy: `ec2.amazonaws.com`
- **Instance profile** `app-instance-profile` — wrapper para adjuntar rol a EC2
- **Group** `bigdata-read` + **user** `lab-user` (con access key)
- **Managed policy** `S3ReadOnlyLab`
- **Secret** `app/db` — credencial de la DB

### Lab 05 — Cómputo (EC2)
- **Key pair** `lab05-key`
- **Security group** `web-sg`
- **Instance** `lab05-web` (t3.micro, us-east-1a)
- **User-data** — baja `hello.txt` de S3 usando IMDSv2

### Lab 06 — Storage (S3)
- **Bucket** `course-data-lake`
- Prefijos: `raw/olist/*`, `raw/events/*`, `processed/*`
- **Bucket policy** — `app-role` puede GetObject
- **Versioning** ON
- **BPA** ON, **SSE-S3** por default

### Lab 07 — Red (VPC)
- **VPC** `course-vpc` (10.0.0.0/16)
- **Subnet pública** 10.0.1.0/24 en `us-east-1a`
- **Subnet privada** 10.0.2.0/24 en `us-east-1b`
- **IGW** `course-igw` + route table pública (0.0.0.0/0 → IGW)
- **Route table privada** con **VPC endpoint Gateway a S3**
- **Security groups** `web-public-sg` y `app-private-sg` (referencia entre SGs)

### Lab 08 — Base de datos (RDS)
- **RDS instance** `app-db` (postgres 16, `db.t3.micro`)
  - `MultiAZ: false` (dev)
  - `StorageEncrypted: true`
  - `PubliclyAccessible: false`
  - `BackupRetentionPeriod: 7`
- **Security group** `db-sg` (5432 desde `app-private-sg`)
- **DB subnet group** `course-db-subnets`
- **Schemas**: `public` (transaccional) + `analytics` (Olist)
- **Snapshot manual** al final del demo

### Lab 11 — Monitoring
- **SNS topic** `project-alerts`
- **CloudWatch alarm** `cpu-alta-web-tier` (CPU > 70% x 3 períodos)
- **Scaling policy** declarada en `monitoring/scaling-policy.json` (target tracking 50% CPU)

### Lab 12 — Messaging
- **SNS topic** `events-topic` (fan-out)
- **SQS** `events-analytics` + `events-audit` + **DLQ** `events-dlq`
- `maxReceiveCount: 3` → mensajes fallidos van a DLQ
- **Redis** para dedupe idempotente (`cloud-foundations-redis`)

---

## Componentes ↔ equivalencias cloud

| Componente | Local (ministack/docker) | Equivalente AWS | Equivalente GCP |
|---|---|---|---|
| Identidad | ministack IAM | AWS IAM | Cloud IAM |
| Cómputo | EC2 mock (ministack) | EC2 | Compute Engine |
| Storage | S3 (ministack) | S3 | Cloud Storage |
| Red | VPC (ministack) | VPC | VPC |
| Base de datos | RDS via container postgres (ministack) | RDS | Cloud SQL |
| Cache | Redis (compose) | ElastiCache | Memorystore |
| Alertas | CloudWatch + SNS (ministack) | CloudWatch + SNS | Cloud Monitoring + Pub/Sub |
| Mensajes | SQS + SNS (ministack) | SQS + SNS | Pub/Sub |

---

## Puntos únicos de falla (SPOFs) candidatos

⚠️ **Esta lista es para el lab 13, no la mirés antes de intentar Q4.**

<details>
<summary>Click para ver los SPOFs candidatos del stack actual</summary>

| # | Componente | Por qué es SPOF | Qué depende |
|---|---|---|---|
| 1 | **EC2 `lab05-web`** | Instancia única en `us-east-1a` | Todos los requests HTTP |
| 2 | **RDS `app-db`** | Single-AZ | App transaccional (schema public) + analytics |
| 3 | **AZ `us-east-1a`** | EC2 + subnet pública viven ahí | Todo el tráfico entrante |
| 4 | **AZ `us-east-1b`** | RDS + subnet privada viven ahí | Todos los datos |
| 5 | **Region `us-east-1`** | Todo el stack | Absolutamente todo |
| 6 | **Redis** | Single node en compose | Idempotency del consumer messaging |
| 7 | **`app-role` access key** | Sin rotación, sin MFA | Todos los servicios que dependen del rol |
| 8 | **Secret `app/db`** | Sin rotación | Conexión a la DB |
| 9 | **DLQ `events-dlq`** | Sin consumer que la procese | Los poison messages se acumulan sin acción |

</details>

---

## Costos por escenario (lab 10 — referencial)

Ver `finops/services.json` para el detalle. Los top drivers del stack son:
- NAT gateway (si se activa — actualmente NO, usamos VPC endpoint)
- RDS instance (si pasa a Multi-AZ, 2x el costo)
- Egress a Internet

---

## Estado de cada capa

| Capa | Lab | Estado en el repo | Redundancia actual |
|---|---|---|---|
| Identity | 04 | ✅ implementado | 1 rol, 1 secret — sin rotación |
| Compute | 05 | ✅ EC2 mock | 1 instance, 1 AZ |
| Storage | 06 | ✅ S3 real | multi-AZ por diseño de S3 |
| Network | 07 | ✅ VPC completa | 2 AZs pero recursos concentrados |
| Data | 08 | ✅ RDS engine real | Single-AZ |
| Monitoring | 11 | ✅ alarma + SNS | 1 alarma sobre CPU |
| Messaging | 12 | ✅ SNS+SQS+DLQ+Redis | DLQ ok, Redis 1 node |
| Serverless / Event-driven / Analytics | 14-16 | pendiente | — |
| Resiliencia | 13 | **este lab** | análisis de lo de arriba |
