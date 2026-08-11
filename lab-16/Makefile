.PHONY: up down zones landing raw curated consumer permisos checks reset help

TODAY     := $(shell date +%F)
TRINO     := docker compose exec -T trino trino --catalog lake --output-format TSV
MC        := docker compose exec -T minio mc
PG        := docker compose exec -T postgres psql -U app -d billetera

# ── Ciclo de vida ─────────────────────────────────────────────────────────────

up:
	docker compose up -d
	@echo "Esperando servicios..."
	@docker compose exec minio mc alias set local http://localhost:9000 minioadmin minioadmin 2>/dev/null || true
	@echo ""
	@echo "Trino UI: http://localhost:8080"
	@echo "MinIO UI: http://localhost:9001  (minioadmin / minioadmin)"
	@echo ""
	@echo "Verificar metastore: make check-metastore"

down:
	docker compose down -v

reset: down up

# ── Infraestructura ───────────────────────────────────────────────────────────

zones:
	@echo "==> Creando zonas (buckets)..."
	$(MC) alias set local http://minio:9000 minioadmin minioadmin
	$(MC) mb --ignore-existing local/landing
	$(MC) mb --ignore-existing local/raw
	$(MC) mb --ignore-existing local/curated
	$(MC) mb --ignore-existing local/consumer
	$(MC) ls local
	@echo "✅ Cuatro zonas creadas"

# ── Ingesta ───────────────────────────────────────────────────────────────────

landing:
	@echo "==> Cargando landing: Postgres → MinIO..."
	@docker compose exec -T postgres \
	  psql -U app -d billetera \
	  -c "\copy pagos TO STDOUT WITH CSV HEADER" \
	  | docker compose exec -i minio sh -c \
	    "cat > /tmp/pagos.csv && mc cp /tmp/pagos.csv local/landing/postgres/pagos/fecha_ingesta=$(TODAY)/"
	@docker compose exec -T postgres \
	  psql -U app -d billetera \
	  -c "\copy usuarios TO STDOUT WITH CSV HEADER" \
	  | docker compose exec -i minio sh -c \
	    "cat > /tmp/usuarios.csv && mc cp /tmp/usuarios.csv local/landing/postgres/usuarios/fecha_ingesta=$(TODAY)/"
	docker compose cp seed/csv/operadores.csv minio:/tmp/operadores.csv
	$(MC) cp /tmp/operadores.csv local/landing/externo/operadores/fecha_ingesta=$(TODAY)/
	@echo ""
	@echo "==> Tamaño landing:"
	$(MC) du local/landing
	@echo "✅ Landing cargado"

# ── Zonas Trino ───────────────────────────────────────────────────────────────

raw:
	@echo "==> Creando schemas y tablas raw en Parquet..."
	$(TRINO) --schema landing <<'EOF'
CREATE SCHEMA IF NOT EXISTS lake.landing
  WITH (location = 's3://landing/');
EOF
	$(TRINO) <<'EOF'
CREATE TABLE IF NOT EXISTS lake.landing.pagos_csv (
  pago_id     varchar,
  user_id     varchar,
  monto       varchar,
  moneda      varchar,
  operador_id varchar,
  estado      varchar,
  creado_en   varchar
)
WITH (
  format            = 'CSV',
  csv_separator     = ',',
  skip_header_line_count = 1,
  external_location = 's3://landing/postgres/pagos/fecha_ingesta=$(TODAY)/'
);
EOF
	$(TRINO) <<'EOF'
CREATE TABLE IF NOT EXISTS lake.landing.usuarios_csv (
  user_id   varchar,
  nombre    varchar,
  documento varchar,
  email     varchar,
  pais      varchar,
  creado_en varchar
)
WITH (
  format            = 'CSV',
  csv_separator     = ',',
  skip_header_line_count = 1,
  external_location = 's3://landing/postgres/usuarios/fecha_ingesta=$(TODAY)/'
);
EOF
	$(TRINO) <<'EOF'
CREATE SCHEMA IF NOT EXISTS lake.raw
  WITH (location = 's3://raw/');

