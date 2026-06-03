
import sqlite3
import os
import json

DB_PATH = os.path.join(os.getcwd(), "app.db")

def check_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        print("--- COMMENTS ---")
        rows = conn.execute("SELECT id, video_id, user_id, text, parent_id FROM comments").fetchall()
        print(json.dumps(rows, indent=2))
        
        print("\n--- CONTENTS (IDs only) ---")
        rows = conn.execute("SELECT id, title FROM contents").fetchall()
        print(json.dumps(rows, indent=2))
        
        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_db()
