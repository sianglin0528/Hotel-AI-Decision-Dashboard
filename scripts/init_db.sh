#!/usr/bin/env bash
set -e
DB_CONT=postgres16

echo "▶ Restart PostgreSQL container..."
docker restart $DB_CONT >/dev/null || true

echo "▶ Ensure database hotel_db exists..."
docker exec -it $DB_CONT psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='hotel_db'" \
  | grep -q 1 || docker exec -it $DB_CONT psql -U postgres -c "CREATE DATABASE hotel_db;"

echo "▶ Seed fake data..."
export PYTHONPATH=$(pwd)
python api/src/seed_fake_data.py

echo "▶ Health check: list tables"
docker exec -it $DB_CONT psql -U postgres -d hotel_db -c "\dt"

echo "✅ Database init complete!"
