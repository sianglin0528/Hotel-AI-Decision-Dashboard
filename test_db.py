# test_db.py
from api.src.db import get_engine
from sqlalchemy import text

def main():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT NOW()"))
            print("✅ DB 連線成功！現在時間：", result.fetchall())
    except Exception as e:
        print("❌ DB 連線失敗：", e)

if __name__ == "__main__":
    main()
