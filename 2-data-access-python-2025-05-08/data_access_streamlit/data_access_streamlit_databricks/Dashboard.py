import os
from posit.connect.external.databricks import ConnectStrategy, sql_credentials, databricks_config
from posit.workbench.external.databricks import WorkbenchStrategy
from databricks import sql
from databricks.sdk.service.iam import CurrentUserAPI
from databricks.sdk.core import ApiClient
import pandas as pd
from math import isnan
import streamlit as st
from helper import regions, purpose_choices, sub_grade_choices, all_zip_codes, office_choices, office_df
from plotnine import ggplot, geom_col, aes, facet_wrap, labs, guides, theme_set, theme_void, theme, element_text
from statistics import mean, median
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(layout="wide", page_title="Dashboard")
st.title("Dashboard")

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_HOST_URL = f"https://{DATABRICKS_HOST}"
SQL_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

theme_set(theme_void())


session_token = st.context.headers.get("Posit-Connect-User-Session-Token")
if not os.getenv("RSTUDIO_PRODUCT") == "CONNECT":
    workbench_strategy = WorkbenchStrategy()
else:
    workbench_strategy = None

cfg = databricks_config(
    posit_workbench_strategy=workbench_strategy,
    posit_connect_strategy=ConnectStrategy(user_session_token=session_token),
    host=DATABRICKS_HOST_URL,
    )

databricks_user = CurrentUserAPI(ApiClient(cfg)).me()

def convert_where_param(param):
    if len(param) == 1:
        return str(param)[:-2] + str(param)[-1]
    else:
        return param

with st.sidebar:
    st.write(f"Hello, {databricks_user.display_name}!")
    st.write("**Select a segment to analyze:**")
    region_input = st.multiselect("Region", options=regions, key="region")
    if not region_input:
        office_choices_selector = office_choices
    else:
        office_filtered = office_df[office_df['region'].isin(region_input)]
        office_choices_selector = dict(zip(office_filtered.office_no, office_filtered.zip_code))
    office_input = st.multiselect("Office", options=office_choices_selector, key="office")    
    purpose_input = st.multiselect("Loan Purpose", options=purpose_choices, key="purpose")
    loan_subgrade_input = st.multiselect("Loan Sub Grade", options=sub_grade_choices, key="loan_subgrade")
    st.image("static/logo.png")

    con = sql.connect(
                server_hostname=cfg.host,
                http_path=SQL_HTTP_PATH,
                credentials_provider=sql_credentials(cfg),
            )

selected_region = tuple(regions) if not region_input else tuple(region_input)
selected_office = tuple(all_zip_codes) if not office_input else tuple(office_choices[x] for x in office_input)
selected_purpose = tuple(purpose_choices) if not purpose_input else tuple(purpose_input)
selected_subgrade = tuple(sub_grade_choices) if not loan_subgrade_input else tuple(loan_subgrade_input)

sql_query = f"""
        SELECT
            `member_id`,
            `region`,
            `grade`,
            `sub_grade`,
            `loan_amnt`,
            `funded_amnt`,
            `term`,
            `int_rate`,
            `emp_title`,
            `emp_length`,
            `annual_inc`,
            `loan_status`,
            `purpose`,
            `title`,
            `zip_code`,
            `addr_state`,
            `dti`,
            `out_prncp`,
            SUBSTR(`zip_code`, 1, 3) AS `office_no`
        FROM (
        SELECT
            `lending_club`.*,
            CASE
        WHEN (SUBSTR(`zip_code`, 1, 1) IN ('8', '9')) THEN 'West'
        WHEN (SUBSTR(`zip_code`, 1, 1) IN ('6', '5', '4')) THEN 'Midwest'
        WHEN (SUBSTR(`zip_code`, 1, 1) IN ('7', '3', '2')) THEN 'South'
        WHEN (SUBSTR(`zip_code`, 1, 1) IN ('1', '0')) THEN 'East'
        ELSE 'NA'
        END AS `region`
            FROM `sol_eng_demo_nickp`.`default`.`lending_club`
            WHERE (NOT((`addr_state` IS NULL)))
        ) `q01`
        WHERE
            (`region` IN {convert_where_param(selected_region)}) AND
            (`zip_code` IN {convert_where_param(selected_office)}) AND
            (`title` IN {convert_where_param(selected_purpose)}) AND
            (`sub_grade` IN {convert_where_param(selected_subgrade)})
        """

with st.spinner('Loading data from Databricks'):
    with con.cursor() as cursor:
        cursor.execute(sql_query)
        df = cursor.fetchall_arrow().to_pandas()

# Bar graph of principal by grade per region
raw_data_princ_grade = df
raw_data_princ_grade["out_prncp"] = pd.to_numeric(raw_data_princ_grade["out_prncp"])
grouped_data_princ_grade = raw_data_princ_grade.groupby(['region', 'grade'])['out_prncp'].sum().reset_index()
grouped_data_princ_grade['out_prncp'] = grouped_data_princ_grade['out_prncp'].div(1000000)
if len(grouped_data_princ_grade) > 0:
    principal_by_grade_graph = (
                ggplot(grouped_data_princ_grade, aes(x="grade", y="out_prncp", fill="grade"))
                + geom_col(stat="identity", position="dodge")
                + facet_wrap("region")
                + guides(fill = "none")
                + theme(
                    text=element_text(color="#FFFFFF"),
                    axis_title_y=element_text(angle=90)
                )
                + labs(
                    x="Loan Grade",
                    y="Loan Principal (M)",
                )
            )
