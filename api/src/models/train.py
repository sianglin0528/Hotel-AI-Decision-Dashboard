import os, joblib
from prophet import Prophet
from api.src.db import fetch_df

os.makedirs("models_store", exist_ok=True)

def train_sales():
    df = fetch_df("SELECT dt AS ds, rooms_sold AS y FROM bookings_daily ORDER BY dt")
    m = Prophet(weekly_seasonality=True, yearly_seasonality=True)
    m.fit(df)
    joblib.dump(m, "models_store/sales.prophet.pkl")

def train_occ():
    df = fetch_df("""
        SELECT dt AS ds, rooms_sold::float / NULLIF(rooms_available,0) AS y
        FROM bookings_daily ORDER BY dt
    """).dropna()
    m = Prophet(weekly_seasonality=True, yearly_seasonality=True)
    m.fit(df)
    joblib.dump(m, "models_store/occ.prophet.pkl")

if __name__ == "__main__":
    train_sales()
    train_occ()
    print("✅ Models trained and saved")
