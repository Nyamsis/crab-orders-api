import os
from dotenv import load_dotenv
load_dotenv()
import pymysql
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request, render_template, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

pymysql.install_as_MySQLdb()

app = Flask(__name__)

# ==============================
# SECURITY
# ==============================
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")

# ==============================
# DATABASE CONFIG
# ==============================
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set.")

if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================
# MODELS
# ==============================
class Admin(db.Model):
    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Order(db.Model):
    __tablename__ = "orders"  # ⚠️ FIXED (avoid reserved keyword issues)

    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(100), nullable=False)
    crab = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="pending")
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# ==============================
# CRAB PRICES
# ==============================
CRAB_PRICES = {
    "King Crab": 10,
    "Snow Crab": 9,
    "Dungeness Crab": 8,
    "Blue Crab": 7,
    "Mud Crab": 6,
    "Kasag": 5
}

# ==============================
# AUTH DECORATOR
# ==============================
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return wrapper

# ==============================
# HELPERS
# ==============================
def get_orders_data():
    orders = db.session.query(Order).all()
    return [{
        "id": o.id,
        "customer": o.customer,
        "crab": o.crab,
        "quantity": o.quantity,
        "price": o.price,
        "total": o.total,
        "status": o.status,
        "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S") if o.timestamp else None
    } for o in orders]

# ==============================
# AUTH ROUTES
# ==============================
@app.route('/login', methods=['GET', 'POST'])
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Missing username or password"}), 400

        admin = db.session.query(Admin).filter_by(username=username).first()

        if admin and check_password_hash(admin.password, password):
            session["admin_logged_in"] = True
            return jsonify({"message": "Login successful"})
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    return render_template("admin_login.html")


@app.route('/admin-logout')
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

# ==============================
# PUBLIC ROUTES
# ==============================
@app.route('/')
def home():
    return render_template("index.html")


@app.route('/order')
def order_page():
    return render_template("order_page.html")


@app.route('/customer-orders')
@admin_required
def customer_order():
    return render_template("customer_order.html")


@app.route('/history', methods=['GET'])
@admin_required
def history():
    if request.accept_mimetypes['application/json'] >= request.accept_mimetypes['text/html']:
        return jsonify({"orders": get_orders_data()})
    return render_template("history.html")

# ==============================
# ORDER ROUTES
# ==============================

# 🔒 ADMIN ONLY: VIEW
@app.route('/orders', methods=['GET'])
@admin_required
def get_orders():
    return jsonify({"orders": get_orders_data()})


# ✅ PUBLIC: CREATE ORDER
@app.route('/orders', methods=['POST'])
def add_order():
    data = request.get_json(silent=True) or {}

    customer = data.get("customer")
    crab_type = data.get("crab")

    if not customer or not crab_type:
        return jsonify({"error": "Missing required data"}), 400

    try:
        quantity = max(1, int(data.get("quantity", 1)))
        price = CRAB_PRICES.get(crab_type)

        if price is None:
            return jsonify({"error": "Invalid crab type"}), 400

        new_order = Order(
            customer=customer,
            crab=crab_type,
            quantity=quantity,
            price=price,
            total=price * quantity,
            status="pending"
        )

        db.session.add(new_order)
        db.session.commit()

        return jsonify({"message": "Order added successfully"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# 🔒 ADMIN ONLY: UPDATE
@app.route('/orders/<int:id>', methods=['PUT'])
@admin_required
def update_order(id):
    data = request.get_json(silent=True) or {}
    order = db.session.get(Order, id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    try:
        if "customer" in data:
            order.customer = data["customer"]

        if "crab" in data:
            if data["crab"] not in CRAB_PRICES:
                return jsonify({"error": "Invalid crab type"}), 400
            order.crab = data["crab"]

        if "quantity" in data:
            order.quantity = max(1, int(data["quantity"]))

        if "status" in data:
            order.status = data["status"]

        order.price = CRAB_PRICES.get(order.crab, 0)
        order.total = order.price * order.quantity

        db.session.commit()
        return jsonify({"message": "Order updated successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# 🔒 ADMIN ONLY: DELETE
@app.route('/orders/<int:id>', methods=['DELETE'])
@admin_required
def delete_order(id):
    order = db.session.get(Order, id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({"message": "Order deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# 🔒 ADMIN ONLY: FINISH
@app.route('/orders/<int:id>/finish', methods=['PUT'])
@admin_required
def finish_order(id):
    order = db.session.get(Order, id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    try:
        order.status = "finished"
        db.session.commit()
        return jsonify({"message": "Order marked as finished"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)