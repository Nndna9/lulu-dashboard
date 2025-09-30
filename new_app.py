
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(layout="wide", page_title="LULU UAE Sales Dashboard")

@st.cache_data
def load_data(path):
    return pd.read_csv(path)

# Load data files (assumes they are in the same folder as app.py)
transactions = load_data("transactions.csv")
customers = load_data("customers_demographics.csv")
loyalty = load_data("loyalty_program.csv")
ad_budget = load_data("ad_budget_monthly.csv")

st.title("LULU Hypermarket — UAE Sales & Loyalty Dashboard (Fixed)")

# Sidebar filters
st.sidebar.header("Filters")
min_date = pd.to_datetime(transactions['transaction_datetime']).min()
max_date = pd.to_datetime(transactions['transaction_datetime']).max()
date_range = st.sidebar.date_input("Transaction date range", [min_date.date(), max_date.date()])

selected_emirates = st.sidebar.multiselect("Emirates", options=transactions['emirate'].unique().tolist(), default=transactions['emirate'].unique().tolist())
selected_categories = st.sidebar.multiselect("Categories", options=transactions['category'].unique().tolist(), default=transactions['category'].unique().tolist())
gender = st.sidebar.multiselect("Gender", options=transactions['gender'].unique().tolist(), default=transactions['gender'].unique().tolist())
loyalty_filter = st.sidebar.selectbox("Loyalty filter", options=["All","Loyalty Members","Non-members"])

# Apply filters
df = transactions.copy()
df['transaction_datetime'] = pd.to_datetime(df['transaction_datetime'])
start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
df = df[(df['transaction_datetime']>=start) & (df['transaction_datetime']<end)]
df = df[df['emirate'].isin(selected_emirates) & df['category'].isin(selected_categories) & df['gender'].isin(gender)]
if loyalty_filter=="Loyalty Members":
    df = df[df['has_loyalty']==True]
elif loyalty_filter=="Non-members":
    df = df[df['has_loyalty']==False]

# KPIs
total_sales = df['total_aed'].sum()
total_transactions = df['transaction_id'].nunique()
avg_basket = df['total_aed'].mean()
st.metric("Total Sales (AED)", f"{total_sales:,.2f}", delta=None)
st.metric("Transactions", f"{total_transactions}", delta=None)
st.metric("Avg Basket (AED)", f"{avg_basket:,.2f}", delta=None)

# Layout: demographics and category breakdown
col1, col2 = st.columns([1,2])
with col1:
    st.subheader("Customer Demographics")
    age_bins = [18,25,35,45,55,65,80]
    df['age_group'] = pd.cut(df['age'], bins=age_bins, labels=["18-24","25-34","35-44","45-54","55-64","65+"], include_lowest=True)
    age_dist = df.groupby('age_group')['total_aed'].sum().reset_index()
    fig_age = px.bar(age_dist, x='age_group', y='total_aed', labels={'total_aed':'Sales (AED)','age_group':'Age group'}, title="Sales by Age Group")
    st.plotly_chart(fig_age, use_container_width=True)

    gender_dist = df.groupby('gender')['total_aed'].sum().reset_index()
    fig_gender = px.pie(gender_dist, names='gender', values='total_aed', title="Sales by Gender")
    st.plotly_chart(fig_gender, use_container_width=True)

with col2:
    st.subheader("Category performance by emirate")
    cat_em = df.groupby(['emirate','category'])['total_aed'].sum().reset_index()
    fig_cat = px.sunburst(cat_em, path=['emirate','category'], values='total_aed', title="Sales by Emirate and Category")
    st.plotly_chart(fig_cat, use_container_width=True)

