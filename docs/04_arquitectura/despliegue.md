# Arquitectura de despliegue (Docker Compose)

```mermaid
graph LR
    subgraph Host["Host (Docker Engine)"]
        SCH["scheduler<br/>(Ofelia)"]
        W["etl_worker<br/>(permanente)"]
        J["etl_pipeline<br/>(job manual, perfil etl)"]
        DASH["dashboard<br/>Streamlit :8501"]
        V1[("./data")]
        V2[("./config")]
        V3[("./logs")]
    end
    U[Navegador] -->|HTTP 8501| DASH
    SCH -->|"docker exec según<br/>config/schedule.ini"| W
    W -.rw.-> V1
    J -.rw.-> V1
    W -.ro.-> V2
    J -.ro.-> V2
    W -.rw.-> V3
    DASH -.ro.-> V1
```

- Una sola imagen (`etl-biomasa:latest`) sirve para el ETL y el dashboard.
- El ETL descarga fuentes y tarifas: necesita salida a Internet hacia los
  dominios de `README.md` (sección *Dominios necesarios*).
- El dashboard sólo lee `./data` (montado de solo lectura).
- El navegador del usuario descarga la cartografía base de Plotly desde
  `cdn.plot.ly`; sin acceso a ese CDN los mapas quedan en blanco.
