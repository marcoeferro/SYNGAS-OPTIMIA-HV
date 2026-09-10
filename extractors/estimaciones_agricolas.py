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
import time
from pathlib import Path
from typing import Any, Final

import httpx
import pandas as pd
from bs4 import BeautifulSoup


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
REQUEST_RATE_DELAY: Final[float] = 1.0
RATE_LIMIT_STATUS_CODE: Final[int] = 429


# ====================== DATOS ======================

START_CAMPAIGN: Final[str] = "1"

CROP_IDS: Final[list[str]] = [
    str(crop_id)
    for crop_id in range(1, 32)
]

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

PROVINCE_ID_SEPARATOR: Final[str] = "-"

CSV_CONTENT_TYPE: Final[str] = "text/csv"
CSV_SEPARATOR: Final[str] = ";"
CSV_DECIMAL: Final[str] = ","
CSV_ENCODING: Final[str] = "latin1"

OUTPUT_ENCODING: Final[str] = "utf-8-sig"


# ====================== ARCHIVOS ======================

OUTPUT_DIRECTORY: Final[Path] = Path("./data")
OUTPUT_FILENAME: Final[str] = "datos_estimaciones.csv"
OUTPUT_PATH: Final[Path] = OUTPUT_DIRECTORY / OUTPUT_FILENAME


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

    for _ in range(MAX_RETRIES):
        response = client.request(
            method,
            url,
            **kwargs,
        )

        if response.status_code != RATE_LIMIT_STATUS_CODE:
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

        time.sleep(wait)

        delay *= 2

    response.raise_for_status()

    return response


# ====================== CATÁLOGOS ======================

def get_hasta(client: httpx.Client) -> int:
    """Obtiene el último período de estimaciones disponible.

    Consulta la página principal de estimaciones y obtiene el mayor
    valor numérico disponible en el selector HTML identificado como
    'hasta'.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.

    Returns:
        Identificador entero del último período disponible.

    Raises:
        ValueError: Si no se encuentra ningún período válido.
    """
    response = request_with_retry(
        client,
        "GET",
        REPORT_URL,
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    options = soup.select(
        f"#{UNTIL_SELECT_ID} option"
    )

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


def get_provincias(
    client: httpx.Client,
) -> JSONData:
    """Obtiene el catálogo de provincias desde MAGyP.

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


def get_departamentos(
    client: httpx.Client,
    provincias: JSONData,
) -> JSONData:
    """Obtiene el catálogo de departamentos de MAGyP.

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
) -> dict[str, Any]:
    """Construye los parámetros para descargar datos agrícolas.

    Args:
        provincia_id: Identificador de la provincia.
        departamento_id: Identificador del departamento.
        hasta: Último período de estimaciones disponible.

    Returns:
        Diccionario con los parámetros requeridos por MAGyP.
    """
    return {
        "cultivo[]": CROP_IDS,
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
) -> pd.DataFrame:
    """Descarga los datos agrícolas de un departamento.

    Args:
        client: Cliente HTTP utilizado para realizar la solicitud.
        provincia_id: Identificador de la provincia.
        departamento_id: Identificador del departamento.
        hasta: Último período de estimaciones disponible.

    Returns:
        DataFrame con los datos agrícolas descargados.
    """
    data = build_download_payload(
        provincia_id=provincia_id,
        departamento_id=departamento_id,
        hasta=hasta,
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
) -> pd.DataFrame:
    """Descarga y etiqueta los datos de un departamento.

    Args:
        client: Cliente HTTP utilizado para realizar las solicitudes.
        provincia: Registro de la provincia.
        departamento: Registro del departamento.
        hasta: Último período disponible.

    Returns:
        DataFrame descargado con Provincia y Departamento agregados.
    """
    dataframe = descargar_datos(
        client=client,
        provincia_id=provincia["id"],
        departamento_id=departamento["id"],
        hasta=hasta,
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
) -> list[pd.DataFrame]:
    """Descarga los datos de todos los departamentos disponibles.

    Recorre cada provincia y sus departamentos asociados, realizando
    una consulta individual para cada uno.

    Args:
        client: Cliente HTTP utilizado para las solicitudes.
        provincias: Catálogo de provincias.
        departamentos: Catálogo de departamentos.
        hasta: Último período disponible.

    Returns:
        Lista de DataFrames, uno por cada departamento descargado.
    """
    dataframes: list[pd.DataFrame] = []

    for _, provincia in provincias.iterrows():
        provincia_id = provincia["id"]

        departamentos_provincia = get_departamentos_provincia(
            departamentos=departamentos,
            provincia_id=provincia_id,
        )

        for _, departamento in departamentos_provincia.iterrows():
            dataframe = descargar_datos_departamento(
                client=client,
                provincia=provincia,
                departamento=departamento,
                hasta=hasta,
            )

            dataframes.append(dataframe)

            time.sleep(REQUEST_RATE_DELAY)

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

def main() -> None:
    """Ejecuta el proceso completo de extracción y consolidación."""
    with httpx.Client(
        headers=HEADERS,
        timeout=HTTP_TIMEOUT,
        follow_redirects=FOLLOW_REDIRECTS,
    ) as client:

        hasta = get_hasta(client)

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
        )

    resultado = combine_dataframes(dataframes)

    save_data(
        dataframe=resultado,
        output_path=OUTPUT_PATH,
    )

    print("Datos de MAGyP descargados y guardados.")
    print(f"Shape: {resultado.shape}")
    print(f"Archivo: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()