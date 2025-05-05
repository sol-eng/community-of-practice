# Data Access - Shiny Snowflake

This Shiny for R application demonstrates building a loan analysis dashboard for a national bank using data pulled from Snowflake via Warehouses. The dashboard works while running in Posit Workbench (using the managed credentials) and while deployed on Posit Connect (using the Snowflake OAuth integration feature).

In order to connect to Snowflake, the parameters must be entered in the `dbPool` function. It is also important to have the `connectcreds` R package installed and loaded if you intend to publish your app to Posit Connect.