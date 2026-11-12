import sqlite3

from backend.database import DATABASE_URL


def migrate_database():

    db_path = DATABASE_URL.replace("sqlite:///", "")

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [
            column[1]
            for column in cursor.fetchall()
        ]

        # Add email column if missing
        if "email" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN email VARCHAR"
            )
            print("[MIGRATION] Email column added.")

        else:
            print("[MIGRATION] Email column already exists.")

        # Add password_hash column if missing
        if "password_hash" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN password_hash VARCHAR"
            )
            print("[MIGRATION] Password hash column added.")

        else:
            print("[MIGRATION] Password hash column already exists.")

        # Create unique email index.
        # SQLite permits multiple NULL values in a unique index.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            ix_users_email_unique
            ON users(email)
        """)

        connection.commit()

        print("\n[MIGRATION] Database migration successful!")

        # Verify existing data.
        cursor.execute("SELECT COUNT(*) FROM users")
        print("Existing users:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM solved_questions")
        print("Solved questions:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM recommendation_history")
        print("Recommendations:", cursor.fetchone()[0])

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate_database()