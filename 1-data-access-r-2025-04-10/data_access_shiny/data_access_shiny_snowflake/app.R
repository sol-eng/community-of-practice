library(shiny)
library(bslib)
library(bsicons)
library(thematic)
library(tidyverse)
library(dbplyr)
library(pool)
library(httr2)
library(DBI)
library(odbc)
library(scales)
library(gt)
library(shinyWidgets)
library(connectcreds)

source("helper.R")

# Set the default theme for ggplot2 plots
ggplot2::theme_set(ggplot2::theme_minimal())

# Apply the CSS used by the Shiny app to the ggplot2 plots
thematic_shiny()

# Define the Shiny UI layout
ui <- page_navbar(
  # Set CSS theme
  theme = bs_theme(bootswatch = "darkly",
                   info = "#5D8BA5",
                   "navbar-dark-bg" = "#222222",
                   "navbar-dark-brand-color" = "#FFFFFF",
                   "navbar-active-color" = "#FFFFFF"),
  # Add title
  title = "Loan Portfolio Analysis",
  nav_panel("Dashboard",
            layout_sidebar(
              sidebar = sidebar(title = "Select a segment to analyze",
                                class ="bg-secondary",
                                selectInput("region", "Region", choices = regions, selected = "", multiple  = TRUE),
                                selectInput("office", "Office", choices = setNames(office_lookup$zip_code, office_lookup$office_no), selected = "", multiple  = TRUE),
                                selectInput("purpose", "Loan Purpose", choices = purpose_choices, selected = "", multiple  = TRUE),
                                selectInput("loan_subgrade", "Loan Sub Grade", choices = sub_grade_choices, selected = "", multiple  = TRUE),
                                tags$img(src = "logo.png", width = "100%", height = "auto")),
              # Layout non-sidebar elements
              layout_columns(
                card(card_header("Principal by Grade"),
                     plotOutput("principal_by_grade_graph"),
                ),
                card(card_header("Loans at Risk"),
                     plotOutput("loans_at_risk_graph"),
                ),
                value_box(title = "Avg Loan Rate",
                          value = textOutput("avg_loan_rate"),
                          theme_color = "secondary"),
                value_box(title = "Median Loan Size",
                          value = textOutput("median_loan_size"),
                          theme_color = "secondary"),
                value_box(title = "Avg Loan Tenor",
                          value = textOutput("avg_loan_tenor"),
                          theme_color = "secondary"),
                card(card_header("Individual loan details"),
                     gt_output("loan_details_table"),
                ),
                col_widths = c(6, 6, 4, 4, 4, 12),
                row_heights = c(5, 2, 5)
              ),
            ),
  ),
  header = tags$div(
    useBusyIndicators(pulse = FALSE),
    tags$head(
      # Note the wrapping of the string in HTML()
      tags$style(HTML("
      .user h6{
        padding-left: calc(var(--bs-gutter-x)* .5);
        margin-top: 10px;
        margin-bottom: 10px;
      }"
      ))
    ),
  ),
)

