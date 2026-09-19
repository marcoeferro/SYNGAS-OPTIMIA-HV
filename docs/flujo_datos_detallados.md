architecture-beta
    %% =============================================================
    %% Flujo de Datos — Pipeline ETL detallado
    %% =============================================================

    %% --- Entrada ---
    group input(cloud)[Entrada]
    service cba_in(server)[CBA CSV] in input
    service magyp_in(server)[MAGYP CSV] in input

    %% --- Transformaciones ---
    group transforms(server)[Transformaciones]
    service clean(server)[Normalizar Strings] in transforms
    service geo(server)[Normalizar Geo] in transforms
    service taxonomy(server)[Resolver Taxonomia] in transforms
    service groupby(server)[Agrupar Clave] in transforms
    service reconcile(server)[Reconciliar Fuentes] in transforms
    service biomass(server)[Calcular Biomasa] in transforms
    service flags(server)[Flags Validez] in transforms

    %% --- Validación ---
    group validation(database)[Validacion]
    service invariants(database)[Invariantes] in validation

    %% --- Salida ---
    group output(disk)[Salida]
    service parquet_out(disk)[Parquet] in output
    service audit_out(disk)[Audit] in output

    %% --- Flujo ---
    cba_in:R --> L:clean
    magyp_in:R --> L:clean
    clean:R --> L:geo
    geo:R --> L:taxonomy
    taxonomy:R --> L:groupby
    groupby:R --> L:reconcile
    reconcile:R --> L:invariants
    invariants:R --> L:biomass
    biomass:R --> L:flags
    flags:R --> L:parquet_out
    flags:R --> L:audit_out