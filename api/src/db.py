import os
import pandas as pd
from sqlalchemy import create_engine, text


from dotenv import load_dotenv
load_dotenv()
# Debug: 看現在讀到的 DATABASE_URL 是什麼
print(">>> DEBUG DATABASE_URL =", os.getenv("DATABASE_URL"))

def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set (put it in .env or Streamlit Secrets)")
    return create_engine(os.getenv("DATABASE_URL"))

def fetch_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    eng = get_engine()
    with eng.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})

if __name__ == "__main__":
    from sqlalchemy import text
    eng = get_engine()
    with eng.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(result.fetchall())