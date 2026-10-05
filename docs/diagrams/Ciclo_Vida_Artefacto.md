# Ciclo de vida de los artefactos

```mermaid
graph LR
    subgraph Fuente["Descargados (versionados por fecha)"]
        R["raw/<br/>YYYYMMDDHHMMSS_*.csv"]
        T["reference/<br/>YYYYMMDDHHMMSS_tarifas.json"]
        H["reference/<br/>tarifas_historial.csv<br/>(solo se agrega)"]
    end
    subgraph Manual["Mantenidos a mano"]
        IC["reference/ic_fr.csv"]
        CM["reference/cuadros_manuales/"]
    end
    subgraph Derivados["Derivados (regenerables)"]
        P["processed/"]
        A["audit/"]
    end
    subgraph Consumo["Consumidores"]
        D[Dashboard]
        N[Notebook main.ipynb]
    end

    R --> P
    IC --> P
    T --> P
    CM --> T
    T --> H
    P --> D
    A --> D
    T --> D
    H --> D
    P --> N
    R --> A
```

- `processed/` y `audit/` se regeneran con `run_etl --skip-extract --skip-tarifas`.
- El historial de tarifas deduplica por (distribuidora, SHA-256 del documento).
