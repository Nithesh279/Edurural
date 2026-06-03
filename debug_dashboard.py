
import sqlite3
import os
import json

DB_PATH = os.path.join(os.getcwd(), "app.db")

def check_dashboard_data():
    conn = sqlite3.connect(DB_PATH)
    print("--- USERS ---")
    users = conn.execute("SELECT id, email, role FROM users").fetchall()
    print(json.dumps(users, indent=2))
    
    print("\n--- DASHBOARD QUERY TEST ---")
    query = """
        SELECT c.id, c.text, c.created_at, u.display_name, u.email, cnt.title, cnt.id,
               (SELECT COUNT(*) FROM comments r WHERE r.parent_id = c.id) as reply_count,
               (SELECT COUNT(*) FROM comments r WHERE r.parent_id = c.id AND r.is_teacher_reply = 1) as teacher_replied
        FROM comments c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN contents cnt ON c.video_id = cnt.id
        WHERE c.parent_id IS NULL
        ORDER BY c.created_at DESC
    """
    rows = conn.execute(query).fetchall()
    print(f"Rows returned: {len(rows)}")
    for r in rows:
        print(r)

    conn.close()

if __name__ == "__main__":
    check_dashboard_data()
