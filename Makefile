.PHONY: setup up down test lint ingest eval clean

up:         ## full containerized stack (app + db)
	docker compose up -d --build

down:
	docker compose down

clean:      ## nuke local env + volumes, start fresh
	docker compose down -v
	rm -rf .venv
