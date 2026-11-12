## DICTAMEN DEL DR. HORACIO LEDESMA

Leí el escrito entero, miré las 25 diapositivas y abrí el repositorio y los datos. Hay buena ingeniería de datos y un esfuerzo honesto de trazabilidad. Eso no alcanza para un Trabajo Final con pretensión de «estimación del potencial». Los números del Capítulo 10 coinciden con el parquet (80,12 TWh, 160,2 Mt, 519.655 equipos, 11,23 billones, 332 departamentos), y se lo reconozco. El problema es el resto.

- **Cifra principal inflada.** La cifra de cabecera se construye sobre una fracción retirable del 50 %. La propia documentación del alumno dice que ese valor es «optimista» y que «30–40 % es más prudente».
- **Sin validación externa.** No hay una sola comparación con otra estimación independiente.
- **Afirmaciones falsas sobre los datos.** Dice que Santa Cruz, Tierra del Fuego y Chubut «tienen energía estimada» y no tienen tarifa, y los datos muestran que no tienen energía alguna. Dice que el error de la inyección estimada está «acotado entre −12 % y +4 %», y con los cuadros que el propio repositorio guarda el error llega a −33 %.
- **Infraestructura contradicha por el repositorio.** El capítulo de infraestructura habla de «mínima exposición» y «usuario sin privilegios», pero el `docker-compose.yml` corre como root, monta el socket de Docker y publica el puerto 8501.
- **Lo que declara como operación real no se puede comprobar.** Caddy, ufw, Tailscale, certificados SSH y el VPS no están en el repositorio.
- **Estado del arte flojo.** Es un marco teórico de manual con un tratado de SSH, y la comparación con alternativas tecnológicas es casi inexistente.
- **Presentación.** Los diagramas se proyectan ilegibles.

**VEREDICTO: DESAPROBADO** en la presente versión. Tres observaciones son bloqueantes (O1, O2, O3). Si el alumno las corrige y atiende las MAYORES, se puede reconsiderar como «Aprobado con correcciones».

Aclaración sobre mi método. No ejecuté `pytest`, no usé git y no accedí al VPS. Lo que no pude comprobar está marcado como NO VERIFICABLE.

---

### O1 · BLOQUEANTE · Rigor del modelo de dominio / Honestidad y limitaciones
- Ubicación: §6.5; Resumen; Anexo A (POL-RECOVERY-001); diapositivas 9, 20 y 22.
- Cita: «f = 0,5 … valor que la literatura sitúa en el extremo superior de lo sostenible (Wilhelm et al., 2007; Blanco-Canqui y Lal, 2009)».
- Problema: el titular del trabajo (80,1 TWh, 58 % de la demanda nacional, 11,2 billones) se apoya en el 50 %, que es el borde superior del rango que el propio §1.1 cita (30–50 %).
  - El §1.1 dice «típicamente entre 30 % y 50 %». El escrito presenta el 50 % como «cota superior sostenible», pero el resultado central se publica con esa cota y no con un valor central.
  - El tablero permite llegar a 70 %, fuera de todo rango bibliográfico citado.
  - Wilhelm et al. (2007) se invoca en apoyo del 50 %, cuando su título dice que el carbono orgánico del suelo restringe todavía más la oferta («further constrains biomass supply»).
- Evidencia: `docs/02_metodologia/decisiones.md`, POL-RECOVERY-001, dice «Agronomy Journal 2021: no más de 25–40 % en maíz con rendimientos altos. Es optimista; 30–40 % es más prudente». Esa admisión no aparece en la tesis. Con 30–40 % el beneficio es 6,7–9,0 billones y la energía 48–64 TWh (Figura 23).
- Corrección exigida: presentar como resultado principal un escenario central de 30–40 % con rango, o justificar con fuente primaria y por cultivo por qué 50 % es central. Quitar a Wilhelm 2007 como respaldo del 50 %, reformular «58 % de la demanda» como techo teórico y no como equivalencia, y citar en el escrito la fuente de 2021 que hoy figura solo en la documentación interna.

### O2 · BLOQUEANTE · Rigor del modelo de dominio / Metodología
- Ubicación: Cap. 6, Cap. 10, §10.6, Figura 23; diapositiva 22.
- Cita: «Se analizó la sensibilidad del beneficio a cada supuesto variándolo de a uno por vez (Saltelli et al., 2008)».
- Problema: el modelo no tiene ninguna validación externa ni análisis de incertidumbre serio.
  - No hay comparación contra otra estimación independiente de rastrojo o energía en Argentina. WISDOM (FAO, 2009/2020), PROBIOMASA o las estimaciones de INTA/Secretaría de Energía se mencionan en el estado del arte pero nunca se contrastan con los resultados.
  - La sensibilidad es de un factor a la vez. Solo la fracción retirada tiene figura y datos propios. Los otros tres supuestos («Informe de avance 2 cuantificó los demás») se citan de un informe interno no publicado, sobre otro período.
  - No se varía el índice de cosecha (IC), el supuesto agronómico más delicado. FR = (1−IC)/IC es no lineal: en maíz, IC 0,47 → 0,42 sube FR de 1,13 a 1,38 (+22 %).
  - Tampoco se varían la humedad del grano, la disponibilidad (0,8) ni las tarifas.
  - Citar a Saltelli (análisis global) para un barrido de un factor a la vez en un modelo lineal es pomposo. La Figura 23 es un gráfico de barras sobre una recta, que no informa nada.
  - Los coeficientes son constantes nacionales por cultivo; el algodón usa un IC de «Xinjiang» (ver O22).
- Evidencia: `data/reference/ic_fr.csv`, columna «Fuente bibliográfica», dice «Estudios regionales (Xinjiang)». No hay tabla ni análisis con IC variable en ningún capítulo.
- Corrección exigida:
  - Tornado o Monte Carlo con rangos justificados para IC, MS, f, consumo específico, α, tarifas y disponibilidad.
  - Tabla de comparación con al menos dos estimaciones independientes (WISDOM u otras) o declaración explícita de que la validación externa falta.
  - Incorporar en el escrito las cifras de sensibilidad del Informe 2 con su cálculo, y rehacer la Figura 23 como tornado.

### O3 · BLOQUEANTE · Veracidad
- Ubicación: Introducción («Alcance y limitaciones»); §5.8; §11.2; diapositivas 11 y 23.
- Cita: «Tres distribuidoras (Santa Cruz, Tierra del Fuego y Tucumán) no publican cuadros legibles por máquina y Chubut carece de una distribuidora provincial única, por lo que esas provincias tienen energía estimada pero no valorización económica»; «esas provincias representan el 0,7 % de la energía estimada».
- Problema: solo Tucumán tiene energía sin valorizar. Santa Cruz, Tierra del Fuego y Chubut no tienen energía en el resultado anual; la tesis lo contradice.
  - El resultado anual contiene 15 provincias. La energía de Tucumán es 0,55 TWh, que es el 0,69 %, es decir todo el «0,7 %».
  - Del mismo modo, EPEN (Neuquén), EDEMSA, EDESTE (Mendoza), ESJ (San Juan) y EDERSA (Río Negro) figuran como éxitos de extracción, pero esas provincias no aportan nada al resultado. En la salida solo aparecen 16 distribuidoras con energía. Las 28 del título «28 distribuidoras» y de la diapositiva 11 sobredimensionan el aporte de la extracción al resultado.
  - Nunca se explica por qué 8 de las 23 provincias del histórico (Chubut, La Rioja, Mendoza, Neuquén, Río Negro, San Juan, Santa Cruz, Tierra del Fuego) desaparecen del período de referencia. Tampoco aparece una consecuencia obvia del §6.4: ¿no hay cultivos con coeficientes allí?
