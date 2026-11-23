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
    "puntaje_compra",
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


def _align_empty_columns(
    current: pd.DataFrame, new: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Da a las columnas todas vacías de ``new`` el tipo que tienen en ``current``.

    Las filas nuevas suelen traer columnas sin ningún valor (p. ej. sin
    tarifa de inyección), de tipo object. pandas 2.x las ignora al elegir
    el tipo del ``concat`` y avisa (FutureWarning) que dejará de hacerlo:
    entonces una columna numérica del historial pasaría a object. Con el
    mismo tipo en los dos lados no hay nada que ignorar. Las columnas de
    enteros pasan a ``Int64`` (admite vacíos): el CSV sigue diciendo ``10``
    y no ``10.0``.
    """
    current, new = current.copy(), new.copy()
    for col in new.columns.intersection(current.columns):
        if not new[col].isna().all():
            continue
        target = current[col].dtype
        if pd.api.types.is_integer_dtype(target):
            target = pd.Int64Dtype()
            current[col] = current[col].astype(target)
        # Columna vacía del tipo pedido (astype no convierte pd.NA a float).
        new[col] = pd.Series(index=new.index, dtype=target)
    return current, new


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
        if not current.empty:
            current, new = _align_empty_columns(current, new)
        frames = [f for f in (current, new) if not f.empty]
        out = pd.concat(frames, ignore_index=True)
        out = out.sort_values(["distribuidora", "vigencia"]).reset_index(drop=True)
        out.to_csv(path, index=False)
        logger.info("[tarifas] Historial: %d filas nuevas en %s", n_new, path)
    elif not path.exists():
        current.to_csv(path, index=False)
    return path, n_new


def representative_by_month(history: pd.DataFrame) -> pd.DataFrame:
    """
    Un cuadro por distribuidora y vigencia: el pleno.

    Algunas fuentes (OCEBA, ZIP del portal nacional) publican varios
    anexos por mes (pleno, con subsidio, por nivel de ingresos). Se elige
    el de mayor puntaje de categoría y, a igualdad, la mayor tarifa de
    compra, con el mismo criterio que el extractor. Las filas sin vigencia
    se descartan.
    """
    valid = history.dropna(subset=["tarifa_compra_kwh", "vigencia"]).copy()
    if valid.empty:
        return valid
    puntaje = valid["puntaje_compra"] if "puntaje_compra" in valid else 0
    valid["_puntaje"] = pd.to_numeric(puntaje, errors="coerce")
    valid["_puntaje"] = valid["_puntaje"].fillna(0)
    return (
        valid.sort_values(["distribuidora", "vigencia", "_puntaje", "tarifa_compra_kwh"])
        .groupby(["distribuidora", "vigencia"], as_index=False)
        .tail(1)
        .drop(columns="_puntaje")
        .reset_index(drop=True)
    )


def latest_by_distribuidora(history: pd.DataFrame) -> pd.DataFrame:
    """
    Última vigencia con tarifa de compra por distribuidora.

    Args:
        history: Salida de ``load_history``.

    Returns:
        Una fila por distribuidora (el cuadro pleno de la vigencia más
        reciente).
    """
    rep = representative_by_month(history)
    if rep.empty:
        return rep
    return rep.groupby("distribuidora", as_index=False).tail(1).reset_index(drop=True)


def tariff_series(history: pd.DataFrame, field: str = "tarifa_compra_kwh") -> pd.DataFrame:
    """
    Serie temporal ancha: vigencia × distribuidora (cuadro pleno por mes).

    Args:
        history: Salida de ``load_history``.
        field: Campo tarifario a pivotear.

    Returns:
        DataFrame con índice ``vigencia`` y una columna por distribuidora.
    """
    rep = representative_by_month(history)
    if rep.empty:
        return pd.DataFrame()
    return rep.pivot(index="vigencia", columns="distribuidora", values=field).sort_index()
