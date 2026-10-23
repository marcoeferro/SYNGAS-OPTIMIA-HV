"""
Carga de la tabla de Índices de Cosecha (IC) y Factores de Residuo (FR).

El IC representa la proporción del rendimiento en grano respecto a la
biomasa aérea total de la planta, ambos en materia seca. El FR se deriva
como (1 - IC) / IC. Como la producción se reporta a humedad comercial
(o en fresco, para papa y ajo), la biomasa residual en base seca es:

    Residuo (t MS) = Producción × MS × FR

donde MS es la fracción de materia seca del producto cosechado.

La tabla se carga desde data/reference/ic_fr.csv si existe; en caso
contrario se utiliza un diccionario embebido como fallback, y se emite
un warning. Esto permite correr el pipeline en entornos sin la tabla
de referencia, manteniendo trazabilidad de la fuente utilizada.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from optimia_hv.biomasa.transformers.string_utils import clean_str

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
IC_TABLE_FILENAME = "ic_fr.csv"
IC_COL = "IC"
FR_COL = "FR"
MS_COL = "MS"
CULTIVO_COL = "Cultivo"
SOURCE_COL = "Fuente bibliográfica"

# Fallback embebido. Solo se usa si el CSV no existe.
# (IC, fuente bibliográfica, MS del producto cosechado)
_BUILTIN_IC: dict[str, tuple[float, str, float]] = {
    "maíz":     (0.47, "Bolsa de Cereales de Buenos Aires (2015)", 0.855),
    "soja":     (0.45, "Bolsa de Cereales de Buenos Aires (2015)", 0.865),
    "trigo":    (0.35, "Bolsa de Cereales de Buenos Aires (2015)", 0.86),
    "girasol":  (0.37, "Raposo (2024)", 0.89),
    "maní":     (0.40, "Haro (2022), promedio granoleico", 0.90),
    "garbanzo": (0.26, "Apáez-Barrios (2017) y Ramacciotti (2015)", 0.86),
    "sorgo":    (0.35, "Zamer y Chiarelli", 0.85),
    "cebada":   (0.53, "Cuda (2014)", 0.88),
    "centeno":  (0.22, "Zubiaga et al. (2023)", 0.86),
    "avena":    (0.35, "Zubiaga et al. (2023)", 0.86),
    "poroto":   (0.45, "Ortega (2001)", 0.85),
    "ajo":      (0.55, "Rizzalli, Villalobos & Orgaz (2002)", 0.35),
    "colza":    (0.28, "Unkovich et al. / Lu et al. (2016)", 0.92),
    "papa":     (0.74, "Xu et al. (QUEFTS, Agronomy Journal)", 0.20),
    "lino":     (0.40, "Estudios ADAS/AHDB", 0.89),
    "arroz":    (0.45, "Hay (1995) y estudios recientes", 0.86),
    "algodón":  (0.30, "Estudios regionales (Xinjiang)", 0.92),
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
            MS_COL: ms,
        }
        for cultivo, (ic, fuente, ms) in _BUILTIN_IC.items()
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
        if not df[IC_COL].between(0, 1, inclusive="neither").all():
            raise ValueError("IC fuera de (0, 1) en la tabla de referencia")
        # FR se recalcula siempre desde IC: un FR persistido podía quedar
        # desincronizado si se editaba el IC a mano.
        fr = (1 - df[IC_COL]) / df[IC_COL]
        if FR_COL in df.columns and not (df[FR_COL] - fr).abs().lt(1e-6).all():
            logger.warning("FR persistido inconsistente con IC; se recalcula.")
        df[FR_COL] = fr
        if MS_COL not in df.columns:
            logger.warning(
                "Tabla IC sin columna MS (materia seca). Se asume MS=1: "
                "el residuo quedará en base húmeda/fresca."
            )
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