- Evidencia: `potencial_energetico_anual.parquet` (2.421 filas): `Provincia` tiene 15 valores. Energía por distribuidora: EDEN+EDEA+EDES 27,17; EPEC 20,70; EPE 11,99; EDESE 5,36; ENERSA 4,67; APE 3,85; SECHEEP 1,84; EDESA 1,73; EDESAL 1,50; EDET 0,55; DPEC 0,35; ECSAPEM 0,14; REFSA 0,11; EMSA 0,06; EJESA 0,06; EDELAP 0,04. `biomasa_validos.parquet` sí contiene las 23 provincias en el histórico, pero en 2021/22–2025/26 solo estas 15 tienen filas.
- Corrección exigida: corregir las tres menciones. Explicar por qué faltan las 8 provincias y reexpresar el alcance real: «de las 28 distribuidoras, 16 intervienen en los resultados; de ellas, una (EDET) sin dato». Recalcular qué parte de la energía depende realmente de tarifa extraída.

### O4 · MAYOR · Rigor del modelo de dominio / Veracidad
- Ubicación: §5.6; Anexo A (POL-TARIFF-002); diapositiva 12.
- Cita: «el error de la estimación queda acotado entre −12 % y +4 % para los registros afectados».
- Problema: la cota es falsa con los cuadros vigentes del repositorio. Sale de una versión anterior del dato («rango observado de ratios ≈ 0,63 a 1»).
  - Con la fórmula del propio texto (beneficio ∝ 0,6 + 0,4·cociente) y el JSON de noviembre de 2026, los cocientes publicados van de 0,12 a 1,00: EDESA 0,119; APE 0,542; EJESA 0,634; ENERSA 0,715; EDELAR 0,752; SECHEEP 0,766.
  - El error mínimo es −33 % (EDESA), −15 % (APE) y −12 % (EJESA). La cota inferior de −12 % solo cubre hasta EJESA.
  - Además, la mediana (0,913) mezcla dos poblaciones que la propia documentación distingue: «T3 grandes demandas ratio 0,9–1» frente a «medianas demandas ratio 0,6–0,8». EPE, que supone el 15 % de la energía y está en «2 B1 Demandas menores a 300 kW», recibe la mediana de la población equivocada y es el principal usuario de la estimación.
  - ESJ muestra compra = inyección = 153,2696 exactamente, y EDERSA 166,388 contra 166,386. Eso apunta a que el parser lee la misma fila dos veces. Esos dos valores entran en la mediana.
- Evidencia: `data/reference/20261111062233_tarifas.json`, campos `tarifa_compra_kwh` y `tarifa_inyeccion_kwh` de EDESA (317,7794/38,009), APE (244,57/132,58), EJESA (191,5834/121,54), ESJ (153,2696/153,2696), EDERSA (166,388/166,386); `decisiones.md`, POL-TARIFF-002.
- Corrección exigida: recalcular la cota con los datos actuales y por población (medianas vs grandes demandas). Estimar la inyección por categoría y no con una única mediana, o adoptar la «alternativa pendiente» del precio estacional. Revisar ESJ y EDERSA y reportar la distribución completa de cocientes.

### O5 · MAYOR · Rigor del modelo de dominio / Veracidad
- Ubicación: §5.3 (parser); Figura 7; §10.5.
- Cita: «tarifa de compra promedio ponderada por energía es de unos 150 $/kWh»; Figura 7: «datos extraídos de los cuadros tarifarios oficiales».
- Problema: las compras entre distribuidoras difieren por factor 3–3,6 (103 a 373 $/kWh) para una supuesta misma categoría, y la tesis no discute si el parser toma cosas equivalentes.
  - APE (244,57) es la suma de «Costo Compra de Energía» 170,16 + «VAD excedente de 4000 kWh» 74,41: se agrega un cargo de distribución por bloque a un precio de energía.
  - EDESA elige 317,78 entre varias columnas; EPEN 373,214 y EMSA 283,836 no se contrastan con ninguna otra fuente.
  - ENERSA detecta tres valores [57,77; 130,84; 131,1] y el parser toma la mediana.
  - EPE elige una de tres columnas de la misma fila.
  - La tesis nunca analiza por qué la dispersión es tan grande; la lectura de ese dato queda en manos del tribunal.
  - La heterogeneidad se refleja en la conclusión de §10.5 («La Pampa o Salta ganan participación económica»): esa participación sale probablemente del parser y de una categoría tarifaria distinta, y no de una diferencia real de precios.
- Evidencia: campo `seccion_compra` y `valores_detectados` del JSON de noviembre para APE, EDESA, EPEN, EMSA, ENERSA, EPE. En `data/reference/tarifas_historial.csv` la fila inicial de APE tiene `seccion_compra` «Costo Compra de Energía | $/kWh | 110,86959 …» con vigencia 2025-12.
- Corrección exigida: tabla de auditoría por distribuidora (categoría efectivamente leída, concepto, unidad, valor, comprobación manual). Quitar de §10.5 la afirmación sobre La Pampa y Salta o sustentarla, y explicar la dispersión 103–373 $/kWh.

### O6 · MAYOR · Veracidad / Figuras
- Ubicación: Figura 7 (§5.8); diapositiva 11 («15 publican tarifa de inyección legible»).
- Cita: «Tarifas de compra e inyección por distribuidora (noviembre de 2026, $/kWh sin impuestos)»; «datos extraídos de los cuadros tarifarios oficiales».
- Problema: en la Figura 7 las barras de inyección de EMSA, EPE, DPEC, ECSAPEM, REFSA y EDESAL son estimaciones, no extracciones. EMSA 259 = 283,836 × 0,913; EPE 134 = 146,77 × 0,913. Solo 8–9 de las 15 barras provienen de un cuadro. El gráfico no distingue estimado de publicado, y la leyenda dice «Inyección» sin más.
- Evidencia: `tarifas.json`: `tarifa_inyeccion_kwh` = None para EMSA, EPE, DPEC, ECSAPEM, REFSA y EDESAL. La Figura 7 muestra valores en las seis.
- Corrección exigida: diferenciar visualmente (barra rayada) lo estimado de lo publicado y aclararlo en el pie. Revisar la frase de la diapositiva 11.

### O7 · MAYOR · Veracidad / Coherencia interna
- Ubicación: Figura 7; §10.2 («tarifas sin impuestos vigentes en noviembre de 2026»); §5.6.
- Cita: «tarifas … vigentes en noviembre de 2026»; «con los cuadros de noviembre de 2026».
- Problema: las vigencias de los cuadros usados van de 2025-10 a 2026-11.
  - REFSA 2025-10; EDELAR 2026-03; DPEC 2026-04; EDEMSA 2026-05; ECSAPEM 2026-05; EDESUR 2026-05; EDENOR 2026-06; SECHEEP 2026-06; EDESAL 2026-06.
  - Con inflación argentina esas tarifas están desactualizadas varios meses frente a las de EPEC (2026-11).
  - Esa mezcla de fechas favorece o perjudica a distribuidoras según su demora, y no se informa.
  - Además, la alerta de la Figura 8 (ENERSA) compara cuadros 2025-12 y 2026-05: la distribuidora clave de Entre Ríos tiene un cuadro de seis meses antes.
- Evidencia: campo `vigencia` por distribuidora en el JSON de noviembre.
- Corrección exigida: reportar la vigencia de cada cuadro, advertir sobre la mezcla de fechas (o actualizar a un mes común por indexación) y quitar «vigentes en noviembre».

