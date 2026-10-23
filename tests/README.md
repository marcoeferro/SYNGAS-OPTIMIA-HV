# Tests

Cada carpeta es un tipo de test. `tests/conftest.py` les pone el marker
según la carpeta, así se puede correr un tipo solo: `pytest -m unit`.

| Carpeta | Qué prueba | Red | Corre en | Bloquea el merge |
|---|---|---|---|---|
| `unit/` | funciones sueltas (parseo, cálculos, métricas) | no | cada PR | sí |
| `integration/` | pipeline completo con datos de `fixtures/` y `tmp_path` | no | cada PR | sí |
| `regression/` | métricas del modelo sobre un dataset fijo vs. umbral | no | cada PR | sí |
| `e2e/` | el dashboard arranca y renderiza | no | cada PR | sí |
| `contract/` | APIs externas reales siguen respondiendo igual | **sí** | nightly | no |

- `pytest` a secas corre todo menos `contract`.
- `pytest -m contract` corre sólo los de contrato (necesitan `.env`).
- Dentro de cada tipo, una subcarpeta por dominio: `biomasa/`, `solar/`,
  `comun/`, `dashboard/`.
- `fixtures/<dominio>/`: archivos chicos y fijos (respuestas de API
  grabadas, CSV recortados). Nada de datos reales completos.
