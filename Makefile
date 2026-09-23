# =============================================================
# Makefile del proyecto ETL Biomasa Residual
# =============================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash
PYTHON := python
PIP := pip
DOCKER_COMPOSE := docker compose
DASHBOARD_PORT ?= 8501

.PHONY: help install install-dev install-etl install-dashboard \
        etl dashboard \
        test test-cov lint format \
        docker-build docker-up docker-down docker-logs docker-shell \
        docker-etl docker-clean \
        clean clean-data clean-cache clean-all

# =============================================================
# Ayuda
# =============================================================
help:
	@echo "Targets disponibles:"
	@echo ""
	@echo "  Instalación"
	@echo "    install-etl          Instala dependencias del pipeline ETL"
	@echo "    install-dashboard    Instala dependencias del dashboard (Streamlit)"
	@echo "    install-dev          Instala con dependencias de desarrollo"
	@echo ""
	@echo "  Ejecución local"
	@echo "    etl                  Ejecuta el pipeline ETL"
	@echo "    dashboard            Levanta Streamlit en modo desarrollo"
	@echo ""
	@echo "  Calidad"
	@echo "    test                 Corre la suite completa de tests"
	@echo "    test-cov             Tests con reporte de cobertura"
	@echo "    lint                 Verifica estilo y tipos"
	@echo "    format               Formatea el código"
	@echo ""
	@echo "  Docker"
	@echo "    docker-build         Construye la imagen del ETL/dashboard"
	@echo "    docker-up            Levanta worker + scheduler + dashboard"
	@echo "    docker-down          Detiene y elimina contenedores"
	@echo "    docker-logs          Sigue los logs del dashboard"
	@echo "    docker-etl           Ejecuta el pipeline ETL como job"
	@echo "    docker-clean         Elimina imágenes y volúmenes"
	@echo ""
	@echo "  Limpieza"
	@echo "    clean                Limpia outputs generados"
	@echo "    clean-data           Limpia datos intermedios y procesados"
	@echo "    clean-cache          Limpia cachés de Python"
	@echo "    clean-all            Limpieza completa"

# =============================================================
# Instalación
# =============================================================
install-etl:
	$(PIP) install -e ".[etl]"

install-dashboard:
	$(PIP) install -e ".[dashboard]"

install-dev:
	$(PIP) install -e ".[dev]"

# =============================================================
# Ejecución local
# =============================================================
etl:
	$(PYTHON) -m etl.pipelines.run_etl --config config/paths.yaml

dashboard:
	streamlit run dashboard/app.py --server.port=$(DASHBOARD_PORT)

# =============================================================
# Calidad
# =============================================================
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=etl --cov-report=term-missing --cov-report=html

lint:
	ruff check etl/ tests/ dashboard/
	mypy etl/ --ignore-missing-imports

format:
	ruff format etl/ tests/ dashboard/
	ruff check --fix etl/ tests/ dashboard/

# =============================================================
# Docker
# =============================================================
docker-build:
	$(DOCKER_COMPOSE) build etl_pipeline

docker-up:
	$(DOCKER_COMPOSE) up -d --build
	@echo "Dashboard:  http://localhost:$(DASHBOARD_PORT)"
	@echo "Scheduler:  config/schedule.ini (cron ETL)"
	@echo "Worker ETL: biomasa_etl_worker"

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f dashboard

docker-shell:
	$(DOCKER_COMPOSE) run --rm --entrypoint /bin/bash dashboard

docker-etl:
	$(DOCKER_COMPOSE) --profile etl run --rm etl_pipeline

docker-clean:
	$(DOCKER_COMPOSE) down -v --rmi local
	docker system prune -f

# =============================================================
# Limpieza
# =============================================================
clean: clean-data clean-cache
	rm -rf outputs/figures/* outputs/tables/* outputs/reports/*
	rm -rf logs/*.log
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-data:
	rm -rf data/interim/* data/processed/* data/audit/*

clean-cache:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean clean-data docker-clean
	@echo "Limpieza completa ejecutada"