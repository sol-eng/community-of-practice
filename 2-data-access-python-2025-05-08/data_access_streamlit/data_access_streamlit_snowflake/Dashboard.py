import os
import pandas as pd
from math import isnan
import streamlit as st
import snowflake.connector
from helper import regions, purpose_choices, sub_grade_choices, all_zip_codes, office_choices, office_df
from configparser import ConfigParser
from plotnine import ggplot, geom_col, aes, facet_wrap, labs, guides, theme_set, theme_void, theme, element_text
from statistics import mean, median
from posit.connect import Client
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(layout="wide", page_title="Dashboard")
st.title("Dashboard")

theme_set(theme_void())

def convert_where_param(param):
    if len(param) == 1:
        return str(param)[:-2] + str(param)[-1]
    else:
        return param

with st.sidebar:
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

if not os.getenv("RSTUDIO_PRODUCT") == "CONNECT" and os.getenv("SNOWFLAKE_HOME") is not None:
    con = snowflake.connector.connect(
        connection_name="workbench",
        warehouse="DEFAULT_WH",
        database = "LENDING_CLUB",
        schema = "PUBLIC",
    )
elif os.getenv("RSTUDIO_PRODUCT") == "CONNECT":
    user_session_token = st.context.headers.get("Posit-Connect-User-Session-Token")
    oauth_token = Client().oauth.get_credentials(user_session_token).get("access_token")

    con = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse="DEFAULT_WH",
        database = "LENDING_CLUB",
        schema = "PUBLIC",
        authenticator="oauth",
        token=oauth_token,
    )
else:
    st.error('No Snowflake credentials found')
    

selected_region = tuple(regions) if not region_input else tuple(region_input)
selected_office = tuple(all_zip_codes) if not office_input else tuple(office_choices[x] for x in office_input)
selected_purpose = tuple(purpose_choices) if not purpose_input else tuple(purpose_input)
selected_subgrade = tuple(sub_grade_choices) if not loan_subgrade_input else tuple(loan_subgrade_input)


sql_query = f"""
WITH sub_table as (
    SELECT
        *,
        SUBSTR(ZIP_CODE, 1, 3) AS OFFICE_NO,
        CASE
            WHEN (SUBSTR(ZIP_CODE, 1, 1) IN ('8', '9')) THEN 'West'
            WHEN (SUBSTR(ZIP_CODE, 1, 1) IN ('6', '5', '4')) THEN 'Midwest'
            WHEN (SUBSTR(ZIP_CODE, 1, 1) IN ('7', '3', '2')) THEN 'South'
            WHEN (SUBSTR(ZIP_CODE, 1, 1) IN ('1', '0')) THEN 'East'
            ELSE 'NA'
        END AS REGION
    FROM LOAN_DATA
    WHERE (NOT((ADDR_STATE IS NULL)))
    )
    SELECT
            ID as MEMBER_ID,
            REGION,
            GRADE,
            SUB_GRADE,
            LOAN_AMNT,
            FUNDED_AMNT,
            TERM,
            INT_RATE,
            EMP_TITLE,
            EMP_LENGTH,
            ANNUAL_INC,
            LOAN_STATUS,
            PURPOSE,
            TITLE,
            ZIP_CODE,
            ADDR_STATE,
            DTI,
            OUT_PRNCP,
            OFFICE_NO
        FROM sub_table
        WHERE
            (REGION IN {convert_where_param(selected_region)}) AND
            (ZIP_CODE IN {convert_where_param(selected_office)}) AND
            (TITLE IN {convert_where_param(selected_purpose)}) AND
            (SUB_GRADE IN {convert_where_param(selected_subgrade)})
            """

with st.spinner('Loading data from Snowflake'):
    with con.cursor() as cursor:
        cursor.execute(sql_query)
        df = cursor.fetch_pandas_all()

