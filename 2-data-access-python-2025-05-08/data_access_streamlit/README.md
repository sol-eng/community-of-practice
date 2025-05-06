# Data Access - Streamlit Applications

This project houses several [Streamlit applications](https://streamlit.io/), each one focused on leveraging
the following data sources (these are just examples, other sources such as
PostgreSQL, Oracle, S3, etc. will work as well). The same patterns will work from other interactive application frameworks
such as [Shiny for Python](https://shiny.posit.co/py/) and [Dash](https://dash.plotly.com/).

* [Snowflake](data_access_streamlit_snowflake/README.md)
* [Databricks](data_access_streamlit_databricks/README.md)

These are provided as example workflows and will need to be modified based on the
data you are trying to access. Also note these are intended to be used with
[Posit Workbench's managed credential feature](https://docs.posit.co/ide/server-pro/user/2024.12.1/posit-workbench/managed-credentials/managed-credentials.html) and
[Posit Connect's OAuth integration feature](https://docs.posit.co/connect/user/oauth-integrations/).