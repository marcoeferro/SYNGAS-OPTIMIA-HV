# Ronda 8: triage

Evaluador: agente nuevo (tipo `Plan`, modelo `sonnet`), con el mismo prompt. Veredicto: **Desaprobado** (3 bloqueantes, 25 mayores, 13 menores). Reprodujo el script de sensibilidad, los 157 casos y las cifras de las Tablas 14 a 17.

Leyenda: **A** = aceptada y corregida; **P** = en parte; **R** = rechazada con fundamento; **AU** = requiere al autor; **S** = cambio del sistema no autorizado (declarado).

| Obs. | Sev. | Decisión | Qué se hizo |
|---|---|---|---|
| O1 | B | AU | Referencias de los coeficientes: siguen pendientes del autor. |
| O2 | B | A | Se retiró «estimación central» para la mediana: la respuesta a P2 es el rango, sin valor puntual ni interpretación probabilística. |
| O3 | B | P | El objetivo general ya se reformuló en la ronda 7; demostrar corridas semanales en el servidor requiere operación real (autor). |
| O4 | M | P | Ya declarado en la ronda 7 (sin paquete congelado); sigue como pendiente 10. |
| O5 | M | A | Verificado: hay pruebas con valor para 21 de 25 distribuidoras (antes decía 16). Corregidos 2.3, 2.8, Tabla 10 y diapositiva 4. |
| O6 | M | A | Verificado en el PDF real: ESJ repite 153,2696 para el generador (el cociente 1,00 es correcto); el fragmento de prueba usa 150,0 a propósito. Declarado. |
| O7 | M | S/R | Columna por encabezado y homogeneización: pendientes del sistema; el precio estacional ya figura como trabajo futuro. |
| O8 | M | S | Regla de reconciliación: pendiente 2. |
| O9 | M | AU | Requiere una fuente verificable para el trigo y el sorgo. |
| O10 | M | P | Se retiró «respaldada»; ahora es «cota superior del rango citado», con la lectura de 30–35 % de Nunes. El valor por defecto es S. |
| O11 | M | A | Se declara que la estabilidad del orden es en buena parte consecuencia del diseño. |
| O12 | M | A | Escritura no atómica declarada (3.3). |
| O13 | M | A | Las invariantes se presentan como controles de implementación, no de plausibilidad. |
| O14 | M | R | Ya declarado (igual que en la ronda 7, O20). |
| O15 | M | R | SSH: pedido explícito del autor. |
| O16 | M | R | Igual que en la ronda 7, O23–O25. |
| O17 | M | R | Igual que en la ronda 7, O22. |
| O18 | M | A | «Están programados para recalcularse»; «está diseñada para mantener actualizada». |
| O19 | M | A | Diapositiva y notas: infraestructura «No cumplido (indicador)». |
| O20 | M | A | Notas: 14,0 billones y «cuatro» supuestos. |
| O21 | m | A | Notas: «157 casos (156 en la integración continua)». |
| O22 | M | R | En la ronda 6 se reemplazaron las capturas por tablas a pedido de otro evaluador; la demostración en vivo depende del tiempo de la mesa. |
| O23 | m | R | Ver la ronda 7, O40. |
| O24 | m | A | Título: «Los diez departamentos principales»; nombre completo. |
| O25 | M | A | Conclusión de 2.9 alineada con 2.5. |
| O26 | m | A | `scripts/`: 145 líneas; total 11.501. |
| O27 | m | R | Redondeo por fila (2,45 → 2,5); sin cambio. |
| O28 | m | R | La base (Anexo E, 205 entradas) está indicada en la frase. |
| O29 | m | P | Mayúscula corregida; el Resumen se mantiene por las precisiones que exigieron rondas anteriores. |
| O30 | m | R | Formato menor; las URL de fuentes institucionales se mantienen. |
| O31 | M | AU | Adjuntar las páginas de FAO e IRENA (pendiente 3 del autor). |
| O32 | M | R | Ya declarado como parámetro de escenario (6.7). |
| O33 | M | S | Correcciones del sistema pendientes de la decisión del autor. |
| O34 | m | P | Figuras 6, 20 y tornado: «escenario de referencia» en lugar de «central» (regeneradas). El resto se mantiene. |
| O35 | m | R | Anglicismos glosados; estilo aceptado en rondas anteriores. |
| O36 | m | A | Guías de la cátedra agregadas a las referencias y citadas. |
| O37 | M | A | Objetivo general: «departamentos argentinos con producción registrada de cultivos extensivos». |
| O38 | m | A | La frase de 141,7 Mt se acota a los 15 cultivos reconciliados. |
| O39 | M | R | Ya declarado como no verificable (8.4–8.5). |
| O40 | M | R | El intérprete local es Python 3.13 con pandas 3.0, ya declarado; la CI con Python 3.11 corrió 156. |
| O41 | m | R | Ya declarado (sin indexar); la indexación figura en trabajos futuros. |
