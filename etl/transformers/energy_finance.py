"""
Cálculo energético y financiero APL PP30 sobre biomasa residual.

Cadena de cálculo (por registro):

    masa_seca_kg        = Residuo Recuperable (t MS) × 1000
    kwh_generados       = masa_seca_kg / CE_seco         # CE_seco: kg MS / kWh
    masa_alimentada_kg  = masa_seca_kg / (1 − H/100)     # kg a humedad operativa
    horas_operacion     = kwh_generados / P_nom
    equipos_pp30        = horas_operacion / (8760 × disponibilidad)

Parámetros de la ficha técnica de All Power Labs (PP30 One Sheet):
consumo de biomasa **1,0 kg/kWh en base seca** (APL: con 10 % de humedad
son 1,1 kg/kWh; con 20 %, 1,2) y potencia **22 kW a 50 Hz** conectado a
red con CHP (25 kW es el valor a 60 Hz). Como el residuo ya está en base
seca, la energía sale directamente de la masa seca; la humedad sólo
determina cuánta masa hay que alimentar.

Compatibilidad: un JSON de tarifas viejo que sólo trae
``consumo_especifico_kg_kwh`` (kg tal cual / kWh) se convierte a base seca
con la humedad operativa: ``CE_seco = CE × (1 − H/100)``.

Los kWh se valorizan bajo balance neto de facturación (Ley 27.424):
ahorro por autoconsumo (tarifa de compra) e ingreso por inyección
(tarifa de inyección), discriminados por distribuidora provincial. Los
montos son **beneficio bruto** (no descuentan CAPEX, O&M ni costo de
recolección/flete del rastrojo).

Las tarifas y parámetros operativos se leen desde el JSON más
reciente en ``data/reference/YYYYMMDDHHMMSS_tarifas.json`` (extractor
``scrape_tarifas``). Las provincias sin mapeo a distribuidora quedan
con métricas financieras en NaN.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from etl.extractors.io_utils import (
    JSON_SUFFIX,
    REF_STEM_TARIFAS,
    find_latest_raw,
)

logger = logging.getLogger(__name__)

# =============================================================
# Constantes de configuración
# =============================================================
DEFAULT_TARIFAS_DIR: Final[Path] = Path("data/reference")

RESIDUO_COL: Final[str] = "Residuo de Biomasa (Tn)"
RESIDUO_REC_COL: Final[str] = "Residuo Recuperable (Tn)"
HOURS_PER_YEAR: Final[float] = 8760.0
DEFAULT_DISPONIBILIDAD: Final[float] = 0.8
PROVINCIA_COL: Final[str] = "Provincia"
CULTIVO_COL: Final[str] = "Cultivo"

KG_PER_TON: Final[float] = 1000.0
HUMEDAD_ALERTA_PCT: Final[float] = 20.0

COL_MASA_HUMEDA_KG: Final[str] = "masa_humeda_kg"
COL_MASA_SECA_KG: Final[str] = "masa_seca_kg"
COL_MASA_ALIM_KG: Final[str] = "masa_alimentada_kg"
COL_EQUIPOS: Final[str] = "equipos_pp30_equivalentes"
COL_TARIFA_PROXY: Final[str] = "tarifa_es_proxy"
COL_TARIFA_ORIGEN: Final[str] = "tarifa_origen"
COL_TARIFA_INY_ESTIMADA: Final[str] = "tarifa_inyeccion_estimada"
# Ratio inyección/compra si ninguna distribuidora publica ambos valores.
DEFAULT_RATIO_INYECCION: Final[float] = 0.75
DEPARTAMENTO_COL: Final[str] = "Departamento"

# Códigos de versiones anteriores del JSON de tarifas.
_LEGACY_CODES: Final[dict[str, str]] = {
    "EPEC_CORDOBA": "EPEC",
    "EPE_SANTA_FE": "EPE",
    "EDEMSA_MENDOZA": "EDEMSA",
    "EDENOR_AMBA": "EDENOR",
}
COL_KWH_TOTALES: Final[str] = "kwh_generados"
COL_KWH_AUTO: Final[str] = "kwh_autoconsumo"
COL_KWH_INY: Final[str] = "kwh_inyectados"
COL_HORAS: Final[str] = "horas_operacion_estimadas"
COL_AHORRO: Final[str] = "ahorro_autoconsumo_ars"
COL_CREDITO: Final[str] = "credito_inyeccion_ars"
COL_BENEFICIO: Final[str] = "beneficio_total_ars"
COL_DISTRIBUIDORA: Final[str] = "distribuidora"
COL_TARIFA_COMPRA: Final[str] = "tarifa_compra_kwh"
COL_TARIFA_INY: Final[str] = "tarifa_inyeccion_kwh"


def resolve_tarifas_path(
    path: Path | str | None = None,
    reference_dir: Path | str = DEFAULT_TARIFAS_DIR,
) -> Path:
    """
    Resuelve la ruta al JSON de tarifas a usar.

    Si ``path`` es un archivo existente, se usa. Si es un directorio o
    None, se busca el ``YYYYMMDDHHMMSS_tarifas.json`` más reciente en
    ``reference_dir``.

    Args:
        path: Archivo o directorio opcional.
        reference_dir: Directorio de referencia por defecto.

    Returns:
        Path al JSON de tarifas.
    """
    if path is not None:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            return find_latest_raw(
                candidate, REF_STEM_TARIFAS, suffix=JSON_SUFFIX
            )
    return find_latest_raw(
        reference_dir, REF_STEM_TARIFAS, suffix=JSON_SUFFIX
    )


def load_tarifas_config(
    path: Path | str | None = None,
    reference_dir: Path | str = DEFAULT_TARIFAS_DIR,
) -> dict[str, Any]:
    """
    Carga el cuadro tarifario y parámetros PP30 desde JSON.

    Args:
        path: Ruta a un JSON concreto o a un directorio de referencia.
            Si es None, usa el más reciente en ``data/reference``.
        reference_dir: Directorio donde buscar ``*_tarifas.json``.

    Returns:
        Diccionario con distribuidoras, mapeo provincial y parámetros.

    Raises:
        FileNotFoundError: Si no hay artefacto de tarifas.
        json.JSONDecodeError: Si el JSON es inválido.
    """
    resolved = resolve_tarifas_path(path, reference_dir=reference_dir)
    logger.info("Cargando tarifas desde %s", resolved)
    with resolved.open(encoding="utf-8") as handle:
        return json.load(handle)


def _norm(text: object) -> str:
    """Normalización mínima para matchear provincias/departamentos."""
    import unicodedata

    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def injection_ratio(cfg: dict[str, Any]) -> float:
    """
    Ratio mediano tarifa de inyección / tarifa de compra.

    Pocas distribuidoras publican el precio de inyección (Ley 27.424). Para
    no valorizar en cero la energía inyectada donde falta, se estima como
    compra × este ratio, calculado con las distribuidoras que publican
    ambos valores extraídos del cuadro.
    """
    ratios = []
    for info in cfg.get("distribuidoras", {}).values():
        estados = info.get("estado_campos", {})
        compra, iny = info.get("tarifa_compra_kwh"), info.get("tarifa_inyeccion_kwh")
        if (
            compra and iny and 0 < iny <= compra
            and estados.get("tarifa_inyeccion_kwh") in ("extraido", "parsed_pdf")
        ):
            ratios.append(float(iny) / float(compra))
    return float(np.median(ratios)) if ratios else DEFAULT_RATIO_INYECCION


class TariffResolver:
    """
    Resuelve la tarifa aplicable a un (provincia, departamento).

    Orden: excepción por departamento → distribuidora(s) de la provincia.
    Si la provincia tiene varias distribuidoras, la tarifa es el promedio
    simple de las que tienen valor y se marca como aproximada.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.dist: dict[str, Any] = {
            _LEGACY_CODES.get(k, k): v for k, v in cfg.get("distribuidoras", {}).items()
        }
        self.prov_map: dict[str, list[str]] = {}
        for k, v in cfg.get("provincia_a_distribuidora", {}).items():
            codes = v if isinstance(v, list) else [v]
            self.prov_map[_norm(k)] = [_LEGACY_CODES.get(c, c) for c in codes]
        self.dept_map: dict[tuple[str, str], str] = {
            (_norm(p), _norm(d)): _LEGACY_CODES.get(c, c)
            for p, depts in cfg.get("departamento_a_distribuidora", {}).items()
            for d, c in depts.items()
        }
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    def resolve(self, provincia: object, departamento: object = None) -> dict[str, Any]:
        """Devuelve distribuidora, tarifas, es_proxy y origen."""
        key = (_norm(provincia), _norm(departamento) if departamento is not None else "")
        if key in self._cache:
            return self._cache[key]
        codes = (
            [self.dept_map[key]] if key in self.dept_map else self.prov_map.get(key[0], [])
        )
        with_value = [
            c for c in codes
            if self.dist.get(c, {}).get("tarifa_compra_kwh") is not None
        ]

        def mean(field: str) -> float:
            vals = [
                float(self.dist[c][field]) for c in with_value
                if self.dist[c].get(field) is not None
            ]
            return float(np.mean(vals)) if vals else np.nan

        origins = sorted({
            self.dist[c].get("estado_campos", {}).get("tarifa_compra_kwh", "desconocido")
            for c in with_value
        })
        result = {
            "distribuidora": "+".join(codes) if codes else None,
            "compra": mean("tarifa_compra_kwh"),
            "inyeccion": mean("tarifa_inyeccion_kwh"),
            "es_proxy": len(codes) > 1
            or any(bool(self.dist.get(c, {}).get("es_proxy", False)) for c in codes),
            "origen": "+".join(origins) if origins else "sin_dato",
        }
        self._cache[key] = result
        return result


