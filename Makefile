.PHONY: help up down restart logs init seed test benchmark reset clean build

help:
	@echo "Enterprise Data Governance System — Commands"
	@echo "--------------------------------------------------------"
	@echo "  make up          Start all containers via Docker Compose"
	@echo "  make down        Stop all running containers"
	@echo "  make restart     Restart all containers"
	@echo "  make logs        Follow container logs"
	@echo "  make init        Run database migrations, OpenFGA model & seeds"
	@echo "  make seed        Re-run synthetic documents and embedding seed"
	@echo "  make test        Execute full automated pytest test suite"
	@echo "  make benchmark   Run performance and latency benchmark suite"
	@echo "  make reset       Clean volume slate and re-initialize system"
	@echo "  make clean       Remove temporary Python/test build artifacts"
	@echo "  make build       Rebuild Docker images"

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

build:
	docker compose build

init:
	python scripts/initialize.py

seed:
	python scripts/seed_data.py

test:
	pytest backend/tests/ -v --cov=backend/src

benchmark:
	python scripts/benchmark.py

reset:
	./scripts/reset_local.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache

