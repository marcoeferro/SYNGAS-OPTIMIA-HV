"""
Fixtures compartidas para la suite de tests.
"""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def df_crops_basic() -> pd.DataFrame:
    """DataFrame mínimo con cultivos para tests de resolución."""
    return pd.DataFrame({
        "Campaña": ["2020/21"] * 3,
        "Provincia": ["cordoba"] * 3,
        "Departamento": ["rio cuarto"] * 3,
        "Cultivo": ["soja 1ra", "soja 2da", "soja total"],
        "Producción": [1000, 500, 1500],
    })


@pytest.fixture
def df_geo_basic() -> pd.DataFrame:
    """DataFrame mínimo con entidades geográficas."""
    return pd.DataFrame({
        "Provincia": ["Córdoba", "Córdoba"],
        "Departamento": ["GRAL. SAN MARTIN", "General San Martín"],
    })


@pytest.fixture
def df_reconciliation_sample() -> pd.DataFrame:
    """DataFrame concatenado con solapamiento entre fuentes."""
    return pd.DataFrame({
        "Provincia": ["cordoba", "cordoba"],
        "Departamento": ["rio cuarto", "rio cuarto"],
        "Campaña": ["2020/21", "2020/21"],
        "Cultivo": ["soja", "soja"],
        "Superficie (Ha)": [1000.0, 1200.0],
        "Produccion (Tn)": [3000.0, 3500.0],
        "Rendimiento (Tn/Ha)": [3.0, 2.92],
        "fuente": ["magyp_estimaciones", "bolsa_cereales_cba"],
    })

# =============================================================
# Tipos de test según la carpeta
# =============================================================
_TIPOS = ("unit", "integration", "e2e", "regression", "contract")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Marca cada test con el tipo de su carpeta (tests/<tipo>/...).

    Así se puede correr un tipo solo, p. ej. ``pytest -m unit`` o
    ``pytest -m contract``, sin decorar cada test a mano.
    """
    for item in items:
        partes = item.path.relative_to(config.rootpath / "tests").parts
        if partes and partes[0] in _TIPOS:
            item.add_marker(getattr(pytest.mark, partes[0]))
