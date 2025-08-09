# api/src/models/train_xgb.py
import os, joblib, numpy as np, pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor
from api.src.db import fetch_df

os.makedirs("models_store", exist_ok=True)

# 1) 讀歷史資料（保留大寫欄位名 + 防呆）
SQL = """
SELECT
  dt::date               AS "Date",        -- 加雙引號保留大寫
  rooms_sold::float      AS y,
  rooms_available::float AS rooms_avail
FROM bookings_daily
ORDER BY dt
"""
hist = fetch_df(SQL)

# 落地防呆：萬一 alias 沒被保留（或不同 DB 行為），這邊統一欄位名
hist.columns = [c.strip() for c in hist.columns]
if "Date" not in hist.columns and "date" in hist.columns:
    hist.rename(columns={"date": "Date"}, inplace=True)
if "y" not in hist.columns and "rooms_sold" in hist.columns:
    hist.rename(columns={"rooms_sold": "y"}, inplace=True)

# 轉時間型態（避免時區干擾）
hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)

# 可選：暫時印出欄位確認（OK 後可刪）
# print("hist columns =>", hist.columns.tolist())
# print(hist.head())


# 2) 造特徵（lags + rolling + 日期）
LAGS  = [1, 7, 14, 28]
ROLLS = [(7, "mean"), (28, "mean")]

def add_features(df: pd.DataFrame) -> pd.DataFrame:
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

df = add_features(hist).dropna().reset_index(drop=True)

FEATURES = [c for c in df.columns if c not in ["Date", "y"]]
X, y = df[FEATURES], df["y"]

# 3) 時序交叉驗證挑最好的一個
tscv = TimeSeriesSplit(n_splits=5)
best_model, best_rmse = None, 1e9

params = dict(
    n_estimators=800, learning_rate=0.05, max_depth=6,
    subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
    random_state=42, tree_method="hist"
)

for tr, va in tscv.split(X):
    m = XGBRegressor(**params)
    m.fit(X.iloc[tr], y.iloc[tr], eval_set=[(X.iloc[va], y.iloc[va])], verbose=False)
    rmse = float(np.sqrt(((m.predict(X.iloc[va]) - y.iloc[va]) ** 2).mean()))
    if rmse < best_rmse:
        best_model, best_rmse = m, rmse

print(f"✅ XGB best RMSE: {best_rmse:.3f}")

# 4) 存模型 + 特徵設定（給推論用）
artifact = {
    "model": best_model,
    "features": FEATURES,
    "lags": LAGS,
    "rolls": ROLLS,
}
joblib.dump(artifact, "models_store/xgb_sales.pkl")
print("💾 saved -> models_store/xgb_sales.pkl")
