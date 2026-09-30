"""
Descarga y consolida datos de estimaciones agrícolas de MAGyP.

El script consulta el portal de Estimaciones Agrícolas del Ministerio de
Agricultura, Ganadería y Pesca (MAGyP) para obtener el período disponible,
el catálogo de provincias y el catálogo de departamentos.

Posteriormente, realiza una consulta individual para cada combinación de
provincia y departamento, obteniendo datos de superficie sembrada,
superficie cosechada, producción y rendimiento.

Los resultados de todas las consultas se consolidan en un único
DataFrame, incorporando las columnas Provincia y Departamento con sus
respectivos nombres descriptivos.

Finalmente, los datos consolidados se almacenan en formato CSV.

La configuración del proceso, incluyendo URLs, headers HTTP, timeout,
reintentos, delays, cultivos, variables, parámetros de agregación,
encoding y ruta de salida, se encuentra centralizada en constantes al
inicio del script.
"""

import io
import json
import time
from pathlib import Path
from typing import Any, Final

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from etl.extractors.io_utils import (
    RAW_STEM_MAGYP,
    build_timestamped_filename,
)

# ====================== CONFIGURACIÓN ======================

BASE_URL: Final[str] = "https://datosestimaciones.magyp.gob.ar"

REPORT_URL: Final[str] = (
    f"{BASE_URL}/reportes.php?reporte=Estimaciones"
)

PROVINCIAS_URL: Final[str] = (
    f"{BASE_URL}/ajax/getProvincias.php"
)

DEPARTAMENTOS_URL: Final[str] = (
    f"{BASE_URL}/ajax/getDepartamentos.php"
)


# ====================== HTTP ======================

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)

HEADERS: Final[dict[str, str]] = {
    "User-Agent": USER_AGENT,
}

