"""Análisis de escenarios, sensibilidad y Monte Carlo de la tesis (Secciones 6.3, 6.8 y 10.6).

Lee los artefactos del ETL (no los modifica) y reproduce las cifras de la tesis:
escenarios de fracción retirada, tornado de un supuesto por vez, escenarios
combinados, simulación de Monte Carlo con semilla fija, sensibilidad del factor
residuo/producto del trigo y estabilidad del ranking de departamentos.

Uso:
    python scripts/analisis_sensibilidad.py [--iteraciones 5000] [--semilla 42]

El ETL calcula con f = 0,4 (valor por defecto); los escenarios se obtienen
reescalando, porque el modelo es lineal en f, en el consumo específico y en las
tarifas. El índice de cosecha (IC) entra de forma no lineal: FR = (1 − IC)/IC.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ANUAL = RAIZ / "data/processed/potencial_energetico_anual.parquet"
HISTORICO = RAIZ / "data/processed/biomasa_validos.parquet"
COEFICIENTES = RAIZ / "data/reference/ic_fr.csv"
AUDITORIA = RAIZ / "data/audit/discrepancias_cba_vs_magyp.parquet"
F_SISTEMA = 0.4   # fracción retirada con que calcula el ETL (POL-RECOVERY-001)
F_REFERENCIA = 0.4


def fr(ic):
    return (1 - ic) / ic


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iteraciones", type=int, default=5000)
    ap.add_argument("--semilla", type=int, default=42)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # consolas de Windows (cp1252)

    a = pd.read_parquet(ANUAL)
    ic = pd.read_csv(COEFICIENTES).set_index("Cultivo")["IC"].to_dict()
    tc = a["tarifa_compra_kwh"].to_numpy()
    ti = a["tarifa_inyeccion_kwh"].to_numpy()
    est = a["tarifa_inyeccion_estimada"].to_numpy()
    k_ref = a["kwh_generados"].to_numpy() * F_REFERENCIA / F_SISTEMA
    fac_ic = lambda d: a["Cultivo"].map(lambda c: fr(ic[c] + d) / fr(ic[c])).to_numpy()

    def beneficio(k, alfa=0.6, tiny=ti, escala_tarifa=1.0):
        return np.nansum(k * alfa * tc + k * (1 - alfa) * tiny) * escala_tarifa / 1e12

    base = beneficio(k_ref)
    print(f"Escenario de referencia (f = 0,4): {k_ref.sum() / 1e9:.2f} TWh/año, {base:.2f} billones $/año")

    print("\nEscenarios de fracción retirada")
    for f in (0.1, 0.2, 0.3, 0.4, 0.5):  # 0,5 solo como comparación con el valor por defecto del ETL
        s = f / F_REFERENCIA
        print(f"  f = {f:.1f}: {k_ref.sum() * s / 1e9:6.1f} TWh/año  {base * s:6.2f} billones")

    print("\nTornado (un supuesto por vez, beneficio en billones)")
    filas = {
        "Fracción retirada 30–40 %": (base * 0.75, base),
        "Índice de cosecha ± 0,05": (beneficio(k_ref * fac_ic(0.05)), beneficio(k_ref * fac_ic(-0.05))),
        "Tarifas ± 20 %": (base * 0.8, base * 1.2),
        "Consumo específico 1,3–1,0": (base / 1.3, base),
        "Inyección no publicada 0–compra": (beneficio(k_ref, tiny=np.where(est, 0, ti)),
                                            beneficio(k_ref, tiny=np.where(est, tc, ti))),
        "Materia seca ± 5 %": (base * 0.95, base * 1.05),
        "Autoconsumo 40–80 %": (beneficio(k_ref, 0.4), beneficio(k_ref, 0.8)),
    }
    for nombre, (lo, hi) in filas.items():
        print(f"  {nombre:34s} {lo:6.2f} – {hi:6.2f}")
    print(f"  Sin autoconsumo (alfa = 0):        {beneficio(k_ref, 0.0):6.2f}")
    print(f"  Inyección estimada con 0,734:      {beneficio(k_ref, tiny=np.where(est, tc * 0.734, ti)):6.2f}")

    bajo = beneficio(k_ref * 0.75 * fac_ic(0.05) / 1.3 * 0.95, escala_tarifa=0.8)
    alto = beneficio(k_ref * fac_ic(-0.05) * 1.05, escala_tarifa=1.2)
    print(f"\nCombinado desfavorable: {bajo:.2f} · favorable: {alto:.2f} billones")

    print("\nFactor residuo/producto del trigo")
    for valor in (0.9, 1.2, 1.5):
        fac = np.where(a["Cultivo"] == "trigo", valor / fr(ic["trigo"]), 1.0)
        print(f"  FR = {valor}: {(k_ref * fac).sum() / 1e9:.1f} TWh ({((k_ref * fac).sum() / k_ref.sum() - 1) * 100:+.1f} %)")

    # Monte Carlo: distribuciones uniformes en los rangos del tornado; IC independiente por cultivo.
    # Se corren dos simulaciones que solo difieren en el rango de la fracción retirada:
    # 30–40 % (Nunes et al., 2021: máximo 40 %) y 10–40 % (incluye la restricción por siembra directa).
    cultivos = sorted(a["Cultivo"].unique())
    clave = (a["Provincia"] + "|" + a["Departamento"]).to_numpy()
    deptos_ref = pd.Series(k_ref).groupby(clave).sum()
    top10_ref = set(deptos_ref.nlargest(10).index)
    p = lambda x: np.percentile(x, [5, 50, 95])
    for f_min in (0.3, 0.1):
        rng = np.random.default_rng(args.semilla)
        energia, benef, spearman, top10 = [], [], [], []
        for _ in range(args.iteraciones):
            f = rng.uniform(f_min, 0.4); ce = rng.uniform(1.0, 1.3); ms = rng.uniform(0.95, 1.05)
            t = rng.uniform(0.8, 1.2); alfa = rng.uniform(0.4, 0.8); r = rng.uniform(0, 1)
            d = dict(zip(cultivos, rng.uniform(-0.05, 0.05, len(cultivos))))
            fic = a["Cultivo"].map(lambda c: fr(ic[c] + d[c]) / fr(ic[c])).to_numpy()
            k = k_ref * (f / F_REFERENCIA) * fic / ce * ms
            energia.append(k.sum() / 1e9)
            benef.append(beneficio(k, alfa, np.where(est, tc * r, ti), t))
            deptos = pd.Series(k).groupby(clave).sum()
            spearman.append(deptos.rank().corr(deptos_ref.rank()))
            top10.append(len(set(deptos.nlargest(10).index) & top10_ref))
        print()
        print(f"Monte Carlo, f entre {f_min:.0%} y 40 % ({args.iteraciones} iteraciones, semilla {args.semilla})")
        print(f"  Energía (TWh/año) P5/P50/P95:      {p(energia).round(1)}")
        print(f"  Beneficio (billones) P5/P50/P95:   {p(benef).round(2)}")
        print(f"  Correlación de rangos departamental (mínimo): {min(spearman):.3f}")
        print(f"  Departamentos del top 10 que se mantienen (mínimo / mediana): {min(top10)} / {int(np.median(top10))}")
        print("  (supuesto: errores de IC independientes entre cultivos y multiplicador de tarifas único)")

    b = pd.read_parquet(HISTORICO)
    camp = sorted(b["Campaña"].unique())
    print("\nHorizonte del promedio (escenario de referencia)")
    for n in (3, 5, 10):
        print(f"  {n:2d} campañas: {b[b['Campaña'].isin(camp[-n:])]['kwh_generados'].sum() / n * F_REFERENCIA / F_SISTEMA / 1e9:.1f} TWh/año")
    sin_ultima = b[b["Campaña"].isin(camp[-5:-1])]["kwh_generados"].sum() / 4 * F_REFERENCIA / F_SISTEMA / 1e9
    print(f"  Sin la última campaña: {sin_ultima:.1f} TWh/año")

    # Regla de reconciliación alternativa: preferir la fuente oficial (MAGyP) cuando ambas informan.
    d = pd.read_parquet(AUDITORIA).rename(columns=lambda c: "Campaña" if c.startswith("Campa") else c)
    d = d[d["Campaña"].isin(camp[-5:])].dropna(subset=["produccion_bolsa_cereales_cba", "produccion_magyp_estimaciones"])
    rel = d["diff_rel_produccion"].abs()
    print()
    print(f"Discrepancias BCCBA–MAGyP en el período: {len(d)} claves; |dif.| > 100 %: {(rel > 1).sum()}; "
          f"mediana |dif.| {rel.median():.2f}; máximo ×{rel.max():.0f}")
    d["fac"] = d["produccion_magyp_estimaciones"] / d[["produccion_bolsa_cereales_cba", "produccion_magyp_estimaciones"]].max(axis=1)
    k = ["Provincia", "Departamento", "Campaña", "Cultivo"]
    m = b[b["Campaña"].isin(camp[-5:])].merge(d[k + ["fac"]], on=k, how="left").fillna({"fac": 1.0})
    m["alt"] = m["kwh_generados"] * m["fac"]
    g = m.groupby(["Provincia", "Departamento"])[["kwh_generados", "alt"]].sum() / 5 * F_REFERENCIA / F_SISTEMA / 1e9
    print(f"Regla «preferir MAGyP»: {g['alt'].sum():.1f} TWh/año frente a {g['kwh_generados'].sum():.1f} con la regla del máximo")
    comunes = len(set(g.nlargest(10, "alt").index) & set(g.nlargest(10, "kwh_generados").index))
    print(f"  Top 10 compartido: {comunes} de 10; primero: {g['alt'].idxmax()} ({g['alt'].max():.2f} TWh/año)")


if __name__ == "__main__":
    main()
