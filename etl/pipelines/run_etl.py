"""
Entrypoint del pipeline ETL de biomasa residual.

Orquesta el flujo end-to-end:
    1. Extracción de fuentes primarias (CBA, MAGYP) hacia data/raw
       con nombres timestamped ``YYYYMMDDHHMMSS_<stem>.csv``.
    2. Carga del artefacto raw más reciente de cada fuente + tabla IC.
    3. Limpieza léxica / geográfica y resolución de cultivos.
    4. Agrupación por clave natural y estandarización de esquema.
    5. Reconciliación multi-fuente por mayor producción.
    6. Cálculo de biomasa residual con flags de validez.
    7. Cálculo energético-financiero APL PP30 (kWh y ARS).
    8. Validación de invariantes.
    9. Persistencia de artefactos curados y de auditoría.

Uso:
    python -m etl.pipelines.run_etl --config config/paths.yaml
    python -m etl.pipelines.run_etl --skip-extract
"""

from __future__ import annotations

import argparse
import logging
import logging.config
import sys
from pathlib import Path

import pandas as pd
import yaml

from etl.extractors import scrape_bolsa_cereales_cba as extract_cba
from etl.extractors import scrape_estimaciones_agricolas as extract_magyp
from etl.extractors.io_utils import (
    RAW_STEM_CBA,
    RAW_STEM_MAGYP,
    find_latest_raw,
)
from etl.loaders.save_processed import save_processed_artifacts
from etl.reference.load_ic import load_ic_table
from etl.transformers.biomass import (
    add_density_columns,
    add_validity_flags,
    compute_biomass,
    report_exclusion_impact,
)
from etl.transformers.energy_finance import add_energy_finance_columns
from etl.transformers.reconciliation import (
    DEFAULT_KEY,
    PROD_COL,
    coverage_report,
    reconciliar_por_mayor_produccion,
)
from etl.transformers.source_cleaning import (
    FUENTE_CBA,
    FUENTE_MAGYP,
    group_and_standardize,
    load_cba_raw,
    load_magyp_raw,
    process_cba,
    process_magyp,
)
from etl.transformers.validation import validar_biomasa, validar_reconciliacion

logger = logging.getLogger("etl")

# =============================================================
# Constantes de configuración
# =============================================================
DEFAULT_CONFIG_PATH = "config/paths.yaml"
DEFAULT_LOGGING_PATH = "config/logging.yaml"
DEFAULT_TARIFAS_PATH = "data/reference"


