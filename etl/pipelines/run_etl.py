"""
Entrypoint del pipeline ETL de biomasa residual.

Orquesta el flujo end-to-end:
    1. Extracción de fuentes primarias (CBA, MAGYP) hacia data/raw
       con nombres timestamped ``YYYYMMDDHHMMSS_<stem>.csv``.
    2. Carga del artefacto raw más reciente de cada fuente + tabla IC.
    3. Limpieza léxica / geográfica y resolución de cultivos.
    4. Agrupación por clave natural y estandarización de esquema.
    5. Reconciliación multi-fuente por mayor producción.
    6. Cálculo de biomasa residual (base seca) con flags de validez y
       residuo recuperable.
    7. Cálculo energético-financiero APL PP30 (kWh y ARS) por campaña.
    8. Anualización sobre el período de referencia (últimas N campañas
       completas): potencial energético y económico anual.
    9. Validación de invariantes.
   10. Persistencia de artefactos curados y de auditoría.

Uso:
    python -m etl.pipelines.run_etl --config config/paths.yaml
    python -m etl.pipelines.run_etl --skip-extract
    python -m etl.pipelines.run_etl --skip-extract --skip-tarifas
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
from etl.extractors import scrape_tarifas as extract_tarifas
from etl.extractors.io_utils import (
    RAW_STEM_CBA,
    RAW_STEM_MAGYP,
    find_latest_raw,
)
from etl.loaders.save_processed import save_parquet, save_processed_artifacts
from etl.reference.load_ic import load_ic_table
from etl.transformers.biomass import (
    DEFAULT_FRACCION_RECUPERABLE,
    RESIDUO_REC_COL,
    add_density_columns,
    add_recoverable_residue,
    add_validity_flags,
    compute_biomass,
    report_exclusion_impact,
)
from etl.transformers.energy_finance import (
    COL_BENEFICIO,
    COL_KWH_TOTALES,
    add_energy_finance_columns,
    load_tarifas_config,
)
from etl.transformers.reconciliation import (
    DEFAULT_KEY,
    PROD_COL,
    compute_discrepancies,
    coverage_report,
    reconciliar_por_mayor_produccion,
)
from etl.transformers.reference_period import (
    annualize,
    select_reference_campaigns,
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
# El archivo versionado es ``logging.yml``; antes se buscaba
# ``logging.yaml`` y el logging configurado nunca se aplicaba.
DEFAULT_LOGGING_PATH = "config/logging.yml"
DEFAULT_TARIFAS_PATH = "data/reference"
DEFAULT_N_CAMPANAS = 5

ANNUAL_GROUP_COLS = ["Provincia", "Departamento", "Cultivo"]
ANNUAL_VALUE_COLS = [
    "Superficie (Ha)",
    PROD_COL,
    "Residuo de Biomasa (Tn)",
    RESIDUO_REC_COL,
]


def setup_logging(logging_path: str | Path = DEFAULT_LOGGING_PATH) -> None:
    """
    Inicializa la configuración de logging desde YAML.

    Args:
        logging_path: Ruta del archivo de configuración.
    """
    logging_path = Path(logging_path)
    if logging_path.exists():
        with open(logging_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        # Crear directorios de handlers de archivo (logs/) si no existen.
        for handler in cfg.get("handlers", {}).values():
            if "filename" in handler:
                Path(handler["filename"]).parent.mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(cfg)
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


def run_tarifas_stage(raw_dir: Path, ref_dir: Path) -> Path | None:
    """
    Ejecuta el extractor de cuadros tarifarios.

    No es bloqueante: si falla, el pipeline continúa con el JSON de
    tarifas más reciente en ``ref_dir``.

    Args:
        raw_dir: Directorio ``data/raw`` (los PDF van a ``raw/tarifas``).
        ref_dir: Directorio ``data/reference``.

    Returns:
        Path del JSON generado o None si falló.
    """
    try:
        return extract_tarifas.run_extractor(
            raw_dir=Path(raw_dir) / "tarifas", reference_dir=ref_dir
        )
    except Exception:
        logger.exception("Extracción de tarifas falló; se usa la referencia previa")
        return None


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
    skip_tarifas: bool = False,
    tarifas_path: str | Path | None = None,
    n_campanas: int = DEFAULT_N_CAMPANAS,
    fraccion_recuperable: float | None = None,
) -> dict:
    """
    Ejecuta el pipeline ETL completo.

    Args:
        config_path: Ruta del archivo de configuración de paths.
        skip_extract: Si True, no descarga fuentes y usa el raw más
            reciente ya presente en disco.
        skip_tarifas: Si True, no descarga cuadros tarifarios.
        tarifas_path: JSON de tarifas o directorio. Si None, usa el
            directorio de referencia de la config.
        n_campanas: Campañas completas del período de referencia anual.
        fraccion_recuperable: Fracción del residuo retirable del lote.
            Si None, usa ``parametros_pp30.fraccion_recuperable_default``
            del JSON de tarifas (o 0.5).

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
    if not skip_tarifas:
        logger.info("Ejecutando extracción de cuadros tarifarios")
        run_tarifas_stage(raw_dir, ref_dir)
    tarifas_cfg = load_tarifas_config(tarifas_path or ref_dir)
    if fraccion_recuperable is None:
        fraccion_recuperable = float(
            tarifas_cfg.get("parametros_pp30", {}).get(
                "fraccion_recuperable_default", DEFAULT_FRACCION_RECUPERABLE
            )
        )

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
    df_discrepancias = compute_discrepancies(df_all, DEFAULT_KEY)
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
    df_biomasa_validos = add_recoverable_residue(
        df_biomasa_validos, fraccion_recuperable
    )

    # --- 7. Energía + finanzas PP30 (por campaña) ---
    logger.info("Calculando métricas energéticas y financieras PP30")
    df_biomasa_validos = add_energy_finance_columns(
        df_biomasa_validos,
        config=tarifas_cfg,
    )

    # --- 8. Potencial anual en el período de referencia ---
    campanas_ref = select_reference_campaigns(df_final, n_campanas)
    logger.info("Período de referencia anual: %s", campanas_ref)
    df_anual = annualize(
        df_biomasa_validos, campanas_ref, ANNUAL_GROUP_COLS, ANNUAL_VALUE_COLS
    )
    # Energía y dinero se recalculan sobre el residuo anualizado (así
    # ``equipos_pp30_equivalentes`` queda expresado por año).
    df_anual = add_energy_finance_columns(df_anual, config=tarifas_cfg)
    logger.info(
        "Potencial anual: %.3e kWh/año, %.3e ARS/año (bruto, provincias con tarifa)",
        df_anual[COL_KWH_TOTALES].sum(),
        df_anual[COL_BENEFICIO].sum(),
    )

    # --- 9. Validación de biomasa ---
    validar_biomasa(df_biomasa)

    # --- 10. Persistencia ---
    paths = save_processed_artifacts(
        df_biomasa=df_biomasa_validos,
        df_descartado=df_descartado,
        df_discrepancias=df_discrepancias,
        processed_dir=processed_dir,
        audit_dir=audit_dir,
    )
    paths["potencial_anual"] = save_parquet(
        df_anual, processed_dir / "potencial_energetico_anual.parquet"
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
        "--skip-tarifas",
        action="store_true",
        help="Omite descarga de cuadros tarifarios; usa el JSON más reciente",
    )
    parser.add_argument(
        "--tarifas",
        default=None,
        help="JSON de tarifas o directorio (default: data/reference)",
    )
    parser.add_argument(
        "--n-campanas",
        type=int,
        default=DEFAULT_N_CAMPANAS,
        help="Campañas completas del período de referencia anual",
    )
    parser.add_argument(
        "--fraccion-recuperable",
        type=float,
        default=None,
        help="Fracción del rastrojo retirable del lote (0, 1]",
    )
    args = parser.parse_args()

    setup_logging(args.log_config)

    try:
        run(
            args.config,
            skip_extract=args.skip_extract,
            skip_tarifas=args.skip_tarifas,
            tarifas_path=args.tarifas,
            n_campanas=args.n_campanas,
            fraccion_recuperable=args.fraccion_recuperable,
        )
    except Exception:
        logger.exception("Fallo en pipeline ETL")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
