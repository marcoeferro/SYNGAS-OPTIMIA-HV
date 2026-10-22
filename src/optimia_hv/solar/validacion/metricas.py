"""Métricas de error del modelo contra la generación real.

Se usan en las comparativas, en el dashboard y en los tests de regresión
(``tests/regression/``). Todas reciben dos series alineadas (mismo índice
o mismo largo) y omiten los pares con algún valor faltante.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


def _pares(real: pd.Series, estimado: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    df = pd.DataFrame({
        "r": np.asarray(real, dtype=float),
        "e": np.asarray(estimado, dtype=float),
    }).dropna()
    return df["r"].to_numpy(), df["e"].to_numpy()


def mae(real: pd.Series, estimado: pd.Series) -> float:
    """Error absoluto medio (mismas unidades que la serie)."""
    r, e = _pares(real, estimado)
    return float(np.mean(np.abs(e - r))) if len(r) else float("nan")


def rmse(real: pd.Series, estimado: pd.Series) -> float:
    """Raíz del error cuadrático medio (penaliza más los errores grandes)."""
    r, e = _pares(real, estimado)
    return float(np.sqrt(np.mean((e - r) ** 2))) if len(r) else float("nan")


def sesgo(real: pd.Series, estimado: pd.Series) -> float:
    """Error medio (estimado − real): positivo = el modelo sobreestima."""
    r, e = _pares(real, estimado)
    return float(np.mean(e - r)) if len(r) else float("nan")


def error_relativo_total(real: pd.Series, estimado: pd.Series) -> float:
    """(Σ estimado − Σ real) / Σ real: error en la energía acumulada del período."""
    r, e = _pares(real, estimado)
    total = r.sum()
    return float((e.sum() - total) / total) if total else float("nan")


@dataclass(frozen=True)
class ResumenMetricas:
    """Métricas de un período."""

    n: int
    mae: float
    rmse: float
    sesgo: float
    error_relativo_total: float

    def como_dict(self) -> dict[str, float]:
        """Diccionario para mostrar en tablas."""
        return asdict(self)


def resumen(real: pd.Series, estimado: pd.Series) -> ResumenMetricas:
    """Todas las métricas juntas."""
    r, _ = _pares(real, estimado)
    return ResumenMetricas(
        n=len(r),
        mae=mae(real, estimado),
        rmse=rmse(real, estimado),
        sesgo=sesgo(real, estimado),
        error_relativo_total=error_relativo_total(real, estimado),
    )