def setup_logging(logging_path: str | Path = DEFAULT_LOGGING_PATH) -> None:
    """
    Inicializa la configuración de logging desde YAML.

    Args:
        logging_path: Ruta del archivo de configuración.
    """
    logging_path = Path(logging_path)
    if logging_path.exists():
        with open(logging_path, encoding="utf-8") as f:
            logging.config.dictConfig(yaml.safe_load(f))
    else:
        logging.basicConfig(level=logging.INFO)


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """
    Carga la configuración de rutas del proyecto.

    Args:
        config_path: Ruta del archivo YAML de configuración.

    Returns:
        Diccionario con la configuración.
    """
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_extract_stage(raw_dir: Path) -> dict[str, Path]:
    """
    Ejecuta los extractors de CBA y MAGYP.

    Cada extractor escribe un CSV timestamped en ``raw_dir`` y devuelve
    la ruta del artefacto generado.

    Args:
        raw_dir: Directorio ``data/raw``.

    Returns:
        Diccionario ``{"cba": Path, "magyp": Path}``.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extract CBA → %s", raw_dir)
    cba_path = extract_cba.run_extractor(output_dir=raw_dir)

    logger.info("Extract MAGYP → %s", raw_dir)
    magyp_path = extract_magyp.run_extractor(output_dir=raw_dir)

    return {"cba": cba_path, "magyp": magyp_path}


def resolve_raw_paths(
    raw_dir: Path,
    extracted: dict[str, Path] | None = None,
) -> dict[str, Path]:
    """
    Resuelve las rutas raw a usar en la etapa de transformación.

    Si ``extracted`` viene de ``run_extract_stage``, se usan esas rutas.
    Si no, se busca el artefacto más reciente (timestamped o legacy)
    para cada stem.

    Args:
        raw_dir: Directorio ``data/raw``.
        extracted: Salida opcional de la etapa de extracción.

    Returns:
        Diccionario ``{"cba": Path, "magyp": Path}``.
    """
    if extracted is not None:
        return extracted

    return {
        "cba": find_latest_raw(raw_dir, RAW_STEM_CBA),
        "magyp": find_latest_raw(raw_dir, RAW_STEM_MAGYP),
    }


def run(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    *,
    skip_extract: bool = False,
    tarifas_path: str | Path = DEFAULT_TARIFAS_PATH,
) -> dict:
    """
    Ejecuta el pipeline ETL completo.

    Args:
        config_path: Ruta del archivo de configuración de paths.
        skip_extract: Si True, no descarga fuentes y usa el raw más
            reciente ya presente en disco.
        tarifas_path: Ruta al JSON de tarifas PP30.

    Returns:
        Diccionario con paths de los artefactos persistidos.
    """
    config = load_config(config_path)
    raw_dir = Path(config["data"]["raw"])
    ref_dir = Path(config["data"]["reference"])
    processed_dir = Path(config["data"]["processed"])
    audit_dir = Path(config["data"]["audit"])

    # --- 1. Extracción ---
    extracted: dict[str, Path] | None = None
    if skip_extract:
        logger.info("Skip extract: se usará el raw más reciente en disco")
    else:
        logger.info("Ejecutando etapa de extracción")
        extracted = run_extract_stage(raw_dir)

    raw_paths = resolve_raw_paths(raw_dir, extracted)
    logger.info("Raw CBA:   %s", raw_paths["cba"])
    logger.info("Raw MAGYP: %s", raw_paths["magyp"])

    # --- 2. Carga + limpieza de fuentes ---
    logger.info("Cargando y limpiando fuentes primarias")
    df_cba_raw = process_cba(load_cba_raw(raw_paths["cba"]))
    df_magyp_raw = process_magyp(load_magyp_raw(raw_paths["magyp"]))
    df_ic = load_ic_table(ref_dir)

    # --- 3. Agrupación y estandarización ---
    df_cba = group_and_standardize(df_cba_raw, FUENTE_CBA)
    df_magyp = group_and_standardize(df_magyp_raw, FUENTE_MAGYP)

    # --- 4. Reconciliación multi-fuente ---
    df_all = pd.concat([df_cba, df_magyp], ignore_index=True)
    logger.info("Cobertura:\n%s", coverage_report(df_all).to_string())
    df_final, df_descartado = reconciliar_por_mayor_produccion(
        df_all, DEFAULT_KEY, PROD_COL
    )

    # --- 5. Validación de reconciliación ---
    validar_reconciliacion(df_final, df_all, DEFAULT_KEY)

    # --- 6. Cálculo de biomasa ---
    df_biomasa = compute_biomass(df_final, df_ic)
    df_biomasa = add_validity_flags(df_biomasa)

    impacto = report_exclusion_impact(df_biomasa)
    logger.info(
        "Impacto de exclusión (_valido_biomasa=False):\n%s",
        impacto.to_string(),
    )

    df_biomasa_validos = df_biomasa[df_biomasa["_valido_biomasa"]].copy()
    df_biomasa_validos = add_density_columns(df_biomasa_validos)

    # --- 7. Energía + finanzas PP30 ---
    logger.info("Calculando métricas energéticas y financieras PP30")
    df_biomasa_validos = add_energy_finance_columns(
        df_biomasa_validos,
        tarifas_path=tarifas_path,
    )

    # --- 8. Validación de biomasa ---
    validar_biomasa(df_biomasa)

    # --- 9. Persistencia ---
    paths = save_processed_artifacts(
        df_biomasa=df_biomasa_validos,
        df_descartado=df_descartado,
        df_discrepancias=pd.DataFrame(),
        processed_dir=processed_dir,
        audit_dir=audit_dir,
    )
    logger.info("Pipeline completado. Artefactos: %s", paths)
    return paths


def main() -> int:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(
        description="ETL de biomasa residual agrícola"
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Config YAML de rutas",
    )
    parser.add_argument(
        "--log-config",
        default=DEFAULT_LOGGING_PATH,
        help="Config YAML de logging",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Omite descarga de fuentes; usa el raw más reciente en disco",
    )
    parser.add_argument(
        "--tarifas",
        default=DEFAULT_TARIFAS_PATH,
        help="JSON de tarifas o directorio data/reference",
    )
    args = parser.parse_args()

    setup_logging(args.log_config)

    try:
        run(
            args.config,
            skip_extract=args.skip_extract,
            tarifas_path=args.tarifas,
        )
    except Exception:
        logger.exception("Fallo en pipeline ETL")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
