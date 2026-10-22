# Metodología — tesis solar

> Cómo se estima la generación de la planta fotovoltaica y cómo se valida
> contra la generación real. El código es la fuente de verdad:
> `src/optimia_hv/solar/`. Para correr el pipeline, ver
> [ejecutar el pipeline solar](../../05_uso/ejecutar_solar.md).

## La planta

| Dato | Valor | Dónde se cambia |
|---|---|---|
| Ubicación | Villa Mercedes, San Luis (−33,6445; −65,4453) | `config/solar.yaml` → `ubicacion` |
| Paneles | 5 × 450 W = **2,25 kWp** | `modelo_15min.potencia_pico_kwp` |
| Inclinación | 35° | `modelo_15min.inclinacion_panel` |
| Inversor | Growatt, eficiencia 93 % | `modelo_15min.eficiencia_inversor` |
| Monitoreo | Portal web `server.growatt.com` (energía diaria y potencia cada 5 min) | `.env` → `GROWATT_*` |

## Fuentes de datos

| Fuente | Qué se usa | Resolución | Módulo |
|---|---|---|---|
| **Growatt** | Energía generada (kWh/día) y potencia instantánea (W) | diaria y 5 min | `extractors/growatt.py` |
| **NASA POWER** | Temperatura a 2 m, humedad relativa, radiación global (kWh/m²/día) | diaria | `extractors/nasa_power.py` |
| **Open-Meteo (archivo)** | Temperatura media, humedad media, radiación (MJ/m² → kWh/m²); y cada 15 min: radiación global, directa, difusa, viento, nubes, presión | diaria y 15 min | `extractors/open_meteo.py` |
| **Open-Meteo (pronóstico)** | Lo mismo, a futuro: 7 días (diario) y 5 días (15 min) | diaria y 15 min | `extractors/open_meteo.py` |

Tratamiento de cada fuente:

- **NASA POWER** publica la radiación con 4-5 días de atraso y marca los
  datos faltantes con `-999`. Se guarda un día sólo si tiene las **tres**
  variables; la corrida diaria revisa los últimos 30 días, así el día se
  completa apenas aparece la radiación.
- **Open-Meteo diario** da la radiación en MJ/m²; se divide por 3,6 para
  tenerla en kWh/m² como NASA y poder compararlas.
- **Growatt diario**: un día en 0 (inversor desconectado o sin reporte) se
  reemplaza por el promedio del día anterior y el siguiente. En la carga
  histórica, si sólo un vecino tiene energía se copia ese valor y el primer
  día de cada mes usa el último valor del mes anterior. En la corrida
  diaria, si todavía no existe el día siguiente, el día queda en 0 y se
  corrige al día siguiente.
- **Growatt intradía**: la potencia viene cada 5 min; la corrida diaria
  guarda un punto cada 15 min (alineado con el modelo) y la validación
  guarda los de 5 min.
- Valores por defecto cuando falta una variable de 15 min (equivalen a los
  `COALESCE` de las consultas originales): viento 2 m/s, nubes 20 %,
  presión 1013,25 hPa, radiación directa 70 % y difusa 30 % de la global.

## Modelo de 15 minutos (actual)

`modelos/modelo_15min.py`. Se aplica igual al **pronóstico** (energía
pronosticada) y al **clima observado** (energía estimada, para validar).

Con radiación en kW/m² (las APIs dan W/m²; se divide por 1000):

1. **Irradiancia efectiva** sobre el panel inclinado β = 35°:

   G_ef = G_dir · (1 + 0,18 · sen β) + G_dif

2. **Temperatura de celda** (modelo NOCT, con atenuación por viento v):

   T_c = T_aire + (G / 0,8) · (NOCT − 20) / 800 · e^(−0,05 · v)

3. **Factores** sobre el performance ratio:

   | Factor | Fórmula | Parámetro |
   |---|---|---|
   | térmico | 1 + γ · (T_c − 25) | γ = −0,0035 /°C |
   | humedad | 1 − 0,002 · HR/100 | |
   | presión | 1 + 0,00005 · (P − 1013,25) | |
   | nubes | 1 − 0,0005 · nubosidad(%) | |

4. **PR dinámico** = PR_base (0,78) × térmico × humedad × presión × nubes.

5. **Energía del intervalo** (kWh):

   E = G_ef · P_pico · η_inv · PR · 0,25 h  (0 si G_ef ≤ 0)

