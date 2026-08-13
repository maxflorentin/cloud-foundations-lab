.PHONY: setup plan-dev apply-dev plan-prod apply-prod checks destroy-dev destroy-prod help

DEV  := infra/envs/dev
PROD := infra/envs/prod

# ── Setup ─────────────────────────────────────────────────────────────────────

setup:
	@echo "==> tofu init dev..."
	cd $(DEV) && tofu init
	@echo "==> tofu init prod..."
	cd $(PROD) && tofu init
	@echo "✅ Providers descargados"

# ── Dev ───────────────────────────────────────────────────────────────────────

plan-dev:
	cd $(DEV) && tofu plan

apply-dev:
	cd $(DEV) && tofu apply -auto-approve

destroy-dev:
	cd $(DEV) && tofu destroy -auto-approve

# ── Prod ──────────────────────────────────────────────────────────────────────

plan-prod:
	cd $(PROD) && tofu plan

apply-prod:
	cd $(PROD) && tofu apply -auto-approve

destroy-prod:
	cd $(PROD) && tofu destroy -auto-approve

# ── Verificación ──────────────────────────────────────────────────────────────

checks:
	@echo "==> Buckets en MinIO:"
	@docker compose -f ../lab-16/compose.yaml exec -T minio mc ls local 2>/dev/null || \
	  docker run --rm --network host --entrypoint mc minio/mc ls http://minioadmin:minioadmin@localhost:9000 2>/dev/null || \
	  echo "(MinIO no accesible via docker — verificá manualmente en http://localhost:9001)"
	@echo ""
	@echo "==> State dev:"
	@test -f .tfstate/dev/terraform.tfstate && echo "  ✅ .tfstate/dev/terraform.tfstate existe" || echo "  ✗ sin state dev"
	@echo "==> State prod:"
	@test -f .tfstate/prod/terraform.tfstate && echo "  ✅ .tfstate/prod/terraform.tfstate existe" || echo "  ✗ sin state prod"

# ── Ayuda ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Targets disponibles:"
	@echo "  make setup        tofu init en dev y prod"
	@echo "  make plan-dev     tofu plan en dev (muestra cambios sin aplicar)"
	@echo "  make apply-dev    tofu apply en dev  → crea dev-{landing,raw,curated,consumer}"
	@echo "  make plan-prod    tofu plan en prod"
	@echo "  make apply-prod   tofu apply en prod → crea prod-{landing,raw,curated,consumer}"
	@echo "  make checks       verifica buckets y state files"
	@echo "  make destroy-dev  elimina recursos dev"
	@echo "  make destroy-prod elimina recursos prod"
	@echo ""
