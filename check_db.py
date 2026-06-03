import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), "app.db")

if not os.path.exists(DB_PATH):
    print(f"❌ Database file not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
try:
    cols = conn.execute("PRAGMA table_info(users)").fetchall()
    print("Columns in 'users' table:")
    found_cols = []
    for col in cols:
        print(f" - {col[1]} ({col[2]})")
        found_cols.append(col[1])
    
    required = ["display_name", "bio", "phone"]
    missing = [c for c in required if c not in found_cols]
    
    if missing:
        print(f"\n❌ MISSING COLUMNS: {missing}")
    else:
        print("\n✅ All profile columns found.")
        
except Exception as e:
    print(f"❌ Error inspecting DB: {e}")
finally:
    conn.close()