Ejemplo: G_dir = 0,7 y G_dif = 0,3 kW/m², 25 °C, sin viento, humedad ni
nubes, 1013,25 hPa → G_ef = 1,072 kW/m², T_c = 25,04 °C, PR = 0,780,
E ≈ 0,437 kWh en 15 min (≈ 1,75 kW medios). Está calculado en
`tests/unit/solar/test_modelos.py::test_calculo_a_mano` (ver la
observación 5 sobre T_c).

## Modelo viejo (línea de base, diario)

`modelos/modelo_viejo.py`. Con la radiación diaria H en kWh/m² (equivale a
las horas solares pico):

E_día = H · P_pico · η_inv · 0,88 · (1 + γ · (T_media − 25)) · (1 − 0,002 · HR/100)

Se compara contra el modelo de 15 min para mostrar cuánto mejora al
resolver el día en intervalos.

## Validación

`validacion/comparativas.py` arma las tablas modelo vs. real y
`validacion/metricas.py` calcula:

| Métrica | Definición | Lectura |
|---|---|---|
| MAE | media de \|estimado − real\| | error típico, en W o kWh |
| RMSE | raíz de la media de (estimado − real)² | penaliza errores grandes |
| Sesgo | media de (estimado − real) | > 0: el modelo sobreestima |
| Error relativo total | (Σ estimado − Σ real) / Σ real | error en la energía del período |

- **Intradía** (15 min): la energía estimada del intervalo se pasa a
  potencia media (kWh × 1000 × 4 W) para compararla con la potencia de
  Growatt. Los intervalos sin dato de Growatt cuentan como 0 W (igual que
  la consulta original).
- **Diaria** (modelo viejo): las métricas del dashboard excluyen los días
  sin dato de Growatt (0 kWh).

Dónde se ven: dashboard → Solar → *Validación del modelo*, el log de
`run_solar --validar` y los scripts de `analisis/solar/`.

## Observaciones abiertas

Detectadas al unificar los scripts; no se cambiaron para no alterar los
resultados ya obtenidos. Conviene revisarlas en la tesis:

1. **Radiación directa: horizontal vs. normal.** El pronóstico usa
   `direct_radiation` (directa sobre plano horizontal) pero la validación
   usa `direct_normal_irradiance` (DNI, sobre un plano perpendicular al
   sol), que es mayor. Así, la energía estimada para validar y la
   pronosticada no son comparables entre sí. Constante:
   `VARIABLES_15MIN_HISTORICO` en `extractors/open_meteo.py`.
2. **Factor de inclinación fijo.** `1 + 0,18 · sen β` no depende de la
   hora ni de la época del año. Un modelo de transposición (p. ej.
   isotrópico o Hay-Davies, con la posición del sol) captaría la diferencia
   entre invierno y verano.
3. **Umbrales de error.** Falta acordar el error máximo aceptable (fase 0
   de la [propuesta](../../04_arquitectura/propuesta_estructura_monorepo.md));
   hoy `tests/regression/solar/` sólo controla que el modelo no cambie sin
   querer.
4. **Zona horaria.** Los scripts usaban `America/Argentina/San_Luis` y
   `Buenos_Aires` según el caso; las dos son UTC−3 y ahora se usa la de
   `config/solar.yaml` en todas las consultas.
5. **Unidades en la temperatura de celda.** La fórmula NOCT espera G en
   W/m² (T_c = T + G · (NOCT − 20) / 800), pero se le pasa G en kW/m²
   dividido por 0,8: con 1000 W/m² la celda queda sólo 0,04 °C sobre el
   aire en vez de ≈ 31 °C. Así el factor térmico casi no descuenta nada y,
   a pleno sol, el modelo sobreestima ≈ 10 %. La corrección sería usar
   `G_W/m² · (NOCT − 20) / 800`; cambiaría los valores de
   `tests/regression/solar/`.

## Limitaciones

- Una sola planta; los parámetros (PR, γ, NOCT) son de datasheet, no
  ajustados con los datos.
- El portal de Growatt no es una API oficial: si cambia la página, el
  extractor deja de funcionar (lo detecta el test de contrato nocturno).
- El pronóstico de 15 min depende de la calidad del pronóstico de
  nubosidad de Open-Meteo, la principal fuente de error en días variables.