else:
    principal_by_grade_graph = None

# Bar graph of % principal risk by grade per region
raw_data_risk = df
raw_data_risk["out_prncp"] = pd.to_numeric(raw_data_risk["out_prncp"])
region_totals = raw_data_risk.groupby(['region', 'grade'])['out_prncp'].sum().reset_index().rename(columns={'region':'region', 'grade':'grade', 'out_prncp':'region_prncp_total'})
        
combined_df_risk = pd.merge(raw_data_risk, region_totals, on=['region', 'grade'], how='left')

grouped_data_risk = combined_df_risk[-combined_df_risk["loan_status"].isin(["Current", "Fully Paid", "Charged Off"])].groupby(['region', 'grade']).agg({'out_prncp': 'sum', 'region_prncp_total': 'min'}).reset_index()
grouped_data_risk['prncp_per_risk'] = (grouped_data_risk['out_prncp']/grouped_data_risk['region_prncp_total']) * 100
if len(grouped_data_risk) > 0:
    risk_by_grade_graph = (
                ggplot(grouped_data_risk, aes(x="grade", y="prncp_per_risk", fill="grade"))
                + geom_col(stat="identity", position="dodge")
                + facet_wrap("region")
                + guides(fill = "none")
                + theme(
                    text=element_text(color="#FFFFFF"),
                    axis_title_y=element_text(angle=90)
                )
                + labs(
                    x="Loan Grade",
                    y="% of Principal",
                )
            )
else:
    risk_by_grade_graph = None

avg_loan_rate = df
avg_loan_rate['int_rate'] = pd.to_numeric(avg_loan_rate['int_rate'].str.replace('%',''))
if len(avg_loan_rate['int_rate']) > 0:
    avg_loan_rate_txt = f"{round(mean(avg_loan_rate['int_rate']), 2)} %"
else:
    avg_loan_rate_txt = "No data"

median_loan_size = df
median_loan_size['loan_amnt'] = pd.to_numeric(median_loan_size['loan_amnt'], downcast = 'float')
if len(median_loan_size['loan_amnt']) > 0:
    median_loan_size_txt = f"${round(median(median_loan_size['loan_amnt']), 0):,}"
else:
    median_loan_size_txt = "No data"

avg_loan_tenor = df
avg_loan_tenor['term'] = pd.to_numeric(avg_loan_tenor['term'].str.replace(' months',''))
if len(avg_loan_tenor['term']) > 0:
    avg_loan_tenor_txt = f"{round(mean(avg_loan_tenor['term'])/12, 2)} years"
else:
    avg_loan_tenor_txt = "No data"

raw_data_tbl = df[["member_id", "region", "office_no", "grade", "sub_grade", "loan_amnt", "term", "int_rate", "emp_title", "emp_length", "annual_inc", "loan_status", "title", "addr_state", "out_prncp"]].rename(columns={'member_id':'ID','region':'Region', 'office_no':'Office', 'addr_state':'State', 'grade':'Grade', 'sub_grade':'Sub Grade', 'loan_amnt':'Loan Amt','term':'Term', 'int_rate':'Rate', 'emp_title':'Emp Title', 'emp_length':'Emp Length', 'annual_inc':'Ann Income', 'loan_status':'Status', 'title':'Purpose', 'out_prncp':'Principal'})
raw_data_tbl['Loan Amt'] = pd.to_numeric(raw_data_tbl['Loan Amt'], downcast = 'float', errors='coerce').apply(lambda x: f'{x}' if isnan(x) else f'${round(x,0):,}')
raw_data_tbl['Ann Income'] = pd.to_numeric(raw_data_tbl['Ann Income'], downcast = 'float', errors='coerce').apply(lambda x: f'{x}' if isnan(x) else f'${round(x,0):,}')
raw_data_tbl['Principal'] = pd.to_numeric(raw_data_tbl['Principal'], downcast = 'float', errors='coerce').apply(lambda x: f'{x}' if isnan(x) else f'${round(x,0):,}')


row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2, row2_col3 = st.columns(3)
row3_col1, = st.columns(1)

with row1_col1:
    if principal_by_grade_graph is not None:
        st.pyplot(ggplot.draw(principal_by_grade_graph))
    else:
        st.write("No data available.")

with row1_col2:
    if risk_by_grade_graph is not None:
        st.pyplot(ggplot.draw(risk_by_grade_graph))
    else:
        st.write("No data available.")

with row2_col1:
    st.metric(label="Avg Loan Rate", value=avg_loan_rate_txt)

with row2_col2:
    st.metric(label="Median Loan Size", value=median_loan_size_txt)

with row2_col3:
    st.metric(label="Avg Loan Tenor", value=avg_loan_tenor_txt)

with row3_col1:
    if len(raw_data_tbl) > 1000:
        st.dataframe(raw_data_tbl.head(1000), hide_index=True)
        st.write("Truncated to 1,000 rows. Apply filters to narrow down request.")
    else:
        st.dataframe(raw_data_tbl)