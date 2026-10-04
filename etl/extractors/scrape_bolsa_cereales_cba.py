"""
Descarga, transforma y almacena datos agrícolas de la Bolsa de Cereales
de Córdoba.

El script descarga un archivo Excel desde SharePoint, extrae las hojas
correspondientes a superficie sembrada, rendimiento y producción, limpia
la estructura de la hoja de superficie sembrada y combina los datos
utilizando las columnas PROVINCIA, DEPARTAMENTO, CULTIVO y CAMPAÑA como
claves.

Finalmente, selecciona y ordena las columnas relevantes y guarda el
resultado en formato CSV.

La configuración del proceso, como la URL de origen, las hojas a leer,
las columnas clave, las columnas de salida, los timeouts y las rutas de
almacenamiento, se encuentra centralizada en constantes al inicio del
script.
"""

from io import BytesIO
from pathlib import Path
from typing import Final

import httpx
import pandas as pd

from etl.extractors.io_utils import (
    RAW_STEM_CBA,
    build_timestamped_filename,
)

# ====================== CONFIGURACIÓN ======================

SOURCE_URL: Final[str] = (
    "https://bccba.sharepoint.com/:x:/s/DWDIA/"
    "ETb905igM2BInC4LHdYVB4gBRI_aUtJaskzfkAJqzLpB-A?download=1"
)

OUTPUT_DIRECTORY: Final[Path] = Path("./data/raw")
OUTPUT_STEM: Final[str] = RAW_STEM_CBA

REQUEST_TIMEOUT: Final[float] = 30.0
FOLLOW_REDIRECTS: Final[bool] = True
CSV_ENCODING: Final[str] = "utf-8-sig"

SHEET_SURFACE: Final[str] = "Superficie Sembrada"
SHEET_YIELD: Final[str] = "Rendimiento"
SHEET_PRODUCTION: Final[str] = "Producción"

SHEETS: Final[list[str]] = [
    SHEET_SURFACE,
    SHEET_YIELD,
    SHEET_PRODUCTION,
]

# El encabezado de cada hoja se detecta buscando esta celda (las hojas
# traen un número variable de filas de título; en 2026 pasaron a ser 10
# en las tres hojas y el extractor con filas fijas dejó de funcionar).
HEADER_MARKER: Final[str] = "PROVINCIA"
HEADER_SEARCH_ROWS: Final[int] = 40

KEY_COLUMNS: Final[list[str]] = [
    "PROVINCIA",
    "DEPARTAMENTO",
    "CULTIVO",
    "CAMPAÑA",
]

OUTPUT_COLUMNS: Final[list[str]] = [
    "PROVINCIA",
    "DEPARTAMENTO",
    "CULTIVO",
    "CAMPAÑA",
    "SEMBRADAS",
    "COSECHADAS",
    "RENDIMIENTO",
    "RENDIMIENTO GRANO LIMPIO Y SECO",
    "PRODUCCIÓN",
    "PRODUCCIÓN GRANO LIMPIO Y SECO",
]

MERGE_TYPE: Final[str] = "outer"

OLE_MAGIC: Final[bytes] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Columnas cuya combinación con la clave identifica un registro real.
CORE_COLUMNS: Final[list[str]] = [
    "SEMBRADAS",
    "COSECHADAS",
    "RENDIMIENTO",
    "PRODUCCIÓN",
]


# ====================== DESCARGA ======================

