.PHONY: help install lint format test infra-up infra-down produce stream batch benchmark

PYTHON ?= python
POETRY ?= poetry
COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.yml

help:
	@echo "Available targets:"
	@echo "  install     Install runtime and dev dependencies via Poetry"
	@echo "  lint        Run ruff and isort (check mode) and black --check"
	@echo "  format      Apply black, isort, and ruff --fix to the codebase"
	@echo "  test        Run the pytest suite with coverage"
	@echo "  infra-up    Start local infrastructure (Kafka, MinIO, etc.) via docker compose"
	@echo "  infra-down  Tear down local infrastructure"
	@echo "  produce     Run the Kafka producer module"
	@echo "  stream      Run the Spark structured streaming job"
	@echo "  batch       Run the Spark batch job"
	@echo "  benchmark   Run the pipeline benchmark script"

install:
	$(POETRY) install

lint:
	$(POETRY) run ruff check src tests
	$(POETRY) run isort --check-only src tests
	$(POETRY) run black --check src tests

format:
	$(POETRY) run isort src tests
	$(POETRY) run black src tests
	$(POETRY) run ruff check --fix src tests

test:
	$(POETRY) run pytest

infra-up:
	$(COMPOSE) -f $(COMPOSE_FILE) up -d

infra-down:
	$(COMPOSE) -f $(COMPOSE_FILE) down -v

produce:
	$(POETRY) run python -m lakehouse.producer

stream:
	$(POETRY) run python -m lakehouse.streaming

batch:
	$(POETRY) run python -m lakehouse.batch

benchmark:
	$(POETRY) run bash scripts/benchmark.sh
