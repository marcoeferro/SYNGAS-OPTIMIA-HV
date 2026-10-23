"""Entrypoint del pipeline solar (ex ``main_actualizaciones.py``).

Corrida diaria (lo que dispara el cron, ``config/crontab``):
    1. Generación diaria Growatt del mes en curso → ``growatt_produccion``.
    2. Clima diario NASA POWER (últimos 30 días) → ``clima_historico_nasa``.
    3. Clima diario Open-Meteo (últimos 30 días) → ``clima_historico_openmeteo``.
    4. Pronóstico diario Open-Meteo (7 días) → ``clima_pronosticado``.
    5. Potencia Growatt de ayer cada 15 min → ``growatt_produccion_intradia``.
    6. Pronóstico Open-Meteo cada 15 min (5 días) → ``pronostico_15min_5days``.
    7. Energía pronosticada cada 15 min (modelo) → ``energia_pronosticada``.

Cada paso es independiente: si uno falla (p. ej. Growatt caído) los demás
se ejecutan igual, y al final se avisa y se sale con código 1.

Otros modos:
    --historico            Carga completa desde ``historico.desde`` (Growatt, NASA,
                           Open-Meteo diarios). Reemplaza a los scripts de
                           ``datosHistoricos/``.
    --validar DESDE HASTA  Clima observado cada 15 min + potencia Growatt del
                           rango, energía estimada con el modelo
                           (``energia_estimada_15min``) y métricas de error.
                           Reemplaza a los scripts de carga de ``ValidarModelo/``.
    --importar-sql URL     Copia una sola vez a Parquet las tablas de la base
                           MySQL anterior.

Uso:
    python -m optimia_hv.solar.pipelines.run_solar
    python -m optimia_hv.solar.pipelines.run_solar --historico
    python -m optimia_hv.solar.pipelines.run_solar --validar 2026-09-12 2026-09-16
    optimia-solar --solo nasa open_meteo
"""

from __future__ import annotations

import argparse
import logging
import logging.config
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pandas as pd
import yaml

from optimia_hv.comun.notifications import notify_run_result
from optimia_hv.solar.configuracion import (
    ConfigSolar,
    CredencialesGrowatt,
    cargar_config,
)
from optimia_hv.solar.extractors import growatt, nasa_power, open_meteo
from optimia_hv.solar.loaders import almacen
from optimia_hv.solar.modelos import modelo_15min
from optimia_hv.solar.validacion import comparativas, metricas

logger = logging.getLogger("optimia_hv.solar")

DEFAULT_CONFIG_PATH: Final[str] = "config/solar.yaml"
DEFAULT_LOGGING_PATH: Final[str] = "config/logging.yml"
ETIQUETA_AVISOS: Final[str] = "Pipeline solar"