### O8 · MAYOR · Rigor del modelo de dominio
- Ubicación: §6.7; §10.2 («Ahorro por autoconsumo (60 %)»); Anexo B.
- Cita: «una fracción α = 60 % de la energía se autoconsume y el resto se inyecta».
- Problema: α = 0,6 no tiene fundamento ni fuente en el escrito. En la documentación del repo figura como «(60 % de autoconsumo, supuesto)».
  - Además el modelo supone que 519.700 equipos autoconsumen el 60 % de 80 TWh (48 TWh) en cada departamento. No se contrasta con la demanda eléctrica rural, ni con los topes de la Ley 27.424 sobre la potencia del usuario-generador ni con los reglamentos provinciales de balance neto.
  - Tampoco se discute si el precio de ahorro por autoconsumo es solo el cargo de energía (sin cargos fijos ni de potencia), ni la estacionalidad: la cosecha es estacional, y el modelo supone 80 % de disponibilidad anual con biomasa almacenada.
- Evidencia: `docs/02_metodologia/metodologia.md` línea 151, con la misma frase. No hay referencia en la tesis salvo la ley.
- Corrección exigida: justificar α con datos de demanda rural y los límites normativos, o declarar que es un parámetro libre. Discutir estacionalidad y almacenamiento del rastrojo.

### O9 · MAYOR · Rigor del modelo de dominio
- Ubicación: §1.2; §6.6; Anexo B (CE = 1,0 kg MS/kWh).
- Cita: «consumo específico de aproximadamente 1,0 kg de biomasa seca por kWh (All Power Labs, s.f.-a)»; «cuyo consumo … el rastrojo suelto requiere acondicionamiento».
- Problema: el único parámetro físico del equipo es el valor de catálogo del fabricante, sin contraste con literatura independiente de gasificación downdraft de residuos agrícolas.
  - El propio §1.2 reconoce que el fabricante aprueba como combustible madera, cáscaras y marlos, y que el rastrojo suelto requiere acondicionamiento.
  - La sensibilidad solo prueba 1,0 y 1,1 kg/kWh (−10 %); la variación para combustibles de menor densidad y mayor ceniza puede ser mayor.
  - Ningún rendimiento neto, parásitos ni pérdidas de acondicionamiento (trituración o peletizado, que consumen energía) entran al balance: el cálculo asume que todo kg de MS retirado se gasifica a 1,0 kg/kWh.
- Evidencia: `docs/02_metodologia/decisiones.md`, POL-ENERGY-001. El único contraste interno es la ficha de APL; el valor del fabricante no se verifica. Esto último no es verificable con el repositorio.
- Corrección exigida: contrastar CE con al menos dos fuentes independientes, incluir un descuento por acondicionamiento y por consumos auxiliares, y ampliar el rango de sensibilidad. Citar en el cuerpo la ficha técnica, que solo figura en las referencias.

### O10 · MAYOR · Estado del arte
- Ubicación: Capítulo 1 (§1.1–§1.9).
- Cita: «El relevamiento muestra que los fundamentos del dominio están consolidados».
- Problema: es un marco teórico de manual, no un estado del arte.
  - No hay trabajos comparables sistematizados: sistemas de información de residuos agrícolas y sus herramientas (SIG, atlas de biomasa, estudios de potencial energético de rastrojo en Argentina o la región), qué existe y qué falta.
  - Solo un antecedente argentino (WISDOM, FAO 2009/2020) y descrito como «orientado a dendroenergía» sin respaldo.
  - La mayor parte del capítulo son manuales o libros de texto antiguos: Reed y Das (1988), Fowler (2006), Kimball y Caserta (2004), Rivest et al. (1978), Diffie y Hellman (1976). Casi nada posterior a 2020 sobre el dominio.
  - La sección 1.7 (SSH, seis subsecciones, criptografía de Diffie-Hellman, RSA, Curve25519) ocupa tanto espacio como todo el dominio energético. Eso es didáctica sobre infraestructura, no estado del arte, y desequilibra el capítulo.
  - Falta literatura sobre scraping de tarifas o datos abiertos eléctricos en Argentina y sobre parsers de cuadros tabulares en PDF (comparación con tabula, camelot o pdfplumber).
- Evidencia: referencias de Cap. 1; el capítulo menciona un único antecedente nacional.
- Corrección exigida: agregar una sección de antecedentes con tabla comparativa (alcance, método, resolución, actualización, valorización económica) incluyendo estudios argentinos y regionales de potencial de residuos; recortar §1.7 a un párrafo y moverlo a un anexo.

### O11 · MAYOR · Justificación de decisiones técnicas
- Ubicación: Tabla 2 (§2.5); §3.3; Cap. 8.
- Cita: «Python 3.11 | Todo el sistema»; «Caddy»; «Ofelia (cron)»; «Streamlit».
- Problema: casi ninguna tecnología se justifica frente a alternativas con criterios explícitos.
  - Solo hay comparación argumentada (y breve) para archivos vs base de datos (§3.3), CSV vs Parquet (§5.7) y la frecuencia semanal (§8.3).
  - Sin justificación: Python frente a otros lenguajes; Parquet y DuckDB frente a SQLite o PostgreSQL (hay un `database.sqlite` vacío de 0 bytes en `data/processed/`); Streamlit frente a Dash, Grafana o Superset; Ofelia con montaje del socket de Docker frente a cron del host o systemd timers; Docker Compose frente a systemd o a un PaaS; Caddy frente a Nginx o Traefik; VPS frente a PaaS; GitHub Actions frente a otros; Debian; Tailscale frente a WireGuard directo; la carpeta `raw/reference/processed/audit` frente a una arquitectura medallón explícita; imagen única para todos los servicios; pytest/ruff.
  - Las únicas «alternativas» reales son los diseños de despliegue continuo revertidos, y están presentados como experiencia, no como comparación con criterios.
- Evidencia: Tabla 2 es solo un inventario («Uso en el trabajo»); no existe tabla de alternativas ni matriz de criterios.
- Corrección exigida: agregar una tabla «decisión–alternativas–criterios–elección» (costo, mantenimiento, curva de aprendizaje, seguridad, reproducibilidad) para al menos: almacenamiento, planificación, framework del tablero, proxy inverso, hosting y CI.

### O12 · MAYOR · Veracidad (infraestructura)
- Ubicación: §8.1, §8.2, §8.4, §8.9, Anexo C; diapositivas 15 y 17.
- Cita: «crea un usuario sin privilegios»; «el tablero … escucha solo en la red interna (puerto 8501)»; «mínima exposición»; «El tablero monta los datos en solo lectura: aunque fuera comprometido, no podría alterar los resultados».
- Problema: `docker-compose.yml` contradice varias afirmaciones.
  - `etl_worker` y `etl_pipeline` corren con `user: "0:0"` (root); el usuario sin privilegios del Dockerfile no se usa en el ETL.
  - El scheduler monta `/var/run/docker.sock:ro`. El `:ro` no restringe la API del socket, y da control del demonio (equivale a root en el host); es lo opuesto a «mínimo privilegio».
  - El servicio `dashboard` publica `"${DASHBOARD_PORT:-8501}:8501"` en todas las interfaces y también monta `./dashboard` y `./config` en el contenedor. En el compose del repositorio no hay Caddy ni red interna; la «topología» de la Figura 9 no corresponde a lo versionado.
  - El `docker-compose.yml` no define `healthcheck`, aunque en §11.3 se lo plantea como trabajo futuro.
  - La imagen del scheduler es `mcuadros/ofelia:latest`, sin fijar versión, lo que contradice «reproducibilidad».
  - La propia nota sobre permisos de Windows/Docker Desktop justifica el root; eso no figura en la tesis.
- Evidencia: `docker-compose.yml` (líneas de `etl_worker`, `etl_pipeline`, `scheduler`, `dashboard`) y `Dockerfile`.
- Corrección exigida: corregir las afirmaciones o corregir el despliegue (usuario no root, imagen del scheduler con tag fijo, red interna, sin `ports` en el dashboard detrás del proxy). Declarar que el socket de Docker en el planificador amplía la superficie de ataque.

