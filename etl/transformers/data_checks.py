"""
Controles de calidad de datos que corren en cada ejecución del ETL.

A diferencia de los tests (que verifican el código con casos fijos), estos
controles miran los datos reales de la corrida y comparan contra la
anterior para detectar cambios sospechosos:

- **Salto de tarifa**: la tarifa de compra vigente de una distribuidora
  cambia más que ``UMBRAL_SALTO_TARIFA`` respecto del cuadro anterior del
  historial (p.ej. un error de parseo que toma otra categoría).
- **Cambio de energía o dinero**: el total anual cambia más que
  ``UMBRAL_TOTAL`` respecto de la corrida anterior, o la energía de una
  provincia relevante cambia más que ``UMBRAL_PROVINCIA`` (p.ej. una fuente
  agrícola que vino incompleta).

Las alertas se registran en el log y en ``data/audit/alertas_calidad.parquet``.
Con ``--estricto`` el pipeline se detiene antes de sobrescribir los datos
publicados.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Final

import numpy as np
import pandas as pd

from etl.loaders.tariff_history import representative_by_month

logger = logging.getLogger(__name__)

UMBRAL_SALTO_TARIFA: Final[float] = 0.5
UMBRAL_TOTAL: Final[float] = 0.2
UMBRAL_PROVINCIA: Final[float] = 0.5
# Provincias con menos de esta fracción de la energía no se comparan:
# en valores chicos cualquier cambio es un porcentaje grande.
MIN_PARTICIPACION_PROVINCIA: Final[float] = 0.01

ESTADOS_EXTRAIDOS: Final[frozenset[str]] = frozenset({"extraido", "parsed_pdf"})
COL_KWH: Final[str] = "kwh_generados"
COL_BENEFICIO: Final[str] = "beneficio_total_ars"

ALERT_COLUMNS: Final[list[str]] = [
    "control", "entidad", "valor_anterior", "valor_actual", "variacion",
    "umbral", "detalle", "fecha",
]


def _alerta(
    control: str, entidad: str, anterior: float, actual: float, umbral: float,
    detalle: str,
) -> dict[str, Any]:
    return {
        "control": control,
        "entidad": entidad,
        "valor_anterior": float(anterior),
        "valor_actual": float(actual),
        "variacion": float(actual / anterior - 1) if anterior else np.nan,
        "umbral": umbral,
        "detalle": detalle,
    }


def _supera(anterior: float, actual: float, umbral: float) -> bool:
    if not anterior or pd.isna(anterior) or pd.isna(actual):
        return False
    return abs(actual / anterior - 1) > umbral


def check_tariff_jumps(
    cfg: dict[str, Any],
    history: pd.DataFrame,
    umbral: float = UMBRAL_SALTO_TARIFA,
) -> list[dict[str, Any]]:
    """
    Tarifas de compra vigentes que saltan respecto del cuadro anterior.

    Se compara cada distribuidora con tarifa extraída en esta corrida
    contra el cuadro pleno de la vigencia anterior más reciente del
    historial. Los valores arrastrados (``fallback_previous``) no se
    comparan: no cambiaron.
    """
    if history is None or history.empty:
        return []
    rep = representative_by_month(history)
    alertas = []
    for code, info in cfg.get("distribuidoras", {}).items():
        estado = info.get("estado_campos", {}).get("tarifa_compra_kwh")
        actual, vigencia = info.get("tarifa_compra_kwh"), info.get("vigencia")
        if estado not in ESTADOS_EXTRAIDOS or actual is None or not vigencia:
            continue
        previas = rep[(rep["distribuidora"] == code) & (rep["vigencia"] < vigencia)]
        if previas.empty:
            continue
        previa = previas.sort_values("vigencia").iloc[-1]
        if _supera(previa["tarifa_compra_kwh"], actual, umbral):
            alertas.append(_alerta(
                "salto_tarifa", code, previa["tarifa_compra_kwh"], actual, umbral,
                f"Cuadro {previa['vigencia']} → {vigencia}. Revisar el documento "
                f"{info.get('documento')} (¿otra categoría o error de parseo?).",
            ))
    return alertas


def check_energy_change(
    df_actual: pd.DataFrame,
    df_anterior: pd.DataFrame | None,
    umbral_total: float = UMBRAL_TOTAL,
    umbral_provincia: float = UMBRAL_PROVINCIA,
    min_participacion: float = MIN_PARTICIPACION_PROVINCIA,
) -> list[dict[str, Any]]:
    """
    Cambios de energía y dinero anuales respecto de la corrida anterior.

    Args:
        df_actual: Potencial anual de esta corrida.
        df_anterior: Potencial anual publicado antes (None en la primera
            corrida).
        umbral_total: Cambio relativo máximo del total sin alertar.
        umbral_provincia: Cambio relativo máximo por provincia sin alertar.
        min_participacion: Fracción mínima de la energía para comparar
            una provincia.
    """
    if df_anterior is None or df_anterior.empty:
        return []
    alertas = []
    totales = ((COL_KWH, "energía anual (kWh)"), (COL_BENEFICIO, "beneficio anual (ARS)"))
    for col, nombre in totales:
        if col not in df_actual or col not in df_anterior:
            continue
        ant, act = df_anterior[col].sum(), df_actual[col].sum()
        if _supera(ant, act, umbral_total):
            alertas.append(_alerta(
                "cambio_total", nombre, ant, act, umbral_total,
                "El total del país cambió respecto de la corrida anterior: revisar "
                "si alguna fuente vino incompleta o cambió una tarifa.",
            ))
    if COL_KWH in df_actual and COL_KWH in df_anterior:
        prov_act = df_actual.groupby("Provincia")[COL_KWH].sum()
        prov_ant = df_anterior.groupby("Provincia")[COL_KWH].sum()
        total = max(prov_act.sum(), prov_ant.sum())
        for prov in sorted(set(prov_act.index) | set(prov_ant.index)):
            ant, act = prov_ant.get(prov, 0.0), prov_act.get(prov, 0.0)
            if max(ant, act) < min_participacion * total:
                continue
            if not ant or _supera(ant, act, umbral_provincia):
                alertas.append(_alerta(
                    "cambio_provincia", str(prov), ant, act, umbral_provincia,
                    "La energía de la provincia cambió respecto de la corrida "
                    "anterior: revisar sus registros agrícolas.",
                ))
    return alertas


def run_data_checks(
    tarifas_cfg: dict[str, Any],
    tarifas_historial: pd.DataFrame | None,
    df_anual: pd.DataFrame,
    df_anual_anterior: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Ejecuta todos los controles y devuelve las alertas (puede estar vacío).

    Cada alerta se registra también en el log como WARNING.
    """
    alertas = check_tariff_jumps(tarifas_cfg, tarifas_historial)
    alertas += check_energy_change(df_anual, df_anual_anterior)
    out = pd.DataFrame(alertas, columns=[c for c in ALERT_COLUMNS if c != "fecha"])
    out["fecha"] = datetime.now().isoformat(timespec="seconds")
    for a in out.itertuples(index=False):
        logger.warning(
            "[control %s] %s: %s → %s (%+.0f %%, umbral %.0f %%). %s",
            a.control, a.entidad, f"{a.valor_anterior:,.2f}", f"{a.valor_actual:,.2f}",
            100 * a.variacion if pd.notna(a.variacion) else float("nan"),
            100 * a.umbral, a.detalle,
        )
    if out.empty:
        logger.info("Controles de calidad: sin alertas")
    return out[ALERT_COLUMNS]
