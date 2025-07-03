import sqlite3

conn = sqlite3.connect("attendance.db")
cursor = conn.cursor()
cursor.execute("SELECT roll, subject, session_id, timestamp FROM attendance")
rows = cursor.fetchall()
conn.close()

if not rows:
    print("⚠️ No attendance records found.")
else:
    print("📋 Attendance Records:")
    for row in rows:
        print(row)