### O13 · MAYOR · Veracidad / Honestidad
- Ubicación: §8.4, §8.5, Figura 9; diapositivas 16 y 17.
- Cita: «Caddy», «ufw», «Tailscale», «certificados SSH de corta duración (dos horas)», «/opt/ops/bin/deploy-gate».
- Problema: todo lo del servidor de producción es NO VERIFICABLE.
  - En el repositorio no hay Caddyfile, reglas de ufw, configuración de sshd, `TrustedUserCAKeys`, `deploy-gate` ni ningún script de aprovisionamiento. Tampoco hay URL pública del tablero ni evidencia (captura, `docker ps`, auditoría) de que el sistema esté «puesto en producción».
  - El Listado 7 es «ilustrativo»; el escrito no lo asocia a una configuración real.
  - Parte de lo descrito (claves con `command=`, certificados SSH, `deploy-gate`) sirve al despliegue continuo que se revirtió (§8.7). No se aclara si todavía se usa, y eso erosiona la afirmación «acceso administrativo por SSH con clave pública, VPN y comandos forzados».
  - «El Informe 11 a Docker 1 GB/0,5 GB por año» no tiene medición documentada.
- Evidencia: búsqueda de Caddy, ufw, tailscale, authorized_keys, deploy-gate en el repositorio: sin archivos de configuración; solo texto de documentación.
- Corrección exigida: agregar un anexo con las configuraciones reales (Caddyfile, `ufw status`, `sshd_config`, salida de `docker compose ps`) o relajar los verbos («se diseñó» en lugar de «se opera»). Aclarar qué parte de §8.5 está efectivamente vigente tras la reversión.

### O14 · MAYOR · Metodología
- Ubicación: §2.1, §2.2 y §2.7.
- Cita: «Contraste con la fuente: todo valor extraído … se comparó, para una muestra, con el documento original».
- Problema: la metodología es crónica del repositorio más que método de investigación.
  - La Tabla 1 reconstruye las fases desde el historial de commits («`git log`»). No hay preguntas de investigación ni hipótesis, tampoco criterios de aceptación cuantitativos.
  - Los «criterios de validación» no son reproducibles. «Una muestra» no tiene tamaño, selección ni resultado. No se informa cuántos valores se verificaron ni con qué tasa de error.
  - Solo hay un ejemplo trazable (10.000 t de maíz) y su prueba codifica el mismo cálculo, con lo cual es una prueba de consistencia circular y no de validez.
  - No hay una sección de validez interna y externa. Las fases 6 y 7 se superponen en fechas (16–28/10 y 27–28/10), y 4 y 5 en el 5/10.
  - Las fases se «descubren» después en el historial, en lugar de planificarse.
- Evidencia: Tabla 1 (fases 4–5 y 6–7 solapadas); no hay protocolo de muestreo.
- Corrección exigida: reformular el capítulo con preguntas, método, criterios y protocolo de verificación (tamaño de muestra, resultados, tasa de error), y una sección de amenazas a la validez interna y externa. Hacer una verificación manual documentada de cada distribuidora usada.

### O15 · MAYOR · Honestidad y limitaciones
- Ubicación: §2.6; §11.1.
- Cita: «52 commits figuran con ese agente como autor y otros llevan la marca de coautoría … La responsabilidad sobre el diseño, las decisiones y los resultados es del autor».
- Problema: la declaración es correcta pero insuficiente.
  - No se cuantifica la proporción real de código, pruebas y documentación generada por el agente (solo 52 commits «autor» de 203 más otros «coautoría», sin números).
  - No se explica cómo se verificó la comprensión del código. El alumno debería poder defender cada línea del parser y de los extractores (3.880 líneas de extractores, 1.368 en `scrape_tarifas.py`).
  - El escrito afirma que las pruebas «se ampliaron» con el agente: parte de las pruebas que dan evidencia de calidad (156 casos) fueron escritas por la misma herramienta que escribió el código.
  - Los 52 commits y la coautoría no pude verificarlos: están en el historial de git, que no consulté. NO VERIFICABLE por mi parte; el alumno debe adjuntar el recuento.
- Evidencia: ninguna cifra de proporción en la tesis.
- Corrección exigida: tabla de contribuciones (archivos o líneas por autor humano o agente) y un anexo con las instrucciones principales y la política de revisión. Declarar la IA también en la presentación (solo aparece en las notas de la diapositiva 7).

### O16 · MAYOR · Coherencia interna / Veracidad
- Ubicación: Tabla 3 (§3.4); §5.1; §11.1 («la mayor parte del código está dedicada a extraer y validar»).
- Cita: «Total Python | 49 | ≈11.450»; «suma unas 2.900 líneas, el 59 % del código de extracción».
- Problema: la tabla no suma su propio total y los porcentajes no son reproducibles.
  - Las filas suman 47 archivos y 11.292 líneas. Para llegar a 49 y ≈11.450 falta `etl/notifications.py` (155 líneas) y los `__init__.py`, que no figuran en la tabla.
  - En §5.1, 2.900 líneas es el 75 % de las 3.880 de `etl/extractors/`, no el 59 %. Las 2.900 parecen incluir `distribuidoras.py` y `tariff_history.py` (otras carpetas), y el denominador no es el de Tabla 3.
  - Extraer y validar no es «la mayor parte del código»: los extractores son 3.878 de 11.292 líneas (34 %), o 43 % sin las pruebas.
- Evidencia: conteo de `wc -l` por archivo (extractores 3.878; reference 807; transformers 1.947; loaders 265; pipelines 518; dashboard 1.692; tests 2.185).
- Corrección exigida: rehacer la tabla con todas las filas, definir el denominador de los porcentajes y moderar «la mayor parte del código».

### O17 · MAYOR · Coherencia interna
- Ubicación: §2.3 (Figura 3); diapositiva 7.
- Cita: «Se registraron 25 fusiones de pull requests»; «25 pull requests integrados».
- Problema: la Figura 3 muestra 30 commits de tipo «merge». No se explica la diferencia de 5 (merges de `main` a ramas, merges de otro tipo).
- Evidencia: Figura 3 (merge = 30; suma de todas las barras 203). El 25 no es verificable por mí sin git.
- Corrección exigida: reconciliar 25 y 30 y explicar qué son los 5 restantes.

### O18 · MAYOR · Coherencia interna / Figuras
- Ubicación: §8.7; diapositiva 18 y Figura 10.
- Cita: «(commit `63cbb88`)»; en la figura: «Revert al árbol a31c418».
- Problema: la tesis identifica la reversión con `63cbb88` y la figura con `a31c418`. Puede ser que uno sea el commit de reversión y el otro el árbol de destino, pero no se aclara y a un lector le parece una contradicción.
- Evidencia: texto de §8.7 y Figura 10 (diapositiva 18). NO VERIFICABLE por mí contra el historial.
- Corrección exigida: unificar la nomenclatura o explicar «commit de reversión» y «árbol de destino».

### O19 · MAYOR · Honestidad y limitaciones
- Ubicación: §4.1; §5.2 «Descarga prudente»; Capítulo 4.
- Cita: «obligaba a imitar la huella TLS de un navegador (`curl_cffi` con `impersonate="chrome110"`)»; «se identifica al cliente con un User-Agent propio».
- Problema: se admite la elusión de un desafío anti-bot sin discusión ética ni legal. No hay mención de `robots.txt`, términos de uso ni licencia de los datos (SharePoint de la Bolsa de Cereales, portales provinciales).
  - Además el User-Agent real imita a Chrome: «Mozilla/5.0 … Chrome/139.0 Safari/537.36 OPTIMIA-HV-ETL/1.0». «User-Agent propio» es engañoso.
  - El extractor descartado se conserva en el repositorio.
  - Las comprobaciones de comportamiento prudente se declaran sin evidencia. Tampoco hay constancia de que cada fuente autorice la reutilización.
