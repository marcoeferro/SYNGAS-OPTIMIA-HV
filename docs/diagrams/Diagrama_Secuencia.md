sequenceDiagram
    autonumber
    participant U as Usuario
    participant B as Navegador
    participant S as Dashboard App
    participant F as Parquet
    participant C as Cache

    U->>B: Ingresa a URL
    B->>S: GET /
    S->>F: Carga biomasa_validos.parquet
    F-->>S: DataFrame
    S->>C: Almacena en cache
    S-->>B: HTML + JS
    B-->>U: Dashboard renderizado

    U->>B: Filtra por provincia
    B->>S: Callback filtro
    S->>C: Consulta cache
    C-->>S: Subconjunto filtrado
    S-->>B: Graficos actualizados
    B-->>U: Vista filtrada