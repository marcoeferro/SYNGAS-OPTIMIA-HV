flowchart TD
    Start([Registro raw]) --> Clean[Normalizar strings]
    Clean --> Geo[Normalizar geografia]
    Geo --> TaxCheck{Esta en taxonomia?}
    TaxCheck -->|No| Fail[Error fail-fast]
    TaxCheck -->|Si| Canon[Obtener nombre canonico]
    Canon --> AggCheck{Grupo tiene agregado?}
    AggCheck -->|Si| KeepAgg[Conservar agregado]
    AggCheck -->|No| KeepComp[Conservar componentes]
    KeepAgg --> Concat[Concatenar fuentes]
    KeepComp --> Concat
    Concat --> Reconcile{Clave en multiples fuentes?}
    Reconcile -->|No| KeepSingle[Conservar]
    Reconcile -->|Si| MaxProd[Seleccionar mayor produccion]
    MaxProd --> Audit[Registrar descarte]
    KeepSingle --> Biomass[Calcular biomasa]
    Audit --> Biomass
    Biomass --> HasIC{Tiene IC?}
    HasIC -->|No| FlagFalse[Flag valido=false]
    HasIC -->|Si| Compute[Calcular residuo]
    Compute --> FlagTrue[Flag valido=true]
    FlagFalse --> Valid[Validar invariantes]
    FlagTrue --> Valid
    Valid --> End([Registro curado])

    style Fail fill:#ffcdd2
    style End fill:#c8e6c9
    style Audit fill:#fff3e0