.PHONY: setup up down test lint ingest eval clean

setup:      ## pre-flight checks + local env via uv (fast iteration)
	./scripts/bootstrap.sh

up:         ## full containerized stack (app + db)
	docker compose up -d --build

down:
	docker compose down

clean:      ## nuke local env + volumes, start fresh
	docker compose down -v
	rm -rf .venv