# Bar graph of principal by grade per region
raw_data_princ_grade = df
raw_data_princ_grade["OUT_PRNCP"] = pd.to_numeric(raw_data_princ_grade["OUT_PRNCP"])
grouped_data_princ_grade = raw_data_princ_grade.groupby(['REGION', 'GRADE'])['OUT_PRNCP'].sum().reset_index()
grouped_data_princ_grade['OUT_PRNCP'] = grouped_data_princ_grade['OUT_PRNCP'].div(1000000)
if len(grouped_data_princ_grade) > 0:
    principal_by_grade_graph = (
                ggplot(grouped_data_princ_grade, aes(x="GRADE", y="OUT_PRNCP", fill="GRADE"))
                + geom_col(stat="identity", position="dodge")
                + facet_wrap("REGION")
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
raw_data_risk["OUT_PRNCP"] = pd.to_numeric(raw_data_risk["OUT_PRNCP"])
region_totals = raw_data_risk.groupby(['REGION', 'GRADE'])['OUT_PRNCP'].sum().reset_index().rename(columns={'REGION':'REGION', 'GRADE':'GRADE', 'OUT_PRNCP':'REGION_PRNCP_TOTAL'})
        
combined_df_risk = pd.merge(raw_data_risk, region_totals, on=['REGION', 'GRADE'], how='left')

grouped_data_risk = combined_df_risk[-combined_df_risk["LOAN_STATUS"].isin(["Current", "Fully Paid", "Charged Off"])].groupby(['REGION', 'GRADE']).agg({'OUT_PRNCP': 'sum', 'REGION_PRNCP_TOTAL': 'min'}).reset_index()
grouped_data_risk['PRNCP_PER_RISK'] = (grouped_data_risk['OUT_PRNCP']/grouped_data_risk['REGION_PRNCP_TOTAL']) * 100
if len(grouped_data_risk) > 0:
    risk_by_grade_graph = (
                ggplot(grouped_data_risk, aes(x="GRADE", y="PRNCP_PER_RISK", fill="GRADE"))
                + geom_col(stat="identity", position="dodge")
                + facet_wrap("REGION")
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
if len(avg_loan_rate['INT_RATE']) > 0:
    avg_loan_rate_txt = f"{round(mean(avg_loan_rate['INT_RATE']), 2)} %"
else:
    avg_loan_rate_txt = "No data"

median_loan_size = df
if len(median_loan_size['LOAN_AMNT']) > 0:
    median_loan_size_txt = f"${round(median(median_loan_size['LOAN_AMNT']), 0):,}"
else:
    median_loan_size_txt = "No data"

avg_loan_tenor = df
avg_loan_tenor['TERM'] = pd.to_numeric(avg_loan_tenor['TERM'].str.replace(' months',''))
if len(avg_loan_tenor['TERM']) > 0:
    avg_loan_tenor_txt = f"{round(mean(avg_loan_tenor['TERM'])/12, 2)} years"
else:
    avg_loan_tenor_txt = "No data"

raw_data_tbl = df[["MEMBER_ID", "REGION", "OFFICE_NO", "GRADE", "SUB_GRADE", "LOAN_AMNT", "TERM", "INT_RATE", "EMP_TITLE", "EMP_LENGTH", "ANNUAL_INC", "LOAN_STATUS", "TITLE", "ADDR_STATE", "OUT_PRNCP"]].rename(columns={'MEMBER_ID':'ID','REGION':'Region', 'OFFICE_NO':'Office', 'ADDR_STATE':'State', 'GRADE':'Grade', 'SUB_GRADE':'Sub Grade', 'LOAN_AMNT':'Loan Amt','TERM':'Term', 'INT_RATE':'Rate', 'EMP_TITLE':'Emp Title', 'EMP_LENGTH':'Emp Length', 'ANNUAL_INC':'Ann Income', 'LOAN_STATUS':'Status', 'TITLE':'Purpose', 'OUT_PRNCP':'Principal'})
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