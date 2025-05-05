# Data Access - Jupyter Notebooks

This project houses several Jupyter Notebooks, each one focused on leveraging
the following data sources:

* [PostgreSQL](databricks_data_access.ipynb)
* [AWS S3](s3_parquet_data_access.ipynb)
* [Snowflake](snowflake_data_access.ipynb)
* [Databricks](databricks_data_access.ipynb)

These are provided as example workflows and will need to be modified based on the
data you are trying to access. Also note these are intended to be used with
[Posit Workbench's managed credential feature](https://docs.posit.co/ide/server-pro/user/2024.12.1/posit-workbench/managed-credentials/managed-credentials.html) and
[Posit Connect's OAuth integration feature](https://docs.posit.co/connect/user/oauth-integrations/).