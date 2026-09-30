"""
Descarga el dataset de la Bolsa de Cereales de Buenos Aires.

El script realiza una solicitud HTTP al endpoint de descarga de la Bolsa
de Cereales utilizando curl_cffi con impersonación de Chrome para
reproducir las características de una solicitud realizada desde un
navegador.

La respuesta obtenida se valida y se almacena directamente en formato
Excel en el directorio de datos configurado.

La configuración del proceso, incluyendo la URL de descarga, la ruta
de salida, el navegador utilizado para la impersonación y el timeout
de la solicitud, se encuentra centralizada en constantes al inicio
del script.
"""

from pathlib import Path
from typing import Final

from curl_cffi import requests

from etl.extractors.io_utils import (
    RAW_STEM_NACION,
    XLSX_SUFFIX,
    build_timestamped_filename,
)

# ====================== CONFIGURACIÓN ======================

DOWNLOAD_URL: Final[str] = (
    "https://www.bolsadecereales.com/admin/phpexcel/Examples/"
    "reporte_bd.php?cultivo=&campania=&zona=&t=PAS"
)

OUTPUT_DIRECTORY: Final[Path] = Path("./data/raw")
OUTPUT_STEM: Final[str] = RAW_STEM_NACION

# ====================== HTTP ======================

HTTP_TIMEOUT: Final[int] = 60
HTTP_SUCCESS_STATUS: Final[int] = 200
BROWSER_IMPERSONATION: Final[str] = "chrome110"


# ====================== DESCARGA ======================

def download_content(url: str) -> bytes:
    """Descarga el contenido binario de una URL.

    La solicitud utiliza curl_cffi con impersonación de Chrome para
    reproducir las características TLS/HTTP de un navegador.

    Args:
        url: URL desde la cual se descargará el archivo.

    Returns:
        Contenido binario descargado.

    Raises:
        RuntimeError: Si el servidor devuelve un código HTTP distinto
            de 200 o una respuesta vacía.
    """
    response = requests.get(
        url,
        impersonate=BROWSER_IMPERSONATION,
        timeout=HTTP_TIMEOUT,
    )

    if response.status_code != HTTP_SUCCESS_STATUS:
        raise RuntimeError(
            "Fallo en la descarga. "
            f"Estado HTTP: {response.status_code}"
        )

    if not response.content:
        raise RuntimeError(
            "Fallo en la descarga. "
            "El servidor devolvió una respuesta vacía."
        )

    return response.content


# ====================== ALMACENAMIENTO ======================

def save_data(
    content: bytes,
    output_path: Path,
) -> None:
    """Guarda contenido binario en un archivo.

    Crea el directorio padre si todavía no existe.

    Args:
        content: Contenido binario que se desea guardar.
        output_path: Ruta del archivo de salida.
    """
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_bytes(content)


# ====================== EJECUCIÓN ======================

def run_extractor(output_dir: Path | str | None = None) -> Path:
    """
    Ejecuta el proceso completo de descarga de Bolsa Nación.

    Persiste un Excel con nombre
    ``YYYYMMDDHHMMSS_datos_bolsa_cereales_nacion.xlsx``.

    Args:
        output_dir: Directorio de salida. Si es None, usa
            ``OUTPUT_DIRECTORY``.

    Returns:
        Path absoluto del archivo persistido.
    """
    target_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIRECTORY
    output_path = target_dir / build_timestamped_filename(
        OUTPUT_STEM,
        suffix=XLSX_SUFFIX,
    )

    content = download_content(DOWNLOAD_URL)
    save_data(content=content, output_path=output_path)

    print(f"Descargado correctamente: {len(content)} bytes.")
    print(f"Archivo: {output_path}")
    return output_path.resolve()


if __name__ == "__main__":
    run_extractor()