# Cómo contribuir

El repo principal es `marcoeferro/optimia`. Cada tesista trabaja en **su
fork** y entra código sólo por **pull request** a `main`.

## Primera vez

```bash
# 1. Forkear desde GitHub (botón "Fork") y clonar TU fork
git clone https://github.com/<tu-usuario>/optimia.git
cd optimia
git remote add upstream https://github.com/marcoeferro/optimia.git

# 2. Entorno
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[all]"
pre-commit install
cp .env.example .env    # y completar
```

## Cada cambio

```bash
git fetch upstream
git switch -c mi-cambio upstream/main
# ... código + tests ...
pytest                  # unit + integration + regression + e2e
git push -u origin mi-cambio
```

Después abrir el PR de `tu-fork:mi-cambio` → `marcoeferro/optimia:main`.

## Qué pasa con el PR

1. El CI (`.github/workflows/ci.yml`) corre lint, tests por tipo y el build
   de la imagen.
2. CODEOWNERS pide la revisión del dueño de cada carpeta.
3. Con los checks en verde y la aprobación, se mergea. Para que se mergee
   solo, tocar **Enable auto-merge** en el PR (los PR desde forks no
   pueden usar el job `automerge` del CI porque su token es de sólo lectura).
4. El merge a `main` dispara `deploy.yml`: le pide el deploy a la API de Dokploy, que
   reconstruye y despliega (ver `deploy/README.md`).

## Dónde va cada cosa

| Qué | Dónde |
|---|---|
| Código que corre en producción | `src/optimia_hv/<dominio>/` |
| Código usado por los dos dominios | `src/optimia_hv/comun/` |
| Páginas del dashboard | `src/optimia_hv/dashboard/vistas/<dominio>/` |
| Tests | `tests/<tipo>/<dominio>/` (ver `tests/README.md`) |
| Notebooks y scripts de figuras | `analisis/<dominio>/` |
| Parámetros | `config/` |
| Secretos | `.env` (nunca en git) |
| Datos y figuras generadas | `data/`, `outputs/` (fuera de git) |

## Configuración del repo principal (dueño)

- `Settings → Branches → main`: exigir PR, 1 aprobación y los checks
  `tests` e `imagen`; bloquear push directo y force-push.
- `Settings → General → Allow auto-merge`: activado.
- `Settings → Actions → Fork pull request workflows`: exigir aprobación
  para colaboradores externos nuevos.
- Secretos de deploy: ver `deploy/README.md`.
