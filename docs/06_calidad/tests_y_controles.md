# Tests y controles de calidad

> Cómo se verifica que el sistema funciona bien. Hay dos tipos de
> verificación con objetivos distintos: **tests** (¿el código hace lo que
> debe?) y **controles de datos** (¿los datos de hoy tienen sentido?).

| | Tests | Controles de datos |
|---|---|---|
| Qué verifican | Que el **código** calcula y lee bien | Que los **datos** de cada corrida son razonables |
| Con qué datos | Casos fijos, escritos a mano o tomados de documentos reales | Los datos recién descargados |
| Cuándo corren | En GitHub (CI) en cada cambio, y a mano | En cada ejecución del ETL |
| Dónde están | `tests/` | `etl/transformers/validation.py`, `etl/transformers/data_checks.py` |
| Si fallan | No se debería aceptar el cambio de código | El ETL se detiene o deja una alerta |

Los tests **no** corren dentro del ETL: verifican el código una vez, cuando
cambia; correrlos cada día con el mismo código daría siempre el mismo
resultado. Lo que sí cambia cada día son los datos, y eso lo cubren los
controles. Ver la decisión [POL-QA-001](../02_metodologia/decisiones.md#pol-qa-001--tests-y-controles-de-calidad-de-datos).

## Tests

Unos 120 tests, todos rápidos (menos de 5 segundos), sin acceso a Internet.

| Archivo | Qué prueba |
|---|---|
| `test_string_utils.py` | Normalización de textos (tildes, mayúsculas, espacios) |
| `test_geography.py` | Nombres de provincias y departamentos, alias entre fuentes |
| `test_crop_consolidation.py` | Total vs. componentes de un cultivo (POL-CROP-001) |
| `test_reconciliation.py` | Mayor producción entre fuentes (POL-SOURCE-001) |
| `test_validation.py` | Que los controles de invariantes detecten errores |
| `test_biomass.py` | Fórmula de biomasa y marcas de validez |
| `test_energy_tarifas.py` | Energía PP30, dinero, asignación de tarifas, inyección estimada, período de referencia |
| `test_tariff_parser.py` | Lectura de cuadros tarifarios con fragmentos de documentos reales de cada distribuidora |
| `test_etl_fixes.py` | Casos de errores corregidos (para que no vuelvan) y reintentos de descarga |
| `test_data_checks.py` | Controles de datos y modo estricto |
| `test_dashboard.py` | Carga de datos del dashboard y estructura de las páginas |

`tests/conftest.py` tiene datos de ejemplo compartidos (*fixtures*) que
pytest pasa automáticamente a los tests que los piden por nombre.

### Correrlos

```bash
pytest                                  # todos (o: make test)
pytest tests/test_tariff_parser.py -v   # un archivo
pytest -k enersa                        # los que contienen "enersa"
make test-cov                           # con cobertura de código
```

### Integración continua (CI)

`.github/workflows/ci.yml` corre en GitHub en cada pull request y en cada
push a `main`:

1. **tests**: instala el proyecto, busca errores reales de código
   (`ruff check --select E9,F`: sintaxis, nombres no definidos, imports sin
   uso) y corre `pytest`.
2. **imagen**: sólo si cambian `Dockerfile`, `pyproject.toml` o
   `.dockerignore`, construye la imagen Docker y verifica que el ETL y el
   dashboard importen dentro de ella.

El resultado aparece en cada pull request (✔ o ✖). El repositorio es
privado y GitHub Actions da 2.000 minutos gratis por mes; cada corrida
usa unos 2 minutos (más si se construye la imagen), y una corrida nueva
en la misma rama cancela la anterior.

### Cuándo agregar un test

- Al corregir un error: un test que lo reproduzca, para que no vuelva.
- Al agregar o cambiar una distribuidora: un fragmento real de su cuadro
  en `test_tariff_parser.py`.
- Al cambiar una fórmula: un caso con el resultado calculado a mano.

## Controles de datos

### 1. Invariantes (cortan el ETL)

Condiciones que **siempre** deben cumplirse. Si alguna falla, el ETL se
detiene con `Invariante rota: …` y no publica nada.

| Control | Qué verifica |
|---|---|
| `validar_reconciliacion` | Cada lugar/cultivo/campaña aparece una sola vez; fuentes válidas; sin superficies ni producciones negativas; no se perdió ningún registro; quedó el de mayor producción |
| `validar_biomasa` | Biomasa finita y no negativa; superficie > 0 en los registros válidos |
| Taxonomía de cultivos | Todo cultivo de las fuentes es conocido (si no, `Cultivos sin mapeo en CROP_TAXONOMY`) |

### 2. Alertas (avisan; con `--estricto` cortan)

Comparan la corrida actual con la anterior para detectar cambios
sospechosos (`etl/transformers/data_checks.py`):

| Control | Se dispara si… | Ejemplo de causa |
|---|---|---|
| `salto_tarifa` | La tarifa de compra de una distribuidora cambia más de **50 %** respecto de su cuadro anterior en el historial | El lector tomó otra categoría del cuadro |
| `cambio_total` | La energía o el dinero totales por año cambian más de **20 %** respecto de la corrida anterior | Una fuente vino incompleta |
| `cambio_provincia` | La energía de una provincia cambia más de **50 %** (sólo provincias con ≥ 1 % del total) | Falta un departamento o cambió un nombre |

Las alertas se escriben en el log (nivel WARNING), en
`data/audit/alertas_calidad.parquet`, en el dashboard (**Auditoría de
datos → Alertas de calidad**) y, si hay un canal configurado, se avisan por
mensaje (ver [avisos](../04_arquitectura/despliegue.md#avisos)). La primera corrida no tiene con qué
comparar y no genera alertas de cambio.

Por defecto el ETL **publica igual** y deja la alerta. Con `--estricto`,
si hay alguna alerta, termina con error **sin reemplazar** los datos
publicados:

```bash
python -m etl.pipelines.run_etl --estricto
```

Los umbrales están al principio de `data_checks.py`
(`UMBRAL_SALTO_TARIFA`, `UMBRAL_TOTAL`, `UMBRAL_PROVINCIA`).

### Qué hacer ante una alerta

1. Mirar el detalle (valor anterior, actual y variación) en el dashboard o
   el log.
2. **Salto de tarifa**: abrir el documento de origen (columna `documento`
   del JSON de tarifas o tabla de tarifas del dashboard) y comparar con el
   valor leído. Si es una suba real (ocurre con la inflación), no hay nada
   que hacer. Si se leyó mal, corregir la fila en
   `etl/reference/distribuidoras.py` (`fila_tarifa`) o el parser, con un
   test.
3. **Cambio de totales o de provincia**: en **Auditoría de datos →
   Campañas** ver si una campaña tiene menos registros que lo habitual, y
   en el log si alguna fuente falló y se usó una descarga anterior.
4. Si los datos estaban mal y se usó `--estricto`, los publicados siguen
   siendo los anteriores; corregir y volver a correr.

### 3. Trazabilidad

No son controles automáticos, pero permiten revisar a mano:

- Registros descartados al combinar fuentes y diferencias entre fuentes
  (`data/audit/`, dashboard → Auditoría).
- Impacto de los cultivos excluidos (log, `Impacto de exclusión`).
- Para cada tarifa: documento, vigencia, SHA-256 y estado.
