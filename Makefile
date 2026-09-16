.PHONY: setup up down test lint ingest reset-db eval clean

setup:      ## pre-flight checks + local env via uv (fast iteration)
	./scripts/bootstrap.sh

up:         ## full containerized stack (app + db)
	docker compose up -d --build

down:
	docker compose down

ingest:     ## chunk + embed + store runbooks (default: data/runbooks/gitlab)
	uv run python scripts/ingest.py $(or $(PATH_TO_INGEST),data/runbooks/gitlab)

reset-db:   ## delete all rows from the chunks table (schema + container untouched)
	uv run python scripts/reset_db.py

clean:      ## nuke local env + volumes, start fresh
	docker compose down -v
	rm -rf .venv