def download_excel(url: str) -> bytes:
    """Descarga un archivo Excel desde una URL.

    Args:
        url: URL del archivo Excel.

    Returns:
        Contenido binario del archivo descargado.

    Raises:
        httpx.HTTPStatusError: Si el servidor devuelve un código HTTP
            indicando un error.
        httpx.RequestError: Si ocurre un error durante la solicitud.
    """
    response = httpx.get(
        url,
        follow_redirects=FOLLOW_REDIRECTS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    # SharePoint devuelve HTML (login/consentimiento) con HTTP 200 cuando
    # el enlace deja de ser público: se valida la firma ZIP de XLSX.
    # Se aceptan XLSX (ZIP, "PK") y XLS (OLE): el archivo publicado pasó
    # a ser BCCBA_ESTADISTICA_CULTIVOS.xls.
    if response.content[:2] != b"PK" and response.content[:8] != OLE_MAGIC:
        raise ValueError(
            "La descarga de CBA no es un archivo Excel (¿enlace de "
            "SharePoint vencido o que requiere login?)."
        )

    return response.content


# ====================== LECTURA ======================

def read_excel_sheets(
    excel_content: bytes,
    sheet_names: list[str],
) -> dict[str, pd.DataFrame]:
    """Lee determinadas hojas de un archivo Excel.

    Args:
        excel_content: Contenido binario del archivo Excel.
        sheet_names: Nombres de las hojas que deben ser leídas.

    Returns:
        Diccionario donde cada clave es el nombre de una hoja y cada
        valor es su correspondiente DataFrame.
    """
    return pd.read_excel(
        BytesIO(excel_content),
        sheet_name=sheet_names,
        header=None,
    )


# ====================== TRANSFORMACIÓN ======================

def find_header_row(
    dataframe: pd.DataFrame,
    marker: str = HEADER_MARKER,
    max_rows: int = HEADER_SEARCH_ROWS,
) -> int:
    """Índice de la primera fila que contiene la celda ``marker``.

    Raises:
        ValueError: Si el encabezado no aparece en las primeras filas.
    """
    head = dataframe.head(max_rows)
    for idx, row in head.iterrows():
        if any(str(v).strip().upper() == marker for v in row.tolist()):
            return int(head.index.get_loc(idx))
    raise ValueError(
        f"No se encontró la fila de encabezado ('{marker}') en la hoja de CBA"
    )


def clean_sheet(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Usa la fila de encabezado detectada y descarta las filas de título."""
    header_row = find_header_row(dataframe)
    return clean_surface_dataframe(dataframe, header_row, header_row + 1)


def clean_surface_dataframe(
    dataframe: pd.DataFrame,
    header_row: int,
    data_start_row: int,
) -> pd.DataFrame:
    """Limpia la estructura del DataFrame de superficie sembrada.

    Utiliza una fila específica del DataFrame como encabezado, elimina
    las filas anteriores y limpia los espacios de los nombres de
    columnas.

    La función no modifica el DataFrame recibido; devuelve una copia
    transformada.

    Args:
        dataframe: DataFrame original de superficie sembrada.
        header_row: Índice de la fila que contiene los nombres de
            columnas.
        data_start_row: Índice desde el cual comienza la información
            válida.

    Returns:
        DataFrame limpio.
    """
    cleaned = dataframe.copy()

    cleaned.columns = cleaned.iloc[header_row]
    cleaned = cleaned.iloc[data_start_row:].reset_index(drop=True)

    cleaned.columns = cleaned.columns.astype(str).str.strip()
    # Columnas vacías del rango usado de la hoja ("nan") y filas en blanco.
    cleaned = cleaned.loc[:, [c for c in cleaned.columns if c and c != "nan"]]
    cleaned = cleaned.dropna(how="all")

    return cleaned


def merge_agricultural_data(
    surface: pd.DataFrame,
    yield_data: pd.DataFrame,
    production: pd.DataFrame,
    keys: list[str],
) -> pd.DataFrame:
    """Combina los DataFrames agrícolas utilizando las columnas clave.

    Se realizan dos merges sucesivos utilizando un outer join para
    evitar perder registros que estén presentes solamente en alguno
    de los DataFrames.

    Las hojas de rendimiento y producción pueden traer varias filas por
    clave (variantes "grano limpio y seco"). Un merge outer muchos-a-
    muchos produce entonces un producto cartesiano que replica la
    superficie y la producción. Se eliminan duplicados exactos de cada
    hoja antes del merge y se deduplica el resultado sobre las columnas
    núcleo, conservando la primera variante de grano limpio y seco.

    Args:
        surface: Datos de superficie sembrada y cosechada.
        yield_data: Datos de rendimiento.
        production: Datos de producción.
        keys: Columnas utilizadas como claves de combinación.

    Returns:
        DataFrame resultante de combinar los tres conjuntos de datos.
    """
    merged = (
        surface.drop_duplicates()
        .merge(yield_data.drop_duplicates(), on=keys, how=MERGE_TYPE)
        .merge(production.drop_duplicates(), on=keys, how=MERGE_TYPE)
    )
    core = [c for c in CORE_COLUMNS if c in merged.columns]
    n_before = len(merged)
    merged = merged.drop_duplicates(subset=keys + core, keep="first")
    if len(merged) < n_before:
        print(
            f"[CBA] {n_before - len(merged)} filas replicadas por merge "
            "cartesiano eliminadas."
        )
    return merged.reset_index(drop=True)


def select_output_columns(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Selecciona y ordena las columnas finales del DataFrame.

    Args:
        dataframe: DataFrame transformado.
        columns: Lista de columnas que deben conservarse y su orden.

    Returns:
        DataFrame con las columnas seleccionadas y ordenadas.
    """
    return dataframe.loc[:, columns].copy()


def transform_dataframes(
    dataframes: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Transforma y combina los DataFrames obtenidos desde Excel.

    Args:
        dataframes: Diccionario con los DataFrames correspondientes a
            las hojas configuradas.

    Returns:
        DataFrame final listo para ser almacenado.
    """
    surface = clean_sheet(dataframes[SHEET_SURFACE])
    yield_data = clean_sheet(dataframes[SHEET_YIELD])
    production = clean_sheet(dataframes[SHEET_PRODUCTION])

    merged = merge_agricultural_data(
        surface=surface,
        yield_data=yield_data,
        production=production,
        keys=KEY_COLUMNS,
    )

    result = select_output_columns(
        dataframe=merged,
        columns=OUTPUT_COLUMNS,
    )
    # Las hojas se leen sin encabezado (header=None): los valores llegan
    # como object y se convierten a numérico.
    for col in OUTPUT_COLUMNS:
        if col not in KEY_COLUMNS:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result


# ====================== ALMACENAMIENTO ======================

def save_data(
    dataframe: pd.DataFrame,
    output_path: Path,
) -> None:
    """Guarda un DataFrame en formato CSV.

    Crea el directorio de destino si todavía no existe.

    Args:
        dataframe: DataFrame que se desea almacenar.
        output_path: Ruta del archivo CSV de salida.
    """
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        output_path,
        index=False,
        encoding=CSV_ENCODING,
    )


# ====================== EJECUCIÓN ======================

def run_extractor(output_dir: Path | str | None = None) -> Path:
    """
    Ejecuta el proceso completo de extracción y transformación CBA.

    Descarga el Excel, transforma las hojas y persiste un CSV con
    nombre ``YYYYMMDDHHMMSS_datos_bolsa_granos_cba.csv``.

    Args:
        output_dir: Directorio de salida. Si es None, usa
            ``OUTPUT_DIRECTORY``.

    Returns:
        Path absoluto del CSV persistido.
    """
    target_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIRECTORY
    output_path = target_dir / build_timestamped_filename(OUTPUT_STEM)

    excel_content = download_excel(SOURCE_URL)
    dataframes = read_excel_sheets(
        excel_content=excel_content,
        sheet_names=SHEETS,
    )
    final_dataframe = transform_dataframes(dataframes)
    save_data(dataframe=final_dataframe, output_path=output_path)

    print("DataFrame final creado y guardado.")
    print(f"Shape: {final_dataframe.shape}")
    print(f"Archivo: {output_path}")
    return output_path.resolve()


if __name__ == "__main__":
    run_extractor()