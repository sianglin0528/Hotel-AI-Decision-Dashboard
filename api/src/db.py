# api/src/db.py
import os
import pandas as pd
from sqlalchemy import create_engine, text

def _read_from_streamlit():
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL") or st.secrets.get("PG_DSN")
    except Exception:
        return None

def get_database_url():
    url = _read_from_streamlit()
    if url:
        return url
    return os.getenv("DATABASE_URL") or os.getenv("PG_DSN")

# --- engine 快取，整個 app 共用一個連線池 ---
_engine = None
def get_engine(echo: bool = False):
    global _engine
    if _engine is None:
        url = get_database_url()
        if not url:
            raise RuntimeError("找不到 DATABASE_URL。請在 .streamlit/secrets.toml 或環境變數設定。")
        _engine = create_engine(url, pool_pre_ping=True, future=True, echo=echo)
    return _engine

# --- 常用 helper ---
def fetch_df(sql: str, params: dict | None = None, engine=None) -> pd.DataFrame:
    eng = engine or get_engine()
    with eng.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

def exec_sql(sql: str, params: dict | None = None, engine=None) -> None:
    eng = engine or get_engine()
    with eng.begin() as conn:
        conn.execute(text(sql), params or {})

# 自測（可留可刪）
if __name__ == "__main__":
    with get_engine(echo=True).connect() as conn:
        print(conn.execute(text("SELECT 1")).scalar())
