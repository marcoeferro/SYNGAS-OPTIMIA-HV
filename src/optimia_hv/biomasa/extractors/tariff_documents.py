"""
Conversión de documentos tarifarios (PDF, XLSX, ZIP) a texto plano.

Los cuadros tarifarios se publican en formatos heterogéneos: PDF (la
mayoría de las distribuidoras), planillas Excel y ZIP con varios
archivos (portal de la Secretaría de Energía). Este módulo los lleva a
un texto línea por línea que consume el parser de ``scrape_tarifas``.

Para planillas, cada fila se convierte en una línea con sus celdas
separadas por `` | ``. Si una celda de encabezado contiene una unidad
(``$/kWh``, ``$/mes``) y los importes están en las filas de abajo, la
unidad se agrega a cada valor numérico de esa columna: así el parser
basado en líneas reconoce los importes igual que en un PDF.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Final

PDF_MAGIC: Final[bytes] = b"%PDF"
ZIP_MAGIC: Final[bytes] = b"PK"
OLE_MAGIC: Final[bytes] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # xls
UNIT_HEADER_PATTERN: Final[str] = r"\$\s*/\s*(?:kWh|mes)"
MAX_ROWS_BELOW_HEADER: Final[int] = 60


def detect_format(content: bytes, name: str = "") -> str | None:
    """
    Detecta el formato por firma binaria (y extensión como desempate).

    Returns:
        ``"pdf"``, ``"xlsx"``, ``"xls"``, ``"zip"`` o None si no es un
        documento soportado (p.ej. HTML de error con HTTP 200).
    """
    # ZIP/XLSX primero: un ZIP sin compresión puede contener "%PDF" en
    # sus primeros bytes (el PDF interno).
    if content[:2] == ZIP_MAGIC:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            return None
        if any(n.startswith("xl/") for n in names):
            return "xlsx"
        return "zip"
    if content[:8] == OLE_MAGIC:
        return "xls"
    if PDF_MAGIC in content[:1024]:
        return "pdf"
    return None


def pdf_to_text(content: bytes, layout: bool = False) -> str:
    """
    Texto de todas las páginas de un PDF (``pypdf``).

    Con ``layout`` se respeta la posición del texto en la página: cada
    fila de una tabla queda en una línea con sus importes (EDESA publica
    un cuadro apaisado de varias tablas lado a lado, que el modo normal
    desordena).
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    mode = "layout" if layout else "plain"
    return "\n".join((page.extract_text(extraction_mode=mode) or "") for page in reader.pages)


def _cell_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        # Se emite con coma decimal (formato argentino) para el parser.
        return f"{value:.6f}".rstrip("0").rstrip(".").replace(".", ",")
    if isinstance(value, int):
        return str(value)
    return str(value).strip()


def rows_to_text(rows: list[list[object]]) -> str:
    """
    Convierte filas de una planilla en líneas de texto.

    Si una celda de encabezado contiene una unidad (``$/kWh``, ``$/mes``)
    y los importes están en las filas siguientes, a cada importe de esa
    columna se le agrega la unidad y, entre corchetes, el texto del
    encabezado (p.ej. ``266,8 $/KWh [Cargo Variable Horas Resto $/KWh]``):
    así el parser sabe a qué banda/cargo corresponde cada columna.
    """
    headers_by_col: dict[int, tuple[str, str, int]] = {}
    lines: list[str] = []
    for r, row in enumerate(rows):
        cells = [_cell_str(v) for v in row]
        out: list[str] = []
        for c, text in enumerate(cells):
            m = re.search(UNIT_HEADER_PATTERN, text, flags=re.IGNORECASE)
            is_number = bool(re.fullmatch(r"-?[\d.]+(?:,\d+)?", text))
            if m and not is_number and not re.search(r"\d+,\d+", text):
                headers_by_col[c] = (m.group(0), text, r)
            if is_number and c in headers_by_col:
                unit, header, header_row = headers_by_col[c]
                if r - header_row <= MAX_ROWS_BELOW_HEADER and not any(
                    re.search(UNIT_HEADER_PATTERN, x, flags=re.IGNORECASE) for x in cells
                ):
                    text = f"{text} {unit} [{header}]"
            out.append(text)
        line = " | ".join(t for t in out if t)
        if line:
            lines.append(line)
    return "\n".join(lines)


def xlsx_to_text(content: bytes) -> str:
    """Texto de todas las hojas de un XLSX (``openpyxl``)."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    parts: list[str] = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        parts.append(f"# HOJA {ws.title}\n{rows_to_text(rows)}")
    return "\n".join(parts)


def xls_to_text(content: bytes) -> str:
    """Texto de un XLS antiguo vía pandas (requiere ``xlrd``)."""
    import pandas as pd

    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    return "\n".join(
        f"# HOJA {name}\n{rows_to_text(df.values.tolist())}"
        for name, df in sheets.items()
    )


def zip_members(content: bytes) -> list[tuple[str, bytes]]:
    """Miembros PDF/XLSX/XLS de un ZIP (no recursivo en ZIP anidados)."""
    members: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            data = zf.read(info)
            if detect_format(data, info.filename) in {"pdf", "xlsx", "xls"}:
                members.append((info.filename, data))
    return members


def document_to_texts(
    content: bytes, name: str = "", layout: bool = False,
) -> list[tuple[str, str]]:
    """
    Convierte un documento en una lista de (nombre, texto).

    Un ZIP produce un elemento por archivo soportado; el resto, uno solo.
    ``layout`` se aplica a los PDF (ver ``pdf_to_text``).

    Raises:
        ValueError: Si el formato no es soportado.
    """
    fmt = detect_format(content, name)
    if fmt == "pdf":
        return [(name, pdf_to_text(content, layout))]
    if fmt == "xlsx":
        return [(name, xlsx_to_text(content))]
    if fmt == "xls":
        return [(name, xls_to_text(content))]
    if fmt == "zip":
        out: list[tuple[str, str]] = []
        for member, data in zip_members(content):
            out.extend(document_to_texts(data, f"{name}!{member}", layout))
        return out
    raise ValueError(f"Formato no soportado (¿HTML de error?): {name}")
