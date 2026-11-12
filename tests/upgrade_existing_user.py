from getpass import getpass

from backend.database import SessionLocal
from backend.models import User
from backend.core.security import hash_password


EMAIL = "hivansh1306@gmail.com"
LEETCODE_USERNAME = "Vansh1306"


def upgrade_user():

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.leetcode_username == LEETCODE_USERNAME
        ).first()

        if not user:
            print("Existing LeetCode user not found!")
            return

        # Check whether email is already registered
        existing_email = db.query(User).filter(
            User.email == EMAIL,
            User.id != user.id
        ).first()

        if existing_email:
            print("Email already belongs to another account!")
            return

        print("Existing account found!")
        print("User ID:", user.id)
        print("LeetCode:", user.leetcode_username)

        password = getpass("Enter your new password: ")
        confirm_password = getpass("Confirm password: ")

        if password != confirm_password:
            print("Passwords do not match!")
            return

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            return

        if len(password.encode("utf-8")) > 72:
            print("Password exceeds bcrypt's 72-byte limit.")
            return

        user.email = EMAIL
        user.password_hash = hash_password(password)

        db.commit()

        print("\nAccount upgraded successfully!")
        print("Email:", user.email)
        print("LeetCode:", user.leetcode_username)
        print("User ID:", user.id)

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()


if __name__ == "__main__":
    upgrade_user()