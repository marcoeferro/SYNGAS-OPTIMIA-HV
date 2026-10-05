# Tarifas eléctricas

> Cómo obtiene el sistema el precio de la electricidad de cada provincia,
> qué tarifa toma, qué distribuidoras faltan y cómo completarlas a mano.

## Qué tarifa se busca

Para valorizar la energía se necesitan dos precios por distribuidora:

- **Tarifa de compra**: lo que paga un usuario por kWh. Se toma la
  categoría de **medianas o grandes demandas** (un establecimiento con un
  equipo de 25 kW), en **baja tensión**, preferentemente para menos de
  300 kW, **banda horaria "Resto"**, **sin impuestos**, del **cuadro pleno**
  (sin subsidios ni regímenes especiales).
- **Tarifa de inyección**: lo que se paga por kWh entregado a la red (Ley
  27.424). Pocas distribuidoras la publican; si falta, se estima (ver
  [metodología](../02_metodologia/metodologia.md#4-dinero-balance-neto-ley-27424)).

## Cómo se obtiene

Programa: `etl/extractors/scrape_tarifas.py`, con el parser
`etl/extractors/tariff_parser.py` y el registro de distribuidoras
`etl/reference/distribuidoras.py`.

```mermaid
flowchart TD
    R["Registro de 28 distribuidoras<br/>(dónde publica cada una)"] --> N["1. Portal nacional<br/>(Secretaría de Energía)"]
    R --> P["2. Fuente propia<br/>(distribuidora o ente regulador)"]
    R --> M["3. Carpeta manual<br/>cuadros_manuales/"]
    N --> D["Descarga PDF / Excel / ZIP"]
    P --> D
    M --> D
    D --> T["Lectura del documento<br/>y elección de la fila"]
    T --> V["Vigencia (mes)<br/>y validación"]
    V --> J["JSON de tarifas vigentes<br/>data/reference/AAAAMMDDhhmmss_tarifas.json"]
    V --> H["Historial<br/>data/reference/tarifas_historial.csv"]
```

1. **Dónde buscar.** Para cada distribuidora se prueba el portal nacional
   (`argentina.gob.ar/.../cuadros-tarifarios-<distribuidora>`, con archivos
   en `energia.gob.ar`), la fuente propia (sitio de la distribuidora, OCEBA
   para Buenos Aires, API de EPE, Boletín Oficial de Misiones, etc.) y la
   carpeta de carga manual.
2. **Leer el documento.** Se convierte el PDF o la planilla a texto y se
   puntúa cada fila con precio en $/kWh según su contexto: categoría,
   tensión, banda horaria. Se descartan las filas residenciales, sociales,
   subsidiadas, de media y alta tensión, peaje, alumbrado, ≥ 300 kW y las
   tarifas mayoristas a cooperativas. Cuando un cuadro no permite reconocer
   la categoría por contexto, el registro indica la fila exacta
   (`fila_tarifa`): EPE, APE y EMSA.
3. **Vigencia.** Se toma la fecha declarada en el documento ("vigente a
   partir del 1° de mayo de 2026"); si no hay, la del nombre del archivo.
4. **Elegir el cuadro.** Entre los documentos del mes más reciente se elige
   el cuadro pleno (mejor categoría y mayor tarifa); entre fuentes, la
   vigencia más reciente.
5. **Validar.** Se rechazan valores fuera de rango (30 a 2.000 $/kWh) y una
   inyección mayor que la compra.
6. **Guardar.** El JSON de tarifas vigentes registra, para cada
   distribuidora, el valor, la vigencia, el documento de origen y el
   **estado**. Cada documento procesado se agrega al historial.

### Estados de una tarifa

| Estado | Significado |
|---|---|
| `extraido` | Leído del cuadro vigente en esta corrida |
| `fallback_previous` | No se pudo leer hoy; se conserva el último valor extraído |
| `sin_dato` | Nunca se pudo extraer; esa provincia no suma dinero |

El dashboard muestra el estado de cada distribuidora en *Dinero* y en
*Auditoría de datos → Tarifas*.

## Situación actual (octubre de 2026)

**22 de 28** distribuidoras con tarifa extraída, 1 con el valor anterior y 5
sin dato. Sin tarifa queda alrededor del 27 % de la energía calculada,
casi toda de Córdoba.

| Distribuidora | Provincia / zona | Compra ($/kWh) | Vigencia | Fuente |
|---|---|---:|---|---|
| EDENOR | CABA norte y GBA norte/oeste | 108,37 | 2026-06 | Portal nacional |
| EDESUR | CABA sur y GBA sur | 107,91 | 2026-05 | Portal nacional |
| EDEN | Buenos Aires (norte y centro) | 135,23 | 2026-09 | OCEBA |
| EDEA | Buenos Aires (costa atlántica) | 136,44 | 2026-09 | OCEBA |
| EDES | Buenos Aires (sur) | 137,18 | 2026-09 | OCEBA |
| EDELAP | Gran La Plata | 148,72 | 2026-09 | OCEBA |
| ECSAPEM | Catamarca | 106,29 | 2026-05 | Portal nacional |
| SECHEEP | Chaco | 117,50 | 2026-06 | Portal nacional |
| DPEC | Corrientes | 109,20 | 2026-04 | Portal nacional |
| ENERSA | Entre Ríos | 130,84 | 2026-05 | Portal nacional |
| REFSA | Formosa | 135,28 | 2026-06 | Sitio propio |
| EJESA | Jujuy | 113,09 | 2025-10 | Valor anterior (página nacional caída) |
| APE | La Pampa | 169,40 | 2025-12 | Portal nacional |
| EDELAR | La Rioja | 104,67 | 2026-03 | Portal nacional |
| EDEMSA | Mendoza | 106,51 | 2026-05 | Portal nacional |
| EDESTE | Mendoza (zona este) | 106,51 | 2026-05 | Portal nacional |
| EMSA | Misiones | 283,84 | 2026-09 | Boletín Oficial de Misiones |
| EPEN | Neuquén | 359,73 | 2026-08 | Sitio propio |
| EDERSA | Río Negro | 155,26 | 2026-09 | Sitio propio |
| EDESA | Salta | 266,81 | 2026-06 | Portal nacional |
| EDESAL | San Luis | 110,76 | 2026-06 | Portal nacional |
| EPE | Santa Fe | 146,77 | 2026-09 | API del sitio de EPE |
| EDESE | Santiago del Estero | 156,66 | 2026-09 | Sitio propio |

Los valores vigentes en cada momento están en el último
`data/reference/*_tarifas.json` y en el dashboard.

### Distribuidoras sin dato

| Distribuidora | Provincia | Motivo | Cómo completarla |
|---|---|---|---|
| EPEC | Córdoba | El sitio responde 403 fuera de Argentina y el portal nacional no publica archivos de EPEC. El ente regulador (`ersep.cba.gov.ar`) está fuera de la lista de dominios permitidos. | Carga manual, o habilitar `ersep.cba.gov.ar` y correr desde Argentina |
| ESJ | San Juan | El portal nacional enlaza archivos que no existen (404). | Carga manual, o habilitar `energiasanjuan.com.ar` |
| SPSE | Santa Cruz | Igual que ESJ; el sitio propio no responde. | Carga manual, o habilitar `spse.gob.ar` |
| DPE | Tierra del Fuego | Sólo publica resoluciones escaneadas (sin texto). | Carga manual |
| EDET | Tucumán | Sus cuadros son PDF escaneados (imágenes, sin texto). | Carga manual |

Chubut no tiene distribuidora provincial única (el servicio lo prestan
cooperativas), por lo que no tiene tarifa asignada.

## Carga manual de cuadros

Para una distribuidora que bloquea la descarga automática:

1. Descargar el cuadro tarifario oficial (PDF, XLSX, XLS o ZIP).
2. Guardarlo en `data/reference/cuadros_manuales/<CÓDIGO>/`, con el código
   del registro (p.ej. `EPEC`), y con año y mes en el nombre:
   `cuadros_manuales/EPEC/cuadro_tarifario_2026_09.pdf`.
3. Correr el extractor (o el ETL completo). El cuadro se procesa como
   cualquier otro, con `fuente_tipo = "manual"`, y queda en el historial.

Un PDF escaneado (sin texto seleccionable) no se puede leer; hace falta una
versión con texto o una planilla.

## Comandos

```bash
python -m etl.extractors.scrape_tarifas                          # tarifas vigentes
python -m etl.extractors.scrape_tarifas --solo EPE EDESAL        # sólo algunas
python -m etl.extractors.scrape_tarifas --historial --desde 2025-01   # reconstruir el historial
```

El ETL completo (`python -m etl.pipelines.run_etl`) ya corre el extractor de
tarifas; `--skip-tarifas` lo saltea y usa el último JSON.

## Agregar o corregir una distribuidora

Todo está en `etl/reference/distribuidoras.py`:

- `slug`: nombre de la página en el portal nacional.
- `indices`: páginas propias donde se buscan enlaces a cuadros.
- `urls` / `url_templates`: archivos directos (con `{ym}` para el mes).
- `fila_tarifa`: fila exacta cuando el parser no puede deducirla.
- `provincia_a_distribuidora` / `departamento_a_distribuidora`: qué
  distribuidora corresponde a cada lugar.

Después de un cambio conviene agregar un test con un fragmento del
documento real en `tests/test_tariff_parser.py`.

## Problemas conocidos

- **ENERSA, noviembre y diciembre de 2025 (historial)**: la planilla pone
  dos tablas lado a lado y se tomó la fila de media tensión (≈ 67 $/kWh) en
  vez de la de baja (≈ 79 $/kWh). El valor vigente (2026-05) es correcto.
- **EDEMSA, abril de 2026 (historial)**: el cuadro del sitio propio se leyó
  como 154,57 $/kWh, un cargo residencial ("excedente a 1600 kWh bim"). El
  valor vigente (2026-05, portal nacional) es correcto.
- **Inyección en EDERSA y ECSAPEM**: el valor detectado corresponde a otra
  categoría y supera la tarifa de compra; la validación lo descarta y se
  usa la estimación.
- **Dominios**: el extractor necesita salida a Internet hacia los sitios de
  la lista [dominios necesarios](../04_arquitectura/despliegue.md#dominios-necesarios).
