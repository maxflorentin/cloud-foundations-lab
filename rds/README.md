# `rds/` — Lab 08: RDS con engine real

Con ministack, `create-db-instance` levanta un container `postgres:16-alpine` real. Toda la API funciona y el motor SQL es real — psql, DDL, DML y snapshots funcionan.

## Archivos

| Archivo | Rol |
|---|---|
| `rds_config.json` | Parámetros declarativos de la instancia (aplicados por `rds_demo.py`) |
| `seed.sql` | DDL + datos de ejemplo (3 tablas: `app_users`, `app_sessions`, `app_audit_log`) |

## Decisiones que documenta `rds_config.json`

- `db.t3.micro` — burstable, free tier en AWS real
- `BackupRetentionPeriod: 7` — habilita PITR
- `MultiAZ: false` — dev. En prod, `true` (ver decisión 009 en `docs/decisions.md`)
- `StorageEncrypted: true` — **se elige al crear**, no se agrega después
- `PubliclyAccessible: false` — la DB vive privada, siempre

## ¿Por qué tablas nuevas (`app_users`, etc.) y no las de Olist?

- **Olist (lab 02)**: datos analíticos del e-commerce → viven en el data lake (S3, lab 06)
- **Base del lab 08**: base transaccional de la app (sesiones, audit, usuarios CRUD) → RDS

Mezclar analytics con transaccional confunde el "para qué sirve cada storage". Este lab practica el segundo.

## Cómo se aplica en la práctica

`scripts/rds_demo.py` hace el flujo:

1. Crea el secret con la password generada
2. Crea el SG de la DB referenciando `app-private-sg` (del lab 07)
3. Crea el DB subnet group
4. `create-db-instance` — ministack levanta el postgres
5. Espera a `available`
6. Aplica `seed.sql` vía `docker exec ministack-rds-app-db`
7. Verifica filas
8. Snapshot para backup

## Managed vs self-managed

Este lab enseña **RDS puro** porque ministack lo permite. La decisión pedagógica "managed vs self-managed" queda como discusión conceptual en el paso 6 del lab, con la tabla side-by-side de qué tareas asume cada uno.

**Regla:** RDS **si podés**. Self-managed solo si tenés requerimientos que RDS no cubre.
