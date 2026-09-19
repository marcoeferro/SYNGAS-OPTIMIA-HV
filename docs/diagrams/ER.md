erDiagram
    CROP_TAXONOMY {
        string raw_name PK
        string canonical
        bool is_aggregate
    }

    IC_FR_TABLE {
        string Cultivo PK
        float IC
        float FR
        string source
    }

    RAW_CBA {
        string Provincia
        string Departamento
        string Campaña
        string Cultivo
        float Cosechadas
        float Produccion
    }

    RAW_MAGYP {
        string Provincia
        string Departamento
        string Campaña
        string Cultivo
        float Sup_Cosechada
        float Produccion
    }

    PROCESSED {
        string Provincia
        string Departamento
        string Campaña
        string Cultivo
        float Superficie
        float Produccion
        float Rendimiento
        float Residuo_Biomasa
        string fuente
    }

    AUDIT_DESCARTADOS {
        string Provincia
        string Departamento
        string Campaña
        string Cultivo
        float Produccion
        string fuente
    }

    CROP_TAXONOMY ||--o{ RAW_CBA : "normaliza"
    CROP_TAXONOMY ||--o{ RAW_MAGYP : "normaliza"
    RAW_CBA ||--o{ PROCESSED : "transforma"
    RAW_MAGYP ||--o{ PROCESSED : "transforma"
    IC_FR_TABLE ||--o{ PROCESSED : "enriquece"
    PROCESSED ||--o{ AUDIT_DESCARTADOS : "descarta"