"""Guardado de las tablas solares (Parquet y, opcional, MySQL).

Los scripts originales escribían en un MySQL local (XAMPP) con
``REPLACE INTO``. En el servidor (Docker) no hay MySQL, así que la copia
principal pasa a ser un Parquet por tabla en ``data/processed/solar/``
(como biomasa), con la misma semántica: si la clave ya existe, la fila
nueva reemplaza a la vieja. Así se corrigen los días que llegaron
incompletos (radiación de NASA en ``-999``, Growatt en 0).

Si se define ``SOLAR_DB_URL`` (p. ej.
``mysql+mysqlconnector://root:@localhost/datos``) cada guardado también se
replica en esa base, con los mismos nombres de tabla y columnas que
antes: las consultas y planillas existentes siguen funcionando. Para traer
lo que ya está en esa base a los Parquet: :func:`importar_desde_sql`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pandas as pd

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

ENV_DB_URL: Final[str] = "SOLAR_DB_URL"

# Tabla → columnas que forman la clave (equivalen a la PRIMARY KEY de MySQL).
CLAVES: Final[dict[str, list[str]]] = {
    "growatt_produccion": ["fecha"],
    "growatt_produccion_intradia": ["fecha_hora"],
    "clima_historico_nasa": ["fecha"],
    "clima_historico_openmeteo": ["fecha"],
    "clima_pronosticado": ["fecha_consulta", "fecha_pronosticada"],
    "pronostico_15min_5days": ["fecha_consulta", "fecha_hora"],
    "energia_pronosticada": ["fecha_hora"],
    "clima_15min_openmeteo": ["fecha_hora"],
    "energia_estimada_15min": ["fecha_hora"],
}


def _normalizar_claves(df: pd.DataFrame, claves: Iterable[str]) -> pd.DataFrame:
    """Fechas como ``date`` y fechas-hora como ``Timestamp``, para comparar claves."""
    df = df.copy()
    for col in claves:
        if col not in df.columns:
            continue
        if col.startswith("fecha_hora"):
            df[col] = pd.to_datetime(df[col])
        else:
            df[col] = pd.to_datetime(df[col]).dt.date
    return df


def ruta_tabla(directorio: Path, tabla: str) -> Path:
    """Ruta del Parquet de una tabla."""
    return Path(directorio) / f"{tabla}.parquet"


def leer(directorio: Path, tabla: str) -> pd.DataFrame:
    """Lee una tabla; DataFrame vacío si todavía no existe."""
    path = ruta_tabla(directorio, tabla)
    if not path.is_file():
        return pd.DataFrame()
    return _normalizar_claves(pd.read_parquet(path), CLAVES.get(tabla, []))


def upsert_parquet(directorio: Path, tabla: str, nuevos: pd.DataFrame) -> int:
    """Agrega o reemplaza filas por clave (semántica de ``REPLACE INTO``).

    Escribe primero un archivo temporal y después lo renombra, para que el
    dashboard nunca lea un Parquet a medio escribir.

    Args:
        directorio: Carpeta de las tablas.
        tabla: Nombre de la tabla (clave de :data:`CLAVES`).
        nuevos: Filas a guardar.

    Returns:
        Cantidad total de filas de la tabla después de guardar.
    """
    claves = CLAVES[tabla]
    nuevos = _normalizar_claves(nuevos, claves)
    previos = leer(directorio, tabla)
    df = pd.concat([previos, nuevos], ignore_index=True) if not previos.empty else nuevos
    df = df.drop_duplicates(subset=claves, keep="last").sort_values(claves)
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    path = ruta_tabla(directorio, tabla)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    return len(df)


def _engine(url: str) -> Engine:
    from sqlalchemy import create_engine  # dependencia opcional (extra [solar])

    return create_engine(url)


def upsert_sql(url: str, tabla: str, nuevos: pd.DataFrame) -> None:
    """Replica las filas en una base SQL: borra las claves existentes e inserta."""
    from sqlalchemy import text

    claves = CLAVES[tabla]
    engine = _engine(url)
    try:
        with engine.begin() as conn:
            if engine.dialect.has_table(conn, tabla):
                condicion = " AND ".join(f"{c} = :{c}" for c in claves)
                filas = nuevos[claves].drop_duplicates().to_dict(orient="records")
                if filas:
                    conn.execute(text(f"DELETE FROM {tabla} WHERE {condicion}"), filas)
            nuevos.to_sql(tabla, conn, if_exists="append", index=False)
    finally:
        engine.dispose()


def guardar(directorio: Path, tabla: str, nuevos: pd.DataFrame) -> int:
    """Guarda en Parquet y, si ``SOLAR_DB_URL`` está definida, también en SQL.

    Un error al replicar en SQL se registra pero no hace fallar la corrida:
    el Parquet ya quedó guardado.

    Returns:
        Filas de la tabla en Parquet después de guardar (0 si no había nada nuevo).
    """
    if nuevos.empty:
        logger.info("%s: sin filas nuevas", tabla)
        return 0
    total = upsert_parquet(directorio, tabla, nuevos)
    logger.info("%s: %d filas guardadas (%d en total)", tabla, len(nuevos), total)
    url = os.environ.get(ENV_DB_URL, "").strip()
    if url:
        try:
            upsert_sql(url, tabla, nuevos)
        except Exception as exc:  # noqa: BLE001 - la réplica es opcional
            logger.warning("No se pudo replicar %s en SQL: %s", tabla, type(exc).__name__)
    return total


def importar_desde_sql(
    url: str,
    directorio: Path,
    tablas: Iterable[str] | None = None,
) -> dict[str, int]:
    """Copia a Parquet las tablas que ya existen en la base SQL anterior.

    Sirve una sola vez, para no perder el histórico cargado en MySQL antes
    de unificar el repositorio. Las tablas que no existan se saltean.

    Returns:
        Tabla → filas importadas.
    """
    engine = _engine(url)
    importadas: dict[str, int] = {}
    try:
        with engine.connect() as conn:
            for tabla in tablas or CLAVES:
                if not engine.dialect.has_table(conn, tabla):
                    logger.info("%s: no existe en la base, se saltea", tabla)
                    continue
                df = pd.read_sql_table(tabla, conn)
                if not df.empty:
                    upsert_parquet(directorio, tabla, df)
                importadas[tabla] = len(df)
                logger.info("%s: %d filas importadas", tabla, len(df))
    finally:
        engine.dispose()
    return importadas
