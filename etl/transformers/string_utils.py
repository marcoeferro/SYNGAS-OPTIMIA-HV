"""
Utilidades de normalización léxica de strings.

Este módulo contiene las primitivas de limpieza textual que se aplican
de manera uniforme a todas las columnas categóricas del pipeline
(cultivos, provincias, departamentos, campañas).

Todas las funciones son puras, idempotentes y no tienen estado.
La idempotencia es un requisito operativo: permite aplicar el pipeline
múltiples veces sin degradar los datos.
"""

from __future__ import annotations

import re
import unicodedata

# =============================================================
# Constantes de configuración
# =============================================================
NORMALIZATION_FORM = "NFKD"
ASCII_ENCODING = "ascii"
WHITESPACE_PATTERN = r"\s+"
WHITESPACE_REPLACEMENT = " "


def clean_str(s: str) -> str:
    """
    Normaliza un string para matching determinístico entre fuentes.

    Pipeline de transformación:
        1. Descomposición Unicode NFKD (é -> e + combining acute).
        2. Transliteración a ASCII descartando diacríticos y ñ.
        3. Colapso de whitespace múltiple a un único espacio.
        4. Conversión a minúsculas y strip de extremos.

    La función es idempotente: clean_str(clean_str(s)) == clean_str(s).

    Args:
        s: String de entrada. Si no es str, se retorna sin modificar
           (permite aplicar sobre columnas con NaN de forma segura).

    Returns:
        String normalizado en minúsculas, sin acentos, sin espacios
        redundantes.

    Examples:
        >>> clean_str("  MAÍZ ")
        'maiz'
        >>> clean_str("Caña de Azúcar")
        'cana de azucar'
        >>> clean_str("Cebada  Cervecera")
        'cebada cervecera'
    """
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize(NORMALIZATION_FORM, s)
    s = s.encode(ASCII_ENCODING, "ignore").decode(ASCII_ENCODING)
    s = re.sub(WHITESPACE_PATTERN, WHITESPACE_REPLACEMENT, s)
    return s.strip().lower()


def strip_periods(s: str) -> str:
    """
    Reemplaza puntos por espacios y colapsa whitespace resultante.

    Resuelve variabilidad de puntuación entre fuentes: 'n.' vs 'n',
    'J.B.' vs 'J B'. Se aplica después de clean_str para operar sobre
    strings ya normalizados.

    Args:
        s: String de entrada.

    Returns:
        String sin puntos, con espacios colapsados y sin extremos.

    Examples:
        >>> strip_periods("leandro n. alem")
        'leandro n alem'
        >>> strip_periods("j.b.alberdi")
        'j b alberdi'
    """
    if not isinstance(s, str):
        return s
    s = s.replace(".", WHITESPACE_REPLACEMENT)
    return re.sub(WHITESPACE_PATTERN, WHITESPACE_REPLACEMENT, s).strip()