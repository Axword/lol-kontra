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
	docker compose exec api python manage.py migrate

makemigrations:
	docker compose exec api python manage.py makemigrations

createsuperuser:
	docker compose exec api python manage.py createsuperuser

seed:
	docker compose exec api python manage.py seed_players --full

seed-sample:
	docker compose exec api python manage.py seed_players --sample

seed-clear:
	docker compose exec api python manage.py seed_players --full --clear

scrape:
	docker compose exec api python -m scraper.main --full

scrape-load:
	docker compose exec api python manage.py seed_players --full --clear

test:
	docker compose exec api pytest -q
	docker compose exec frontend npm test --if-present

shell:
	docker compose exec api python manage.py shell

bash-api:
	docker compose exec api bash

bash-front:
	docker compose exec frontend sh

clean:
	docker compose down -v
	docker system prune -f
