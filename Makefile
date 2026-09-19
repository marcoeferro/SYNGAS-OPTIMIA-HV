# =============================================================
# Makefile del proyecto ETL Biomasa Residual
# =============================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash
PYTHON := python
PIP := pip
DOCKER_COMPOSE := docker compose
SHAPER_PORT ?= 5454

.PHONY: help install install-dev install-etl install-shaper \
        etl dashboard shaper-dev \
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
	@echo "    install-etl         Instala dependencias del pipeline ETL"
	@echo "    install-dev          Instala con dependencias de desarrollo"
	@echo "    install-shaper       Instala el binario de Shaper (pip)"
	@echo ""
	@echo "  Ejecución local"
	@echo "    etl                  Ejecuta el pipeline ETL"
	@echo "    shaper-dev           Levanta Shaper en modo desarrollo"
	@echo ""
	@echo "  Calidad"
	@echo "    test                 Corre la suite completa de tests"
	@echo "    test-cov             Tests con reporte de cobertura"
	@echo "    lint                 Verifica estilo y tipos"
	@echo "    format               Formatea el código"
	@echo ""
	@echo "  Docker"
	@echo "    docker-build         Construye la imagen del ETL"
	@echo "    docker-up            Levanta Shaper (dashboard)"
	@echo "    docker-down          Detiene y elimina contenedores"
	@echo "    docker-logs          Sigue los logs de Shaper"
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

install-dev:
	$(PIP) install -e ".[dev]"

install-shaper:
	$(PIP) install shaper-bin

# =============================================================
# Ejecución local
# =============================================================
etl:
	$(PYTHON) -m etl.pipelines.run_etl --config config/paths.yaml

shaper-dev:
	shaper dev

# =============================================================
# Calidad
# =============================================================
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=etl --cov-report=term-missing --cov-report=html

lint:
	ruff check etl/ tests/
	mypy etl/ --ignore-missing-imports

format:
	ruff format etl/ tests/
	ruff check --fix etl/ tests/

# =============================================================
# Docker
# =============================================================
docker-build:
	$(DOCKER_COMPOSE) build etl_pipeline

docker-up:
	$(DOCKER_COMPOSE) up -d dashboard
	@echo "Shaper disponible en http://localhost:$(SHAPER_PORT)"

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