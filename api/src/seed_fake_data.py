import numpy as np, pandas as pd
from datetime import date, timedelta
from api.src.db import get_engine
from sqlalchemy import text


engine=get_engine()

with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS bookings_daily(
      dt date primary key,
      rooms_sold int,
      rooms_available int,
      adr numeric,
      revenue numeric
    );
    CREATE TABLE IF NOT EXISTS compset_rates(
      dt date,
      hotel varchar(80),
      price numeric,
      primary key (dt, hotel)
    );
    """))

start = date.today() - timedelta(days=365)
dates = pd.date_range(start, periods=365, freq="D")
rng = np.random.default_rng(42)
rooms_available = 120
sold = (rng.normal(0.72, 0.1, len(dates)) * rooms_available).clip(30, rooms_available).astype(int)
adr = np.round(rng.normal(3250, 300, len(dates)).clip(2200, 4200), 0)
rev = sold * adr

book = pd.DataFrame({
    "dt": dates.date,
    "rooms_sold": sold,
    "rooms_available": rooms_available,
    "adr": adr,
    "revenue": rev
})
book.to_sql("bookings_daily", engine, if_exists="append", index=False)

rows = []
for h in ["CompA","CompB","CompC","CompD","CompE"]:
    base = rng.integers(2800, 3600)
    prices = (base + np.round(rng.normal(0, 180, len(dates)))).clip(2400, 4200)
    rows += [{"dt": d.date(), "hotel": h, "price": float(p)} for d, p in zip(dates, prices)]
pd.DataFrame(rows).to_sql("compset_rates", engine, if_exists="append", index=False)

print("✅ Fake data seeded")