# Loyalty program impact
st.subheader("Loyalty Program Impact")
loyal = df.groupby('has_loyalty').agg(total_sales=('total_aed','sum'), transactions=('transaction_id','nunique'), avg_basket=('total_aed','mean')).reset_index()
loyal['has_loyalty'] = loyal['has_loyalty'].map({True:'Members', False:'Non-members'})
fig_loyal = px.bar(loyal, x='has_loyalty', y='total_sales', text='avg_basket', labels={'total_sales':'Sales (AED)','has_loyalty':'Customer Type'}, title="Sales: Loyalty Members vs Non-members (avg basket shown)")
st.plotly_chart(fig_loyal, use_container_width=True)

# Points redeemed vs sales
redeem = df[df['points_redeemed']>0]
if not redeem.empty:
    redeem_summary = redeem.groupby('customer_id').agg(points_redeemed=('points_redeemed','sum'), sales_after_redeem=('total_aed','sum')).reset_index()
    fig_redeem = px.scatter(redeem_summary, x='points_redeemed', y='sales_after_redeem', hover_data=['customer_id'], title="Points Redeemed vs Sales (per customer)")
    st.plotly_chart(fig_redeem, use_container_width=True)
else:
    st.info("No point-redemption transactions in the selected filters.")

# Ad budget vs sales (monthly) - Robust implementation using graph_objects
st.subheader("Advertising Budget vs Sales (last 12 months)")
monthly_sales = df.copy()
monthly_sales['month'] = monthly_sales['transaction_datetime'].dt.to_period('M').astype(str)
sales_month_cat = monthly_sales.groupby(['month','category'])['total_aed'].sum().reset_index()
ad = ad_budget.copy()

# Merge and ensure numeric columns exist
merged = pd.merge(ad, sales_month_cat, on=['month','category'], how='left')
merged['ad_budget_aed'] = pd.to_numeric(merged.get('ad_budget_aed', 0)).fillna(0)
merged['total_aed'] = pd.to_numeric(merged.get('total_aed', 0)).fillna(0)

# Convert month strings (e.g., "2025-09") to datetime for plotting
def safe_month_to_dt(m):
    try:
        return pd.to_datetime(str(m) + "-01")
    except Exception:
        try:
            return pd.to_datetime(m)
        except Exception:
            return pd.NaT

merged['month_dt'] = merged['month'].apply(safe_month_to_dt)
merged = merged.sort_values('month_dt')

# Build figure with one dashed line for budget and solid line for sales per category
fig = go.Figure()
for cat in merged['category'].unique():
    dfc = merged[merged['category']==cat].sort_values('month_dt')
    if dfc['month_dt'].isna().all():
        continue
    fig.add_trace(go.Scatter(
        x=dfc['month_dt'],
        y=dfc['ad_budget_aed'],
        mode='lines+markers',
        name=f"{cat} - Ad Budget",
        line=dict(dash='dash'),
        hovertemplate='%{x|%b %Y}<br>%{y:.2f} AED<br>'
    ))
    fig.add_trace(go.Scatter(
        x=dfc['month_dt'],
        y=dfc['total_aed'],
        mode='lines+markers',
        name=f"{cat} - Sales",
        line=dict(dash='solid'),
        hovertemplate='%{x|%b %Y}<br>%{y:.2f} AED<br>'
    ))

fig.update_layout(title="Ad Budget vs Sales by Category", xaxis_title="Month", yaxis_title="AED", hovermode='x unified', legend_title_text='Series')
st.plotly_chart(fig, use_container_width=True)

# Top products
st.subheader("Top Products")
top_products = df.groupby(['category','product']).agg(sales=('total_aed','sum'), qty=('quantity','sum')).reset_index().sort_values('sales', ascending=False).head(15)
fig_top = px.bar(top_products, x='product', y='sales', color='category', title="Top selling products (by sales)")
st.plotly_chart(fig_top, use_container_width=True)

# Download sample filtered data
st.sidebar.markdown("### Export")
if st.sidebar.button("Download filtered transactions CSV"):
    st.sidebar.download_button("Click to download", data=df.to_csv(index=False), file_name="filtered_transactions.csv", mime="text/csv")
