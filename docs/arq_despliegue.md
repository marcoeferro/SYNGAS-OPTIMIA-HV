
architecture-beta

group host(cloud)[Host]

group etl(server)[ETL] in host service etl_img(server)[ETL_Image] in etl service etl_cmd(server)[Run_ETL] in etl

group dashboard(database)[Dashboard] in host service streamlit_img(server)[Streamlit] in dashboard service dashboard_port(database)[Port_8501] in dashboard

group volumes(disk)[Volumes] in host service processed(disk)[Processed] in volumes service audit(disk)[Audit] in volumes

group external(internet)[External] in host service browser(internet)[Browser] in external

etl_img:R --> L:processed etl_img:R --> L:audit

streamlit_img:R --> L:processed streamlit_img:R --> L:audit

dashboard_port:R --> L:browser