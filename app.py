from api.src.models.infer import forecast_sales, forecast_occupancy, forecast_sales_xgb
from api.src.db import fetch_df, get_engine
from sqlalchemy import text
from api.src.db import get_engine, fetch_df
from sqlalchemy import text



import pandas as pd
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Hotel AI Decision Dashboard", layout="wide")

engine = get_engine()

# 測試連線（可以先留著）
with engine.connect() as conn:
    print("DB 測試結果：", conn.execute(text("SELECT 1")).scalar())


# =======================
# Mock API client (replace later with real FastAPI calls)
# =======================
def fetch_sales_forecast(days: int = 30) -> pd.DataFrame:
    return forecast_sales(days)

def fetch_occupancy_forecast(days: int = 30) -> pd.DataFrame:
    return forecast_occupancy(days)

def fetch_competitor_prices(days: int = 30) -> pd.DataFrame:
    sql = """
    WITH base AS (
      SELECT dt::date AS dt,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS "Comp P50",
             percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS "Comp P75"
      FROM compset_rates
      WHERE dt >= (CURRENT_DATE - INTERVAL '30 day')
      GROUP BY 1
    )
    SELECT d::date AS "Date",
           COALESCE(b."Comp P50", 3200) AS "Comp P50",
           COALESCE(b."Comp P75", 3600) AS "Comp P75",
           COALESCE(b."Comp P50", 3200) AS "My Price"
    FROM generate_series(
           CURRENT_DATE,
           CURRENT_DATE + (CAST(:days AS int) - 1),
           INTERVAL '1 day'
         ) AS d
    LEFT JOIN base b ON b.dt = d::date
    ORDER BY 1;
    """
    df = fetch_df(sql, {"days": days})
    df.rename(columns={"date": "Date"}, inplace=True)  # 保證有大寫 D
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df



# =======================
# Sidebar filters
# =======================
st.sidebar.header("全域篩選")
hotel = st.sidebar.selectbox("飯店", ["Hotel A", "Hotel B"])
days = st.sidebar.selectbox("日期區間", [7, 14, 30], index=2)
room_type = st.sidebar.selectbox("房型", ["全部", "豪華雙人房", "標準房"])
channel = st.sidebar.multiselect("渠道", ["全部", "Booking", "Agoda", "官網"], default=["全部"])
pricing_mode = st.sidebar.selectbox("策略模板", ["保守", "中性", "積極"], index=1)
# 模型切換（Prophet / XGBoost）
model_choice = st.radio("Sales model", ["Prophet", "XGBoost"], index=0, horizontal=True)


# =======================
# KPI Header
# =======================
st.title("Hotel AI Decision Dashboard")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Revenue", "$1.28M", "+5%")
col2.metric("OCC", "78%", "+2%")
col3.metric("ADR", "$3,250", "+3%")
col4.metric("RevPAR", "$2,535", "+2.5%")

# =======================
# Fetch data (mock)
# =======================
# 依切換選擇銷售預測模型
df_sales = forecast_sales(days) if model_choice == "Prophet" else forecast_sales_xgb(days)
df_occ = fetch_occupancy_forecast(days)
df_price = fetch_competitor_prices(days)

df = df_sales.merge(df_occ, on="Date").merge(df_price, on="Date")

df = df.rename(columns={
    "SalesForecast": "SalesForecast",
    "OccForecast": "OccForecast"
})


# 改回舊欄位名，避免 suggest_price 找不到
df = df.rename(columns={
    "SalesForecast": "SalesForecast",
    "OccForecast": "OccForecast"
})


# Suggested price rule
def suggest_price(row, mode="中性"):
    # baseline by OCC and competitors
    if row["OccForecast"] >= 0.85:
        base = row["Comp P75"]
        bump = 0.05 if mode == "積極" else (0.02 if mode == "中性" else 0.0)
    elif row["OccForecast"] >= 0.7:
        base = row["Comp P50"]
        bump = 0.02 if mode == "積極" else (0.01 if mode == "中性" else 0.0)
    else:
        base = row["Comp P50"] - 100
        bump = -0.02 if mode == "積極" else (-0.01 if mode == "中性" else 0.0)
    return int(round(base * (1 + bump)))