def _resolve_param(
    config: dict[str, Any],
    key: str,
    override: float | None,
) -> float:
    """Resuelve un parámetro operativo con override opcional."""
    if override is not None:
        return float(override)
    return float(config["parametros_pp30"][key])


def compute_energy_metrics(
    df: pd.DataFrame,
    *,
    humedad_pct: float | None = None,
    consumo_especifico_kg_kwh: float | None = None,
    consumo_especifico_seco_kg_kwh: float | None = None,
    potencia_nominal_kw: float | None = None,
    disponibilidad: float | None = None,
    residuo_col: str | None = None,
    config: dict[str, Any] | None = None,
    tarifas_path: Path | str | None = None,
) -> pd.DataFrame:
    """
    Calcula masa alimentada, kWh generados, horas y equipos equivalentes.

    Fórmulas (Guía APL PP30):
        masa_seca_kg       = Residuo_t_MS * 1000
        kwh_generados      = masa_seca_kg / CE_seco
        masa_alimentada_kg = masa_seca_kg / (1 - H/100)
        horas              = kwh_generados / P_nom
        equipos            = horas / (8760 * disponibilidad)

    ``equipos_pp30_equivalentes`` sólo tiene sentido sobre cantidades
    anuales (una campaña o un promedio anual).

    Args:
        df: DataFrame con la columna de residuo (t MS).
        humedad_pct: Humedad operativa del material (%). Si None, usa el
            default del config.
        consumo_especifico_kg_kwh: kg de biomasa *tal cual* por kWh (se
            convierte a base seca con la humedad).
        consumo_especifico_seco_kg_kwh: kg de materia seca por kWh. Tiene
            prioridad sobre ``consumo_especifico_kg_kwh``.
        potencia_nominal_kw: Potencia continua de referencia (PP30).
        disponibilidad: Factor de disponibilidad anual del equipo (0, 1].
        residuo_col: Columna de residuo a convertir. Si None, usa
            ``Residuo Recuperable (Tn)`` si existe, si no el residuo total.
        config: Config ya cargado. Si None, se lee desde ``tarifas_path``.
        tarifas_path: JSON de tarifas o directorio ``data/reference``.

    Returns:
        Copia del DataFrame con columnas energéticas agregadas.

    Raises:
        KeyError: Si falta la columna de residuo.
        ValueError: Si humedad, CE, potencia o disponibilidad son inválidos.
    """
    if residuo_col is None:
        residuo_col = RESIDUO_REC_COL if RESIDUO_REC_COL in df.columns else RESIDUO_COL
    if residuo_col not in df.columns:
        raise KeyError(f"Falta columna requerida: {residuo_col}")

    cfg = config if config is not None else load_tarifas_config(tarifas_path)
    h = _resolve_param(cfg, "humedad_pct_default", humedad_pct)
    params = cfg.get("parametros_pp30", {})
    if consumo_especifico_seco_kg_kwh is not None:
        ce = float(consumo_especifico_seco_kg_kwh)
    elif consumo_especifico_kg_kwh is None and "consumo_especifico_seco_kg_kwh" in params:
        ce = float(params["consumo_especifico_seco_kg_kwh"])
    else:
        # Consumo "tal cual" (JSON viejos u override explícito) → base seca.
        ce_tal_cual = _resolve_param(cfg, "consumo_especifico_kg_kwh", consumo_especifico_kg_kwh)
        ce = ce_tal_cual * (1.0 - h / 100.0)
    pnom = _resolve_param(cfg, "potencia_nominal_kw", potencia_nominal_kw)
    if disponibilidad is None:
        disponibilidad = float(
            cfg.get("parametros_pp30", {}).get("disponibilidad", DEFAULT_DISPONIBILIDAD)
        )

    if not (0.0 <= h < 100.0):
        raise ValueError(f"humedad_pct fuera de rango [0, 100): {h}")
    if ce <= 0.0:
        raise ValueError(f"consumo específico debe ser > 0: {ce}")
    if pnom <= 0.0:
        raise ValueError(f"potencia_nominal_kw debe ser > 0: {pnom}")
    if not (0.0 < disponibilidad <= 1.0):
        raise ValueError(f"disponibilidad debe estar en (0, 1]: {disponibilidad}")
    if h > HUMEDAD_ALERTA_PCT:
        logger.warning(
            "Humedad %.1f%% supera el umbral crítico del PP30 (%.1f%%). "
            "Se requiere secado previo; riesgo de alquitranes.",
            h,
            HUMEDAD_ALERTA_PCT,
        )

    out = df.copy()
    residuo = pd.to_numeric(out[residuo_col], errors="coerce")
    out[COL_MASA_SECA_KG] = residuo * KG_PER_TON
    out[COL_MASA_ALIM_KG] = out[COL_MASA_SECA_KG] / (1.0 - h / 100.0)
    out[COL_KWH_TOTALES] = out[COL_MASA_SECA_KG] / ce
    out[COL_HORAS] = out[COL_KWH_TOTALES] / pnom
    out[COL_EQUIPOS] = out[COL_HORAS] / (HOURS_PER_YEAR * disponibilidad)
    return out


