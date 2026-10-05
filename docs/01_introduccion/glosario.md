# Glosario

Términos agronómicos, energéticos y técnicos usados en el proyecto, en
orden alfabético.

| Término | Significado |
|---|---|
| **Alerta de calidad** | Aviso que genera el ETL cuando un dato cambió de forma sospechosa respecto de la corrida anterior (p.ej. una tarifa que se duplica). No detiene el proceso salvo en modo `--estricto`. Ver [tests y controles](../06_calidad/tests_y_controles.md). |
| **Autoconsumo** | Electricidad generada que se consume en el mismo establecimiento. Se valoriza con la tarifa de compra (lo que se deja de pagar). Se supone el 60 % de lo generado. |
| **Banda horaria "Resto"** | Las tarifas de medianas y grandes demandas cobran distinto según la hora: *pico*, *resto* y *valle*. "Resto" es la franja diurna principal; es la que usa el sistema como tarifa representativa. |
| **Beneficio bruto** | Ahorro por autoconsumo + ingreso por inyección. No descuenta inversión, operación ni recolección y transporte del rastrojo. |
| **Biomasa residual / rastrojo** | Restos de la planta que quedan después de cosechar el grano (tallos, hojas, chalas). |
| **Bolsa de Cereales de Córdoba (BCCBA, CBA)** | Entidad que publica estadísticas de cultivos por departamento. Segunda fuente agrícola del proyecto. |
| **Campaña** | Ciclo agrícola, escrito como `2023/24` (siembra en 2023, cosecha en 2024). |
| **Campaña de referencia** | Las últimas 5 campañas completas. Los resultados anuales son su promedio. La campaña en curso se excluye porque sus datos están incompletos. |
| **CI (integración continua)** | Ejecución automática de los tests en GitHub cada vez que se propone un cambio. |
| **Consumo específico** | Kilogramos de biomasa que consume el gasificador para generar 1 kWh. Para el PP30, 1,0 kg de materia seca por kWh según la ficha del fabricante. |
| **Cuadro tarifario** | Documento oficial con los precios de la electricidad de una distribuidora, por categoría de usuario y vigencia mensual. |
| **Dashboard** | Tablero web con mapas y gráficos de los resultados. Ver [guía del dashboard](../05_uso/dashboard.md). |
| **Departamento / partido** | División administrativa de una provincia (en Buenos Aires se llaman partidos). Es la unidad geográfica más chica del análisis. |
| **Distribuidora** | Empresa que vende electricidad a los usuarios de una zona (p.ej. EPE en Santa Fe, EDEN en el norte de Buenos Aires). |
| **Docker** | Herramienta que empaqueta el programa con todo lo que necesita para correr igual en cualquier servidor. |
| **ETL** | *Extract, Transform, Load*: el proceso que descarga los datos (extraer), los limpia y calcula (transformar) y guarda los resultados (cargar). |
| **Fracción recuperable** | Parte del rastrojo que puede retirarse del lote sin dañar el suelo. Se supone 50 %. |
| **FR (factor de residuo)** | Toneladas de rastrojo seco por tonelada de grano seco. Se calcula a partir del índice de cosecha: FR = (1 − IC) / IC. |
| **GADM** | Base de datos de límites administrativos del mundo. El dashboard usa sus polígonos de provincias y departamentos (versión 4.1). |
| **Gasificador** | Equipo que calienta biomasa con poco oxígeno y la convierte en un gas combustible (*syngas*) para mover un motor generador. |
| **Historial de tarifas** | Registro de todos los cuadros tarifarios procesados desde enero de 2025 (`data/reference/tarifas_historial.csv`). |
| **IC (índice de cosecha)** | Fracción del peso seco de la planta que es grano. Un IC de 0,47 (maíz) significa que el 47 % es grano y el 53 % es rastrojo. |
| **Inyección** | Electricidad que se entrega a la red pública. Se paga a la tarifa de inyección (Ley 27.424); si la distribuidora no la publica, se estima. |
| **kWh / MWh / GWh / TWh** | Unidades de energía. 1 TWh = 1.000 GWh = 1.000.000 MWh = 1.000.000.000 kWh. Un hogar promedio consume unos 3.000 kWh por año. |
| **Ley 27.424** | Ley de generación distribuida: permite a los usuarios generar su propia electricidad renovable e inyectar el excedente a la red. |
| **MAGyP** | Ministerio de Agricultura, Ganadería y Pesca de la Nación. Publica las Estimaciones Agrícolas por departamento. Principal fuente agrícola. |
| **Materia seca (MS)** | Peso de un material sin su agua. La producción de grano se informa con humedad comercial; MS es la fracción seca (p.ej. 0,855 en maíz). |
| **OCEBA** | Organismo de Control de Energía Eléctrica de la Provincia de Buenos Aires. Publica los cuadros tarifarios de EDEN, EDEA, EDES y EDELAP. |
| **Parquet** | Formato de archivo para tablas de datos, compacto y rápido de leer. Los resultados del ETL se guardan así. |
| **PP30 (Power Pallet 30)** | Gasificador de biomasa de All Power Labs: 22 kW eléctricos conectado a una red de 50 Hz como la argentina (25 kW a 60 Hz). Acepta chips de madera, cáscaras y marlo; el rastrojo debe triturarse o pelletizarse. Es el equipo de referencia del proyecto. |
| **Reconciliación** | Paso que resuelve los casos en que dos fuentes informan el mismo lugar, cultivo y campaña: se conserva el de mayor producción. |
| **Residuo recuperable** | Rastrojo que se puede retirar del lote: biomasa residual × fracción recuperable. Es lo que se usa para calcular la energía. |
| **Scraper / extractor** | Programa que descarga y lee automáticamente información de un sitio web o documento. |
| **Syngas** | Gas de síntesis producido por el gasificador (mezcla de monóxido de carbono, hidrógeno y otros gases). Da nombre al proyecto. |
| **Tarifa de compra** | Precio que paga un usuario por cada kWh. El sistema usa la categoría de medianas o grandes demandas en baja tensión, banda "Resto", sin impuestos. |
| **Tarifa de inyección** | Precio que se paga al usuario-generador por cada kWh que entrega a la red. |
| **Vigencia** | Mes desde el que rige un cuadro tarifario (formato `AAAA-MM`). |