df["Suggested Price"] = df.apply(lambda r: suggest_price(r, pricing_mode), axis=1)

# Executive Summary
st.subheader("AI Executive Summary")
weak_days = (df["OccForecast"] < 0.6).sum()
strong_days = (df["OccForecast"] >= 0.85).sum()
avg_occ = df["OccForecast"].mean()
st.info(
    f"接下來 {days} 天平均入住率約 {avg_occ:.0%}，旺日 {strong_days} 天、弱日 {weak_days} 天。"
    f" 建議旺日對齊競品 P75 並{'加價' if pricing_mode!='保守' else '維持'}，弱日推出官網優惠與加值方案。"
)

# =======================
# Tabs
# =======================
tab1, tab2, tab3 = st.tabs(["📈 Sales Forecast", "🏠 Occupancy Forecast", "💰 Dynamic Pricing"])

# Tab 1 - Sales Forecast
with tab1:
    st.subheader("未來銷售量預測")
    fig_sales = px.line(df_sales, x="Date", y="SalesForecast", markers=True)
    st.plotly_chart(fig_sales, use_container_width=True)
    st.dataframe(df_sales)

# Tab 2 - Occupancy Forecast
with tab2:
    st.subheader("未來入住率預測")
    fig_occ = px.line(df_occ, x="Date", y="OccForecast", markers=True)
    fig_occ.add_hline(y=0.6, line_dash="dot")  # 阈值線
    fig_occ.add_hline(y=0.85, line_dash="dot")
    st.plotly_chart(fig_occ, use_container_width=True)
    st.dataframe(df_occ)

# Tab 3 - Dynamic Pricing
with tab3:
    st.subheader("競業動態定價（含建議）")
    # Decision cards
    st.markdown("### 決策卡")
    # Top 3 strong & weak by OCC
    top_strong = df.sort_values("OccForecast", ascending=False).head(3)
    top_weak = df.sort_values("OccForecast", ascending=True).head(3)

    def render_card(row, kind="strong"):
        date_str = row["Date"].strftime("%Y-%m-%d")
        if kind == "strong":
            st.success(
                f"**{date_str}｜Demand Surge**  \n"
                f"預測入住率：**{row['OccForecast']:.0%}** ｜ 競品 P75：${int(row['Comp P75'])}  \n"
                f"👉 建議房價：**${int(row['Suggested Price'])}**（現價 ${int(row['My Price'])}）  \n"
                f"理由：旺日 + 高競品，維持轉化可小幅上調"
            )
        else:
            st.warning(
                f"**{date_str}｜需求偏弱**  \n"
                f"預測入住率：**{row['OccForecast']:.0%}** ｜ 競品 P50：${int(row['Comp P50'])}  \n"
                f"👉 建議房價：**${int(row['Suggested Price'])}**（現價 ${int(row['My Price'])}）  \n"
                f"策略：平日促銷 / 官網加碼 / 加值方案"
            )

    left, right = st.columns(2)
    with left:
        st.caption("🏷️ 旺日建議（Top 3）")
        for _, r in top_strong.iterrows():
            render_card(r, "strong")
    with right:
        st.caption("🧊 淡日建議（Top 3）")
        for _, r in top_weak.iterrows():
            render_card(r, "weak")

    st.markdown("---")
    st.markdown("### 價格走勢")
    fig_price = px.line(df, x="Date", y=["My Price", "Comp P50", "Comp P75", "Suggested Price"], markers=True)
    st.plotly_chart(fig_price, use_container_width=True)

    st.markdown("### 建議價表格（可下載）")
    st.dataframe(df[["Date","My Price","Comp P50","Comp P75","OccForecast","Suggested Price"]])
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("下載建議價 CSV", csv, file_name="pricing_suggestions.csv", mime="text/csv")

# ====== Developer note ======
st.caption("Developer note: 將 fetch_* 函式改為 requests 調用您的 FastAPI 端點即可切換為真資料。")
