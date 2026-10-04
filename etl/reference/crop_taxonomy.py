"""
Taxonomía canónica de cultivos del dominio agropecuario argentino.

Este módulo es la fuente de verdad del mapeo entre nombres raw
reportados por las fuentes y nombres canónicos utilizados en el
pipeline. Toda modificación requiere:

    1. Justificación documentada en docs/decision_log.md.
    2. Aprobación del steward del dominio.
    3. Actualización de tests si altera contratos existentes.

Estructura de cada entrada:
    canonical:      Nombre canónico del cultivo.
    is_aggregate:   True si el registro es un 'total' reportado por la
                    fuente (prevalece sobre componentes por regla de
                    resolución de doble conteo).

Reglas de negocio embebidas:
    - Los nombres canónicos compuestos ('cana de azucar', 'yerba mate')
      no se colapsan a la primera palabra.
    - Cultivos biológicamente distintos ('trigo candeal' vs 'trigo') se
      preservan como entidades separadas.
    - Nombres base canónicos ('soja', 'trigo', etc.) se incluyen como
      entradas explícitas no-agregadas porque aparecen en la fuente CBA
      sin sufijo 'total'.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class CropEntry(TypedDict):
    """Estructura de una entrada de la taxonomía."""

    canonical: str
    is_aggregate: bool


# =============================================================
# Constantes de configuración
# =============================================================
TAXONOMY_VERSION: Literal["1.0.0"] = "1.0.0"

# =============================================================
# Taxonomía canónica
# =============================================================
CROP_TAXONOMY: dict[str, CropEntry] = {
    # --- Familia soja ---
    "soja":       {"canonical": "soja",   "is_aggregate": False},
    "soja 1ra":   {"canonical": "soja",   "is_aggregate": False},
    "soja 2da":   {"canonical": "soja",   "is_aggregate": False},
    "soja total": {"canonical": "soja",   "is_aggregate": True},

    # --- Familia cebada ---
    "cebada":           {"canonical": "cebada", "is_aggregate": False},
    "cebada cervecera": {"canonical": "cebada", "is_aggregate": False},
    "cebada forrajera": {"canonical": "cebada", "is_aggregate": False},
    "cebada total":     {"canonical": "cebada", "is_aggregate": True},

    # --- Familia poroto ---
    "poroto":        {"canonical": "poroto", "is_aggregate": False},
    "poroto alubia": {"canonical": "poroto", "is_aggregate": False},
    "poroto negro":  {"canonical": "poroto", "is_aggregate": False},
    "poroto otros":  {"canonical": "poroto", "is_aggregate": False},
    "poroto total":  {"canonical": "poroto", "is_aggregate": True},

    # --- Totales sin breakdown y nombres base ---
    "trigo":         {"canonical": "trigo",   "is_aggregate": False},
    "trigo total":   {"canonical": "trigo",   "is_aggregate": True},
    "papa":          {"canonical": "papa",    "is_aggregate": False},
    "papa total":    {"canonical": "papa",    "is_aggregate": True},
    "cebolla":       {"canonical": "cebolla", "is_aggregate": False},
    "cebolla total": {"canonical": "cebolla", "is_aggregate": True},

    # --- Compuestos / biológicamente distintos ---
    "trigo candeal":  {"canonical": "trigo candeal",  "is_aggregate": False},
    "cana de azucar": {"canonical": "cana de azucar", "is_aggregate": False},
    "yerba mate":     {"canonical": "yerba mate",     "is_aggregate": False},

    # --- Cultivos simples ---
    # alfalfa: forrajera reportada por CBA (sin IC; queda excluida por
    # flag). Se mapea para evitar el fail-fast cuando trae producción.
    "alfalfa":   {"canonical": "alfalfa",  "is_aggregate": False},
    "ajo":       {"canonical": "ajo",      "is_aggregate": False},
    "algodon":   {"canonical": "algodon",  "is_aggregate": False},
    "alpiste":   {"canonical": "alpiste",  "is_aggregate": False},
    "arroz":     {"canonical": "arroz",    "is_aggregate": False},
    "arveja":    {"canonical": "arveja",   "is_aggregate": False},
    "avena":     {"canonical": "avena",    "is_aggregate": False},
    "banana":    {"canonical": "banana",   "is_aggregate": False},
    "cartamo":   {"canonical": "cartamo",  "is_aggregate": False},
    "centeno":   {"canonical": "centeno",  "is_aggregate": False},
    "colza":     {"canonical": "colza",    "is_aggregate": False},
    "garbanzo":  {"canonical": "garbanzo", "is_aggregate": False},
    "girasol":   {"canonical": "girasol",  "is_aggregate": False},
    "jojoba":    {"canonical": "jojoba",   "is_aggregate": False},
    "lenteja":   {"canonical": "lenteja",  "is_aggregate": False},
    "limon":     {"canonical": "limon",    "is_aggregate": False},
    "lino":      {"canonical": "lino",     "is_aggregate": False},
    "maiz":      {"canonical": "maiz",     "is_aggregate": False},
    "mandarina": {"canonical": "mandarina","is_aggregate": False},
    "mani":      {"canonical": "mani",     "is_aggregate": False},
    "mijo":      {"canonical": "mijo",     "is_aggregate": False},
    "naranja":   {"canonical": "naranja",  "is_aggregate": False},
    "pomelo":    {"canonical": "pomelo",   "is_aggregate": False},
    "sorgo":     {"canonical": "sorgo",    "is_aggregate": False},
    "te":        {"canonical": "te",       "is_aggregate": False},
    "tung":      {"canonical": "tung",     "is_aggregate": False},
}


def get_canonical_names(taxonomy: dict[str, CropEntry] = CROP_TAXONOMY) -> set[str]:
    """
    Retorna el conjunto de nombres canónicos de la taxonomía.

    Args:
        taxonomy: Diccionario de taxonomía.

    Returns:
        Conjunto de nombres canónicos únicos.
    """
    return {entry["canonical"] for entry in taxonomy.values()}