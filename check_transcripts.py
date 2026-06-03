import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT id, title, length(transcript) FROM contents").fetchall()
        print(f"Found {len(rows)} videos in database:")
        for r in rows:
            print(f"ID: {r[0]}, Title: {r[1]}, Transcript Length: {r[2] if r[2] else 'None'}")
    except Exception as e:
        print(f"Error reading DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
