# Bolsa de Cereales de Buenos Aires (descartada)
https://www.bolsadecereales.com/datasets

## Columnas
Campaña	Zona	Cultivo	Sembrado (Ha)	Perdido(Ha)	Cosechado(Ha)	Rinde(qq/Ha)	Producción(MTn)

**Nota**: Este Dataset Utiliza ZONAS PAS para discriminar el Territorio las zonas pas son las siguientes:

****Zonas PAS (Panorama Agrícola Semanal)****

La zonificación original del PAS consta de 14 zonas definidas por criterios agroecológicos homogéneos (tipo de suelo, precipitaciones, etc.):

I - NOA (Noroeste Argentino): Incluye provincias de Catamarca, Jujuy, Salta, Santiago del Estero (parte oeste) y Tucumán. 
II - NEA (Noreste Argentino): Comprende Chaco, Formosa y Santiago del Estero (este).
III - Centro-Norte de Córdoba. 
IV - Sur de Córdoba. 
V - Centro-Norte de Santa Fe.
VI - Núcleo Norte: Este de Córdoba, Centro-Sur de Santa Fe y Sudoeste de Entre Ríos.
VII - Núcleo Sur.
VIII - Centro-Este de Entre Ríos.
IX - Norte de La Pampa - Oeste de Buenos Aires. 
X - Centro de Buenos Aires. 
XI - Sudoeste de Buenos Aires - Sur de La Pampa. 
XII - Sudeste de Buenos Aires. 
XIII - San Luis. 
XIV - Cuenca del Salado. 

![alt text](image.png)

Por esto el dataset no permite discriminar correctamente por provincia (salvo San Luis, donde sólo queda afuera un departamento) y, como el análisis es por provincia y departamento, queda descartado como fuente. Además, el sitio bloquea descargas automáticas (desafío anti-bot de Cloudflare).

# Ministerio de Agricultura, Ganadería y Pesca de la Nación (MAGyP)
https://datosestimaciones.magyp.gob.ar/reportes.php?reporte=Estimaciones

## Columnas
Cultivo,Campaña,Provincia,Departamento,idProvincia,idDepartamento,Sup. Sembrada,Sup. Cosechada,Producción,Rendimiento

Superficie: se muestran en hectáreas (Ha), 
Produccion: se muestran en toneladas (Tn)
Rendimiento: se muestran en kg/ha.


# Bolsa de Cereales de Córdoba
https://bccba.sharepoint.com/:x:/s/DWDIA/IQA2_dOYoDNgSJwuCx3WFQeIAUSP2lLSWrJM35ACasy6Qfg?rtime=_N4iR4sM30g

## Columnas
PROVINCIA, DEPARTAMENTO, CULTIVO, CAMPAÑA, SEMBRADAS, COSECHADAS, RENDIMIENTO, RENDIMIENTO GRANO LIMPIO Y SECO, PRODUCCIÓN, PRODUCCIÓN GRANO LIMPIO Y SECO

Superficie sembrada: hectáreas (Ha)
Producción: toneladas (Tn)
Rendimiento: quintales por hectárea (qq/Ha)

Desde 2026 el archivo se publica como `.xls` con 10 filas de título en cada
hoja; el extractor detecta la fila de encabezado buscando `PROVINCIA`.
La base también cubre departamentos de otras provincias (San Luis,
Santiago del Estero, La Pampa, Catamarca, Tucumán), que se reconcilian con
MAGyP.

![alt text](image-1.png)

# Bahia blanca

# BAires Quequen

# Baires Darsena 

# Rosario

# Cuadros tarifarios eléctricos

Tarifas de las 28 distribuidoras del registro `etl/reference/distribuidoras.py`.
Para cada una se prueba primero el portal nacional y después la fuente
propia; se toma el cuadro de vigencia más reciente.

| Fuente | Distribuidoras | Formato |
|--------|----------------|---------|
| Portal de la Secretaría de Energía (`argentina.gob.ar/.../cuadros-tarifarios-<slug>`, archivos en `energia.gob.ar`, por HTTP) | La mayoría | PDF, XLSX, ZIP |
| OCEBA (`oceba.gba.gov.ar`) | EDEN, EDEA, EDES, EDELAP | PDF por anexo |
| EPE (`epe.santafe.gov.ar/institucional-api/download/<uuid>`) | EPE | PDF vía API del sitio |
| Sitios propios (EDERSA, EDESE, EPEN, REFSA, EDENOR, ...) | Varias | PDF |
| `data/reference/cuadros_manuales/<CÓDIGO>/` | Cualquiera | Cargados a mano |

Sin dato automático al 2026-10: EPEC (sitio con 403 fuera de Argentina; el
ente regulador `ersep.cba.gov.ar` está fuera de la lista de dominios
permitidos), EDET y DPE (PDF escaneados), ESJ y SPSE (enlaces rotos en el
portal y sitios propios fuera de la lista de dominios). EJESA usa el último
valor extraído.