def compute_finance_metrics(
    df: pd.DataFrame,
    *,
    factor_autoconsumo: float | None = None,
    config: dict[str, Any] | None = None,
    tarifas_path: Path | str | None = None,
) -> pd.DataFrame:
    """
    Segmenta kWh en autoconsumo/inyección y calcula retornos en ARS.

    Requiere que ``compute_energy_metrics`` haya corrido antes
    (columna ``kwh_generados``).

    Args:
        df: DataFrame con ``kwh_generados`` y ``Provincia``.
        factor_autoconsumo: α ∈ [0, 1]. Si None, usa el default del config.
        config: Config ya cargado. Si None, se lee desde ``tarifas_path``.
        tarifas_path: JSON de tarifas o directorio ``data/reference``.

    Returns:
        Copia del DataFrame con columnas financieras agregadas.

    Raises:
        KeyError: Si faltan columnas requeridas.
        ValueError: Si α está fuera de [0, 1].
    """
    if COL_KWH_TOTALES not in df.columns:
        raise KeyError(
            f"Falta columna {COL_KWH_TOTALES}. "
            "Ejecutar compute_energy_metrics antes."
        )
    if PROVINCIA_COL not in df.columns:
        raise KeyError(f"Falta columna requerida: {PROVINCIA_COL}")

    cfg = config if config is not None else load_tarifas_config(tarifas_path)
    alpha = _resolve_param(cfg, "factor_autoconsumo_default", factor_autoconsumo)
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(
            f"factor_autoconsumo debe estar en [0.0, 1.0]: {alpha}"
        )

    resolver = TariffResolver(cfg)
    out = df.copy()
    dept = out[DEPARTAMENTO_COL] if DEPARTAMENTO_COL in out.columns else None
    resolved = [
        resolver.resolve(p, d)
        for p, d in zip(
            out[PROVINCIA_COL],
            dept if dept is not None else [None] * len(out),
            strict=True,
        )
    ]
    out[COL_DISTRIBUIDORA] = [r["distribuidora"] for r in resolved]
    out[COL_TARIFA_COMPRA] = pd.to_numeric(
        pd.Series([r["compra"] for r in resolved], index=out.index), errors="coerce"
    )
    out[COL_TARIFA_INY] = pd.to_numeric(
        pd.Series([r["inyeccion"] for r in resolved], index=out.index), errors="coerce"
    )
    # Aproximación: provincia con varias distribuidoras/cooperativas
    # (promedio) o distribuidora marcada como proxy.
    out[COL_TARIFA_PROXY] = [r["es_proxy"] for r in resolved]
    # Origen de la tarifa de compra (extraido / fallback_previous /
    # baseline_manual / sin_dato): permite filtrar sólo valores reales.
    out[COL_TARIFA_ORIGEN] = [r["origen"] for r in resolved]
    sin_tarifa = out[COL_DISTRIBUIDORA].isna()
    if sin_tarifa.any():
        logger.info(
            "%d registros sin distribuidora mapeada (finanzas en NaN). "
            "Provincias: %s",
            int(sin_tarifa.sum()),
            sorted(out.loc[sin_tarifa, PROVINCIA_COL].astype(str).unique())[:30],
        )

    # Sin precio de inyección publicado: se estima con el ratio observado
    # (ver ``injection_ratio``) y se marca para poder filtrarlo.
    ratio = injection_ratio(cfg)
    estimar = out[COL_TARIFA_INY].isna() & out[COL_TARIFA_COMPRA].notna()
    out[COL_TARIFA_INY_ESTIMADA] = estimar
    out.loc[estimar, COL_TARIFA_INY] = out.loc[estimar, COL_TARIFA_COMPRA] * ratio
    if estimar.any():
        logger.info(
            "Tarifa de inyección estimada como compra × %.3f en %d registros",
            ratio, int(estimar.sum()),
        )

    kwh = pd.to_numeric(out[COL_KWH_TOTALES], errors="coerce")
    out[COL_KWH_AUTO] = kwh * alpha
    out[COL_KWH_INY] = kwh * (1.0 - alpha)
    out[COL_AHORRO] = out[COL_KWH_AUTO] * out[COL_TARIFA_COMPRA]
    out[COL_CREDITO] = out[COL_KWH_INY] * out[COL_TARIFA_INY]
    out[COL_BENEFICIO] = out[COL_AHORRO] + out[COL_CREDITO]
    return out


