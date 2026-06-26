.DEFAULT_GOAL := help

.PHONY: help install lint format test infra-up infra-down topics list-topics consume \
        produce bootstrap stream batch benchmark smoke-test

PYTHON ?= python
POETRY ?= poetry
COMPOSE ?= docker compose
COMPOSE_FILE ?= infrastructure/docker-compose.yml

PRODUCE_ARGS ?= --rate 100 --duration 60
SMOKE_PRODUCE_ARGS ?= --rate 50 --duration 5
SMOKE_CONSUME_ARGS ?= --max-messages 10 --timeout-seconds 10

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*## "; printf "Available targets:\n"} \
	      /^[a-zA-Z_-]+:.*## / { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install runtime and dev dependencies via Poetry
	$(POETRY) install

lint: ## Run ruff, isort --check, and black --check
	$(POETRY) run ruff check src tests
	$(POETRY) run isort --check-only src tests
	$(POETRY) run black --check src tests

format: ## Apply isort, black, and ruff --fix
	$(POETRY) run isort src tests
	$(POETRY) run black src tests
	$(POETRY) run ruff check --fix src tests

test: ## Run the pytest suite with coverage
	$(POETRY) run pytest

infra-up: ## Start local infrastructure (Kafka, MinIO, Spark) via docker compose
	./scripts/infra-up.sh

infra-down: ## Tear down local infrastructure
	./scripts/infra-down.sh

topics: ## Create the Kafka topics this project relies on (idempotent)
	./scripts/create-topics.sh

list-topics: ## List all Kafka topics on the local broker
	./scripts/list-topics.sh

consume: ## Consume a sample of messages from customer_events for inspection
	./scripts/consume-sample.sh

produce: ## Run the Kafka producer (override flags with PRODUCE_ARGS=...)
	$(POETRY) run bash scripts/produce.sh $(PRODUCE_ARGS)

bootstrap: ## Create the Iceberg events table inside the spark container (idempotent)
	./scripts/bootstrap-iceberg.sh

stream: ## Run the Spark structured streaming job
	$(POETRY) run python -m lakehouse.streaming

batch: ## Run the Spark batch job
	$(POETRY) run python -m lakehouse.batch

benchmark: ## Run the pipeline benchmark script
	$(POETRY) run bash scripts/benchmark.sh

smoke-test: ## End-to-end local check: infra → topics → short producer run → sample consume
	$(MAKE) infra-up
	$(MAKE) topics
	$(POETRY) run bash scripts/produce.sh $(SMOKE_PRODUCE_ARGS)
	./scripts/consume-sample.sh $(SMOKE_CONSUME_ARGS)
