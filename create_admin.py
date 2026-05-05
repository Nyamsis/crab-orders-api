from werkzeug.security import generate_password_hash
from app import db, Admin   # <-- replace 'app' with your actual file name (no .py)

admin = Admin(
    username="admin",
    password=generate_password_hash("1234")
)

db.session.add(admin)
db.session.commit()

print("Admin created successfully!")