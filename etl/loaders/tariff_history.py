"""
Historial de tarifas extraídas (append-only).

Cada documento tarifario procesado agrega una fila a
``data/reference/tarifas_historial.csv`` con la vigencia del cuadro, los
valores extraídos y la huella SHA-256 del archivo fuente. El historial
permite:

- Ver la evolución de cada tarifa en el tiempo (series mensuales).
- Auditar de qué documento salió cada valor.
- Evitar reprocesar o duplicar documentos ya registrados (la clave de
  deduplicación es ``(distribuidora, sha256)``).

Se usa CSV (y no Parquet) para que el historial sea legible y
versionable en git con diffs claros.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Final

import pandas as pd

logger = logging.getLogger(__name__)

HISTORY_FILENAME: Final[str] = "tarifas_historial.csv"
HISTORY_COLUMNS: Final[list[str]] = [
    "distribuidora",
    "vigencia",
    "tarifa_compra_kwh",
    "tarifa_inyeccion_kwh",
    "cargo_fijo_mensual",
    "seccion_compra",
    "n_valores_compra",
    "n_valores_inyeccion",
    "fuente_tipo",
    "documento",
    "sha256",
    "fecha_extraccion",
]
DEDUP_KEY: Final[list[str]] = ["distribuidora", "sha256"]


def history_path(reference_dir: Path | str) -> Path:
    """Ruta del CSV de historial dentro de ``data/reference``."""
    return Path(reference_dir) / HISTORY_FILENAME


def load_history(reference_dir: Path | str) -> pd.DataFrame:
    """
    Carga el historial de tarifas (vacío con esquema si no existe).

    Args:
        reference_dir: Directorio ``data/reference``.

    Returns:
        DataFrame ordenado por distribuidora y vigencia.
    """
    path = history_path(reference_dir)
    if not path.exists():
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    df = pd.read_csv(path, dtype={"vigencia": str, "sha256": str})
    for col in HISTORY_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[HISTORY_COLUMNS].sort_values(["distribuidora", "vigencia"]).reset_index(
        drop=True
    )


def append_history(
    records: list[dict[str, Any]],
    reference_dir: Path | str,
) -> tuple[Path, int]:
    """
    Agrega registros al historial, sin duplicar documentos ya cargados.

    Args:
        records: Filas con (al menos) las columnas de ``HISTORY_COLUMNS``.
        reference_dir: Directorio ``data/reference``.

    Returns:
        Tupla (ruta del CSV, cantidad de filas nuevas agregadas).
    """
    path = history_path(reference_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_history(reference_dir)
    if not records:
        if not path.exists():
            current.to_csv(path, index=False)
        return path, 0
    new = pd.DataFrame(records)
    for col in HISTORY_COLUMNS:
        if col not in new.columns:
            new[col] = pd.NA
    new = new[HISTORY_COLUMNS].drop_duplicates(subset=DEDUP_KEY)
    if not current.empty:
        known = set(map(tuple, current[DEDUP_KEY].astype(str).values))
        mask = [tuple(map(str, k)) not in known for k in new[DEDUP_KEY].values]
        new = new[mask]
    n_new = len(new)
    if n_new:
        frames = [f for f in (current, new) if not f.empty]
        out = pd.concat(frames, ignore_index=True)
        out = out.sort_values(["distribuidora", "vigencia"]).reset_index(drop=True)
        out.to_csv(path, index=False)
        logger.info("[tarifas] Historial: %d filas nuevas en %s", n_new, path)
    elif not path.exists():
        current.to_csv(path, index=False)
    return path, n_new


def latest_by_distribuidora(history: pd.DataFrame) -> pd.DataFrame:
    """
    Última vigencia con tarifa de compra por distribuidora.

    Args:
        history: Salida de ``load_history``.

    Returns:
        Una fila por distribuidora (la de vigencia más reciente; ante
        empate, la extracción más reciente).
    """
    valid = history.dropna(subset=["tarifa_compra_kwh"])
    if valid.empty:
        return valid
    return (
        valid.sort_values(["distribuidora", "vigencia", "fecha_extraccion"])
        .groupby("distribuidora", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def tariff_series(history: pd.DataFrame, field: str = "tarifa_compra_kwh") -> pd.DataFrame:
    """
    Serie temporal ancha: vigencia × distribuidora.

    Args:
        history: Salida de ``load_history``.
        field: Campo tarifario a pivotear.

    Returns:
        DataFrame con índice ``vigencia`` y una columna por distribuidora.
    """
    if history.empty:
        return pd.DataFrame()
    return (
        history.dropna(subset=[field])
        .sort_values("fecha_extraccion")
        .pivot_table(index="vigencia", columns="distribuidora", values=field, aggfunc="last")
        .sort_index()
    )
