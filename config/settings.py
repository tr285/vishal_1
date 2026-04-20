import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
    
    # Primary DB (MySQL)
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "MYSQL_PASSWORD")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "airtel_payment_bank")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    
    # Secondary DB (Supabase/PostgreSQL)
    SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")

settings = Config()
