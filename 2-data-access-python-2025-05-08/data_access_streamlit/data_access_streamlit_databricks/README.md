# Data Access - Streamlit Databricks

This Streamlit application demonstrates building a loan analysis dashboard for a national bank using data pulled from Databricks via SQL Warehouses. The dashboard works while running in Posit Workbench (using the managed credentials) and while deployed on Posit Connect (using the Databricks OAuth integration feature).

Ensure you have the following environment variables setup in a `.env` file:

`DATABRICKS_HOST`
`DATABRICKS_HTTP_PATH`