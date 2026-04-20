import psycopg2
import os

DATABASE_URL = os.getenv("SUPABASE_DB_URL")

db = psycopg2.connect(DATABASE_URL)
cursor = db.cursor()