server <- function(input, output, session) {
  
  observe({
    if (is.null(input$region)) {
      office_choices <- office_lookup
    } else {
      office_choices <- office_lookup |>
        filter(region %in% input$region)
    }
    
    updateSelectInput(session, "office",
                      label = "Office",
                      choices = setNames(office_choices$zip_code, office_choices$office_no)
    )
  })
  
  pool_con <- reactive({
    con <- try(
      dbPool(
        odbc::snowflake(),
        warehouse = "DEFAULT_WH",
        database = "LENDING_CLUB",
        schema = "PUBLIC",
        account = "<YOUR_SNOWFLAKE_ACCOUNT_HERE"
        )
      )
    
    validate(need(class(con) != "try-error", "Issue connecting to Snowflake"))
    
    con
  })
  
  # Provide default values for inputs
  selected_region <- reactive({
    if (is.null(input$region)) regions else input$region
  })
  
  selected_office <- reactive({
    if (is.null(input$office)) office_lookup$zip_code else input$office
  })
  
  selected_purpose <- reactive({
    if (is.null(input$purpose)) purpose_choices else input$purpose
  })
  
  selected_subgrade <- reactive({
    if (is.null(input$loan_subgrade)) sub_grade_choices else input$loan_subgrade
  })
  
  
  # Render bar plot for principal outstanding by grade per region
  output$principal_by_grade_graph <- renderPlot({
    filtered_data() |>
      group_by(region, grade) |>
      summarise(out_prncp = sum(as.numeric(out_prncp), na.rm = TRUE)) |>
      ggplot(aes(x = grade, y = out_prncp, fill = grade)) +
      geom_col() +
      guides(fill = "none") +
      theme(
        axis.text = element_text(size = 14, face = "bold"),
        axis.title = element_text(size = 14, face = "bold"),
        strip.text.x = element_text(
          size = 14, face = "bold"
        ),
        strip.text.y = element_text(
          size = 14, face = "bold"
        )
      ) +
      facet_wrap(~region) +
      scale_y_continuous(labels = unit_format(unit = "M", scale = 1e-6)) +
      ylab("Loan Principal") +
      xlab("Loan Grade")
  })
  
  # Render bar plot for % of principal at risk by grade per region
  output$loans_at_risk_graph <- renderPlot({
    raw_data <- filtered_data()
    
    region_totals <-
      raw_data |>
      group_by(region, grade) |>
      summarise(region_prncp_total = sum(as.numeric(out_prncp), na.rm = TRUE))
    
    raw_data |>
      left_join(region_totals, by = c("region", "grade")) |>
      filter(!(loan_status %in% c("Current", "Fully Paid", "Charged Off"))) |>
      group_by(region, grade) |>
      summarise(prncp_per_risk = (sum(as.numeric(out_prncp), na.rm = TRUE) / region_prncp_total[1]) * 100) |>
      ggplot(aes(x = grade, y = prncp_per_risk, fill = grade)) +
      geom_col() +
      guides(fill = "none") +
      theme(
        axis.text = element_text(size = 14, face = "bold"),
        axis.title = element_text(size = 14, face = "bold"),
        strip.text.x = element_text(
          size = 14, face = "bold"
        ),
        strip.text.y = element_text(
          size = 14, face = "bold"
        )
      ) +
      facet_wrap(~region) +
      ylab("% of Principal") +
      xlab("Loan Grade")
  })
  
  
  
  # Filter data against selections
  filtered_data <- reactive({
    req(selected_purpose())
    req(selected_subgrade())
    req(selected_region())
    req(selected_office())
    
    data <- tbl(
      pool_con(),
      "LOAN_DATA"
    ) |>
      filter(!is.na(ADDR_STATE)) |>
      mutate(REGION = case_when(stringr::str_sub(ZIP_CODE, 1, 1) %in% c("8","9") ~ "West",
                                stringr::str_sub(ZIP_CODE, 1, 1) %in% c("6","5","4") ~ "Midwest",
                                stringr::str_sub(ZIP_CODE, 1, 1) %in% c("7","3","2") ~ "South",
                                stringr::str_sub(ZIP_CODE, 1, 1) %in% c("1","0") ~ "East",
                                TRUE ~ "NA")) |>
      filter(REGION %in% !!selected_region(),
             ZIP_CODE %in% !!selected_office(),
             PURPOSE %in% !!selected_purpose(),
             SUB_GRADE %in% !!selected_subgrade()
      ) |>
      rename(member_id = ID, region = REGION, grade = GRADE, sub_grade = SUB_GRADE,
             loan_amnt = LOAN_AMNT, funded_amnt = FUNDED_AMNT,
             term = TERM, int_rate = INT_RATE, emp_title = EMP_TITLE,
             emp_length = EMP_LENGTH, annual_inc = ANNUAL_INC, loan_status = LOAN_STATUS,
             purpose = PURPOSE, title = TITLE, zip_code = ZIP_CODE, addr_state = ADDR_STATE,
             dti = DTI, out_prncp = OUT_PRNCP) |>
      select(member_id, region, grade, sub_grade, loan_amnt, funded_amnt,
             term, int_rate, emp_title, emp_length, annual_inc, loan_status,
             purpose, title, zip_code, addr_state, dti, out_prncp) |>
      mutate(office_no = stringr::str_sub(zip_code, 1, 3)) |>
      collect()
    
    validate(need(nrow(data) > 0, "No data available"))
    
    data
  })
  
  output$avg_loan_rate <- renderText({
    avg_loan_rate <-
      filtered_data() |>
      mutate(int_rate = as.numeric(str_remove(int_rate, "%"))) |>
      summarise(avg_rate = mean(int_rate, na.rm = TRUE)) |>
      pull(avg_rate)
    
    paste(as.character(round(avg_loan_rate[1], 2)), "%")
  })
  
  output$median_loan_size <- renderText({
    median_loan_size <-
      filtered_data() |>
      mutate(loan_amnt = as.numeric(loan_amnt)) |>
      summarise(median_amt = median(loan_amnt, na.rm = TRUE)) |>
      pull(median_amt)
    
    paste0("$",as.character(formatC(round(median_loan_size[1], 0), format="d", big.mark=",")))
  })
  
  output$avg_loan_tenor <- renderText({
    avg_loan_tenor <-
      filtered_data() |>
      mutate(loan_tenor = case_when(term == "36 months" ~ 36,
                                    term == "60 months" ~ 60,
                                    TRUE ~ as.numeric(NA))) |>
      summarise(avg_tenor = mean(loan_tenor, na.rm = TRUE)) |>
      pull(avg_tenor)
    
    paste(as.character(round(avg_loan_tenor[1]/12, 2)), "years")
  })
  
  
  output$loan_details_table <- render_gt({
    raw_data <- filtered_data()
    
    data_transformed <-
      raw_data |>
      mutate(member_id = str_pad(member_id, 8, pad = "0")) |>
      select(member_id, region, office_no, grade, sub_grade, loan_amnt, term, int_rate,
             emp_title, emp_length, annual_inc, loan_status,
             title, addr_state, out_prncp) |>
      mutate(loan_amnt = as.numeric(loan_amnt),
             annual_inc = as.numeric(annual_inc),
             out_prncp = as.numeric(out_prncp)) |>
      rename(ID = member_id, Region = region, Office = office_no, State = addr_state, Grade = grade, `Sub Grade` = sub_grade,
             `Loan Amt` = loan_amnt, Term = term, Rate = int_rate, `Emp Title` = emp_title,
             `Emp Length` = emp_length, `Ann Income` = annual_inc, Status = loan_status,
             Purpose = title, Principal = out_prncp)
    
    if (nrow(data_transformed > 1000)) {
      table_start <-
        data_transformed |>
        head(1000) |>
        gt() |>
        tab_source_note(source_note =
                          "Truncated to 1,000 rows. Apply filters to narrow down the request."
        )
    } else {
      table_start <-
        data_transformed |>
        gt()
    }
    
    table_start |>
      fmt_currency(`Loan Amt`, decimals = 0) |>
      fmt_currency(`Ann Income`, decimals = 0) |>
      fmt_currency(Principal, decimals = 0)
  })
}

shinyApp(ui = ui, server = server)