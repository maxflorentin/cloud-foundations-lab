# Lab 08 — Bases de datos: RDS gestionada con engine real

Cierra el stack base **IAM(04) → EC2(05) → S3(06) → VPC(07) → datos (hoy)**.

> **Engine real vía ministack**
> Ministack levanta un container `postgres:16-alpine` cada vez que llamás `create-db-instance`. Toda la API funciona (crear, describir endpoint, snapshot) y el motor SQL es real — psql/DDL/DML corren de verdad, no simulado.

---

## Prerequisitos

- Branch `lab-08-tuNombre` desde main
- Labs previos corridos en orden (crean recursos que este lab reusa):
  - Lab 04: `python scripts/iam_demo.py` (necesario para `app-role`)
  - Lab 07: `python scripts/vpc_demo.py` (necesario para `course-vpc`, `app-private-sg`)
- Servicios activos: `docker compose up -d localstack`
- `awslocal --version` responde

```bash
# Verificar prereqs
awslocal iam get-role --role-name app-role --query "Role.Arn"
awslocal ec2 describe-vpcs --filters Name=tag:Name,Values=course-vpc --query "Vpcs[0].VpcId"
```

---

## Paso 1 — Mirar el plan de infra en JSON

```bash
cat rds/rds_config.json
cat rds/seed.sql
```

Cada valor en `rds_config.json` es una decisión de arquitectura documentada:

| Parámetro | Valor | Decisión |
|---|---|---|
| `InstanceClass` | `db.t3.micro` | burstable, dev, free tier en AWS real |
| `BackupRetentionPeriod` | 7 | días de retención de backup (habilita PITR) |
| `MultiAZ` | `false` | Single-AZ en dev; en prod → `true` |
| `StorageEncrypted` | `true` | **se elige al crear, no se agrega después** |
| `PubliclyAccessible` | `false` | la DB va en subnet privada — siempre |

---

## Paso 2 — Correr el demo end-to-end

```bash
python3 scripts/rds_demo.py
```

Hace 10 pasos en secuencia:
1. Crear secret en Secrets Manager
2. Recuperar recursos de VPC del lab 07
3. Crear SG de la DB (referencia al `app-private-sg`)
4. Crear DB subnet group
5. `create-db-instance` — ministack levanta postgres real
6. Esperar a `available`
7. Consumir el secret (patrón: nunca password hardcodeada)
8. Aplicar `seed.sql` al engine real
9. Verificar filas
10. Snapshot para backup

Output esperado incluye:
```
9. Verificar filas
    app_users=5
    app_audit_log=5

10. Snapshot para backup
  ✓ snapshot: app-db-snap-1783... (status=available)
```

Si ves `app_users=5` es porque el `seed.sql` corrió sobre un postgres real dentro del container `ministack-rds-app-db`.

---

## Paso 3 — Explorar la DB a mano

```bash
# Conectarse al container postgres que ministack levantó
docker exec -it ministack-rds-app-db psql -U app -d appdb

# Dentro de psql:
\dt                          # ver tablas
SELECT * FROM app_users;     # ver los 5 usuarios seed
INSERT INTO app_users (email, full_name) VALUES ('nuevo@test.com', 'Nuevo');
\q
```

---

## Paso 4 — Snapshot y describir

```bash
awslocal rds describe-db-instances \
  --db-instance-identifier app-db \
  --query "DBInstances[0].{Status:DBInstanceStatus,Engine:Engine,Endpoint:Endpoint.Address}"

awslocal rds describe-db-snapshots \
  --db-instance-identifier app-db
```

En AWS real, los snapshots son la base de PITR (Point-in-Time Recovery): podés restaurar a cualquier segundo dentro de `BackupRetentionPeriod`.

---

## Paso 5 — El patrón operativo: rol + secret + SG

Repasar cómo interactúan las capas del stack para llegar a la DB:

