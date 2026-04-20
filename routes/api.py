from flask import Blueprint, jsonify, session
from services.user_service import UserService
from services.transaction_service import TransactionService

api_bp = Blueprint('api', __name__)

@api_bp.route("/get-balance")
def get_balance():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user = UserService.get_user_by_id(session["user_id"])
    if user:
        return jsonify({"balance": float(user["balance"])})
    return jsonify({"error": "User not found"}), 404

@api_bp.route("/live-transactions")
def live_transactions():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session["user_id"]
    user = UserService.get_user_by_id(user_id)
    
    if user['role'] == 'admin':
        transactions = TransactionService.get_all_transactions(limit=50)
    else:
        transactions = TransactionService.get_user_transactions(user_id, limit=20)
        
    # Format transactions for JSON
    formatted = []
    for t in transactions:
        formatted.append({
            "id": t["id"],
            "amount": float(t["amount"]),
            "timestamp": t["timestamp"].strftime("%d %b %Y, %I:%M %p"),
            "sender_name": t["sender_name"],
            "receiver_name": t["receiver_name"],
            "is_credit": True if "sender_id" in t and t["receiver_id"] == user_id else False
        })
        
    return jsonify({"transactions": formatted})
