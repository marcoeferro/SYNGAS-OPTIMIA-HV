flowchart LR

CBA --> Extract
MAGYP --> Extract

Extract --> Transform
Transform --> DuckDB
DuckDB --> Dashboard