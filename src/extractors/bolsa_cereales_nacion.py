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


# ====================== CONFIGURACIÓN ======================

DOWNLOAD_URL: Final[str] = (
    "https://www.bolsadecereales.com/admin/phpexcel/Examples/"
    "reporte_bd.php?cultivo=&campania=&zona=&t=PAS"
)

OUTPUT_DIRECTORY: Final[Path] = Path("data")
OUTPUT_FILENAME: Final[str] = "datos_bolsa_cereales_nacion.xlsx"
OUTPUT_PATH: Final[Path] = OUTPUT_DIRECTORY / OUTPUT_FILENAME


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

def main() -> None:
    """Ejecuta el proceso completo de descarga y almacenamiento."""
    content = download_content(DOWNLOAD_URL)

    save_data(
        content=content,
        output_path=OUTPUT_PATH,
    )

    print(
        "Descargado correctamente: "
        f"{len(content)} bytes."
    )
    print(f"Archivo: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()