.PHONY: setup up down zones landing raw curated consumer permisos checks reset help

TODAY      := $(shell date +%F)
PORT_MINIO ?= 9000

DUCK := ./bin/duckdb
MC   := docker compose exec -T minio mc

# Prepend S3 config (substituye {{PORT}}) y pasa el SQL a DuckDB
duck = cat sql/_s3.sql sql/$(1).sql | sed 's/{{PORT}}/$(PORT_MINIO)/g' | $(DUCK) :memory:

# ── Setup (una vez) ───────────────────────────────────────────────────────────

setup:
	@echo "==> Descargando DuckDB CLI..."
	mkdir -p bin
	ARCH=$$(uname -m); \
	if [ "$$ARCH" = "aarch64" ]; then ZIP=duckdb_cli-linux-aarch64.zip; \
	else ZIP=duckdb_cli-linux-amd64.zip; fi; \
	curl -fsSL "https://github.com/duckdb/duckdb/releases/download/v1.3.2/$$ZIP" \
	  -o /tmp/duckdb.zip
	unzip -o /tmp/duckdb.zip duckdb -d bin/
	chmod +x bin/duckdb
	@echo "✅ bin/duckdb listo"

# ── Ciclo de vida ─────────────────────────────────────────────────────────────

up:
	docker compose up -d
	@echo ""
	@echo "MinIO UI: http://localhost:9001  (minioadmin / minioadmin)"
	@echo ""
	@echo "Próximos pasos:  make zones  →  make landing  →  make raw  →  make curated  →  make consumer"

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
	@echo "==> Landing: Postgres → MinIO (sin transformar)..."
	docker compose exec -T postgres \
	  psql -U app -d billetera \
	  -c "\copy pagos TO STDOUT WITH CSV HEADER" \
	  | docker compose exec -i minio sh -c \
	    "cat > /tmp/pagos.csv && mc cp /tmp/pagos.csv local/landing/postgres/pagos/fecha_ingesta=$(TODAY)/"
	docker compose exec -T postgres \
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

# ── Zonas DuckDB ──────────────────────────────────────────────────────────────

raw:
	@echo "==> Raw: CSV → Parquet tipado y particionado por fecha..."
	$(call duck,raw)
	$(MC) du local/landing local/raw
	@echo "✅ Raw listo"

curated:
	@echo "==> Curated: dedup, join operadores/usuarios, PII enmascarada..."
	$(call duck,curated)
	@echo "✅ Curated listo"

consumer:
	@echo "==> Consumer: agregados diarios por país..."
	$(call duck,consumer)
	@echo "✅ Consumer listo"

# ── Permisos por zona ─────────────────────────────────────────────────────────

permisos:
	@echo "==> Creando usuario analista (acceso solo a consumer)..."
	$(MC) alias set local http://minio:9000 minioadmin minioadmin
	$(MC) admin user add local analista analista123
	printf '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetObject","s3:ListBucket"],"Resource":["arn:aws:s3:::consumer","arn:aws:s3:::consumer/*"]}]}' \
	  | docker compose exec -i minio sh -c "cat > /tmp/solo-consumer.json"
	$(MC) admin policy create local solo-consumer /tmp/solo-consumer.json
	$(MC) admin policy attach local solo-consumer --user analista
	@echo ""
	@echo "==> Verificando permisos:"
	$(MC) alias set analista http://minio:9000 analista analista123
	@echo "--- consumer (debe listar) ---"
	$(MC) ls analista/consumer
	@echo "--- curated (debe fallar con Access Denied) ---"
	$(MC) ls analista/curated 2>&1 || true
	@echo "--- landing (debe fallar con Access Denied) ---"
	$(MC) ls analista/landing 2>&1 || true
	@echo "✅ Permisos aplicados"

# ── Calidad ───────────────────────────────────────────────────────────────────

checks:
	@echo "==> Chequeos de calidad sobre curated..."
	$(call duck,checks)
	@echo ""
	@echo "==> Tamaño por zona:"
	$(MC) du local/landing local/raw local/curated local/consumer
	@echo "✅ Checks completados"

# ── Utilidades ────────────────────────────────────────────────────────────────

logs:
	docker compose logs -f

help:
	@echo ""
	@echo "Targets disponibles:"
	@echo "  make setup      Descargar DuckDB CLI"
	@echo "  make up         Levantar Postgres + MinIO"
	@echo "  make zones      Crear los 4 buckets en MinIO"
	@echo "  make landing    Extraer de Postgres + CSV → landing (sin transformar)"
	@echo "  make raw        CSV → Parquet tipado y particionado"
	@echo "  make curated    Limpiar, unir, enmascarar PII"
	@echo "  make consumer   Agregar por fecha y país para el negocio"
	@echo "  make permisos   Crear usuario analista (acceso solo a consumer)"
	@echo "  make checks     Chequeos de calidad"
	@echo "  make logs       Seguir logs de los servicios"
	@echo "  make down       Bajar todo y borrar volúmenes"
	@echo ""