AJAX_HEADERS: Final[dict[str, str]] = {
    **HEADERS,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

HTTP_TIMEOUT: Final[float] = 120.0
REQUEST_TIMEOUT: Final[float] = HTTP_TIMEOUT
FOLLOW_REDIRECTS: Final[bool] = True

MAX_RETRIES: Final[int] = 6
INITIAL_RETRY_DELAY: Final[float] = 2.0
REQUEST_RATE_DELAY: Final[float] = 1.5
RATE_LIMIT_STATUS_CODE: Final[int] = 429
RETRYABLE_STATUS_CODES: Final[set[int]] = {429, 500, 502, 503, 504}

# ====================== DATOS ======================

START_CAMPAIGN: Final[str] = "1"

# CROP_IDS se obtiene dinámicamente parseando el HTML del selector #cultivo
# (ver get_crop_ids / extract_crop_ids_from_html)

VARIABLES: Final[list[str]] = [
    "Sup. Sembrada",
    "Sup. Cosechada",
    "Producción",
    "Rendimiento",
]

AGGREGATION: Final[str] = "Total Departamentos"

DOWNLOAD_SUBMIT_VALUE: Final[str] = "Descargar"


# ====================== PARSEO ======================

UNTIL_SELECT_ID: Final[str] = "hasta"
CROP_SELECT_ID: Final[str] = "cultivo"

PROVINCE_ID_SEPARATOR: Final[str] = "-"

CSV_CONTENT_TYPE: Final[str] = "text/csv"
CSV_SEPARATOR: Final[str] = ";"
CSV_DECIMAL: Final[str] = ","
CSV_ENCODING: Final[str] = "latin1"

OUTPUT_ENCODING: Final[str] = "utf-8-sig"


# ====================== ARCHIVOS ======================

OUTPUT_DIRECTORY: Final[Path] = Path("./data/raw")
OUTPUT_STEM: Final[str] = RAW_STEM_MAGYP

PROVINCIAS_CACHE_PATH: Final[Path] = (
    OUTPUT_DIRECTORY / "estimaciones_agricolas_provincias.json"
)
DEPARTAMENTOS_CACHE_PATH: Final[Path] = (
    OUTPUT_DIRECTORY / "estimaciones_agricolas_departamentos.json"
)


# ====================== TIPOS ======================

JSONData: type = list[dict[str, Any]]


# ====================== HTTP ======================

def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Realiza una solicitud HTTP con reintentos ante HTTP 429.

    Utiliza un backoff exponencial cuando el servidor no proporciona
    explícitamente un valor mediante el header Retry-After.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.
        method: Método HTTP, por ejemplo GET o POST.
        url: URL del recurso solicitado.
        **kwargs: Argumentos adicionales enviados a client.request().

    Returns:
        Respuesta HTTP exitosa.

    Raises:
        httpx.HTTPStatusError: Si la respuesta contiene un código HTTP
            de error distinto de 429, o si se agotan los reintentos.
        httpx.RequestError: Si ocurre un error de comunicación.
    """
    delay = INITIAL_RETRY_DELAY

    for attempt in range(MAX_RETRIES):
        response = client.request(method, url, **kwargs)

        if response.status_code not in RETRYABLE_STATUS_CODES:
            response.raise_for_status()
            return response

        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                wait = float(retry_after)
            except ValueError:
                wait = delay
        else:
            wait = delay

        print(
            f"HTTP {response.status_code} en intento {attempt + 1}/{MAX_RETRIES}. "
            f"Esperando {wait:.1f}s..."
        )
        time.sleep(wait)
        delay *= 2

    response.raise_for_status()
    return response


# ====================== CATÁLOGOS ======================

def get_report_html(client: httpx.Client) -> str:
    """Obtiene el HTML de la página principal de estimaciones.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.

    Returns:
        Contenido HTML de la página de reportes.
    """
    response = request_with_retry(
        client,
        "GET",
        REPORT_URL,
    )
    return response.text


def extract_hasta_from_html(html: str) -> int:
    """Extrae el último período disponible desde el HTML del selector #hasta.

    Args:
        html: Contenido HTML de la página de reportes.

    Returns:
        Identificador entero del último período disponible.

    Raises:
        ValueError: Si no se encuentra ningún período válido.
    """
    soup = BeautifulSoup(html, "html.parser")

    options = soup.select(f"#{UNTIL_SELECT_ID} option")

    values = [
        int(option["value"])
        for option in options
        if option.get("value", "").isdigit()
    ]

    if not values:
        raise ValueError(
            "No se encontró ningún período válido en el selector "
            f"#{UNTIL_SELECT_ID}."
        )

    return max(values)


def extract_crop_ids_from_html(html: str) -> list[str]:
    """Extrae los IDs de cultivo desde el HTML del selector #cultivo.

    Args:
        html: Contenido HTML de la página de reportes.

    Returns:
        Lista de valores (value) de las opciones del selector de cultivos.

    Raises:
        ValueError: Si no se encuentra el selector o no hay opciones válidas.
    """
    soup = BeautifulSoup(html, "html.parser")

    options = soup.select(f"#{CROP_SELECT_ID} option")

    crop_ids = [
        str(option["value"]).strip()
        for option in options
        if option.get("value") is not None and str(option["value"]).strip() != ""
    ]

    if not crop_ids:
        raise ValueError(
            "No se encontró ningún cultivo válido en el selector "
            f"#{CROP_SELECT_ID}."
        )

    return crop_ids


def get_hasta_and_crop_ids(
    client: httpx.Client,
) -> tuple[int, list[str]]:
    """Obtiene el último período y los IDs de cultivo con una sola petición.

    Reutiliza el mismo HTML de la página de reportes para evitar
    solicitudes adicionales.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.

    Returns:
        Tupla (hasta, crop_ids).
    """
    html = get_report_html(client)
    hasta = extract_hasta_from_html(html)
    crop_ids = extract_crop_ids_from_html(html)
    return hasta, crop_ids


def load_json_cache(path: Path) -> JSONData | None:
    """Carga un catálogo JSON desde disco si el archivo existe.

    Args:
        path: Ruta del archivo JSON de caché.

    Returns:
        Lista de diccionarios si el archivo existe y es válido;
        None en caso contrario.
    """
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass

    return None


def save_json_cache(path: Path, data: JSONData) -> None:
    """Guarda un catálogo JSON en disco.

    Args:
        path: Ruta del archivo JSON de caché.
        data: Datos a serializar.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_provincias(client: httpx.Client) -> JSONData:
    """Realiza la petición AJAX de provincias a MAGyP.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.

    Returns:
        Lista de diccionarios con la información de las provincias.
    """
    response = request_with_retry(
        client,
        "POST",
        PROVINCIAS_URL,
        headers=AJAX_HEADERS,
    )
    return response.json()


def get_provincias(client: httpx.Client) -> JSONData:
    """Obtiene el catálogo de provincias, usando caché en disco si existe.

    Si existe estimaciones_agricolas_provincias.json lo carga.
    Si no existe, hace la petición AJAX, guarda el archivo y continúa.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.

    Returns:
        Lista de diccionarios con la información de las provincias.
    """
    cached = load_json_cache(PROVINCIAS_CACHE_PATH)
    if cached is not None:
        print(f"Provincias cargadas desde caché: {PROVINCIAS_CACHE_PATH}")
        return cached

    print("Provincias no encontradas en caché. Solicitando a MAGyP...")
    data = fetch_provincias(client)
    save_json_cache(PROVINCIAS_CACHE_PATH, data)
    print(f"Provincias guardadas en: {PROVINCIAS_CACHE_PATH}")
    return data


def build_departamentos_request(
    provincias: JSONData,
) -> dict[str, str]:
    """Construye los parámetros para solicitar los departamentos.

    Args:
        provincias: Lista de provincias devuelta por MAGyP.

    Returns:
        Diccionario con los parámetros requeridos por el endpoint.
    """
    return {
        str(index): str(provincia["id"])
        for index, provincia in enumerate(provincias)
    }


def fetch_departamentos(
    client: httpx.Client,
    provincias: JSONData,
) -> JSONData:
    """Realiza la petición AJAX de departamentos a MAGyP.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.
        provincias: Catálogo de provincias obtenido previamente.

    Returns:
        Lista de diccionarios con la información de los departamentos.
    """
    data = build_departamentos_request(provincias)

    response = request_with_retry(
        client,
        "POST",
        DEPARTAMENTOS_URL,
        headers=AJAX_HEADERS,
        data=data,
    )

    return response.json()


def get_departamentos(
    client: httpx.Client,
    provincias: JSONData,
) -> JSONData:
    """Obtiene el catálogo de departamentos, usando caché en disco si existe.

    Si existe estimaciones_agricolas_departamentos.json lo carga.
    Si no existe, hace la petición AJAX, guarda el archivo y continúa.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.
        provincias: Catálogo de provincias obtenido previamente.

    Returns:
        Lista de diccionarios con la información de los departamentos.
    """
    cached = load_json_cache(DEPARTAMENTOS_CACHE_PATH)
    if cached is not None:
        print(f"Departamentos cargados desde caché: {DEPARTAMENTOS_CACHE_PATH}")
        return cached

    print("Departamentos no encontrados en caché. Solicitando a MAGyP...")
    data = fetch_departamentos(client, provincias)
    save_json_cache(DEPARTAMENTOS_CACHE_PATH, data)
    print(f"Departamentos guardados en: {DEPARTAMENTOS_CACHE_PATH}")
    return data


# ====================== TRANSFORMACIÓN DE CATÁLOGOS ======================

def parse_provincia(
    provincia: dict[str, Any],
) -> dict[str, str]:
    """Transforma un registro de provincia al formato interno.

    Args:
        provincia: Registro original devuelto por MAGyP.

    Returns:
        Diccionario normalizado con ID y nombre de provincia.
    """
    return {
        "id": str(provincia["id"]),
        "nombre": provincia["descr"].strip(),
    }


def parse_departamento(
    departamento: dict[str, Any],
) -> dict[str, str]:
    """Transforma un registro de departamento al formato interno.

    El endpoint devuelve los datos con el formato:

        id: "ID_PROVINCIA-ID_DEPARTAMENTO"
        dpto: "NOMBRE_DEPARTAMENTO - NOMBRE_PROVINCIA"

    Args:
        departamento: Registro original devuelto por MAGyP.

    Returns:
        Diccionario normalizado con ID de departamento, ID de provincia
        y nombre de departamento.

    Raises:
        ValueError: Si el formato recibido no contiene los separadores
            esperados.
    """
    raw_id = departamento["id"].strip()
    raw_name = departamento["dpto"].strip()

    try:
        provincia_id, departamento_id = raw_id.split(
            PROVINCE_ID_SEPARATOR,
            1,
        )

        departamento_name, _ = raw_name.split(
            PROVINCE_ID_SEPARATOR,
            1,
        )
    except ValueError as exc:
        raise ValueError(
            "El departamento recibido desde MAGyP tiene un formato "
            f"inesperado: {departamento}"
        ) from exc

    return {
        "id": departamento_id.strip(),
        "id_provincia": provincia_id.strip(),
        "nombre": departamento_name.strip(),
    }


def construir_catalogos(
    provincias_response: JSONData,
    departamentos_response: JSONData,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye los DataFrames normalizados de provincias y departamentos.

    Args:
        provincias_response: Respuesta original del endpoint de
            provincias.
        departamentos_response: Respuesta original del endpoint de
            departamentos.

    Returns:
        Tupla formada por:

        - DataFrame de provincias.
        - DataFrame de departamentos.
    """
    provincias = pd.DataFrame(
        [
            parse_provincia(provincia)
            for provincia in provincias_response
        ]
    )

    departamentos = pd.DataFrame(
        [
            parse_departamento(departamento)
            for departamento in departamentos_response
        ]
    )

    return provincias, departamentos


def get_departamentos_provincia(
    departamentos: pd.DataFrame,
    provincia_id: str,
) -> pd.DataFrame:
    """Filtra los departamentos pertenecientes a una provincia.

    Args:
        departamentos: DataFrame completo de departamentos.
        provincia_id: Identificador de la provincia.

    Returns:
        DataFrame con los departamentos de la provincia indicada.
    """
    return departamentos.loc[
        departamentos["id_provincia"] == provincia_id
    ].copy()


# ====================== DESCARGA DE DATOS ======================

def build_download_payload(
    provincia_id: str,
    departamento_id: str,
    hasta: int,
    crop_ids: list[str],
) -> dict[str, Any]:
    """Construye los parámetros para descargar datos agrícolas.

    Args:
        provincia_id: Identificador de la provincia.
        departamento_id: Identificador del departamento.
        hasta: Último período de estimaciones disponible.
        crop_ids: Lista de IDs de cultivo a solicitar.

    Returns:
        Diccionario con los parámetros requeridos por MAGyP.
    """
    return {
        "cultivo[]": crop_ids,
        "variable[]": VARIABLES,
        "desde": START_CAMPAIGN,
        "hasta": str(hasta),
        "agregacion": AGGREGATION,
        "provincia[]": [provincia_id],
        "departamento[]": [
            f"{provincia_id}-{departamento_id}"
        ],
        "submit": DOWNLOAD_SUBMIT_VALUE,
    }


def read_csv_response(content: bytes) -> pd.DataFrame:
    """Interpreta contenido binario como CSV de MAGyP.

    Args:
        content: Contenido binario del archivo CSV.

    Returns:
        DataFrame construido a partir del CSV.
    """
    return pd.read_csv(
        io.BytesIO(content),
        sep=CSV_SEPARATOR,
        decimal=CSV_DECIMAL,
        encoding=CSV_ENCODING,
    )


def read_excel_response(content: bytes) -> pd.DataFrame:
    """Interpreta contenido binario como archivo Excel.

    Args:
        content: Contenido binario del archivo Excel.

    Returns:
        DataFrame construido a partir del Excel.
    """
    return pd.read_excel(
        io.BytesIO(content),
    )


def is_csv_response(
    response: httpx.Response,
) -> bool:
    """Determina si una respuesta HTTP contiene un CSV.

    Args:
        response: Respuesta HTTP recibida.

    Returns:
        True si el Content-Type indica CSV; de lo contrario, False.
    """
    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    return (
        CSV_CONTENT_TYPE in content_type
        or "csv" in content_type
    )


def is_xlsx_response(
    content: bytes,
) -> bool:
    """Determina si el contenido corresponde a un archivo XLSX.

    Args:
        content: Contenido binario recibido.

    Returns:
        True si el contenido comienza con la firma ZIP utilizada
        por los archivos XLSX.
    """
    return content[:2] == b"PK"


def is_xls_response(
    content: bytes,
) -> bool:
    """Determina si el contenido corresponde a un archivo XLS.

    Args:
        content: Contenido binario recibido.

    Returns:
        True si el contenido comienza con la firma OLE utilizada
        por los archivos XLS.
    """
    return content[:8] == (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    )


def parse_download_response(
    response: httpx.Response,
) -> pd.DataFrame:
    """Interpreta una respuesta de descarga como CSV o Excel.

    Primero utiliza el Content-Type para identificar CSV. Luego utiliza
    las firmas binarias conocidas para XLSX y XLS. Finalmente intenta
    interpretar el contenido como CSV y, como último recurso, como
    Excel.

    Args:
        response: Respuesta HTTP obtenida desde MAGyP.

    Returns:
        DataFrame con los datos descargados.

    Raises:
        ValueError: Si la respuesta no puede interpretarse como CSV
            ni como Excel.
    """
    content = response.content

    if is_csv_response(response):
        return read_csv_response(content)

    if is_xlsx_response(content) or is_xls_response(content):
        return read_excel_response(content)

    try:
        return read_csv_response(content)
    except Exception as csv_error:
        try:
            return read_excel_response(content)
        except Exception as excel_error:
            raise ValueError(
                "La respuesta del servidor no pudo interpretarse "
                "como CSV ni Excel."
            ) from excel_error


def descargar_datos(
    client: httpx.Client,
    provincia_id: str,
    departamento_id: str,
    hasta: int,
    crop_ids: list[str],
) -> pd.DataFrame:
    """Descarga los datos agrícolas de un departamento.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.
        provincia_id: Identificador de la provincia.
        departamento_id: Identificador del departamento.
        hasta: Último período de estimaciones disponible.
        crop_ids: Lista de IDs de cultivo a solicitar.

    Returns:
        DataFrame con los datos agrícolas descargados.
    """
    data = build_download_payload(
        provincia_id=provincia_id,
        departamento_id=departamento_id,
        hasta=hasta,
        crop_ids=crop_ids,
    )

    response = request_with_retry(
        client,
        "POST",
        REPORT_URL,
        data=data,
    )

    return parse_download_response(response)


# ====================== CONSOLIDACIÓN ======================

def add_location_columns(
    dataframe: pd.DataFrame,
    provincia: str,
    departamento: str,
) -> pd.DataFrame:
    """Agrega las columnas descriptivas de ubicación.

    Args:
        dataframe: DataFrame con los datos descargados.
        provincia: Nombre de la provincia.
        departamento: Nombre del departamento.

    Returns:
        Copia del DataFrame con las columnas Provincia y Departamento.
    """
    result = dataframe.copy()

    result["Provincia"] = provincia
    result["Departamento"] = departamento

    return result


def descargar_datos_departamento(
    client: httpx.Client,
    provincia: pd.Series,
    departamento: pd.Series,
    hasta: int,
    crop_ids: list[str],
) -> pd.DataFrame:
    """Descarga y etiqueta los datos de un departamento.

    Args:
        client: Cliente HTTP utilizado para realizar las solicitudes.
        provincia: Registro de la provincia.
        departamento: Registro del departamento.
        hasta: Último período disponible.
        crop_ids: Lista de IDs de cultivo a solicitar.

    Returns:
        DataFrame descargado con Provincia y Departamento agregados.
    """
    dataframe = descargar_datos(
        client=client,
        provincia_id=provincia["id"],
        departamento_id=departamento["id"],
        hasta=hasta,
        crop_ids=crop_ids,
    )

    return add_location_columns(
        dataframe=dataframe,
        provincia=provincia["nombre"],
        departamento=departamento["nombre"],
    )


def descargar_todos_los_datos(
    client: httpx.Client,
    provincias: pd.DataFrame,
    departamentos: pd.DataFrame,
    hasta: int,
    crop_ids: list[str],
) -> list[pd.DataFrame]:
    """Descarga los datos de todos los departamentos disponibles.

    Recorre cada provincia y sus departamentos asociados, realizando
    una consulta individual para cada uno.

    Args:
        client: Cliente HTTP utilizado para las solicitudes.
        provincias: Catálogo de provincias.
        departamentos: Catálogo de departamentos.
        hasta: Último período disponible.
        crop_ids: Lista de IDs de cultivo a solicitar.

    Returns:
        Lista de DataFrames, uno por cada departamento descargado.
    """
    dataframes: list[pd.DataFrame] = []
    total = 0
    ok = 0
    fail = 0

    for _, provincia in provincias.iterrows():
        provincia_id = provincia["id"]

        departamentos_provincia = get_departamentos_provincia(
            departamentos=departamentos,
            provincia_id=provincia_id,
        )

        for _, departamento in departamentos_provincia.iterrows():
            total += 1
            nombre_prov = provincia["nombre"]
            nombre_depto = departamento["nombre"]

            try:
                dataframe = descargar_datos_departamento(
                    client=client,
                    provincia=provincia,
                    departamento=departamento,
                    hasta=hasta,
                    crop_ids=crop_ids,
                )
                dataframes.append(dataframe)
                ok += 1
                print(f"{nombre_prov} - {nombre_depto} Successfully Scrapped!")
            except Exception as exc:
                fail += 1
                print(
                    f"{nombre_prov} - {nombre_depto} FAILED: {type(exc).__name__}: {exc}"
                )

            time.sleep(REQUEST_RATE_DELAY)

    print(f"Descarga finalizada: {ok}/{total} OK, {fail} fallidos.")
    return dataframes


def combine_dataframes(
    dataframes: list[pd.DataFrame],
) -> pd.DataFrame:
    """Combina todos los DataFrames descargados.

    Args:
        dataframes: Lista de DataFrames individuales.

    Returns:
        DataFrame consolidado.

    Raises:
        ValueError: Si no existen DataFrames para combinar.
    """
    if not dataframes:
        raise ValueError(
            "No se descargaron datos para consolidar."
        )

    return pd.concat(
        dataframes,
        ignore_index=True,
    )


# ====================== ALMACENAMIENTO ======================

def save_data(
    dataframe: pd.DataFrame,
    output_path: Path,
) -> None:
    """Guarda los datos consolidados en formato CSV.

    Crea automáticamente el directorio de destino si no existe.

    Args:
        dataframe: DataFrame que se desea guardar.
        output_path: Ruta completa del archivo de salida.
    """
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        output_path,
        index=False,
        encoding=OUTPUT_ENCODING,
    )


# ====================== EJECUCIÓN ======================

def run_extractor(output_dir: Path | str | None = None) -> Path:
    """
    Ejecuta el proceso completo de extracción y consolidación MAGyP.

    Persiste un CSV con nombre
    ``YYYYMMDDHHMMSS_datos_estimaciones.csv``.

    Args:
        output_dir: Directorio de salida. Si es None, usa
            ``OUTPUT_DIRECTORY``.

    Returns:
        Path absoluto del CSV persistido.
    """
    target_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIRECTORY
    output_path = target_dir / build_timestamped_filename(OUTPUT_STEM)

    with httpx.Client(
        headers=HEADERS,
        timeout=HTTP_TIMEOUT,
        follow_redirects=FOLLOW_REDIRECTS,
    ) as client:
        hasta, crop_ids = get_hasta_and_crop_ids(client)
        print(f"Período hasta: {hasta}")
        print(f"Cultivos detectados ({len(crop_ids)}): {crop_ids}")

        provincias_response = get_provincias(client)
        departamentos_response = get_departamentos(
            client,
            provincias_response,
        )
        provincias, departamentos = construir_catalogos(
            provincias_response,
            departamentos_response,
        )
        dataframes = descargar_todos_los_datos(
            client=client,
            provincias=provincias,
            departamentos=departamentos,
            hasta=hasta,
            crop_ids=crop_ids,
        )

    resultado = combine_dataframes(dataframes)
    save_data(dataframe=resultado, output_path=output_path)

    print("Datos de MAGyP descargados y guardados.")
    print(f"Shape: {resultado.shape}")
    print(f"Archivo: {output_path}")
    return output_path.resolve()


if __name__ == "__main__":
    run_extractor()