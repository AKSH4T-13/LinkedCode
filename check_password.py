from backend.database import SessionLocal
from backend.models import User
from backend.core.security import verify_password

db = SessionLocal()

try:
    user = db.query(User).filter(
        User.email == "user@example.com"
    ).first()

    if not user:
        print("User not found!")

    elif not user.password_hash:
        print("Password hash missing!")

    else:
        result = verify_password(
            "string",
            user.password_hash
        )

        print("Password verification:", result)

finally:
    db.close()