.PHONY: setup up down logs test test-api test-ml test-web smoke supabase secrets docs
setup:        ## Crea .env con secretos aleatorios
	./scripts/gen-secrets.sh --write
up: setup     ## Levanta todo el stack
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f --tail=100 api worker ml
test: test-api test-ml test-web
test-api:
	cd apps/api && python -m pytest -q
test-ml:
	cd apps/ml && python -m pytest -q
test-web:
	cd apps/web && npm ci && npm test && npm run typecheck && npm run build
smoke:
	./scripts/smoke.sh
docs:        ## Genera la documentación en PDF (docs/pdf)
	python scripts/md2pdf.py --out docs/pdf docs/MANUAL_USO.md docs/MANUAL_RESPONSABLE.md docs/architecture/ARQUITECTURA.md
supabase:
	./scripts/supabase_deploy.sh
secrets:
	./scripts/gen-secrets.sh
