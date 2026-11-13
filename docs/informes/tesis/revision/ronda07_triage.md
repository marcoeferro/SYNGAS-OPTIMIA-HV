# Ronda 7: triage

Evaluador: agente nuevo (tipo `Plan`, modelo `sonnet`), con el mismo prompt que la ronda 6. Veredicto: **Desaprobado** (3 bloqueantes, 27 mayores, 15 menores). Verificó con el intérprete del repositorio la mayoría de las cifras de las Tablas 6, 10 y 14 a 17 y las medianas del Monte Carlo.

Leyenda: **A** = aceptada y corregida; **P** = corregida en parte; **R** = rechazada con fundamento; **AU** = requiere al autor; **S** = requiere un cambio del sistema (no autorizado; declarado).

| Obs. | Sev. | Decisión | Qué se hizo |
|---|---|---|---|
| O1 | B | AU | Referencias completas de los coeficientes: no están en los informes de avance (verificado); no se fabrican. |
| O2 | B | A | Monte Carlo rehecho con tope respaldado (30–40 % y 10–40 %): 40–61 TWh (mediana 49) y 16–57 TWh (mediana 35). Se retiró «que admite la bibliografía» para 30–50 %; 0,5 pasa a ser «sin respaldo». Tornado y figuras regenerados. |
| O3 | B | A | Objetivo general: «dejar preparado para su operación periódica». Objetivo 6: «No cumplido en su indicador». |
| O4 | M | P | Variante FR trigo = 1,2 informada como escenario alternativo (59,5 TWh); no se reemplaza sin una fuente local verificable. |
| O5 | M | A | La mediana del Monte Carlo pasa a ser la estimación central; el escenario de referencia se declara «cota superior respaldada». |
| O6 | M | A | La robustez del orden se acota a los supuestos de independencia; se agrega la regla de reconciliación alternativa como segunda prueba. |
| O7 | M | P | Divergencia con las guías de la cátedra (inyección 35–65 %) incorporada en «Origen del trabajo». Indexación por IPC y precio estacional quedan como trabajo futuro (ya listados). |
| O8 | M | S | Selección de columna por encabezado: pendiente del sistema (ya declarado). |
| O9 | M | A | Premisa del combustible no aprobado en el Resumen, el Abstract y la diapositiva de resultados. |
| O10 | M | R | Ya declarado (Secciones 3.4 y 6.7, límite del art. 4 en 12.3); acotar por demanda requiere datos que no existen. |
| O11 | M | A | Se corrige: los identificadores `POL-…` no se citan en el código. |
| O12 | M | A | Frases de reproducibilidad corregidas; falta de paquete de datos congelado declarada. |
| O13 | M | A | Frase del script acotada a lo que imprime. |
| O14 | M | P | Defecto de `.dockerignore` declarado en 8.5 y 12.3; corrección pendiente del sistema. |
| O15 | M | A | «157 casos (156 en la última corrida de CI)». |
| O16 | m | A | Diferencia Tabla 4 / Tabla 6 explicada por cambios posteriores al corte. |
| O17 | m | A | 38 % → 39 % en las notas. |
| O18 | m | A | Documentación técnica: 19 archivos, 3.209 líneas. |
| O19 | m | A | «Mayoritariamente»: 155 de 175 (verificado). |
| O20 | M | R | Revisión sistemática: ya declarada como no realizada (1.2, 12.1, 12.3 ítem 16). |
| O21 | M | R | El capítulo se titula «Estado del arte y marco teórico»; 1.5–1.8 son marco teórico deliberadamente. |
| O22 | M | R | Muestreo ciego imposible sin los documentos originales versionados; la validez se declara de consistencia. |
| O23 | M | S | Planificador: cambio del sistema (pendiente 3). |
| O24 | M | A | Diapositiva: «medido solo frente a CSV». |
| O25 | M | R | Matriz ponderada para decisiones triviales no aporta; los RNF ya se discuten en la Tabla 5. |
| O26 | M | S | Prueba de equivalencia del tablero: pendiente 6. |
| O27 | M | R | El autor pidió explícitamente explicar SSH. |
| O28 | M | A | Justificación corregida (una sola en `POL-SOURCE-001`); distribución de diferencias (385 de 1.454 > 100 %, máx. ×834); regla alternativa: 62,3 TWh, 9/10 del top 10, Río Cuarto 1,97 (verificado y agregado al script). |
| O29 | M | A | La causa pasa a ser hipótesis no verificada contra el portal. |
| O30 | m | A | `Retry-After` solo numérico y sin *jitter*, declarado. |
| O31 | m | A | Ventana de plausibilidad en pesos corrientes, declarada. |
| O32 | m | A | Fila de ENERSA sin marcar, declarada. |
| O33 | m | S | Limpieza del repositorio: pendiente 8. |
| O34 | m | AU | Páginas de IRENA/FAO: adjuntar copias (pendiente 3 del autor). |
| O35 | M | P | Afirmaciones sin cita reformuladas («140 Mt» con dato propio; cooperativas; frecuencia de cuadros). |
| O36 | m | R | Numeración 5A/9A y figuras de actividad se mantienen; índice sin páginas por formato Markdown (el PDF lo pagina). |
| O37 | m | R | UNViMe confirmado por el autor. |
| O38 | m | A | Nueva sección «Origen del trabajo». |
| O39 | M | P | Diapositiva de distribución ampliada a diez departamentos; los objetivos se movieron al cuerpo en la ronda 6 a pedido de otro evaluador (observaciones contradictorias). |
| O40 | m | P | Diapositiva 14 rebalanceada. |
| O41 | M | A | Diapositiva del tablero: advierte que abre en 50 % (80 TWh) y que la tesis usa 40 %. |
| O42 | m | R | Ya declarado en 7.1 y Anexo E. |
| O43 | M | S | Correcciones del compose: pendiente 3. |
| O44 | M | AU | Registro de prompts: no existe; se declara (2.7). |
| O45 | m | A | Comprobación dimensional con bases explícitas. |
