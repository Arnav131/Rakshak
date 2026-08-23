# Supabase database runbook

1. Copy `.env.example` to `.env`.
2. In Supabase, open **Connect** and copy the Session pooler Postgres URL.
3. Set `DATABASE_URL` in `.env`.

```bash
pip install -r requirements.txt
python backend/manage.py makemigrations
python backend/manage.py migrate
python backend/manage.py seed_master_data
python backend/manage.py seed_routes
python backend/manage.py seed_sensors
python backend/manage.py seed_demo_data
python backend/manage.py seed_users
python backend/manage.py runserver
```

`makemigrations` should normally say `No changes detected`.
SQLite is intentionally blocked; use Supabase/PostgreSQL for every Django query.