CREATE TABLE IF NOT EXISTS lake.raw.pagos (
  pago_id     bigint,
  user_id     integer,
  monto       decimal(12,2),
  moneda      varchar,
  operador_id varchar,
  estado      varchar,
  creado_en   timestamp(6),
  fecha       date
)
WITH (
  format             = 'PARQUET',
  partitioned_by     = ARRAY['fecha'],
  external_location  = 's3://raw/pagos/'
);

INSERT INTO lake.raw.pagos
SELECT
  CAST(pago_id     AS bigint),
  CAST(user_id     AS integer),
  CAST(monto       AS decimal(12,2)),
  moneda,
  operador_id,
  estado,
  CAST(creado_en   AS timestamp(6)),
  CAST(CAST(creado_en AS timestamp(6)) AS date) AS fecha
FROM lake.landing.pagos_csv;
EOF
	$(TRINO) <<'EOF'
CREATE TABLE IF NOT EXISTS lake.raw.usuarios (
  user_id   integer,
  nombre    varchar,
  documento varchar,
  email     varchar,
  pais      varchar,
  creado_en timestamp(6)
)
WITH (
  format            = 'PARQUET',
  external_location = 's3://raw/usuarios/'
);

INSERT INTO lake.raw.usuarios
SELECT
  CAST(user_id   AS integer),
  nombre,
  documento,
  email,
  pais,
  CAST(creado_en AS timestamp(6))
FROM lake.landing.usuarios_csv;
EOF
	$(TRINO) <<'EOF'
CREATE TABLE IF NOT EXISTS lake.raw.operadores (
  operador_id    varchar,
  nombre         varchar,
  tipo           varchar,
  pais           varchar,
  comision_pct   varchar
)
WITH (
  format            = 'CSV',
  csv_separator     = ',',
  skip_header_line_count = 1,
  external_location = 's3://landing/externo/operadores/fecha_ingesta=$(TODAY)/'
);
EOF
	@echo ""
	@echo "==> Tamaño landing vs raw:"
	$(MC) du local/landing
	$(MC) du local/raw
	@echo "✅ Raw listo"

curated:
	@echo "==> Creando curated: tipada, deduplicada, unida, PII enmascarada..."
	$(TRINO) <<'EOF'
CREATE SCHEMA IF NOT EXISTS lake.curated
  WITH (location = 's3://curated/');

CREATE TABLE IF NOT EXISTS lake.curated.pagos
WITH (
  format            = 'PARQUET',
  partitioned_by    = ARRAY['fecha'],
  external_location = 's3://curated/pagos/'
)
AS
WITH dedup AS (
  SELECT *,
    row_number() OVER (PARTITION BY pago_id ORDER BY creado_en DESC) AS rn
  FROM lake.raw.pagos
)
SELECT
  p.pago_id,
  p.user_id,
  p.monto,
  p.moneda,
  p.estado,
  o.nombre                                      AS operador,
  o.tipo                                        AS operador_tipo,
  upper(o.pais)                                 AS operador_pais,
  COALESCE(TRY(CAST(o.comision_pct AS double)), 0.0) AS comision_pct,
  substr(u.documento, 1, 3) || '***'            AS documento_masked,
  regexp_replace(u.email, '^[^@]+', '***')      AS email_masked,
  p.creado_en,
  p.fecha
FROM dedup p
JOIN lake.raw.operadores o ON o.operador_id = p.operador_id
JOIN lake.raw.usuarios   u ON u.user_id     = p.user_id
WHERE p.rn = 1
  AND p.monto > 0;
EOF
	@echo "✅ Curated listo"

consumer:
	@echo "==> Creando tabla consumer: agregados por fecha y país..."
	$(TRINO) <<'EOF'
CREATE SCHEMA IF NOT EXISTS lake.consumer
  WITH (location = 's3://consumer/');

CREATE TABLE IF NOT EXISTS lake.consumer.pagos_diarios
WITH (
  format            = 'PARQUET',
  external_location = 's3://consumer/pagos_diarios/'
)
AS
SELECT
  fecha,
  operador_pais                                              AS pais,
  count(*)                                                   AS pagos,
  sum(monto)                                                 AS monto_total,
  round(
    sum(CASE WHEN estado = 'aprobado' THEN 1.0 ELSE 0.0 END) / count(*),
    4
  )                                                          AS tasa_aprobacion
