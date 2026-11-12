from backend.database import SessionLocal
from backend.models import User

db = SessionLocal()

try:
    users = db.query(User).all()

    for user in users:
        print("ID:", user.id)
        print("Email:", repr(user.email))
        print("LeetCode:", user.leetcode_username)
        print("Password hash exists:", bool(user.password_hash))
        print("------------------------")

finally:
    db.close()