from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import date
from api.src.db import fetch_df

def _load_history():
    sql = """
    SELECT dt::date AS dt,
           COALESCE(rooms_sold, 0) AS rooms_sold,
           COALESCE(occupancy_rate, 0) AS occupancy
    FROM bookings_daily
    WHERE dt <= CURRENT_DATE
    ORDER BY dt;
    """
    return fetch_df(sql)

def _future_index(days: int) -> pd.DatetimeIndex:
    return pd.date_range(start=pd.to_datetime(date.today()), periods=days, freq="D")

# Prophet 版：銷售量
def forecast_sales(days: int = 30) -> pd.DataFrame:
    hist = _load_history()
    ds = pd.to_datetime(hist["dt"])
    y = hist["rooms_sold"].astype(float)

    try:
        from prophet import Prophet
        m = Prophet(weekly_seasonality=True, yearly_seasonality=False, daily_seasonality=False)
        m.fit(pd.DataFrame({"ds": ds, "y": y}))
        future = pd.DataFrame({"ds": _future_index(days)})
        fcst = m.predict(future)
        yhat = np.maximum(0, np.round(fcst["yhat"]).astype(int))
        return pd.DataFrame({"Date": fcst["ds"].dt.date, "SalesForecast": yhat})
    except Exception:
        # 後備：以星期幾平均 + 噪音
        dow_avg = hist.groupby(pd.to_datetime(hist["dt"]).dt.dayofweek)["rooms_sold"].mean()
        future = _future_index(days)
        vals = [dow_avg.get(d.dayofweek, y.mean()) for d in future]
        return pd.DataFrame({"Date": future.date, "SalesForecast": np.array(vals, int)})

# Prophet 版：入住率（0~1）
def forecast_occupancy(days: int = 30) -> pd.DataFrame:
    hist = _load_history()
    ds = pd.to_datetime(hist["dt"])
    y = hist["occupancy"].astype(float)

    try:
        from prophet import Prophet
        m = Prophet(weekly_seasonality=True, yearly_seasonality=False, daily_seasonality=False)
        m.fit(pd.DataFrame({"ds": ds, "y": y}))
        future = pd.DataFrame({"ds": _future_index(days)})
        fcst = m.predict(future)
        occ = np.clip(fcst["yhat"].values, 0.2, 0.98)
        return pd.DataFrame({"Date": future["ds"].dt.date, "OccForecast": occ})
    except Exception:
        dow_avg = hist.groupby(pd.to_datetime(hist["dt"]).dt.dayofweek)["occupancy"].mean()
        future = _future_index(days)
        vals = [dow_avg.get(d.dayofweek, y.mean()) for d in future]
        return pd.DataFrame({"Date": future.date, "OccForecast": np.clip(vals, 0.2, 0.98)})

# XGBoost 版：銷售量（與 Prophet 並存）
def forecast_sales_xgb(days: int = 30) -> pd.DataFrame:
    from xgboost import XGBRegressor
    from sklearn.model_selection import train_test_split

    hist = _load_history()
    hist = hist.assign(dt=pd.to_datetime(hist["dt"]))
    hist["dow"] = hist["dt"].dt.dayofweek
    hist["is_weekend"] = (hist["dow"] >= 5).astype(int)
    hist["sin_7"] = np.sin(2*np.pi*hist["dt"].dt.dayofyear/7.0)
    hist["cos_7"] = np.cos(2*np.pi*hist["dt"].dt.dayofyear/7.0)

    X = hist[["dow", "is_weekend", "sin_7", "cos_7"]]
    y = hist["rooms_sold"].astype(float)

    if len(hist) > 20:
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, shuffle=False)
    else:
        X_tr, y_tr = X, y

    model = XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9, objective="reg:squarederror"
    )
    model.fit(X_tr, y_tr)

    future = _future_index(days)
    F = pd.DataFrame({
        "dow": future.dayofweek,
        "is_weekend": (future.dayofweek >= 5).astype(int),
        "sin_7": np.sin(2*np.pi*future.dayofyear/7.0),
        "cos_7": np.cos(2*np.pi*future.dayofyear/7.0),
    })
    pred = np.maximum(0, np.round(model.predict(F)).astype(int))
    return pd.DataFrame({"Date": future.date, "SalesForecast": pred})
