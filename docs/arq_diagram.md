
architecture-beta

group sources(cloud)[Fuentes de Datos] service cba_csv(server)[CBA CSV] in sources service magyp_csv(server)[MAGYP CSV] in sources

group etl(server)[Pipeline ETL] service extractors(server)[Extractores] in etl service transformers(server)[Transformers] in etl service loaders(server)[Loaders] in etl

group storage(disk)[Almacenamiento] service raw_dir(disk)[RAW] in storage service ref_dir(disk)[REFERENCE] in storage service interim_dir(disk)[INTERIM] in storage service processed_dir(disk)[PROCESSED] in storage service audit_dir(disk)[AUDIT] in storage

group serving(database)[Capa de Servicio] service duckdb_engine(database)[DuckDB Engine] in serving service streamlit_app(server)[Streamlit Dashboard] in serving

group consumers(internet)[Consumidores] service browser(internet)[Browser] in consumers

cba_csv:R --> L:extractors magyp_csv:R --> L:extractors extractors:R --> L:raw_dir raw_dir:R --> L:transformers ref_dir:R --> L:transformers transformers:R --> L:interim_dir transformers:R --> L:processed_dir transformers:R --> L:audit_dir

processed_dir:R --> L:duckdb_engine audit_dir:R --> L:duckdb_engine

duckdb_engine:R --> L:streamlit_app streamlit_app:R --> L:browser