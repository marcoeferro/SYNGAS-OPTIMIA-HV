# Revisión adversaria de la tesis y la presentación

Registro del proceso de revisión con un evaluador adversario («profesor riguroso») sobre `tesis.md` y `presentacion.html`. El diseño del evaluador y sus fuentes están en `diseno_evaluador.md`, y el prompt usado en cada ronda en `prompt_evaluador.md`. Cada ronda usó un agente nuevo y aislado: solo lectura, sin historial de git, sin acceso a esta carpeta y con un modelo distinto del redactor.

| Ronda | Veredicto | Bloqueantes | Mayores | Menores | Total |
|---|---|---|---|---|---|
| 1 | Desaprobado | 3 | 24 | 18 | 45 |
| 2 | Desaprobado | 4 | 26 | 9 | 39 |
| 3 | Desaprobado | 2 | 27 | 20 | 49 |
| 4 | Aprobado con correcciones obligatorias | 3 | 26 | 13 | 42 |
| 5 | Aprobado con correcciones obligatorias | 3 | 26 | 8 | 37 |
| 6 | Desaprobado | 2 | 21 | 10 | 33 |
| 7 | Desaprobado | 3 | 27 | 15 | 45 |
| 8 | Desaprobado | 3 | 25 | 13 | 41 |
| 9 | Desaprobado | 1 | 14 | 13 | 28 |
| 10 | Aprobado con correcciones obligatorias | 3 | 15 | 8 | 26 |

El triage de cada ronda está en `rondaNN_triage.md`: qué se aceptó y corrigió, qué se corrigió en parte, qué se rechazó con fundamento y qué queda pendiente.

## Pendientes que requieren al autor

1. Agradecimientos (opcional; la sección se retiró por estar vacía).
2. Completar las referencias de los coeficientes agronómicos (`data/reference/ic_fr.csv`), con datos bibliográficos y la página de cada índice de cosecha.
3. Dar acceso al jurado al repositorio y a los informes de avance, y adjuntar las páginas citadas de FAO (2009), IRENA (2023) y Nunes et al. (2021).
4. ~~Confirmar el nombre de la universidad~~: resuelto (Universidad Nacional de Villa Mercedes, UNViMe; director Jonathan Bosso).

## Pendientes que cambian el sistema (decisión del autor)

1. ~~Valor por defecto de la fracción retirada en 0,4, regenerando los artefactos~~: resuelto el 12/11/2026 (artefactos regenerados con los datos del 11/11; mismo total) (`etl/transformers/biomass.py`, `PARAMETROS_PP30_DEFAULT` en `scrape_tarifas.py` y el tablero).
2. Regla de reconciliación sin sesgo, prefiriendo la fuente oficial (`POL-SOURCE-001`).
3. ~~`docker-compose.yml`: ETL sin superusuario, `127.0.0.1:8501:8501` y versión fija de Ofelia~~: resuelto el 12/11/2026. Queda pendiente el acceso del planificador al *socket* de Docker (cron dentro de la imagen) y hacer `chown` de `data/` y `logs/` en el servidor.
4. ~~Eliminar el reintento ante 403, el extractor descartado y `curl_cffi`~~: resuelto. Se retiraron el extractor y la dependencia; el reintento único ante 403 se mantiene y se justifica en la Sección 5.2.
5. Regla de selección de cuadros: preferir la vigencia más reciente (caso REFSA). Elegir la columna por encabezado en lugar de usar la mediana.
6. Prueba de equivalencia entre `apply_supuestos` (tablero) y el ETL.
7. Política de fusión automática: revisión humana obligatoria.
8. Sincronizar `README.md`, la documentación y `pyproject.toml` con la entrega.
9. ~~`.dockerignore`: excluir `.env*`, `logs/` y `.coverage`~~: resuelto el 12/11/2026.
10. Paquete de datos congelado (crudos y cuadros usados) para reproducir las cifras sin depender de fuentes vivas (ronda 7).
