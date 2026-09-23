"""
Persistencia de artefactos del pipeline.

Centraliza la escritura a disco de datasets curados y de auditoría.
Garantiza creación de directorios, formato consistente (Parquet con
compresión snappy) y logging de la operación.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
PARQUET_ENGINE = "pyarrow"
PARQUET_COMPRESSION = "snappy"


def save_parquet(df: pd.DataFrame, path: Path | str) -> Path:
    """
    Persiste un DataFrame en formato Parquet.

    Crea directorios padre si no existen. Usa engine pyarrow y
    compresión snappy por defecto.

    Args:
        df: DataFrame a persistir.
        path: Ruta de destino.

    Returns:
        Path absoluto del archivo persistido.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(
        path,
        engine=PARQUET_ENGINE,
        compression=PARQUET_COMPRESSION,
        index=False,
    )
    logger.info("Persistido %s (%d filas)", path, len(df))
    return path.resolve()


def save_processed_artifacts(
    df_biomasa: pd.DataFrame,
    df_descartado: pd.DataFrame,
    df_discrepancias: pd.DataFrame,
    processed_dir: Path | str,
    audit_dir: Path | str,
) -> dict[str, Path]:
    """
    Persiste el conjunto de artefactos del pipeline.

    Args:
        df_biomasa: Dataset curado de biomasa válida.
        df_descartado: Registros descartados en reconciliación.
        df_discrepancias: Discrepancias CBA vs MAGYP.
        processed_dir: Directorio de salida curada.
        audit_dir: Directorio de salida de auditoría.

    Returns:
        Diccionario con paths de los archivos persistidos.
    """
    processed_dir = Path(processed_dir)
    audit_dir = Path(audit_dir)

    paths = {
        "biomasa": save_parquet(df_biomasa, processed_dir / "biomasa_validos.parquet"),
        "descartados": save_parquet(df_descartado, audit_dir / "descartados_reconciliacion.parquet"),
        "discrepancias": save_parquet(df_discrepancias, audit_dir / "discrepancias_cba_vs_magyp.parquet"),
    }
    return paths