- Evidencia: `etl/extractors/scrape_tarifas.py` líneas 88–92; `scrape_bolsa_cereales_nacion.py` línea 66 (`impersonate=`). Ninguna mención de `robots` en `etl/` ni `docs/`.
- Corrección exigida: agregar una sección de aspectos legales y éticos (licencias de datos abiertos, términos de uso, robots.txt, política de rate limit), y describir fielmente el User-Agent.

### O20 · MAYOR · Calidad de pruebas / Veracidad
- Ubicación: §7.1; Tabla 6; diapositiva 14.
- Cita: «ejecutan 156 casos»; «se ejecuta en unos cuatro segundos»; «En la versión entregada, los 156 casos pasan».
- Problema: verifiqué las 120 funciones de prueba (4+6+8+5+32+16+5+6+3+4+29+2 = 120) y los 12 archivos. Los 156 casos con parametrización no los pude confirmar: no ejecuté `pytest` por la regla de solo lectura. NO VERIFICABLE (156, cuatro segundos, «pasan»).
  - La Tabla 6 titula la columna «Pruebas» con valores que son funciones (120) y no casos (156); el total no aparece.
  - No hay cobertura medida (aunque `pytest-cov` figura en dev). No hay pruebas de los extractores contra la web real y los de tarifas dependen de fixtures de documentos viejos: el «contrato con las fuentes» queda como trabajo futuro.
  - El «ejemplo trazable» de §6.8 (31 equipos, $629 M) lo pude reproducir a mano, pero usa 0,917 de cociente y 135 $/kWh, no 0,913 ni la tarifa real; ver O28.
- Evidencia: `grep` de `def test_` por archivo; sin `.coveragerc` ni reporte de cobertura.
- Corrección exigida: incluir la salida de `pytest` y la cobertura medida; corregir el encabezado de la Tabla 6 (funciones o casos).

### O21 · MAYOR · Veracidad / Rigor del modelo
- Ubicación: §7.3; Figura 8.
- Cita: «El primer hallazgo de este mecanismo fue real: un salto de la tarifa de ENERSA de 67,28 a 130,84 $/kWh reveló que el valor anterior provenía, por error, de una tabla de media tensión».
- Problema: la Figura 8, que es la captura de la corrida final del 11 de noviembre, muestra esa misma alerta abierta: «salto_tarifa | ENERSA | 67.28 → 130.84 | +94 % | Cuadro 2025-12 → 2026-05».
  - El mecanismo se presenta como resuelto y el resultado entregado conserva la alerta sin explicación (el escrito no dice si se descartó o se aceptó).
  - Además el JSON actual de ENERSA detecta tres compras [57,77; 130,84; 131,1] y elige 130,84 por mediana: el 57,77 sigue entrando.
  - La alerta no es un error: puede ser un aumento real, pero eso justamente lo hace inadecuado como «hallazgo de error».
- Evidencia: captura `img/ui_auditoria.png`, `alertas_calidad.parquet` (1 fila) y JSON de noviembre (ENERSA).
- Corrección exigida: documentar la disposición de la alerta, mostrar el documento fuente y reformular el ejemplo.

### O22 · MAYOR · Citas y referencias / Rigor
- Ubicación: Tabla 5 (§6.4).
- Cita: «Bolsa de Cereales de Buenos Aires (2015)»; «Raposo (2024)»; «Cuda (2014)»; «Zamer y Chiarelli»; «Haro (2022)»; «Estudios regionales»; «Zubiaga et al. (2023)».
- Problema: ninguna de esas fuentes de IC figura en la lista de referencias, salvo Hay (1995).
  - Los coeficientes son el corazón del modelo y su procedencia no es rastreable.
  - «Zamer y Chiarelli» no tiene año ni título, «Estudios regionales» no es una fuente. En el CSV, el de algodón es «Estudios regionales (Xinjiang)», es decir de China, aplicado a Argentina; el de lino es «Estudios ADAS/AHDB» (Reino Unido) y el de papa «Xu et al. (QUEFTS)».
  - Tampoco están citadas las fuentes de MS («estándares de comercialización de granos, Argentina»).
  - La tabla oculta el origen foráneo reemplazándolo por «Estudios regionales».
  - El mismo IC (0,35) se aplica al trigo, sorgo y avena sin distinguir variedad ni ambiente, y un IC (0,47 en maíz) es un único valor para todo el país.
- Evidencia: `data/reference/ic_fr.csv`, columnas «Fuente bibliográfica» y «Fuente MS»; lista de referencias (§Referencias).
- Corrección exigida: agregar las referencias completas, reemplazar «Estudios regionales» por la fuente real y su origen geográfico, y justificar o reemplazar los coeficientes importados.

### O23 · MAYOR · Citas y referencias
- Ubicación: lista de referencias.
- Problema: hay referencias sin cita en el texto y fuentes de apoyo débil.
  - No citadas en el cuerpo: Eco (2001), All Power Labs (s.f.-b), Conventional Commits, Apache Parquet, Anthropic (2026), Ferro (2026a–c); el Informe 1 y el Informe 2 solo se nombran sin cita parentética.
  - FAO (2020) aparece como «actualizado en 2020» sin formato autor-año.
  - Darghouth et al. (2011) trata de ahorros de PV residencial en California; no define el balance neto argentino.
  - Las afirmaciones sobre la Secretaría de Energía («republica parte … con demoras y omisiones», §1.3), sobre Telegram y webhooks y sobre el 192 horas carecen de cita o dato.
  - Sin cita: «las tarifas cambian como máximo una vez por mes» (§8.3): se afirma sin dato y el propio historial muestra distribuidoras con cambios más frecuentes. «Las estimaciones agrícolas con menor frecuencia aún»: también sin respaldo.
  - Hay referencias que no se sustentan en el texto, como el RFC 8709 (Ed25519 en SSH), que se menciona pero no figura en la lista: «incorporado a SSH por el RFC 8709».
  - Formato APA 7 en español: la coma antes de «y» en la lista de autores («…, y Warren, B.») es de estilo inglés.
- Evidencia: búsqueda de cada cita en el cuerpo y en la lista.
- Corrección exigida: depurar la lista (cada cita en el texto y viceversa), agregar RFC 8709 y las fuentes de los coeficientes, y normalizar el formato APA.

### O24 · MAYOR · Estructura de TFG
- Ubicación: Portada; Agradecimientos; Índice.
- Cita: «Director/a: [a completar]»; «[Sección a completar por el autor.]».
- Problema: la entrega tiene campos sin completar (director y agradecimientos). El Objetivo 3 dice «capaz de leer las publicaciones de las 28 distribuidoras», pero se cumple con 25 (§11.1 lo reformula como «25 de las 28»). No hay anexo con muestras de datos, ni listado de figuras que cubra tablas y listados (hay 11 tablas y 8 listados, pero solo se indexan figuras).
  - No hay objetivos medibles ni criterios de éxito. El objetivo 5 («Asegurar la calidad») no es verificable.
  - No existen resultados de la validación contra la fuente (O14) ni un capítulo de discusión propiamente dicho; Capítulo 10 y Capítulo 11 mezclan resultados y conclusiones.
  - El Índice no tiene numeración de páginas.
- Evidencia: texto de portada, Agradecimientos, Objetivo 3 y §11.1.
- Corrección exigida: completar los campos, reescribir el Objetivo 3 y los demás con indicadores medibles, agregar un capítulo de discusión, y agregar índices de tablas y listados y números de página.