FROM lake.curated.pagos
GROUP BY fecha, operador_pais
ORDER BY fecha DESC, pais;
EOF
	@echo ""
	@echo "==> Preview pagos_diarios (últimos 5 días):"
	$(TRINO) --execute "SELECT * FROM lake.consumer.pagos_diarios ORDER BY fecha DESC LIMIT 10"
	@echo "✅ Consumer listo"

# ── Permisos por zona ─────────────────────────────────────────────────────────

permisos:
	@echo "==> Creando usuario analista con acceso solo a consumer..."
	$(MC) alias set local http://minio:9000 minioadmin minioadmin
	$(MC) admin user add local analista analista123
	@docker compose exec -T minio sh -c 'cat > /tmp/solo-consumer.json <<'"'"'EOF'"'"' \
{\
  "Version": "2012-10-17",\
  "Statement": [{\
    "Effect": "Allow",\
    "Action": ["s3:GetObject", "s3:ListBucket"],\
    "Resource": ["arn:aws:s3:::consumer", "arn:aws:s3:::consumer/*"]\
  }]\
}\
EOF'
	$(MC) admin policy create local solo-consumer /tmp/solo-consumer.json
	$(MC) admin policy attach local solo-consumer --user analista
	@echo ""
	@echo "==> Verificando permisos (esperar Access Denied en curated y landing):"
	$(MC) alias set analista http://minio:9000 analista analista123
	@echo "--- consumer (debe listar) ---"
	$(MC) ls analista/consumer
	@echo "--- curated (debe fallar) ---"
	$(MC) ls analista/curated 2>&1 || true
	@echo "--- landing (debe fallar) ---"
	$(MC) ls analista/landing 2>&1 || true
	@echo "✅ Permisos aplicados"

# ── Calidad ───────────────────────────────────────────────────────────────────

checks:
	@echo "==> Ejecutando chequeos de calidad sobre curated..."
	@echo ""
	@echo "-- 1. Duplicados de pago_id --"
	$(TRINO) --execute \
	  "SELECT count(*) - count(DISTINCT pago_id) AS duplicados FROM lake.curated.pagos"
	@echo ""
	@echo "-- 2. Nulos en campos críticos --"
	$(TRINO) --execute \
	  "SELECT count(*) AS nulos FROM lake.curated.pagos WHERE operador IS NULL OR pais IS NULL"
	@echo ""
	@echo "-- 3. Rangos de monto --"
	$(TRINO) --execute \
	  "SELECT count(*) AS fuera_de_rango FROM lake.curated.pagos WHERE monto <= 0 OR fecha > current_date"
	@echo ""
	@echo "-- 4. Frescura del dato --"
	$(TRINO) --execute \
	  "SELECT max(fecha) AS ultima_fecha, min(fecha) AS primera_fecha, count(DISTINCT fecha) AS dias FROM lake.curated.pagos"
	@echo ""
	@echo "-- 5. Tamaño por zona --"
	$(MC) du local/landing local/raw local/curated local/consumer
	@echo "✅ Checks completados"

# ── Utilidades ────────────────────────────────────────────────────────────────

check-metastore:
	@echo "Probando conexión metastore → Trino..."
	$(TRINO) --execute "SHOW CATALOGS"
	$(TRINO) --execute "SHOW SCHEMAS FROM lake"

logs:
	docker compose logs -f metastore trino

help:
	@echo ""
	@echo "Targets disponibles:"
	@echo "  make up          Levantar todos los servicios"
	@echo "  make zones       Crear los 4 buckets en MinIO"
	@echo "  make landing     Extraer de Postgres + CSV → landing"
	@echo "  make raw         Convertir a Parquet particionado → raw"
	@echo "  make curated     Limpiar, unir, enmascarar PII → curated"
	@echo "  make consumer    Agregar para el negocio → consumer"
	@echo "  make permisos    Crear usuario analista con acceso solo a consumer"
	@echo "  make checks      Ejecutar chequeos de calidad"
	@echo "  make check-metastore  Verificar que Trino ve el catálogo lake"
	@echo "  make logs        Seguir logs de metastore y trino"
	@echo "  make down        Bajar todo y borrar volúmenes"
	@echo ""
