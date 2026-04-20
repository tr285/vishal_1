import os
import mysql.connector
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseAbstractionLayer:
    def __init__(self):
        self.mysql_conn = None
        self.pg_conn = None
        self.sqlite_conn = None
        self._active_db = None
        self.connect()

    def connect(self):
        # 1. Try MySQL First
        try:
            self.mysql_conn = mysql.connector.connect(
                host=settings.MYSQL_HOST,
                user=settings.MYSQL_USER,
                password=settings.MYSQL_PASSWORD,
                database=settings.MYSQL_DATABASE,
                port=settings.MYSQL_PORT
            )
            if self.mysql_conn.is_connected():
                self._active_db = 'mysql'
                logger.info("Successfully connected to Primary DB (MySQL).")
                self.initialize_schema()
                self.ensure_mock_admin()
                return
        except Exception as e:
            logger.warning(f"MySQL Connection failed: {e}. Falling back...")

        # 2. Fallback to Supabase (PostgreSQL)
        if settings.SUPABASE_DB_URL:
            try:
                self.pg_conn = psycopg2.connect(settings.SUPABASE_DB_URL)
                self._active_db = 'postgres'
                logger.info("Successfully connected to Secondary DB (Supabase/PostgreSQL).")
                self.initialize_schema()
                self.ensure_mock_admin()
                return
            except Exception as e:
                logger.error(f"Supabase Connection failed: {e}.")
                
        # 3. Final Fallback to Local SQLite (Zero-config)
        try:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'airtel_local.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self.sqlite_conn.row_factory = sqlite3.Row
            self._active_db = 'sqlite'
            logger.info("Successfully connected to Fallback DB (SQLite Local).")
            self.initialize_schema()
            
            # Since SQLite is blank, let's inject a mock Admin user to allow deposits
            self.ensure_mock_admin()
            return
        except Exception as e:
            logger.error(f"SQLite fallback failed: {e}")
        
        logger.error("No database connections available!")

    def _get_cursor(self):
        if self._active_db == 'mysql' and self.mysql_conn:
            if not self.mysql_conn.is_connected():
                self.connect()
            raw_cursor = self.mysql_conn.cursor(dictionary=True)
        elif self._active_db == 'postgres' and self.pg_conn:
            if self.pg_conn.closed != 0:
                self.connect()
            raw_cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        elif self._active_db == 'sqlite' and self.sqlite_conn:
            raw_cursor = self.sqlite_conn.cursor()
        else:
            raise Exception("No active database connection")
            
        class CursorWrapper:
            def __init__(self, cursor, active_db):
                self._cursor = cursor
                self._active_db = active_db
            
            def execute(self, query, params=None):
                if self._active_db == 'sqlite':
                    query = query.replace('%s', '?')
                return self._cursor.execute(query, params or ())
                
            def __getattr__(self, attr):
                return getattr(self._cursor, attr)
                
        return CursorWrapper(raw_cursor, self._active_db)

    def execute(self, query, params=None):
        cursor = self._get_cursor()
        try:
            cursor.execute(query, params)
            
            if self._active_db == 'mysql':
                self.mysql_conn.commit()
            elif self._active_db == 'postgres':
                self.pg_conn.commit()
            elif self._active_db == 'sqlite':
                self.sqlite_conn.commit()
        except Exception as e:
            self.rollback()
            raise e
        finally:
            cursor.close()

    def _parse_sqlite_row(self, row):
        if not row:
            return row
        import datetime
        d = dict(row)
        for k, v in d.items():
            if k == 'timestamp' and isinstance(v, str):
                try:
                    d[k] = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
        return d

    def fetchall(self, query, params=None):
        cursor = self._get_cursor()
        try:
            cursor.execute(query, params)
            if self._active_db == 'sqlite':
                return [self._parse_sqlite_row(row) for row in cursor.fetchall()]
            return cursor.fetchall()
        finally:
            cursor.close()

    def fetchone(self, query, params=None):
        cursor = self._get_cursor()
        try:
            cursor.execute(query, params)
            res = cursor.fetchone()
            if self._active_db == 'sqlite' and res:
                return self._parse_sqlite_row(res)
            return res
        finally:
            cursor.close()
            
    def commit(self):
        if self._active_db == 'mysql' and self.mysql_conn:
            self.mysql_conn.commit()
        elif self._active_db == 'postgres' and self.pg_conn:
            self.pg_conn.commit()
        elif self._active_db == 'sqlite' and self.sqlite_conn:
            self.sqlite_conn.commit()

    def rollback(self):
        if self._active_db == 'mysql' and self.mysql_conn:
            self.mysql_conn.rollback()
        elif self._active_db == 'postgres' and self.pg_conn:
            self.pg_conn.rollback()
        elif self._active_db == 'sqlite' and self.sqlite_conn:
            self.sqlite_conn.rollback()

    def initialize_schema(self):
        mysql_schema = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                mobile VARCHAR(15) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                balance DECIMAL(15, 2) DEFAULT 0.00,
                role VARCHAR(10) DEFAULT 'user'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'success',
                transaction_type VARCHAR(50) DEFAULT 'transfer',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS deposits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                utr VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS external_transfers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                bank_name VARCHAR(100) NOT NULL,
                account_no VARCHAR(50) NOT NULL,
                ifsc VARCHAR(20) NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'completed',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS loans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                amount_granted DECIMAL(15, 2) NOT NULL,
                amount_due DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        ]

        pg_schema = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                mobile VARCHAR(15) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                balance DECIMAL(15, 2) DEFAULT 0.00,
                role VARCHAR(10) DEFAULT 'user'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                sender_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                receiver_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'success',
                transaction_type VARCHAR(50) DEFAULT 'transfer',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS deposits (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount DECIMAL(15, 2) NOT NULL,
                utr VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS external_transfers (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                bank_name VARCHAR(100) NOT NULL,
                account_no VARCHAR(50) NOT NULL,
                ifsc VARCHAR(20) NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'completed',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS loans (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount_granted DECIMAL(15, 2) NOT NULL,
                amount_due DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        sqlite_schema = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name VARCHAR(100) NOT NULL,
                mobile VARCHAR(15) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                balance DECIMAL(15, 2) DEFAULT 0.00,
                role VARCHAR(10) DEFAULT 'user'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'success',
                transaction_type VARCHAR(50) DEFAULT 'transfer',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                utr VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS external_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NOT NULL,
                bank_name VARCHAR(100) NOT NULL,
                account_no VARCHAR(50) NOT NULL,
                ifsc VARCHAR(20) NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'completed',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NOT NULL,
                amount_granted DECIMAL(15, 2) NOT NULL,
                amount_due DECIMAL(15, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        ]

        if self._active_db == 'mysql':
            schema_to_run = mysql_schema
        elif self._active_db == 'postgres':
            schema_to_run = pg_schema
        else:
            schema_to_run = sqlite_schema

        for query in schema_to_run:
            self.execute(query)

    def ensure_mock_admin(self):
        admin = self.fetchone("SELECT id FROM users WHERE role='admin'")
        if not admin:
            # Create a mock admin user to facilitate mock deposits safely
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash("admin143", method="pbkdf2:sha256")
            self.execute("INSERT INTO users (full_name, mobile, password, balance, role) VALUES (%s, %s, %s, %s, %s)",
                         ("Admin Bank", "admin143", hashed, 1000000.00, "admin"))

# Singleton instance
db = DatabaseAbstractionLayer()