### O25 · MAYOR · Presentación de defensa
- Ubicación: diapositivas 8, 11, 16, 17, 18, 19, 21.
- Problema: lo que se proyecta es ilegible.
  - En la diapositiva 16 el diagrama de SSH (la parte central del tema) tiene un texto de ≈10 px sobre 1600 px; no se lee proyectado. Lo mismo ocurre con los diagramas de las diapositivas 8, 11 y 17 (texto interno de 9–12 px), la Figura 10 de la 18 y los mapas de la 21.
  - La diapositiva 19 muestra tres capturas del tablero con texto microscópico. La tercera («Auditoría») es una página casi vacía.
  - La diapositiva 12 usa código en 14,5 px y la 17 en 14 px; pies de figura y numeración en 15–16 px.
  - El gráfico de la diapositiva 7 tiene anotaciones diminutas («Docker, tests», «Informe 2»).
- Evidencia: capturas 7, 8, 11, 12, 16, 17, 19, 21; CSS `pre{font-size:17px}`, estilos en línea 14,5 px y 14 px.
- Corrección exigida: rehacer los diagramas con letra mínima de 18 px para la proyección o dividirlos en dos diapositivas, y reemplazar las capturas por recortes ampliados de la parte relevante.

### O26 · MAYOR · Presentación de defensa / Honestidad
- Ubicación: diapositivas 20 y 23.
- Cita: «Potencial técnico anual (2021/22–2025/26)»; «Objetivos cumplidos y tres aprendizajes».
- Problema: la diapositiva 20 da el titular (80,1 TWh; 11,2 billones) sin mencionar en pantalla que el beneficio es bruto, que f = 50 % es optimista y que no incluye costos (solo en las notas del orador). Las limitaciones se postergan a la diapositiva 24, la penúltima.
  - La 23 afirma «Objetivos cumplidos» (sin matices) cuando el Objetivo 3 se cumplió al 89 % (25 de 28) y el cálculo no se validó externamente.
  - La diapositiva 20 no explica «billones» (10¹²), que en inglés (billion) es otra magnitud; ni «Mt MS».
  - La notación «Tc» y «Ti» de la diapositiva 9 no se define en la lámina.
- Evidencia: capturas 9, 20, 23 y 24.
- Corrección exigida: mover las limitaciones junto con los resultados, incluir en la diapositiva 20 «beneficio bruto, f = 50 %, sin costos», definir las notaciones y reescribir «Objetivos cumplidos».

### O27 · MAYOR · Presentación de defensa / Coherencia con el escrito
- Ubicación: diapositivas 1–25 en conjunto; diapositivas 8–18.
- Problema: la distribución del tiempo no es coherente con lo que se evalúa.
  - Hay seis diapositivas (14–18) de ingeniería (calidad, infraestructura, SSH, despliegue, CI) frente a una de resultados y una de sensibilidad, y ninguna de validación del modelo ni de la calidad de las tarifas.
  - La diapositiva 19 (tablero) no muestra el tablero funcionando.
  - La diapositiva 5 repite en pantalla párrafos del Capítulo 1. Las diapositivas 5, 6, 13, 15 y 24 tienen más de la mitad del espacio vacío mientras otras están saturadas.
  - La pendiente de 25 diapositivas en 20–25 min deja unos 50–60 s por lámina, con 3 de ellas de código.
  - La diapositiva 19 sugiere que la captura «Supuestos ajustables» es de la página «Dinero»; la imagen es la misma que la de la Figura 15 recortada.
- Evidencia: capturas de todas las diapositivas.
- Corrección exigida: reequilibrar hacia el dominio, la validación y las limitaciones; recortar SSH a una lámina; demostrar el tablero en vivo o con una captura legible.

### O28 · MENOR · Coherencia interna
- Ubicación: §6.8 (ejemplo trazable) frente a §5.6 y §10.5; diapositiva 9.
- Cita: «ahorro ≈ 4,82 GWh × 0,6 × 135 $/kWh»; «crédito … × 135 × 0,917».
- Problema: el ejemplo usa cociente 0,917 y 135 $/kWh mientras que el resto del texto usa 0,913 y ≈150 $/kWh. La documentación del repositorio también dice 0,917. El resultado de $629 M cambiaría con los valores vigentes. Con la tarifa de EDEN (135,23) el número es plausible, pero hay que declararlo.
- Evidencia: `docs/03_datos/tarifas_electricas.md` línea 84 («0,917»); `parametros_pp30`/`injection_ratio`; JSON con 0,913.
- Corrección exigida: usar los mismos parámetros en todo el texto o aclarar que el ejemplo es ilustrativo, y actualizar el 0,917 de la documentación.

### O29 · MENOR · Coherencia interna / Estructura
- Ubicación: §3.2; Figura 4; diapositivas 6 y 8.
- Cita: «archivos organizados por madurez (`raw`, `reference`, `processed`, `audit`)»; diapositiva 6: «ETL por capas (bronce → oro)».
- Problema: `reference` y `audit` no son niveles de madurez, y `data/interim/` está vacío y no se menciona. La referencia a la arquitectura medallón (Armbrust et al., 2021) no se corresponde con la estructura real de carpetas. Falta una justificación de la organización de carpetas de datos.
- Evidencia: árbol `data/` (`audit`, `interim` vacío, `processed`, `raw`, `reference`) y `data/processed/database.sqlite` de 0 bytes.
- Corrección exigida: describir la estructura real y retirar la analogía bronce-plata-oro o justificarla. Eliminar el `database.sqlite` residual.

### O30 · MENOR · Veracidad
- Ubicación: §8.3; `config/schedule.ini`.
- Cita: «cada ejecución insume unos 30 minutos de descargas».
- Problema: dato sin medición documentada en el escrito (el comentario del `schedule.ini` repite «≈ 30 min y ≈ 10 MB por corrida»). Los 1 GB de imagen, 300–600 MB del tablero y 0,5 GB/año de §8.2 y §8.8 tampoco tienen evidencia. NO VERIFICABLE.
- Evidencia: sin logs de corridas en el repositorio utilizable (`logs/` sin registro de corrida).
- Corrección exigida: adjuntar logs de corridas con duración y consumo de memoria.

### O31 · MENOR · Veracidad
- Ubicación: Tabla 2; `pyproject.toml`.
- Problema: la tabla de herramientas omite dependencias efectivas (matplotlib, seaborn, PyYAML, mypy, pytest-cov, Jupyter). El código dice «Un PP30 (25 kW)» en comentarios del parser (líneas 392 y 408 de `tariff_parser.py`) mientras que la tesis usa 22 kW; el venv local es Python 3.13 y la tesis dice 3.11. Un comentario del propio repo («Los CSV raw se versionan…») muestra convivencia de nomenclaturas. No hay bloqueo de versiones (`pandas>=2.0`, sin `requirements.lock`).
- Evidencia: `pyproject.toml` y `tariff_parser.py`.
- Corrección exigida: actualizar los comentarios, fijar dependencias y alinear la Tabla 2.

### O32 · MENOR · Coherencia interna
- Ubicación: Figura 19 / diapositiva 21; §10.1.
- Cita: «15 cultivos»; Figura 19 muestra 14 barras (Maíz … Colza).
- Problema: la figura omite un cultivo del total de 15 (probablemente lino, ajo o papa, con aporte mínimo) y no lo dice. Por otra parte, «Energía por cultivo» muestra TWh con un valor de maíz de 28,3 (35,3 %) frente al 35,4 % del texto: coherente, pero la leyenda no indica la base.
- Evidencia: parquet (15 cultivos) y la imagen `fig_energia_cultivo.png`.
- Corrección exigida: incluir todos los cultivos o rotular «otros».

