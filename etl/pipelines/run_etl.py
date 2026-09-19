"""
Entrypoint del pipeline ETL de biomasa residual.

Orquesta el flujo end-to-end:
    1. Carga de fuentes primarias (CBA, MAGYP) y tabla IC.
    2. Normalización léxica y geográfica.
    3. Resolución de agregados vs componentes.
    4. Agrupación por clave natural.
    5. Reconciliación multi-fuente por mayor producción.
    6. Cálculo de biomasa residual con flags de validez.
    7. Validación de invariantes.
    8. Persistencia de artefactos curados y de auditoría.

Uso:
    python -m etl.pipelines.run_etl --config config/paths.yaml
"""

from __future__ import annotations

import argparse
import logging
import logging.config
import sys
from pathlib import Path

import pandas as pd
import yaml

from etl.loaders.save_processed import save_processed_artifacts
from etl.reference.crop_taxonomy import CROP_TAXONOMY
from etl.reference.load_ic import load_ic_table
from etl.transformers.biomass import (
    add_density_columns,
    add_validity_flags,
    compute_biomass,
    report_exclusion_impact,
)
from etl.transformers.crop_consolidation import resolve_crops
from etl.transformers.geography import flag_invalid_geo, normalize_geo
from etl.transformers.reconciliation import (
    DEFAULT_KEY,
    PROD_COL,
    SUP_COL,
    coverage_report,
    reconciliar_por_mayor_produccion,
)
from etl.transformers.string_utils import clean_str
from etl.transformers.validation import validar_biomasa, validar_reconciliacion

logger = logging.getLogger("etl")

# =============================================================
# Constantes de configuración
# =============================================================
DEFAULT_CONFIG_PATH = "config/paths.yaml"
DEFAULT_LOGGING_PATH = "config/logging.yaml"

CBA_RAW_FILENAME = "datos_bolsa_granos_cba.csv"
MAGYP_RAW_FILENAME = "datos_estimaciones.csv"

CBA_RENAME_MAP = {
    "PROVINCIA": "Provincia",
    "DEPARTAMENTO": "Departamento",
    "CULTIVO": "Cultivo",
    "CAMPAÑA": "Campaña",
}

MAGYP_NUM_COLS = ["Sup. Sembrada", "Sup. Cosechada", "Producción", "Rendimiento"]
GROUP_KEYS = ["Campaña", "Provincia", "Departamento", "Cultivo"]


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


def _process_cba(raw_path: Path) -> pd.DataFrame:
    """
    Aplica el pipeline de limpieza a la fuente CBA.

    Args:
        raw_path: Ruta del CSV crudo de CBA.

    Returns:
        DataFrame normalizado con columnas canónicas.
    """
    df = pd.read_csv(raw_path)
    df = df.drop(
        columns=["RENDIMIENTO GRANO LIMPIO Y SECO", "PRODUCCIÓN GRANO LIMPIO Y SECO"]
    ).dropna()
    df = df.rename(columns=CBA_RENAME_MAP)
    df["Cultivo"] = df["Cultivo"].apply(clean_str)
    df = normalize_geo(df)
    df = flag_invalid_geo(df)
    df = resolve_crops(df, CROP_TAXONOMY)
    df = df.drop(columns=["_dept_valido"])
    return df


