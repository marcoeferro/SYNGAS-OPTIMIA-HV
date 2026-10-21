"""
Normalización canónica de entidades administrativas subprovinciales.

Resuelve variabilidad ortográfica entre fuentes para permitir el cruce
por clave natural (Provincia, Departamento). Aplica cuatro mecanismos
de normalización:

    1. Léxica: lower, sin acentos, whitespace colapsado.
    2. Puntuación: puntos convertidos a espacios.
    3. Abreviaturas: expansión token a token con diccionario declarativo.
    4. Alias: mapeo explícito de casos residuales indexado por
       (provincia, departamento), porque el espacio de nombres de
       departamentos es intra-provincial (existen múltiples 'capital').
"""

from __future__ import annotations

import pandas as pd

from optimia_hv.biomasa.transformers.string_utils import clean_str, strip_periods

# =============================================================
# Constantes de configuración
# =============================================================
DEFAULT_PROV_COL = "Provincia"
DEFAULT_DEPT_COL = "Departamento"

# Placeholders que no constituyen entidades geográficas reales.
INVALID_DEPT_VALUES: frozenset[str] = frozenset(
    {"sin definir", "", "na", "n/a"}
)

# Diccionario de expansión de abreviaturas seguras.
# Solo se expanden tokens completos, nunca dentro de un token.
ABBREV_SAFE: dict[str, str] = {
    "gral": "general",
    "pte": "presidente",
    "gob": "gobernador",
    "dr": "doctor",
    "dra": "doctora",
    "cnl": "coronel",
    "tte": "teniente",
    "sgt": "sargento",
    "cap": "capitan",
}

# Alias residuales indexados por (provincia_canónica, dept_normalizado).
# Sólo casos no resueltos por reglas genéricas.
DEPT_ALIASES: dict[tuple[str, str], str] = {
    ("tucuman", "j b alberdi"): "juan b alberdi",
    ("santiago del estero", "j f ibarra"): "juan felipe ibarra",
    # MAGyP y la Bolsa de Córdoba nombran distinto el mismo departamento:
    # sin alias la reconciliación no los cruza y suma ambas fuentes.
    ("santiago del estero", "juan f ibarra"): "juan felipe ibarra",
    ("san luis", "libertador san martin"): "libertador general san martin",
}


def expand_abbrevs(s: str, mapping: dict[str, str] = ABBREV_SAFE) -> str:
    """
    Expande abreviaturas token a token según diccionario.

    Preserva nombres compuestos: no expande dentro de tokens
    (e.g., 'grales' no se convierte en 'generales').

    Args:
        s: String de entrada (idealmente ya procesado por clean_str).
        mapping: Diccionario de abreviaturas a expansiones.

    Returns:
        String con abreviaturas reemplazadas.
    """
    if not isinstance(s, str):
        return s
    return " ".join(mapping.get(tok, tok) for tok in s.split(" "))


def resolve_dept_alias(
    provincia: str,
    dept: str,
    aliases: dict[tuple[str, str], str] = DEPT_ALIASES,
) -> str:
    """
    Resuelve alias de departamento indexado por provincia.

    El scope provincial evita colisiones entre homónimos
    (e.g., múltiples provincias con departamento 'capital').

    Args:
        provincia: Nombre canónico de la provincia.
        dept: Nombre normalizado del departamento.
        aliases: Diccionario de alias.

    Returns:
        Nombre canónico del departamento.
    """
    return aliases.get((provincia, dept), dept)


def normalize_geo(
    df: pd.DataFrame,
    prov_col: str = DEFAULT_PROV_COL,
    dept_col: str = DEFAULT_DEPT_COL,
    aliases: dict[tuple[str, str], str] = DEPT_ALIASES,
) -> pd.DataFrame:
    """
    Normaliza Provincia y Departamento a representación canónica.

    Aplica el pipeline completo: clean_str -> strip_periods ->
    expand_abbrevs -> resolve_dept_alias. La operación es determinística
    y no destructiva (retorna copia).

    Args:
        df: DataFrame con columnas de provincia y departamento.
        prov_col: Nombre de la columna de provincia.
        dept_col: Nombre de la columna de departamento.
        aliases: Diccionario de alias a aplicar.

    Returns:
        DataFrame con provincia y departamento normalizados.
    """
    df = df.copy()
    df[prov_col] = df[prov_col].apply(clean_str)
    df[dept_col] = (
        df[dept_col]
        .apply(clean_str)
        .apply(strip_periods)
        .apply(expand_abbrevs)
    )
    df[dept_col] = [
        resolve_dept_alias(p, d, aliases)
        for p, d in zip(df[prov_col], df[dept_col])
    ]
    return df


def flag_invalid_geo(
    df: pd.DataFrame,
    dept_col: str = DEFAULT_DEPT_COL,
    invalid_values: frozenset[str] = INVALID_DEPT_VALUES,
) -> pd.DataFrame:
    """
    Marca departamentos placeholder o inválidos con flag booleano.

    No elimina ni imputa. El flag permite excluirlos de agregaciones
    sin perder la fila en la capa curada.

    Args:
        df: DataFrame con columna de departamento.
        dept_col: Nombre de la columna de departamento.
        invalid_values: Conjunto de valores a marcar como inválidos.

    Returns:
        DataFrame con columna adicional '_dept_valido'.
    """
    df = df.copy()
    df["_dept_valido"] = ~df[dept_col].isin(invalid_values)
    return df