### O33 · MENOR · Figuras, tablas y listados
- Ubicación: Figuras 17 a 23; Figuras 11–16.
- Problema: hay problemas de formato en las figuras.
  - Los gráficos de matplotlib usan punto decimal («15.0», «12.5», «11,2» mezclado con coma) frente al resto del documento en coma. Los capturados del tablero usan «11.23 billones» y «0.5M».
  - La Figura 17 no marca el período de referencia ni el promedio (160,2 Mt); la 18 debería mostrar cuánto es de biomasa y cuánto de energía; la Figura 23 solo repite una recta.
  - Las Figuras 11 a 16 son capturas de pantalla extensas que aportan poco al texto. La Figura 15 «Panel de supuestos» es una captura de la página «Dinero» completa.
  - La Figura 8 muestra la barra «Deploy» de Streamlit en modo desarrollo; la Figura 9 superpone el rótulo «docker compose up» sobre un recuadro.
  - La Figura 20 se cita antes que la 19 (§10.3 antes de §10.4); las figuras de resultados provienen de capturas del tablero sin escala legible en el mapa.
  - Las «Fuente: elaboración propia» de tablas y figuras sin indicar el archivo y la fecha de datos.
- Evidencia: imágenes de `docs/informes/tesis/img/`.
- Corrección exigida: unificar el formato numérico, recortar capturas y numerar y citar las figuras en orden.

### O34 · MENOR · Redacción académica
- Ubicación: Resumen; §3.6; §8.9; §10.8; §11.4.
- Cita: «tolerante a fallos»; «una decisión de ingeniería madura»; «lejos de ser una limitación»; «La transición energética no depende solo …»; «el beneficio bruto asociado es elevado».
- Problema: el registro es a veces autocomplaciente y grandilocuente («decisión de ingeniería madura», «convierte la incertidumbre … en herramienta», «Esa es, en última instancia, la contribución…»). Se mezclan la primera persona del plural («se calcula») y construcciones impersonales con el yo («el alumno», «el autor») y una excepción: «corresponde declarar» (§2.6).
  - Anglicismos innecesarios: *backoff*, *fail-fast*, *scraping*, *bundle*, *pipeline*, *healthchecks*, *webhook*, *fallback*, *hash*, *stack*, *commit*, *pull request*.
  - Expresiones coloquiales («trampas reales», «Sitios difíciles»).
  - «Billones» se usa en el sentido hispano (10¹²) y en el abstract inglés como *trillion*; hay que indicarlo.
  - Las conclusiones parciales repiten lo dicho en el capítulo.
- Evidencia: textos citados.
- Corrección exigida: sobriedad, persona gramatical única, reemplazo de anglicismos por términos en castellano o cursiva con glosa.

### O35 · MENOR · Estructura de TFG
- Ubicación: Resumen (en español y en inglés).
- Problema: el resumen incluye resultados numéricos sin sus calificaciones (sin f = 50 % ni los 16 distribuidoras efectivas), describe «28 distribuidoras» en lugar de 25 y no incluye limitaciones. El abstract en inglés es una versión recortada, sin mencionar la validación. Las palabras clave incluyen «SSH» y «Docker», que no son temas de investigación.
- Evidencia: Resumen y Abstract.
- Corrección exigida: reescribir con objetivo, método, resultado, limitaciones y conclusión, y las mismas cifras en ambos idiomas.

### O36 · MENOR · Coherencia interna
- Ubicación: Tabla 1; §2.2; §2.3.
- Problema: Tabla 1 menciona 17 días de trabajo efectivo y 63 días calendario (diapositiva 7), pero hay 8 fases con solapamientos (fases 4/5 el 5/10; 6/7 el 27–28/10) y un salto sin fase entre 24 y 29/09. La fase 8 («11/11») es un solo día. La diapositiva 7 agrupa en 4 etapas, y la nota dice «8 fases». «Documentación de cierre» incluye una «fe de erratas» de un informe que se declara aparte.
- Evidencia: Tabla 1 y diapositiva 7.
- Corrección exigida: homogeneizar fases y fechas entre escrito y diapositiva.

### O37 · MENOR · Veracidad / Coherencia
- Ubicación: §1.1 y §6.1; Anexo A.
- Cita: «se mantiene vigente por sí solo» (§11.4); «actualiza semanalmente de forma autónoma» (§11.1).
- Problema: la afirmación de autonomía no se sostiene con evidencia de operación sostenida.
  - La carpeta `data/raw` contiene 9 pares de descargas con fechas dispersas: 4/10 (2 veces), 5/10 (3), 31/10, 2/11 (2) y 11/11. Solo una corrida programada documentada (11/11 06:00). El cambio a ejecución semanal es de noviembre de 2026, con una sola corrida semanal posible entre el cambio y la entrega.
  - No hay evidencia de operación sostenida de semanas en producción. La captura de la alerta de ENERSA muestra una corrida del 11/11 06:30.
  - No se informa cuántas veces falló una fuente o se activó la segunda pasada.
- Evidencia: nombres de archivos en `data/raw/` (`20261111060001_datos_bolsa_granos_cba.csv`, etc.).
- Corrección exigida: reformular «autónomo» o aportar los registros de varias corridas semanales, fallos y recuperaciones.

### O38 · MENOR · Veracidad
- Ubicación: §6.2; §6.4.
- Cita: «Taxonomía de 49 entradas».
- Problema: no pude confirmar con certeza el conteo de entradas (conté unas 51 líneas de definición en `crop_taxonomy.py`, algunas son estructura). NO VERIFICABLE con rigor. Tampoco queda claro cuántos cultivos fueron descartados por no tener coeficientes (por ejemplo, alpiste en MAGyP, que figura en los datos crudos); §6.4 dice que «se informa el impacto» pero la tesis no cuantifica qué parte de la producción total queda fuera del cálculo.
- Evidencia: `etl/reference/crop_taxonomy.py`; `datos_estimaciones.csv` con «Alpiste».
- Corrección exigida: confirmar el número y cuantificar la producción excluida.

### O39 · MENOR · Veracidad / Redacción
- Ubicación: §10.4; diapositiva 21.
- Cita: «El trigo tiene un peso mayor que su participación en la producción».
- Problema: se afirma sin mostrar la participación en producción de cada cultivo. Una tabla con producción, IC, FR y energía por cultivo lo respaldaría. El punto sobre el maíz y el trigo en la Tabla 5 es correcto en dirección, pero debe mostrarse.
- Evidencia: parquet, `Produccion (Tn)` por cultivo; la tesis no incluye la tabla.
- Corrección exigida: agregar la tabla de producción vs energía por cultivo.

### O40 · MENOR · Metodología / Rigor
- Ubicación: §6.8 (anualización); POL-PERIOD-001.
- Cita: «un departamento sin registro en una campaña cuenta como cero».
- Problema: se confunde ausencia de dato con producción nula; en la práctica puede ser un faltante, lo cual contradice POL-MISSING-001 («un faltante es un faltante»). La regla de completitud del 80 % depende de la mediana de campañas previas. El período incluye la sequía de 2022/23 (111 Mt) y una campaña récord (≈198 Mt en 2025/26, Figura 17) sin discusión del sesgo; la «mediana de campañas» no se justifica con otros horizontes.
- Evidencia: Figura 17 y §6.8.
- Corrección exigida: justificar el tratamiento y mostrar la sensibilidad al horizonte (3, 5, 10 campañas).

### O41 · MENOR · Honestidad y limitaciones
- Ubicación: §11.2.
- Problema: faltan limitaciones que el propio análisis revela: dispersión y calidad de las tarifas (O5), vigencias mezcladas (O7), validación externa ausente (O2), homogeneidad de coeficientes importados (O22), logística, estacionalidad y demanda (O8), sin pruebas de contrato con las fuentes y dependencia del parser frente a cambios de portal. «Cooperativas» figura, pero sin cuantificar. El impacto de las provincias sin resultado (O3) tampoco figura.
- Evidencia: §11.2 enumera 7 limitaciones, ninguna de las anteriores.
- Corrección exigida: ampliar la lista y vincularla a los resultados.

