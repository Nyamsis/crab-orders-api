from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# ==============================
# DATABASE CONFIG (MYSQL ONLY)
# ==============================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Please configure your MySQL connection.")

# Fix mysql:// to mysql+pymysql://
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================
# MODEL
# ==============================
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(100), nullable=False)
    crab = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

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
    return [{
        "id": o.id,
        "customer": o.customer,
        "crab": o.crab,
        "quantity": o.quantity,
        "price": o.price,
        "total": o.total,
        "status": o.status,
        "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S") if o.timestamp else None
    } for o in Order.query.all()]

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
def get_history():
    return jsonify({"orders": get_orders_data()})

@app.route('/orders', methods=['GET'])
def get_orders():
    return jsonify({"orders": get_orders_data()})

@app.route('/orders', methods=['POST'])
def add_order():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        quantity = int(data["quantity"])
        crab = data["crab"]
        price = CRAB_PRICES.get(crab, 0)
    except:
        return jsonify({"error": "Invalid data"}), 400

    order = Order(
        customer=data["customer"],
        crab=crab,
        quantity=quantity,
        price=price,
        total=price * quantity,
        status="pending",
        timestamp=datetime.utcnow()
    )

    db.session.add(order)
    db.session.commit()

    return jsonify({"message": "Order added successfully"})

@app.route('/orders/<int:id>', methods=['PUT'])
def update_order(id):
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    order = Order.query.get(id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    if "customer" in data:
        order.customer = data["customer"]

    if "crab" in data:
        order.crab = data["crab"]

    if "quantity" in data:
        order.quantity = int(data["quantity"])

    order.price = CRAB_PRICES.get(order.crab, 0)
    order.total = order.price * order.quantity
    order.timestamp = datetime.utcnow()

    db.session.commit()

    return jsonify({"message": "Order updated successfully"})

@app.route('/orders/<int:id>', methods=['DELETE'])
def delete_order(id):
    order = Order.query.get(id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    db.session.delete(order)
    db.session.commit()

    return jsonify({"message": "Order deleted successfully"})

@app.route('/orders/<int:id>/finish', methods=['PUT'])
def finish_order(id):
    order = Order.query.get(id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    order.status = "finished"
    order.timestamp = datetime.utcnow()

    db.session.commit()

    return jsonify({"message": "Order marked as finished"})

# ==============================
# MAIN
# ==============================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
