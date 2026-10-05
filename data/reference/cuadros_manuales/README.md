# Cuadros tarifarios cargados a mano

Algunas distribuidoras bloquean la descarga automática o publican sus
cuadros como imágenes escaneadas. Para esos casos se puede bajar el cuadro
oficial a mano y dejarlo en esta carpeta: el extractor de tarifas lo
procesa como cualquier otro.

## Pasos

1. Descargar el cuadro tarifario oficial de la distribuidora o del ente
   regulador (PDF con texto, XLSX, XLS o ZIP).
2. Crear una carpeta con el **código** de la distribuidora (ver la tabla
   abajo o `etl/reference/distribuidoras.py`) y guardar el archivo con el
   **año y mes** de vigencia en el nombre (`AAAA_MM`):

   ```
   cuadros_manuales/EDET/cuadro_tarifario_2026_09.pdf
   ```

3. Correr el extractor de tarifas o el ETL completo:

   ```bash
   python -m etl.extractors.scrape_tarifas --solo EDET
   ```

4. Verificar en el dashboard (**Dinero → Tarifas por distribuidora**) que
   la distribuidora aparezca como extraída con `fuente_tipo = manual`.

## Distribuidoras que hoy lo necesitan

| Código | Provincia | Motivo |
|---|---|---|
| `SPSE` | Santa Cruz | El portal nacional enlaza archivos inexistentes; el sitio propio no responde |
| `DPE` | Tierra del Fuego | Sólo resoluciones escaneadas |
| `EDET` | Tucumán | Cuadros escaneados |

## Notas

- Un PDF **escaneado** (sin texto seleccionable) no se puede leer: hace
  falta una versión con texto o una planilla.
- Si hay varios archivos, se usa el de vigencia más reciente.
- Cada cuadro procesado queda en `data/reference/tarifas_historial.csv`.

Más detalle: [`docs/03_datos/tarifas_electricas.md`](../../../docs/03_datos/tarifas_electricas.md).
