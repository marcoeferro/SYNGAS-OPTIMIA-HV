"""
Carga de la tabla de Índices de Cosecha (IC) y Factores de Residuo (FR).

El IC representa la proporción del rendimiento en grano respecto a la
biomasa aérea total de la planta. El FR se deriva como (1 - IC) / IC y
permite estimar biomasa residual como Producción × FR.

La tabla se carga desde data/reference/ic_fr.csv si existe; en caso
contrario se utiliza un diccionario embebido como fallback, y se emite
un warning. Esto permite correr el pipeline en entornos sin la tabla
de referencia, manteniendo trazabilidad de la fuente utilizada.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from etl.transformers.string_utils import clean_str

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
IC_TABLE_FILENAME = "ic_fr.csv"
IC_COL = "IC"
FR_COL = "FR"
CULTIVO_COL = "Cultivo"
SOURCE_COL = "Fuente bibliográfica"

# Fallback embebido. Solo se usa si el CSV no existe.
_BUILTIN_IC: dict[str, tuple[float, str]] = {
    "maíz":     (0.47, "Bolsa de Cereales de Buenos Aires (2015)"),
    "soja":     (0.45, "Bolsa de Cereales de Buenos Aires (2015)"),
    "trigo":    (0.35, "Bolsa de Cereales de Buenos Aires (2015)"),
    "girasol":  (0.37, "Raposo (2024)"),
    "maní":     (0.40, "Haro (2022), promedio granoleico"),
    "garbanzo": (0.26, "Apáez-Barrios (2017) y Ramacciotti (2015)"),
    "sorgo":    (0.35, "Zamer y Chiarelli"),
    "cebada":   (0.53, "Cuda (2014)"),
    "centeno":  (0.22, "Zubiaga et al. (2023)"),
    "avena":    (0.35, "Zubiaga et al. (2023)"),
    "poroto":   (0.45, "Ortega (2001)"),
    "ajo":      (0.55, "Rizzalli, Villalobos & Orgaz (2002)"),
    "colza":    (0.28, "Unkovich et al. / Lu et al. (2016)"),
    "papa":     (0.74, "Xu et al. (QUEFTS, Agronomy Journal)"),
    "lino":     (0.40, "Estudios ADAS/AHDB"),
    "arroz":    (0.45, "Hay (1995) y estudios recientes"),
    "algodón":  (0.30, "Estudios regionales (Xinjiang)"),
}


def _build_dataframe_from_builtin() -> pd.DataFrame:
    """
    Construye el DataFrame de IC/FR desde el diccionario embebido.

    Returns:
        DataFrame con columnas Cultivo, IC, Fuente bibliográfica, FR.
    """
    rows = [
        {
            CULTIVO_COL: clean_str(cultivo),
            IC_COL: ic,
            SOURCE_COL: fuente,
        }
        for cultivo, (ic, fuente) in _BUILTIN_IC.items()
    ]
    df = pd.DataFrame(rows)
    df[FR_COL] = (1 - df[IC_COL]) / df[IC_COL]
    return df


def load_ic_table(reference_dir: Path | str) -> pd.DataFrame:
    """
    Carga la tabla IC/FR desde el directorio de referencia.

    Si el archivo no existe, usa el fallback embebido y emite un
    warning. La columna 'Cultivo' se normaliza con clean_str para
    garantizar compatibilidad con el resto del pipeline.

    Args:
        reference_dir: Directorio donde buscar ic_fr.csv.

    Returns:
        DataFrame con columnas Cultivo, IC, Fuente bibliográfica, FR.
    """
    path = Path(reference_dir) / IC_TABLE_FILENAME

    if path.exists():
        logger.info("Cargando tabla IC/FR desde %s", path)
        df = pd.read_csv(path)
        df[CULTIVO_COL] = df[CULTIVO_COL].apply(clean_str)
        if FR_COL not in df.columns:
            df[FR_COL] = (1 - df[IC_COL]) / df[IC_COL]
        return df

    logger.warning(
        "Tabla IC/FR no encontrada en %s. Usando fallback embebido. "
        "Considerar persistir con save_ic_table() para trazabilidad.",
        path,
    )
    return _build_dataframe_from_builtin()


def save_ic_table(df: pd.DataFrame, reference_dir: Path | str) -> Path:
    """
    Persiste la tabla IC/FR en el directorio de referencia.

    Args:
        df: DataFrame con la tabla IC/FR.
        reference_dir: Directorio de destino.

    Returns:
        Path del archivo persistido.
    """
    reference_dir = Path(reference_dir)
    reference_dir.mkdir(parents=True, exist_ok=True)
    path = reference_dir / IC_TABLE_FILENAME
    df.to_csv(path, index=False)
    logger.info("Tabla IC/FR persistida en %s", path)
    return path