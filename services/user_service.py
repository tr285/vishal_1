from models.database import db
from werkzeug.security import generate_password_hash, check_password_hash

class UserService:
    @staticmethod
    def create_user(full_name, mobile, password):
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        query = "INSERT INTO users (full_name, mobile, password) VALUES (%s, %s, %s)"
        db.execute(query, (full_name, mobile, hashed_password))

    @staticmethod
    def authenticate_user(mobile, password):
        query = "SELECT * FROM users WHERE mobile=%s"
        user = db.fetchone(query, (mobile,))
        if user and check_password_hash(user["password"], password):
            return user
        return None

    @staticmethod
    def get_user_by_id(user_id):
        query = "SELECT id, full_name, mobile, balance, role FROM users WHERE id=%s"
        return db.fetchone(query, (user_id,))

    @staticmethod
    def update_profile(user_id, full_name):
        query = "UPDATE users SET full_name=%s WHERE id=%s"
        db.execute(query, (full_name, user_id))

    @staticmethod
    def change_password(user_id, current_password, new_password):
        # Fetch current to verify
        query = "SELECT password FROM users WHERE id=%s"
        user = db.fetchone(query, (user_id,))
        if not user or not check_password_hash(user["password"], current_password):
            return False
            
        hashed_password = generate_password_hash(new_password, method="pbkdf2:sha256")
        update_query = "UPDATE users SET password=%s WHERE id=%s"
        db.execute(update_query, (hashed_password, user_id))
        return True

    @staticmethod
    def get_all_users():
        query = "SELECT id, full_name, mobile, balance, role FROM users"
        return db.fetchall(query)

    @staticmethod
    def get_admin_user():
        query = "SELECT id FROM users WHERE role='admin' LIMIT 1"
        return db.fetchone(query)
        
    @staticmethod
    def get_total_users():
        query = "SELECT COUNT(*) AS total_users FROM users"
        res = db.fetchone(query)
        return res["total_users"] if res else 0

    @staticmethod
    def get_total_balance():
        query = "SELECT SUM(balance) AS total_balance FROM users"
        res = db.fetchone(query)
        return res["total_balance"] if res and res["total_balance"] else 0
