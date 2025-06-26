import sqlite3

def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        session_id TEXT NOT NULL,
        roll TEXT NOT NULL,
        name TEXT NOT NULL,
        device_id TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()