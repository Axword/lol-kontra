.PHONY: up down build logs migrate createsuperuser seed scrape test shell bash-api bash-front clean

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec api python manage.py bootstrap_database
	docker compose exec api python manage.py check_release_data

makemigrations:
	docker compose exec api python manage.py makemigrations

createsuperuser:
	docker compose exec api python manage.py createsuperuser

seed:
	docker compose exec api python manage.py seed_players --full

seed-sample:
	docker compose exec api python manage.py seed_players --sample

seed-clear:
	@test "$(CONFIRM_DATA_LOSS)" = "yes" || (echo "Use CONFIRM_DATA_LOSS=yes only for disposable development data"; exit 1)
	docker compose exec api python manage.py seed_players --full --clear

scrape:
	docker compose exec api python -m scraper.main --full

scrape-load:
	docker compose exec api python manage.py seed_players --full

test:
	docker compose exec api pytest -q
	docker compose exec frontend npm test -- --run

shell:
	docker compose exec api python manage.py shell

bash-api:
	docker compose exec api bash

bash-front:
	docker compose exec frontend sh

clean:
	@test "$(CONFIRM_DATA_LOSS)" = "yes" || (echo "Use CONFIRM_DATA_LOSS=yes only to delete local development volumes"; exit 1)
	docker compose down -v
