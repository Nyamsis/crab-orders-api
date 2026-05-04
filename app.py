import os
import pymysql
from datetime import datetime, timezone
from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy

# This is required for many cloud environments to recognize the MySQL driver
pymysql.install_as_MySQLdb()

app = Flask(__name__)

# ==============================
# DATABASE CONFIG
# ==============================
# Railway usually provides DATABASE_URL or MYSQL_URL
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Check your Railway environment variables.")

# Standardize the driver prefix
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================
# MODEL (Mapped to 'Crab' Table)
# ==============================
class Order(db.Model):
    __tablename__ = '`order`' # This matches your manual table name exactly
    
    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(100), nullable=False)
    crab = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="pending")
    # Updated to modern UTC handling
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
# HELPERS
# ==============================
def get_orders_data():
    # Using modern session.query
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
# ROUTES
# ==============================
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/history-page')
def history_page():
    return render_template("history.html")

@app.route('/history', methods=['GET'])
@app.route('/orders', methods=['GET'])
def get_orders():
    return jsonify({"orders": get_orders_data()})

@app.route('/orders', methods=['POST'])
def add_order():
    data = request.get_json()
    if not data or "customer" not in data or "crab" not in data:
        return jsonify({"error": "Missing required data"}), 400

    try:
        quantity = int(data.get("quantity", 1))
        crab_type = data["crab"]
        price = CRAB_PRICES.get(crab_type, 0)
        
        new_order = Order(
            customer=data["customer"],
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
        db.session.rollback() # Important: undo changes if DB error occurs
        return jsonify({"error": str(e)}), 500

@app.route('/orders/<int:id>', methods=['PUT'])
def update_order(id):
    data = request.get_json()
    # session.get is the modern way to find by ID
    order = db.session.get(Order, id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    if "customer" in data: order.customer = data["customer"]
    if "crab" in data: order.crab = data["crab"]
    if "quantity" in data: order.quantity = int(data["quantity"])
    if "status" in data: order.status = data["status"]

    # Recalculate based on updated info
    order.price = CRAB_PRICES.get(order.crab, 0)
    order.total = order.price * order.quantity

    try:
        db.session.commit()
        return jsonify({"message": "Order updated successfully"})
    except:
        db.session.rollback()
        return jsonify({"error": "Update failed"}), 500

@app.route('/orders/<int:id>', methods=['DELETE'])
def delete_order(id):
    order = db.session.get(Order, id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({"message": "Order deleted successfully"})
    except:
        db.session.rollback()
        return jsonify({"error": "Delete failed"}), 500

@app.route('/orders/<int:id>/finish', methods=['PUT'])
def finish_order(id):
    order = db.session.get(Order, id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    order.status = "finished"
    db.session.commit()
    return jsonify({"message": "Order marked as finished"})

# ==============================
# MAIN
# ==============================
if __name__ == '__main__':
    # We do NOT use db.create_all() here because you are doing it manually
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)