### O42 · MENOR · Justificación de decisiones técnicas / Rigor
- Ubicación: §5.3; §6.3.
- Problema: umbrales sin justificación empírica: rango de 30–2.000 $/kWh en pesos nominales (queda obsoleto con la inflación), factor de cambio de ¼ a 4 (la inflación anual argentina hace que un cambio de 4 veces pase sin alarma, y el 50 % de `salto_tarifa` es arbitrario), puntajes +3, +1, −2 del parser, el 5 % de fallos, el 80 % de completitud, las 192 horas. La regla de reconciliación «mayor producción» (§6.3) se justifica con un argumento de declaraciones juradas («tiende a subestimarse») no respaldado con evidencia propia; sesga hacia arriba por construcción. Las discrepancias entre fuentes se guardan pero no se analizan en el texto.
- Evidencia: constantes en `tariff_parser.py` (`PRICE_MIN/PRICE_MAX`), `scrape_tarifas.py` (`MAX_CHANGE_FACTOR`), `data_checks.py`.
- Corrección exigida: justificar cada umbral (calibración con datos) y reportar la magnitud del sesgo de la regla de «mayor producción» con los 3.298 descartes.

### O43 · MENOR · Presentación de defensa
- Ubicación: notas del orador (todas las diapositivas).
- Problema: las notas son telegráficas, sin guion de tiempos; no hay una estimación de minutos por sección. La nota de la diapositiva 19 dice «Hacer clic en las imágenes para ampliarlas» (depende de un lightbox, que no funciona en un PDF proyectado). La diapositiva 1 dice «Presentarse». No hay diapositiva de referencias ni de preguntas esperables. Las notas sostienen cifras («el trigo pesa más …») sin respaldo en lámina.
- Evidencia: atributos `data-notes` en `presentacion.html`.
- Corrección exigida: agregar un guion con tiempos, una diapositiva de referencias clave y un apéndice con respuestas a objeciones previsibles.

### O44 · MENOR · Citas y referencias
- Ubicación: §1.1 (WISDOM); §1.7.1.
- Cita: «el estudio WISDOM Argentina (FAO, 2009), actualizado en 2020»; «En 1995, tras un ataque de captura de contraseñas en la red de la Universidad Tecnológica de Helsinki, Tatu Ylönen diseñó SSH».
- Problema: la historia de SSH y la mención de WISDOM carecen de cita puntual con página. La nota de WISDOM como «dendroenergía» no se sustenta (la fuente principal sí contempla residuos agrícolas), y la referencia de 2020 no tiene URL. «Ylonen (1996)» sobre un hecho histórico de 1995 debe verificarse. También, Brooker (2015) y Fowler (2006) son blogs y Wiggins (2011) un sitio web: fuentes no revisadas por pares sosteniendo decisiones de diseño.
- Evidencia: lista de referencias y §1.1.
- Corrección exigida: citar con página y reemplazar fuentes no arbitradas cuando se use como respaldo.

### O45 · MENOR · Estructura de TFG
- Ubicación: Capítulos 6 a 10; Anexo A.
- Problema: faltan elementos de rigor del dominio: coherencia dimensional explícita (unidades de cada columna en Tabla 11: «Beneficio (miles de M$)» es inusual; usar millones de pesos o $·10⁹), comparación del orden de magnitud con producción eléctrica agroindustrial real, y el listado de unidades en el Anexo B no incluye t, kg, GWh, TWh. El «Inventario de unidades» que se menciona en la fase 7 de la Tabla 1 no se incluye en el escrito. El precio en pesos corrientes de noviembre de 2026 y su conversión a una moneda estable (USD) no se discuten, a pesar de que la inflación hace poco interpretable «11,2 billones» sin referencia.
- Evidencia: Tabla 1 (fase 7), Anexo B.
- Corrección exigida: agregar el inventario de unidades, expresar el beneficio también en USD con la cotización utilizada, y verificar la coherencia dimensional de cada fórmula.

---

## TABLA RESUMEN

**Por severidad**

| Severidad | Cantidad | Observaciones |
|---|---|---|
| BLOQUEANTE | 3 | O1, O2, O3 |
| MAYOR | 24 | O4–O27 |
| MENOR | 18 | O28–O45 |
| **Total** | **45** | |

**Por dimensión (dimensión principal de cada observación)**

| Dimensión | Cantidad | Observaciones |
|---|---|---|
| 1. Estructura de TFG | 3 | O24, O35, O45 |
| 2. Justificación de decisiones técnicas | 2 | O11, O42 |
| 3. Estado del arte | 1 | O10 |
| 4. Metodología | 1 | O14 |
| 5. Rigor del modelo de dominio | 7 | O2, O4, O5, O8, O9, O40, O1* |
| 6. Veracidad | 8 | O3, O12, O13, O16, O20, O30, O31, O38 |
| 7. Coherencia interna | 6 | O17, O18, O28, O32, O36, O37 |
| 8. Citas y referencias | 3 | O22, O23, O44 |
| 9. Figuras, tablas y listados | 2 | O6, O33 |
| 10. Redacción académica | 1 | O34 |
| 11. Presentación de defensa | 4 | O25, O26, O27, O43 |
| 12. Honestidad y limitaciones | 3 | O15, O19, O41 |

\* O1 se cuenta en rigor del modelo y honestidad; O6, O7, O21 y O39 cruzan veracidad y figuras con rigor. La suma de la tabla por dimensión principal es 41; las cuatro restantes (O6, O7, O21, O39) están contadas en dos dimensiones y no se suman dos veces al total de 45.

---

### Qué no pude verificar (NO VERIFICABLE)
- Los 156 casos de prueba, los cuatro segundos de ejecución y que «pasan». No ejecuté `pytest`.
- Las cifras de commits (203, 25 fusiones, 52 de agente), el commit `63cbb88` y los −5.764 líneas en 161 archivos, que requieren git.
- Todo el servidor de producción: VPS, Caddy, ufw, Tailscale, certificados SSH, `deploy-gate`.
- Los tiempos y recursos de §8.8 (30 min, 1 GB, 0,5 GB/año).
- La veracidad de la ficha técnica del PP30 (1,0 kg/kWh, 22 kW) contra el documento del fabricante.
- El número exacto de 49 entradas de la taxonomía.

### Qué sí verifiqué y coincide
- El parquet anual: 2.421 filas, 25 columnas, 332 departamentos, 15 provincias, 15 cultivos, 38,0 Mha, 141,7 Mt de grano, 160,2 y 80,1 Mt, 80,12 TWh, 519.655 equipos, ahorro 7,17, crédito 4,07 y beneficio 11,23 billones, 99,3 % con tarifa, 24,3 % con inyección estimada, y el ranking por provincia y por departamento.
- Las 110.819 filas y 33 columnas del histórico, los 3.298 descartes, las 57 campañas, las 933 filas y las vigencias del historial tarifario (2024-07 a 2026-11) y la mediana 0,913 sobre 15 distribuidoras.
- 25 de 28 extraídas, 11 desde el portal nacional y 14 desde fuentes propias.
- Las 120 funciones de prueba y su reparto por archivo, y los conteos de líneas por directorio de Tabla 3 (las filas, no el total).
- Los umbrales de reintentos, 5 % de fallos, 1,5 s entre solicitudes, 60 s de segunda pasada, `ofelia` semanal `0 0 6 * * 1`, 192 horas, CI con tres trabajos y `--match-head-commit`.
- La coherencia aritmética del ejemplo de 10.000 t de maíz y de la sensibilidad (6,7–15,7 billones).

### Critical Files for Implementation
- C:\dev\optimia\docs\informes\tesis\tesis.md
- C:\dev\optimia\docs\informes\tesis\presentacion.html
- C:\dev\optimia\docker-compose.yml
- C:\dev\optimia\data\reference\20261111062233_tarifas.json
- C:\dev\optimia\docs\02_metodologia\decisiones.md