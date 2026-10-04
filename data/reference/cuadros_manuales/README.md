# Cuadros tarifarios cargados a mano

Para distribuidoras cuya fuente bloquea la descarga automática, guardar el
cuadro oficial en una carpeta con el código de la distribuidora
(ver `etl/reference/distribuidoras.py`), por ejemplo:

```
cuadros_manuales/EPEC/cuadro_tarifario_2026_09.pdf
```

Formatos: PDF, XLSX, XLS o ZIP. Incluir el año y mes en el nombre
(`AAAA_MM`) para que la vigencia se reconozca aunque el texto no la declare.
