from models.database import db
from services.user_service import UserService
from decimal import Decimal
import logging

logger = logging.getLogger("transaction_service")
logger.setLevel(logging.INFO)

MAX_TRANSACTION_LIMIT = Decimal("1000000.00")  # ₹10 Lakhs max per transaction limit for fraud detection

class TransactionService:
    @staticmethod
    def get_user_transactions(user_id, limit=None):
        query = """
            SELECT t.id, t.amount, t.timestamp,
                   t.sender_id, t.receiver_id,
                   u1.full_name AS sender_name,
                   u2.full_name AS receiver_name
            FROM transactions t
            JOIN users u1 ON t.sender_id = u1.id
            JOIN users u2 ON t.receiver_id = u2.id
            WHERE t.sender_id=%s OR t.receiver_id=%s
            ORDER BY t.timestamp DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        return db.fetchall(query, (user_id, user_id))

    @staticmethod
    def get_all_transactions(limit=50):
        query = """
            SELECT t.id, t.amount, t.timestamp,
                   u1.full_name AS sender_name,
                   u2.full_name AS receiver_name
            FROM transactions t
            JOIN users u1 ON t.sender_id = u1.id
            JOIN users u2 ON t.receiver_id = u2.id
            ORDER BY t.timestamp DESC
            LIMIT %s
        """
        return db.fetchall(query, (limit,))
        
    @staticmethod
    def get_total_transactions_count():
        query = "SELECT COUNT(*) AS total_transactions FROM transactions"
        res = db.fetchone(query)
        return res["total_transactions"] if res else 0

    @staticmethod
    def transfer_money(sender_id, receiver_mobile, amount):
        if amount <= 0:
            return False, "Invalid amount"
            
        if amount > MAX_TRANSACTION_LIMIT:
            return False, "Security Alert: Amount exceeds transaction limit of ₹10,00,000."
            
        # Get Sender
        sender = UserService.get_user_by_id(sender_id)
        if not sender or Decimal(str(sender['balance'])) < amount:
            return False, "Insufficient balance"
            
        # Get Receiver
        query_recv = "SELECT id, full_name FROM users WHERE mobile=%s"
        receiver = db.fetchone(query_recv, (receiver_mobile,))
        if not receiver:
            return False, "Receiver not found"
            
        if sender_id == receiver['id']:
            return False, "Cannot send money to yourself"

        try:
            cursor = db._get_cursor()
            
            # Deduct from sender
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount, sender_id))
            # Add to receiver
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, receiver['id']))
            # Insert record
            cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount, transaction_type)
                VALUES (%s, %s, %s, %s)
            """, (sender_id, receiver['id'], amount, 'transfer'))
            
            db.commit()
            logger.info(f"Transfer SUCCESS: UID {sender_id} sent ₹{amount} to UID {receiver['id']}")
            return True, receiver['full_name']
            
        except Exception as e:
            db.rollback()
            logger.error(f"Transfer FAILED: {str(e)}")
            return False, str(e)
            
    @staticmethod
    def create_deposit_request(user_id, amount, utr):
        if amount <= 0:
            return False, "Invalid Amount"
            
        if amount > MAX_TRANSACTION_LIMIT:
            return False, "Security Alert: Deposit amount exceeds limit of ₹10,00,000. Please contact your branch."
            
        admin = UserService.get_admin_user()
        if not admin:
            return False, "Admin account not found for simulation"
            
        admin_id = admin["id"]
        
        if user_id == admin_id:
            return False, "Admin cannot deposit using this method"

        try:
            existing = db.fetchone("SELECT id FROM deposits WHERE utr=%s", (utr,))
            if existing:
                return False, "UTR has already been submitted for a deposit. Please wait for verification."

            cursor = db._get_cursor()
            cursor.execute("""
                INSERT INTO deposits (user_id, amount, utr, status)
                VALUES (%s, %s, %s, 'pending')
            """, (user_id, amount, utr))
            
            db.commit()
            logger.info(f"Deposit Created: UID {user_id} requested ₹{amount} (UTR: {utr})")
            return True, "Deposit request submitted successfully. Pending Admin verification."
            
        except Exception as e:
            db.rollback()
            logger.error(f"Deposit Creation FAILED: {str(e)}")
            return False, str(e)

    @staticmethod
    def approve_deposit(deposit_id):
        deposit = db.fetchone("SELECT * FROM deposits WHERE id=%s AND status='pending'", (deposit_id,))
        if not deposit:
            return False, "Deposit not found or already processed"
            
        amount = deposit['amount']
        user_id = deposit['user_id']
        
        admin = UserService.get_admin_user()
        if not admin:
             return False, "Admin account not found"
        admin_id = admin['id']
        
        try:
            cursor = db._get_cursor()
            
            # Add to admin pool
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, admin_id))
            # Add to user
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, user_id))
            # Insert record
            cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount)
                VALUES (%s, %s, %s)
            """, (admin_id, user_id, amount))
            # Update deposit status
            cursor.execute("UPDATE deposits SET status='approved' WHERE id=%s", (deposit_id,))
            
            db.commit()
            return True, "Deposit Approved"
        except Exception as e:
            db.rollback()
            return False, str(e)

    @staticmethod
    def reject_deposit(deposit_id):
        try:
            db.execute("UPDATE deposits SET status='rejected' WHERE id=%s", (deposit_id,))
            return True, "Deposit rejected"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_pending_deposits():
        query = """
            SELECT d.id, d.amount, d.utr, d.timestamp, u.full_name, u.mobile 
            FROM deposits d
            JOIN users u ON d.user_id = u.id
            WHERE d.status='pending'
            ORDER BY d.timestamp ASC
        """
        return db.fetchall(query)

    @staticmethod
    def delete_transaction(transaction_id):
        query = "DELETE FROM transactions WHERE id=%s"
        db.execute(query, (transaction_id,))

    @staticmethod
    def external_bank_transfer(user_id, bank_name, account_no, ifsc, amount):
        if amount <= 0:
            return False, "Invalid Amount"
        if amount > MAX_TRANSACTION_LIMIT:
            return False, "Amount exceeds transfer limit."
            
        user = UserService.get_user_by_id(user_id)
        if not user or Decimal(str(user['balance'])) < amount:
            return False, "Insufficient balance"
            
        admin = UserService.get_admin_user()
        if not admin:
            return False, "System bank not available"
            
        try:
            cursor = db._get_cursor()
            # Deduct from user
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount, user_id))
            # Deduct from admin (bank reserves leaving system)
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount, admin['id']))
            # Insert into external_transfers
            cursor.execute("""
                INSERT INTO external_transfers (user_id, bank_name, account_no, ifsc, amount) 
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, bank_name, account_no, ifsc, amount))
            
            db.commit()
            return True, "Bank Transfer Initiated Successfully"
        except Exception as e:
            db.rollback()
            return False, str(e)

    @staticmethod
    def apply_for_loan(user_id, amount):
        if amount <= 0:
            return False, "Invalid loan amount"
        if amount > 50000:
            return False, "Maximum instant loan allowed is ₹50,000"
            
        admin = UserService.get_admin_user()
        if not admin or Decimal(str(admin['balance'])) < amount:
            return False, "System resources temporarily unavailable for loans"
            
        amount_due = (Decimal(str(amount)) * Decimal('1.05')).quantize(Decimal('0.01'))  # 5% flat interest
        
        try:
            cursor = db._get_cursor()
            # Deduct from admin
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount, admin['id']))
            # Credit user
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, user_id))
            
            # Log as standard transaction from admin to user
            cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount)
                VALUES (%s, %s, %s)
            """, (admin['id'], user_id, amount))
            
            # Create Loan record
            cursor.execute("""
                INSERT INTO loans (user_id, amount_granted, amount_due, status)
                VALUES (%s, %s, %s, 'active')
            """, (user_id, amount, amount_due))
            
            db.commit()
            return True, "Loan granted successfully"
        except Exception as e:
            db.rollback()
            return False, str(e)

    @staticmethod
    def repay_loan(user_id, loan_id):
        # We enforce full repayment
        loan = db.fetchone("SELECT * FROM loans WHERE id=%s AND user_id=%s AND status='active'", (loan_id, user_id))
        if not loan:
            return False, "Loan not found or already repaid"
            
        amount_due = Decimal(str(loan['amount_due']))
        user = UserService.get_user_by_id(user_id)
        if not user or Decimal(str(user['balance'])) < amount_due:
            return False, "Insufficient balance to repay loan"
            
        admin = UserService.get_admin_user()
        try:
            cursor = db._get_cursor()
            # Deduct from user
            cursor.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount_due, user_id))
            # Send back to admin
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount_due, admin['id']))
            
            # Log repayment transaction
            cursor.execute("""
                INSERT INTO transactions (sender_id, receiver_id, amount)
                VALUES (%s, %s, %s)
            """, (user_id, admin['id'], amount_due))
            
            # Update loan status
            cursor.execute("UPDATE loans SET status='repaid' WHERE id=%s", (loan_id,))
            
            db.commit()
            return True, "Loan repaid successfully"
        except Exception as e:
            db.rollback()
            return False, str(e)
            
    @staticmethod
    def get_user_loans(user_id):
        query = "SELECT * FROM loans WHERE user_id=%s ORDER BY timestamp DESC"
        return db.fetchall(query, (user_id,))