@dataclass
class Resultado:
    """Qué pasó en una corrida: filas guardadas por tabla y pasos fallidos."""

    guardadas: dict[str, int] = field(default_factory=dict)
    errores: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True si ningún paso falló."""
        return not self.errores


def setup_logging(logging_path: str | Path = DEFAULT_LOGGING_PATH) -> None:
    """Inicializa el logging desde YAML (mismo archivo que biomasa)."""
    logging_path = Path(logging_path)
    if logging_path.exists():
        cfg = yaml.safe_load(logging_path.read_text(encoding="utf-8"))
        for handler in cfg.get("handlers", {}).values():
            if "filename" in handler:
                Path(handler["filename"]).parent.mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(cfg)
    else:
        logging.basicConfig(level=logging.INFO)


def _paso(
    resultado: Resultado,
    nombre: str,
    cfg: ConfigSolar,
    tabla: str,
    obtener: Callable[[], pd.DataFrame],
) -> pd.DataFrame | None:
    """Ejecuta un paso, guarda su tabla y registra el error sin cortar la corrida."""
    logger.info("[%s] %s", nombre, tabla)
    try:
        df = obtener()
        resultado.guardadas[tabla] = len(df)
        almacen.guardar(cfg.almacen_dir, tabla, df)
        return df
    except Exception as exc:  # noqa: BLE001 - un paso caído no frena a los demás
        logger.exception("[%s] falló", nombre)
        resultado.errores[nombre] = f"{type(exc).__name__}: {exc}"
        return None


# =============================================================
# Corrida diaria
# =============================================================
PASOS_DIARIOS: Final[list[str]] = [
    "growatt_diaria", "nasa", "open_meteo", "pronostico_diario",
    "growatt_15min", "pronostico_15min", "energia_pronosticada",
]


def run_diario(
    cfg: ConfigSolar,
    hoy: date | None = None,
    solo: list[str] | None = None,
) -> Resultado:
    """Corrida diaria: los 7 pasos de ``main_actualizaciones.py``.

    Args:
        cfg: Configuración solar.
        hoy: Fecha de la corrida (para tests); por defecto, hoy.
        solo: Subconjunto de :data:`PASOS_DIARIOS` (por defecto, todos).
    """
    hoy = hoy or date.today()
    ayer = hoy - timedelta(days=1)
    inicio_ventana = hoy - timedelta(days=cfg.ventana_revision_dias)
    pasos = set(solo or PASOS_DIARIOS)
    r = Resultado()
    lat, lon, tz = cfg.latitud, cfg.longitud, cfg.zona_horaria

    def con_growatt(fn: Callable[[growatt.ClienteGrowatt], pd.DataFrame]) -> pd.DataFrame:
        with growatt.ClienteGrowatt(CredencialesGrowatt.desde_entorno()) as cliente:
            return fn(cliente)

    if "growatt_diaria" in pasos:
        _paso(r, "growatt_diaria", cfg, "growatt_produccion",
              lambda: con_growatt(lambda c: growatt.diaria_mes_actual(c, hoy)))
    if "nasa" in pasos:
        _paso(r, "nasa", cfg, "clima_historico_nasa",
              lambda: nasa_power.descargar_diario(lat, lon, inicio_ventana, hoy))
    if "open_meteo" in pasos:
        _paso(r, "open_meteo", cfg, "clima_historico_openmeteo",
              lambda: open_meteo.historico_diario(lat, lon, inicio_ventana, hoy, tz))
    if "pronostico_diario" in pasos:
        _paso(r, "pronostico_diario", cfg, "clima_pronosticado",
              lambda: open_meteo.pronostico_diario(lat, lon, tz, fecha_consulta=hoy))
    if "growatt_15min" in pasos:
        _paso(r, "growatt_15min", cfg, "growatt_produccion_intradia",
              lambda: con_growatt(lambda c: growatt.intradia(c, [ayer], paso_min=15)))
    pronostico = None
    if "pronostico_15min" in pasos:
        pronostico = _paso(
            r, "pronostico_15min", cfg, "pronostico_15min_5days",
            lambda: open_meteo.pronostico_15min(
                lat, lon, cfg.dias_pronostico_15min, tz, fecha_consulta=hoy
            ),
        )
    if "energia_pronosticada" in pasos:
        def _energia() -> pd.DataFrame:
            # Si el paso 6 no corrió o falló, se usa el último pronóstico guardado.
            base = pronostico
            if base is None:
                base = almacen.leer(cfg.almacen_dir, "pronostico_15min_5days")
            if base.empty:
                raise RuntimeError("No hay pronóstico de 15 min guardado")
            return modelo_15min.energia_pronosticada(base, params=cfg.modelo_15min)
        _paso(r, "energia_pronosticada", cfg, "energia_pronosticada", _energia)
    return r


# =============================================================
# Carga histórica
# =============================================================
def run_historico(cfg: ConfigSolar, hoy: date | None = None) -> Resultado:
    """Carga completa desde ``historico.desde`` (ex ``datosHistoricos/``)."""
    hoy = hoy or date.today()
    desde = cfg.historico_desde
    lat, lon, tz = cfg.latitud, cfg.longitud, cfg.zona_horaria
    r = Resultado()

    def _growatt() -> pd.DataFrame:
        with growatt.ClienteGrowatt(CredencialesGrowatt.desde_entorno()) as cliente:
            return growatt.diaria_historica(cliente, desde, hoy - timedelta(days=1))

    _paso(r, "growatt_historico", cfg, "growatt_produccion", _growatt)
    _paso(r, "nasa_historico", cfg, "clima_historico_nasa",
          lambda: nasa_power.descargar_diario(lat, lon, desde, hoy))
    _paso(r, "open_meteo_historico", cfg, "clima_historico_openmeteo",
          lambda: open_meteo.historico_diario(lat, lon, desde, hoy, tz))
    return r


# =============================================================
# Validación del modelo
# =============================================================
def run_validacion(
    cfg: ConfigSolar,
    desde: date,
    hasta: date,
    paso_intradia_min: int = 5,
) -> Resultado:
    """Carga clima y generación de un rango y estima la energía con el modelo.

    Reemplaza a ``climaHistorico_OP_15min.py``, ``growatt_intradia.py`` y
    ``estimacionEnergia15min.py``. Al final registra las métricas de error
    (ver ``validacion/metricas.py``).
    """
    lat, lon, tz = cfg.latitud, cfg.longitud, cfg.zona_horaria
    r = Resultado()
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]

    clima = _paso(r, "clima_15min", cfg, "clima_15min_openmeteo",
                  lambda: open_meteo.historico_15min(lat, lon, desde, hasta, tz))

    def _growatt() -> pd.DataFrame:
        with growatt.ClienteGrowatt(CredencialesGrowatt.desde_entorno()) as cliente:
            return growatt.intradia(cliente, dias, paso_min=paso_intradia_min)

    _paso(r, "growatt_intradia", cfg, "growatt_produccion_intradia", _growatt)

    def _energia() -> pd.DataFrame:
        base = clima if clima is not None else almacen.leer(cfg.almacen_dir,
                                                            "clima_15min_openmeteo")
        return modelo_15min.energia_estimada_historica(base, cfg.modelo_15min)

    estimada = _paso(r, "energia_estimada", cfg, "energia_estimada_15min", _energia)

    real = almacen.leer(cfg.almacen_dir, "growatt_produccion_intradia")
    if estimada is not None and not real.empty:
        comp = comparativas.intradia_real_vs_estimada(estimada, real, desde, hasta)
        res = metricas.resumen(comp["potencia_real_w"], comp["potencia_estimada_w"])
        logger.info(
            "Métricas %s a %s (potencia, W): n=%d MAE=%.1f RMSE=%.1f sesgo=%+.1f "
            "error energía total=%+.1f%%",
            desde, hasta, res.n, res.mae, res.rmse, res.sesgo,
            res.error_relativo_total * 100,
        )
    return r


# =============================================================
# CLI
# =============================================================
def main(argv: list[str] | None = None) -> int:
    """Entrypoint CLI (``optimia-solar``)."""
    parser = argparse.ArgumentParser(description="Pipeline solar: clima, generación y modelo")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config YAML solar")
    parser.add_argument("--log-config", default=DEFAULT_LOGGING_PATH,
                        help="Config YAML de logging")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--historico", action="store_true",
                      help="Carga completa desde historico.desde")
    modo.add_argument("--validar", nargs=2, metavar=("DESDE", "HASTA"),
                      type=date.fromisoformat,
                      help="Valida el modelo en un rango (AAAA-MM-DD AAAA-MM-DD)")
    modo.add_argument("--importar-sql", metavar="URL",
                      help="Importa a Parquet las tablas de la base SQL anterior")
    parser.add_argument("--solo", nargs="+", choices=PASOS_DIARIOS,
                        help="Corrida diaria: sólo estos pasos")
    args = parser.parse_args(argv)

    setup_logging(args.log_config)
    cfg = cargar_config(args.config)

    if args.importar_sql:
        importadas = almacen.importar_desde_sql(args.importar_sql, cfg.almacen_dir)
        logger.info("Importación terminada: %s", importadas)
        return 0
    if args.historico:
        resultado = run_historico(cfg)
    elif args.validar:
        resultado = run_validacion(cfg, *args.validar)
    else:
        resultado = run_diario(cfg, solo=args.solo)

    logger.info("Filas por tabla: %s", resultado.guardadas)
    if resultado.ok:
        notify_run_result(etiqueta=ETIQUETA_AVISOS)
        return 0
    detalle = "; ".join(f"{k}: {v}" for k, v in resultado.errores.items())
    logger.error("Pasos con error: %s", detalle)
    notify_run_result(RuntimeError(detalle), etiqueta=ETIQUETA_AVISOS)
    return 1


if __name__ == "__main__":
    sys.exit(main())
