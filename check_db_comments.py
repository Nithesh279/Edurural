
import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), "app.db")

def check_comments():
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"--- Checking DB: {DB_PATH} ---")
        
        # Check comments table
        try:
            comments = conn.execute("SELECT * FROM comments").fetchall()
            print(f"Total Comments: {len(comments)}")
            for c in comments:
                print(c)
        except Exception as e:
            print(f"Error reading comments table: {e}")
            
        # Check Contents table (to ensure join works)
        try:
            contents = conn.execute("SELECT id, title FROM contents").fetchall()
            print(f"\nTotal Contents: {len(contents)}")
            for c in contents:
                print(c)
        except Exception as e:
            print(f"Error reading contents table: {e}")

        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    check_comments()
