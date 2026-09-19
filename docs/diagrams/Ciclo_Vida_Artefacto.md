graph LR
    subgraph Immutable["Inmutables"]
        R[raw/]
        REF[reference/]
    end

    subgraph Derived["Derivados"]
        I[interim/]
        P[processed/]
        A[audit/]
    end

    subgraph Output["Consumibles"]
        D[Dashboard]
        N[Notebooks]
    end

    R --> I
    REF --> I
    I --> P
    I --> A
    P --> D
    P --> N
    A --> N

    R -.Regenerable desde.-> I
    I -.Regenerable desde raw.-> P
    P -.Regenerable desde raw.-> D

    style Immutable fill:#e1f5ff
    style Derived fill:#fff3e0
    style Output fill:#e8f5e9