def add_energy_finance_columns(
    df: pd.DataFrame,
    *,
    humedad_pct: float | None = None,
    factor_autoconsumo: float | None = None,
    consumo_especifico_kg_kwh: float | None = None,
    potencia_nominal_kw: float | None = None,
    disponibilidad: float | None = None,
    tarifas_path: Path | str | None = None,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Orquesta el cálculo energético + financiero en un solo paso.

    Args:
        df: DataFrame de biomasa válida con residuo y provincia.
        humedad_pct: Override de humedad (%).
        factor_autoconsumo: Override de α.
        consumo_especifico_kg_kwh: Override de CE.
        potencia_nominal_kw: Override de potencia nominal.
        disponibilidad: Override del factor de disponibilidad anual.
        tarifas_path: JSON de tarifas o directorio ``data/reference``.
        config: Config ya cargado (evita releer el JSON).

    Returns:
        DataFrame con columnas energéticas y financieras.
    """
    cfg = config if config is not None else load_tarifas_config(tarifas_path)
    out = compute_energy_metrics(
        df,
        humedad_pct=humedad_pct,
        consumo_especifico_kg_kwh=consumo_especifico_kg_kwh,
        potencia_nominal_kw=potencia_nominal_kw,
        disponibilidad=disponibilidad,
        config=cfg,
    )
    out = compute_finance_metrics(
        out,
        factor_autoconsumo=factor_autoconsumo,
        config=cfg,
    )
    return out
