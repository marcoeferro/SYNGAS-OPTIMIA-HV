"""Configuración de la tesis solar.

Lee ``config/solar.yaml`` (coordenadas, parámetros de los modelos, rutas) y
las variables de entorno con secretos (credenciales de Growatt). Antes cada
script tenía las coordenadas, la base de datos y la clave de Growatt
escritas en el código; ahora se cambian sin tocarlo y la clave nunca se
sube al repositorio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final

import yaml

# Raíz del repo (donde están data/ y config/). OPTIMIA_ROOT la fija la imagen
# Docker; si no, se deduce de src/optimia_hv/solar/ -> raíz.
PROJECT_ROOT: Final[Path] = Path(
    os.environ.get("OPTIMIA_ROOT") or Path(__file__).resolve().parents[3]
)
DEFAULT_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "solar.yaml"


@dataclass(frozen=True)
class ParametrosModelo15min:
    """Parámetros del modelo físico de 15 minutos (datasheet de la planta)."""

    potencia_pico_kwp: float = 2.25
    eficiencia_inversor: float = 0.93
    pr_base: float = 0.78
    gamma: float = -0.0035
    noct: float = 45.0
    inclinacion_panel: float = 35.0


@dataclass(frozen=True)
class ParametrosModeloViejo:
    """Parámetros del modelo viejo (diario, línea de base)."""

    potencia_pico_kwp: float = 2.25
    eficiencia_inversor: float = 0.93
    pr_base: float = 0.88
    gamma: float = -0.0035


@dataclass(frozen=True)
class CredencialesGrowatt:
    """Usuario, clave e ID de planta del portal Growatt (desde ``.env``)."""

    usuario: str
    clave: str
    plant_id: str

    @classmethod
    def desde_entorno(cls) -> CredencialesGrowatt:
        """Lee ``GROWATT_USER``, ``GROWATT_PASSWORD`` y ``GROWATT_PLANT_ID``.

        Raises:
            RuntimeError: Si falta alguna variable.
        """
        valores = {
            nombre: os.environ.get(nombre, "").strip()
            for nombre in ("GROWATT_USER", "GROWATT_PASSWORD", "GROWATT_PLANT_ID")
        }
        faltan = [k for k, v in valores.items() if not v]
        if faltan:
            raise RuntimeError(
                f"Faltan variables de entorno de Growatt: {', '.join(faltan)}. "
                "Copiá .env.example a .env y completalas."
            )
        return cls(
            usuario=valores["GROWATT_USER"],
            clave=valores["GROWATT_PASSWORD"],
            plant_id=valores["GROWATT_PLANT_ID"],
        )


@dataclass(frozen=True)
class ConfigSolar:
    """Configuración completa de la tesis solar."""

    latitud: float = -33.64451720576176
    longitud: float = -65.44526071823961
    zona_horaria: str = "America/Argentina/San_Luis"
    historico_desde: date = date(2024, 8, 1)
    ventana_revision_dias: int = 30
    dias_pronostico_15min: int = 5
    modelo_15min: ParametrosModelo15min = field(default_factory=ParametrosModelo15min)
    modelo_viejo: ParametrosModeloViejo = field(default_factory=ParametrosModeloViejo)
    almacen_dir: Path = PROJECT_ROOT / "data" / "processed" / "solar"


def _ruta(valor: str | Path) -> Path:
    p = Path(valor)
    return p if p.is_absolute() else PROJECT_ROOT / p


def cargar_config(path: str | Path = DEFAULT_CONFIG_PATH) -> ConfigSolar:
    """Lee ``config/solar.yaml``; las claves que falten toman el valor por defecto.

    Args:
        path: Ruta al YAML. Si no existe, se usan los valores por defecto.

    Returns:
        Configuración de la tesis solar.
    """
    path = Path(path)
    datos: dict[str, Any] = {}
    if path.is_file():
        datos = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    base = ConfigSolar()
    ubic = datos.get("ubicacion", {})
    desde = datos.get("historico", {}).get("desde")
    return ConfigSolar(
        latitud=float(ubic.get("latitud", base.latitud)),
        longitud=float(ubic.get("longitud", base.longitud)),
        zona_horaria=str(ubic.get("zona_horaria", base.zona_horaria)),
        historico_desde=date.fromisoformat(str(desde)) if desde else base.historico_desde,
        ventana_revision_dias=int(datos.get("ventana_revision_dias", base.ventana_revision_dias)),
        dias_pronostico_15min=int(datos.get("dias_pronostico_15min", base.dias_pronostico_15min)),
        modelo_15min=ParametrosModelo15min(**datos.get("modelo_15min", {})),
        modelo_viejo=ParametrosModeloViejo(**datos.get("modelo_viejo", {})),
        almacen_dir=_ruta(datos.get("almacen", {}).get("dir", base.almacen_dir)),
    )
