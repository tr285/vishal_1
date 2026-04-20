from flask import Flask, redirect
from werkzeug.exceptions import HTTPException
from config.settings import settings

# Initialize application
app = Flask(__name__)
app.secret_key = settings.SECRET_KEY

# Register Blueprints
from routes.auth import auth_bp
from routes.user import user_bp
from routes.transaction import transaction_bp
from routes.admin import admin_bp
from routes.api import api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(transaction_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp, url_prefix='/api')

@app.route("/")
def home():
    return redirect("/login")

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return e
    
    error_message = str(e)
    if "No active database connection" in error_message:
        return """
        <div style="font-family: sans-serif; padding: 40px; text-align: center; color: #333;">
            <h1 style="color: #ef4444;">Database Connection Error</h1>
            <p>The application could not connect to either the primary MySQL database or the fallback Supabase PostgreSQL database.</p>
            <p><strong>Fix:</strong> Ensure your <code>.env</code> file or Vercel Environment Variables are correctly configured with a <code>SUPABASE_DB_URL</code> or correct MySQL credentials.</p>
        </div>
        """, 500

    return f"<h1>Internal Server Error</h1><p>{error_message}</p>", 500

if __name__ == "__main__":
  app.run(debug=True, port=8080)