import sqlite3
from datetime import datetime
import pandas as pd

def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            session_id TEXT,
            roll TEXT,
            name TEXT,
            device_id TEXT,
            ip_address TEXT,
            timestamp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            roll TEXT PRIMARY KEY,
            name TEXT
        )
    """)
    conn.commit()
    conn.close()

def has_already_submitted(subject, session_id, device_id=None, ip_address=None):
    import sqlite3
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    if device_id:
        cursor.execute("""
            SELECT roll FROM attendance
            WHERE subject = ? AND session_id = ? AND device_id = ?
        """, (subject, session_id, device_id))
        result = cursor.fetchone()
        if result:
            existing_roll = result[0].strip().upper()
            if roll and existing_roll != roll.strip().upper():
                conn.close()
                return True

    if ip_address:
        cursor.execute("""
            SELECT roll FROM attendance
            WHERE subject = ? AND session_id = ? AND ip_address = ?
        """, (subject, session_id, ip_address))
        result = cursor.fetchone()
        if result:
            existing_roll = result[0].strip().upper()
            if roll and existing_roll != roll.strip().upper():
                conn.close()
                return True

    conn.close()
    return False

def roll_exists(roll):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM students WHERE roll = ?", (roll.strip().upper(),))
    result = cursor.fetchone()
    conn.close()
    return result is not None

from datetime import datetime  # ✅ Make sure this is at top of file

def mark_attendance(subject, session_id, roll, name, device_id, ip_address):
    import sqlite3
    from datetime import datetime  # optional if already imported above

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO attendance (subject, session_id, roll, name, device_id, ip_address, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (subject, session_id, roll, name, device_id, ip_address, timestamp))

    print("✅ Attendance saved for:", roll, name)
    conn.commit()
    conn.close()

def load_student_list():
    try:
        df = pd.read_excel("student_list.xlsx")
        return df
    except Exception as e:
        print("❌ Error loading student list:", e)
        return None

def seed_students_from_excel():
    df = pd.read_excel("student_list.xlsx")
    df.rename(columns=lambda x: x.strip().lower(), inplace=True)  # ✅ Normalize column names
    
    df["roll"] = df["roll"].str.strip().str.upper()
    df["name"] = df["name"].str.strip()

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    
    #create table if not exists
    cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                roll TEXT PRIMARY KEY,
                name TEXT
                )
    """)

    #Insert or update students
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO students (roll, name) 
            VALUES (?, ?)
            ON CONFLICT(roll) DO UPDATE SET name = excluded.name
        """, (row["roll"], row["name"]))
    conn.commit()
    conn.close()

# Success message
print("Students seeded successfully!")