```
Cliente HTTP → ALB (público)
              ↓
              EC2 en subnet pública (con SG public)
              ↓
              EC2 en subnet privada — app-private-sg
                                     rol IAM: app-role (lab 04)
              ↓ (5432, SG-to-SG, no CIDR)
              RDS en subnet privada — db-sg
                                     - No publicly accessible
                                     - Storage encrypted
                                     - Password en Secrets Manager
```

La app **nunca** tiene la password en código. La lee del secret usando su rol.

---

## Paso 6 — Managed vs self-managed (concepto)

RDS te quita **la operación**, no la base. Seguís diseñando schema y queries; delegás:

| Tarea | Self-managed (postgres en EC2) | RDS |
|---|---|---|
| Instalar postgres | vos (yum install, `postgresql-setup --initdb`) | AWS |
| Iniciar / systemd | vos | AWS |
| Parches minor version | vos (cron + downtime) | AWS (maintenance window) |
| Backups automáticos | vos (pg_dump + S3) | AWS (`BackupRetentionPeriod`) |
| PITR | vos (WAL archiving custom) | AWS |
| Multi-AZ failover | vos (streaming replication + failover) | AWS (1 flag) |
| Read replicas | vos | AWS (1 flag) |
| Monitoring | vos (Prometheus + node_exporter) | CloudWatch |
| Encryption at rest | vos (LUKS) | KMS (1 flag) |

**Regla:** RDS **si podés**. Self-managed solo si tenés requerimientos que RDS no cubre (extensiones no soportadas, control de kernel, versión específica).

---

## Paso 7 — Documentar en `decisions.md`

```
### 009 — Multi-AZ false en dev, true en prod

Decision: RDS Single-AZ en dev/staging y Multi-AZ en prod.

Contexto: Multi-AZ duplica el costo (standby síncrono en otra AZ) y no atiende
tráfico. En dev no justifica el gasto. En prod es la base de HA.

Tradeoff: dev no tiene failover automático. Si la base cae en dev, el equipo
notifica y se reinicia; en prod el failover ocurre sin intervención.

Resultado: parametrizado por entorno en rds_config.json.
```

```
### 010 — Credencial en Secrets Manager, nunca en el código

Decision: password de la DB en Secrets Manager. La app la lee en runtime con su rol.

Contexto: credenciales en código son el vector de incidente más común
(commits accidentales, leaks en logs, exposición en bug bounty).

Tradeoff: una dependencia más en AWS. A favor: rotación automática soportada,
acceso auditado en CloudTrail, control vía IAM.

Resultado: app/db en Secrets Manager, mismo código de conexión que en prod real.
```

---

## Checkpoint

- [ ] `rds_demo.py` corrió y muestra `app_users=5, app_audit_log=5`
- [ ] Snapshot creado con status `available`
- [ ] `docker exec -it ministack-rds-app-db psql` responde (verificación manual)
- [ ] SG de la DB referencia `app-private-sg` (no CIDR)
- [ ] Secret creado y leído desde el script
- [ ] Decisiones 009 y 010 en `decisions.md`

---

## Para llevar: ministack vs LocalStack Community vs AWS real

| Acción | Ministack | LocalStack Community | AWS real |
|---|---|---|---|
| `create-db-instance` (API + estado) | ✅ | ❌ Pro-only | ✅ |
| Engine SQL real (postgres/mysql) | ✅ container real | ❌ | ✅ |
| `create-db-snapshot` | ✅ | ❌ | ✅ |
| PITR (`restore-to-point-in-time`) | ⚠️ parcial | ❌ | ✅ |
| Multi-AZ failover real | ⚠️ modelado | ❌ | ✅ |
| Read replicas | ⚠️ modelado | ❌ | ✅ |
| CloudWatch metrics del engine | ⚠️ parcial | ❌ | ✅ |

Ministack cambia la lección de este lab: en lugar de "postgres-on-EC2 vs docker vs RDS-referencia" (workaround por LocalStack Community sin RDS), ahora enseñamos **RDS puro con engine real** y la comparación conceptual "managed vs self-managed" queda como decisión pedagógica en Paso 6.
