# Data Access - Shiny Applications

This project houses several [Shiny applications](https://shiny.posit.co/), each one focused on leveraging
the following data sources (these are just examples, other sources such as
PostgreSQL, Oracle, S3, etc. will work as well):

* [Snowflake](data_access_shiny_snowflake/README.md)
* [Databricks](data_access_shiny_databricks/README.md)

These are provided as example workflows and will need to be modified based on the
data you are trying to access. Also note these are intended to be used with
[Posit Workbench's managed credential feature](https://docs.posit.co/ide/server-pro/user/2024.12.1/posit-workbench/managed-credentials/managed-credentials.html) and
[Posit Connect's OAuth integration feature](https://docs.posit.co/connect/user/oauth-integrations/).