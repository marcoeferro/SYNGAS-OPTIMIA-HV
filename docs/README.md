# Documentación

> Índice de toda la documentación del proyecto: qué contiene cada
> documento y en qué orden leerlo. Volver al [README principal](../README.md).

## Por dónde empezar

| Si querés… | Leé, en este orden |
|---|---|
| **Entender qué hace el sistema** (sin conocimientos técnicos) | [Cómo funciona](01_introduccion/como_funciona.md) → [Glosario](01_introduccion/glosario.md) → [Guía del dashboard](05_uso/dashboard.md) |
| **Revisar los cálculos** | [Metodología](02_metodologia/metodologia.md) → [Decisiones](02_metodologia/decisiones.md) → [Fuentes de datos](03_datos/fuentes.md) → [Tarifas eléctricas](03_datos/tarifas_electricas.md) |
| **Instalarlo y operarlo** | [Instalación](05_uso/instalacion.md) → [Ejecutar el ETL](05_uso/ejecutar_etl.md) → [Despliegue](04_arquitectura/despliegue.md) → [Solución de problemas](05_uso/solucion_de_problemas.md) |
| **Modificar el código** | [Arquitectura](04_arquitectura/arquitectura.md) → [Flujo de datos](04_arquitectura/flujo_de_datos.md) → [Contratos de artefactos](03_datos/contratos_de_artefactos.md) → [Tests y controles](06_calidad/tests_y_controles.md) → [Decisiones](02_metodologia/decisiones.md) |
| **Saber qué cambió y por qué** | [Reporte de cambios](07_historial/reporte_cambios.md) |

## Contenido

### 01 — Introducción

| Documento | Contenido | Público |
|---|---|---|
| [como_funciona.md](01_introduccion/como_funciona.md) | Qué preguntas responde el sistema, el recorrido de los datos en 6 pasos, qué tan confiables son los resultados y su orden de magnitud | Todos |
| [glosario.md](01_introduccion/glosario.md) | Definición de cada término (biomasa, IC, MS, PP30, campaña, distribuidora, ETL, Parquet…) | Todos |

### 02 — Metodología

| Documento | Contenido | Público |
|---|---|---|
| [metodologia.md](02_metodologia/metodologia.md) | Fórmulas de biomasa, energía y dinero; coeficientes por cultivo; asignación de tarifas; período de referencia; ejemplo numérico; limitaciones | Técnico / revisor |
| [decisiones.md](02_metodologia/decisiones.md) | Registro de decisiones con código `POL-…`: qué se decidió, por qué y dónde está en el código | Técnico / revisor |

### 03 — Datos

| Documento | Contenido | Público |
|---|---|---|
| [fuentes.md](03_datos/fuentes.md) | Fuentes agrícolas (MAGyP, Bolsa de Córdoba), la descartada (Bolsa de Buenos Aires) y las pendientes | Todos |
| [tarifas_electricas.md](03_datos/tarifas_electricas.md) | Qué tarifa se usa, cómo se obtiene, estado de las 28 distribuidoras, carga manual y problemas conocidos | Todos / operador |
| [contratos_de_artefactos.md](03_datos/contratos_de_artefactos.md) | Cada archivo que genera el sistema: ruta, formato y columnas | Desarrollador / integrador |
| [modelo_de_datos.md](03_datos/modelo_de_datos.md) | Diagrama de las tablas y sus relaciones | Desarrollador |

### 04 — Arquitectura

| Documento | Contenido | Público |
|---|---|---|
| [arquitectura.md](04_arquitectura/arquitectura.md) | Componentes, carpetas del código, decisiones de diseño y tecnologías | Desarrollador |
| [flujo_de_datos.md](04_arquitectura/flujo_de_datos.md) | Las 10 etapas del ETL y el recorrido de un registro | Desarrollador / revisor |
| [ciclo_de_vida_de_los_datos.md](04_arquitectura/ciclo_de_vida_de_los_datos.md) | Qué archivos se conservan, cuáles se regeneran, limpieza del disco | Operador |
| [despliegue.md](04_arquitectura/despliegue.md) | Servicios Docker, horario del ETL, variables, recursos, seguridad, dominios necesarios, migración a la nube | Operador |
| [propuesta_estructura_monorepo.md](04_arquitectura/propuesta_estructura_monorepo.md) | Estructura de carpetas biomasa + solar, tipos de test y flujo fork → PR → deploy | Desarrollador |

### 05 — Uso

| Documento | Contenido | Público |
|---|---|---|
| [instalacion.md](05_uso/instalacion.md) | Instalar con Docker o con Python, actualizar y detener | Operador |
| [ejecutar_etl.md](05_uso/ejecutar_etl.md) | Correr el ETL, opciones, reintentos, archivos generados, logs | Operador |
| [dashboard.md](05_uso/dashboard.md) | Qué muestra cada página del dashboard y cómo leerla | Todos |
| [solucion_de_problemas.md](05_uso/solucion_de_problemas.md) | Errores conocidos y cómo resolverlos | Operador |

### 06 — Calidad

| Documento | Contenido | Público |
|---|---|---|
| [tests_y_controles.md](06_calidad/tests_y_controles.md) | Tests automáticos, CI, controles de datos, alertas y qué hacer ante una | Desarrollador / operador |

### 07 — Historial

| Documento | Contenido | Público |
|---|---|---|
| [reporte_cambios.md](07_historial/reporte_cambios.md) | Registro histórico de errores encontrados y correcciones (octubre de 2026). No describe el estado actual: para eso, el resto de los documentos | Revisor |

### Informes

`informes/` contiene informes de avance del proyecto (documentos
académicos, con su propio formato). No forman parte de la documentación
técnica.

## Otros README del repositorio

- [`data/reference/cuadros_manuales/README.md`](../data/reference/cuadros_manuales/README.md):
  cómo cargar a mano un cuadro tarifario.

## Para asistentes de IA (LLM)

Si sos un modelo de lenguaje leyendo este repositorio:

1. **Contexto general**: [como_funciona.md](01_introduccion/como_funciona.md)
   y [glosario.md](01_introduccion/glosario.md).
2. **Cálculos y su justificación**: [metodologia.md](02_metodologia/metodologia.md)
   y [decisiones.md](02_metodologia/decisiones.md). Los códigos `POL-…`
   aparecen citados en el código fuente.
3. **Estructura del código**: [arquitectura.md](04_arquitectura/arquitectura.md)
   (tabla de componentes por carpeta) y
   [flujo_de_datos.md](04_arquitectura/flujo_de_datos.md) (etapa → módulo).
4. **Esquemas de los archivos**: [contratos_de_artefactos.md](03_datos/contratos_de_artefactos.md).
5. **Tarifas** (la parte más compleja del extractor):
   [tarifas_electricas.md](03_datos/tarifas_electricas.md).
6. **Operación y errores**: [05_uso/](05_uso/) y
   [tests_y_controles.md](06_calidad/tests_y_controles.md).

Reglas útiles:

- La fuente de verdad es el **código**; si un documento lo contradice,
  confiar en el código y señalar la diferencia.
- [reporte_cambios.md](07_historial/reporte_cambios.md) es **histórico**:
  las partes marcadas **[Superado]** ya no aplican.
- No modificar `docs/informes/`.
- Los valores de tarifas y totales de los documentos son de octubre de
  2026; los vigentes están en `data/reference/*_tarifas.json` (el más
  reciente) y en `data/processed/`.
