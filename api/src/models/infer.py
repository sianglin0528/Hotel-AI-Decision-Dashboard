import joblib, pandas as pd
from datetime import date, timedelta
from api.src.db import fetch_df

def _future(days: int) -> pd.DataFrame:
    start = date.today()
    return pd.DataFrame({"ds": [start + timedelta(days=i) for i in range(int(days))]})

def forecast_sales(days: int = 30) -> pd.DataFrame:
    model  = joblib.load("models_store/sales.prophet.pkl")
    future = _future(days)
    out = model.predict(future)[["ds", "yhat"]].copy()
    out.rename(columns={"ds": "Date", "yhat": "SalesForecast"}, inplace=True)
    out["Date"] = pd.to_datetime(out["Date"]).dt.date
    return out

def forecast_occupancy(days: int = 30) -> pd.DataFrame:
    model  = joblib.load("models_store/occ.prophet.pkl")
    future = _future(days)
    out = model.predict(future)[["ds", "yhat"]].copy()
    out.rename(columns={"ds": "Date", "yhat": "OccForecast"}, inplace=True)
    out["Date"] = pd.to_datetime(out["Date"]).dt.date
    return out

# 在 infer.py 補上
def _load_hist_sales():
    q = """
    SELECT
      dt::date               AS "Date",
      rooms_sold::float      AS y,
      rooms_available::float AS rooms_avail   -- 加這行，和訓練一致
    FROM bookings_daily
    ORDER BY dt
    """
    df = fetch_df(q)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df

def _add_feats_for_xgb(df, LAGS, ROLLS):
    df = df.copy().sort_values("Date")
    for l in LAGS:
        df[f"lag_{l}"] = df["y"].shift(l)
    for w, stat in ROLLS:
        if stat == "mean":
            df[f"roll_{w}_mean"] = df["y"].rolling(w).mean()
    df["dow"]   = df["Date"].dt.weekday
    df["dom"]   = df["Date"].dt.day
    df["month"] = df["Date"].dt.month
    return df

def forecast_sales_xgb(days: int = 30) -> pd.DataFrame:
    art = joblib.load("models_store/xgb_sales.pkl")
    model, FEATURES, LAGS, ROLLS = art["model"], art["features"], art["lags"], art["rolls"]

    hist = _load_hist_sales().copy()
    work = hist.copy()
    preds = []

    # 若 rooms_avail 有缺，先補
    if "rooms_avail" in work.columns:
        work["rooms_avail"] = work["rooms_avail"].ffill().bfill()

    current = work["Date"].max()

    for _ in range(int(days)):
        next_date = current + timedelta(days=1)

        # 用最後一筆 rooms_avail 當未來的供應量（先簡單 ffill）
        base_avail = work["rooms_avail"].iloc[-1] if "rooms_avail" in work.columns else None
        new_row = {"Date": next_date, "y": None}
        if base_avail is not None:
            new_row["rooms_avail"] = base_avail

        tmp = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)

        # 造特徵
        tmp = _add_feats_for_xgb(tmp, LAGS, ROLLS)

        # 再次保證 rooms_avail 不為空
        if "rooms_avail" in tmp.columns:
            tmp["rooms_avail"] = tmp["rooms_avail"].ffill().bfill()

        # 有些特徵可能不在 tmp（極少見），做個保底
        available_feats = [f for f in FEATURES if f in tmp.columns]
        xrow = tmp.iloc[[-1]][available_feats]

        yhat = float(model.predict(xrow)[0])
        preds.append({"Date": next_date.date(), "SalesForecast": yhat})

        # 把預測回灌，供下一日 lag/roll 使用
        work.loc[len(work)] = {"Date": next_date, "y": yhat, **({"rooms_avail": base_avail} if base_avail is not None else {})}
        current = next_date

    return pd.DataFrame(preds)


