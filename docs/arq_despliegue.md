architecture-beta

group host(cloud)[Host]

group etl(server)[ETL] in host
service etl_img(server)[ETL_Image] in etl
service etl_cmd(server)[Run_ETL] in etl

group shaper(database)[Shaper] in host
service shaper_img(server)[Shaper_Image] in shaper
service shaper_port(database)[Port_5454] in shaper

group volumes(disk)[Volumes] in host
service processed(disk)[Processed] in volumes
service audit(disk)[Audit] in volumes
service shaper_data(disk)[ShaperData] in volumes

group external(internet)[External] in host
service browser(internet)[Browser] in external

etl_img:R --> L:processed
etl_img:R --> L:audit

shaper_img:R --> L:processed
shaper_img:R --> L:audit
shaper_img:R --> L:shaper_data

shaper_port:R --> L:browser