# Convenience targets. Run `make help` for the list.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help install seed test lint up down logs ps dags pipeline clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install the package with dev extras
	python3 -m venv .venv && . .venv/bin/activate && \
		pip install -U pip && pip install -e ".[dev,db]"

seed: ## Generate simulated LMS data into data/raw
	. .venv/bin/activate && python -m sla.simulate.generate

test: ## Run the test suite
	. .venv/bin/activate && pytest

lint: ## Run ruff
	. .venv/bin/activate && ruff check .

up: ## Start the stack (postgres, airflow, chromadb)
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Tail all service logs
	docker compose logs -f

ps: ## Show service status
	docker compose ps

dags: ## List Airflow DAGs inside the scheduler
	docker compose exec airflow-scheduler airflow dags list

pipeline: ## Trigger ingest, transform then indicators DAGs (in order)
	docker compose exec airflow-scheduler airflow dags trigger dag_ingest
	docker compose exec airflow-scheduler airflow dags trigger dag_transform
	docker compose exec airflow-scheduler airflow dags trigger dag_indicators

rag-ingest: ## Embed pedagogy docs into ChromaDB (via the api container)
	docker compose exec api python -m sla.rag.ingest

api-logs: ## Tail the API logs
	docker compose logs -f api

dashboard-logs: ## Tail the Streamlit logs
	docker compose logs -f dashboard

clean: ## Stop the stack and remove volumes (DESTRUCTIVE)
	docker compose down -v
