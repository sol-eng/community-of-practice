# Data Access - Shiny Databricks

This Shiny for R application demonstrates building a loan analysis dashboard for a national bank using data pulled from Databricks via SQL Warehouses. The dashboard works while running in Posit Workbench (using the managed credentials) and while deployed on Posit Connect (using the Databricks OAuth integration feature).

In order to connect to Databricks, the `httpPath` parameter must be entered in the `dbPool` function. It is also important to have the `connectcreds` R package installed and loaded if you intend to publish your app to Posit Connect.