def _process_magyp(raw_path: Path) -> pd.DataFrame:
    """
    Aplica el pipeline de limpieza a la fuente MAGYP.

    Args:
        raw_path: Ruta del CSV crudo de MAGYP.

    Returns:
        DataFrame normalizado con columnas canónicas.
    """
    df = pd.read_csv(raw_path, encoding="utf-8-sig")
    df["Cultivo"] = df["Cultivo"].apply(clean_str)
    df = normalize_geo(df)
    df = flag_invalid_geo(df)
    df = resolve_crops(df, CROP_TAXONOMY)
    df = df.drop(columns=["_dept_valido"])
    for c in MAGYP_NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _group_and_standardize(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
    """
    Agrupa por clave natural y estandariza el esquema de columnas.

    Args:
        df: DataFrame ya resuelto.
        fuente: Identificador de fuente ('magyp_estimaciones' | 'bolsa_cereales_cba').

    Returns:
        DataFrame con columnas estandarizadas y columna 'fuente'.
    """
    if fuente == "magyp_estimaciones":
        grouped = (
            df.groupby(GROUP_KEYS, as_index=False)
            .agg({"Sup. Cosechada": "sum", "Producción": "sum"})
        )
        grouped["Rendimiento (Tn/Ha)"] = grouped["Producción"] / grouped["Sup. Cosechada"]
        grouped = grouped.rename(columns={
            "Sup. Cosechada": "Superficie (Ha)",
            "Producción": "Produccion (Tn)",
        })
    else:
        grouped = (
            df.groupby(GROUP_KEYS, as_index=False)
            .agg({"COSECHADAS": "sum", "PRODUCCIÓN": "sum"})
        )
        grouped["Rendimiento (Tn/Ha)"] = grouped["PRODUCCIÓN"] / grouped["COSECHADAS"]
        grouped = grouped.rename(columns={
            "COSECHADAS": "Superficie (Ha)",
            "PRODUCCIÓN": "Produccion (Tn)",
        })
    grouped = grouped[[
        "Provincia", "Departamento", "Campaña", "Cultivo",
        "Superficie (Ha)", "Produccion (Tn)", "Rendimiento (Tn/Ha)",
    ]]
    grouped["fuente"] = fuente
    return grouped


def run(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """
    Ejecuta el pipeline ETL completo.

    Args:
        config_path: Ruta del archivo de configuración.

    Returns:
        Diccionario con paths de los artefactos persistidos.
    """
    config = load_config(config_path)
    raw_dir = Path(config["data"]["raw"])
    ref_dir = Path(config["data"]["reference"])
    processed_dir = Path(config["data"]["processed"])
    audit_dir = Path(config["data"]["audit"])

    # --- 1. Carga de fuentes ---
    logger.info("Cargando fuentes primarias")
    df_cba_raw = _process_cba(raw_dir / CBA_RAW_FILENAME)
    df_magyp_raw = _process_magyp(raw_dir / MAGYP_RAW_FILENAME)
    df_ic = load_ic_table(ref_dir)

    # --- 2. Agrupación y estandarización ---
    df_cba = _group_and_standardize(df_cba_raw, "bolsa_cereales_cba")
    df_magyp = _group_and_standardize(df_magyp_raw, "magyp_estimaciones")

    # --- 3. Reconciliación multi-fuente ---
    df_all = pd.concat([df_cba, df_magyp], ignore_index=True)
    logger.info("Cobertura:\n%s", coverage_report(df_all).to_string())
    df_final, df_descartado = reconciliar_por_mayor_produccion(df_all, DEFAULT_KEY, PROD_COL)

    # --- 4. Validación de reconciliación ---
    validar_reconciliacion(df_final, df_all, DEFAULT_KEY)

    # --- 5. Cálculo de biomasa ---
    df_biomasa = compute_biomass(df_final, df_ic)
    df_biomasa = add_validity_flags(df_biomasa)

    impacto = report_exclusion_impact(df_biomasa)
    logger.info("Impacto de exclusión por falta de IC:\n%s", impacto.to_string())

    df_biomasa_validos = df_biomasa[df_biomasa["_valido_biomasa"]].copy()
    df_biomasa_validos = add_density_columns(df_biomasa_validos)

    # --- 6. Validación de biomasa ---
    validar_biomasa(df_biomasa)

    # --- 7. Persistencia ---
    paths = save_processed_artifacts(
        df_biomasa=df_biomasa_validos,
        df_descartado=df_descartado,
        df_discrepancias=pd.DataFrame(),  # Placeholder; ver decisión abajo
        processed_dir=processed_dir,
        audit_dir=audit_dir,
    )
    logger.info("Pipeline completado. Artefactos: %s", paths)
    return paths


def main() -> int:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(description="ETL de biomasa residual agrícola")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config YAML de rutas")
    parser.add_argument("--log-config", default=DEFAULT_LOGGING_PATH, help="Config YAML de logging")
    args = parser.parse_args()

    setup_logging(args.log_config)

    try:
        run(args.config)
    except Exception:
        logger.exception("Fallo en pipeline ETL")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())