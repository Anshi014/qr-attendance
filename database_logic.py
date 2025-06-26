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

def has_already_submitted(subject, device_id=None, ip_address=None):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    if device_id:
        cursor.execute("SELECT 1 FROM attendance WHERE subject=? AND device_id=?", (subject, device_id))
    elif ip_address:
        cursor.execute("SELECT 1 FROM attendance WHERE subject=? AND ip_address=?", (subject, ip_address))
    else:
        conn.close()
        return False

    result = cursor.fetchone()
    conn.close()
    return result is not None

def roll_exists(roll):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM students WHERE roll = ?", (roll.strip().upper(),))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_attendance(subject, session_id, roll, name, device_id, ip_address):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO attendance (subject, session_id, roll, name, device_id, ip_address, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (subject, session_id, roll, name, device_id, ip_address, timestamp))

    #Add this debug print here
    print("Attendance save for:",roll, name)
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
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute(
            "INSERT OR IGNORE INTO students (roll, name) VALUES (?, ?)",
            (row["roll"].strip().upper(), row["name"])
        )
    conn.commit()
    conn.close()

# Success message
print("Students seeded successfully!")
