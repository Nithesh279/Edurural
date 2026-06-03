import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # Check for videos with NULL or empty transcripts
        rows = conn.execute("SELECT id, title, original_filename FROM contents WHERE transcript IS NULL OR transcript = ''").fetchall()
        print(f"Found {len(rows)} videos with MISSING transcripts:")
        for r in rows:
            print(f"ID: {r[0]}, Title: {r[1]}, Filename: {r[2]}")
            
        # Check for videos WITH transcripts
        rows_ok = conn.execute("SELECT id, title, length(transcript) FROM contents WHERE transcript IS NOT NULL AND transcript != '' LIMIT 5").fetchall()
        print(f"\nFound videos WITH transcripts (first 5):")
        for r in rows_ok:
            print(f"ID: {r[0]}, Title: {r[1]}, Length: {r[2]}")
            
    except Exception as e:
        print(f"Error reading DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
