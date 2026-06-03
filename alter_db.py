import sqlite3

def alter_db():
    conn = sqlite3.connect('app.db')
    try:
        conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''")
        print("Added full_name")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
        print("Added email")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
        print("Added phone")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

if __name__ == '__main__':
    alter_db()
    print("Database alteration complete.")
