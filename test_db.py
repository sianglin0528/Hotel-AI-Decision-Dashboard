from sqlalchemy import create_engine, text

# 你的 Postgres 連線字串
DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/mydb"

try:
    engine = create_engine(DATABASE_URL, echo=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        print("✅ 成功連線到資料庫！查詢結果：", result)
except Exception as e:
    print("❌ 無法連線到資料庫")
    print(e)
