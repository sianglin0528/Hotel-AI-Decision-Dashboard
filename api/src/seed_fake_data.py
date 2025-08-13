import numpy as np, pandas as pd
from datetime import date, timedelta
from sqlalchemy import text
from api.src.db import get_engine

engine = get_engine()

def ensure_tables():
    sql = """
    CREATE TABLE IF NOT EXISTS compset_rates(
      dt date NOT NULL,
      hotel varchar(50) NOT NULL,
      price numeric NOT NULL
    );
    CREATE TABLE IF NOT EXISTS bookings_daily(
      dt date PRIMARY KEY,
      rooms_sold int,
      rooms_available int,
      adr numeric,
      revenue numeric,
      occupancy_rate numeric,
      revpar numeric,
      channel varchar(50),
      room_type varchar(50)
    );"""
    with engine.begin() as c:
        c.execute(text(sql))

def gen_bookings(n_days=90):
    start = date.today() - timedelta(days=n_days-1)
    days = [start + timedelta(d) for d in range(n_days)]
    rooms_avail = np.full(n_days, 120)
    occ = np.clip(np.random.normal(0.72, 0.12, n_days), 0.35, 0.98)
    rooms_sold = (rooms_avail * occ).astype(int)
    adr = np.round(np.random.normal(3200, 250, n_days), 0)
    revenue = rooms_sold * adr
    revpar = revenue / rooms_avail
    channels = np.random.choice(["官網","Booking","Agoda"], size=n_days)
    room_type = np.random.choice(["標準房","豪華雙人房"], size=n_days)
    return pd.DataFrame({
        "dt": days, "rooms_sold": rooms_sold, "rooms_available": rooms_avail,
        "adr": adr, "revenue": revenue,
        "occupancy_rate": rooms_sold/rooms_avail, "revpar": revpar,
        "channel": channels, "room_type": room_type
    })

def gen_compset(n_days=90, k=4):
    start = date.today() - timedelta(days=n_days-30)  # 多留 30 天給百分位
    days = [start + timedelta(d) for d in range(n_days+30)]
    rows = []
    for h in range(k):
        bias = np.random.randint(-150, 150)
        base = np.random.normal(3200 + bias, 220, len(days))
        for d, p in zip(days, base):
            rows.append({"dt": d, "hotel": f"Comp{h+1}", "price": max(1800, int(p))})
    return pd.DataFrame(rows)

def main():
    ensure_tables()
    df_b = gen_bookings(90)
    df_c = gen_compset(120, 5)
    with engine.begin() as c:
        df_b.to_sql("bookings_daily", c.connection, if_exists="replace", index=False)
        df_c.to_sql("compset_rates", c.connection, if_exists="replace", index=False)
    print("✅ seed done")

if __name__ == "__main__":
    main()
