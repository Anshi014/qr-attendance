import sqlite3
from datetime import datetime

conn = sqlite3.connect("attendance.db")
cursor = conn.cursor()

# Sample attendance entry
roll = "23BCA001"
name = "Anshika Bharti"
subject = "AI"
session_id = "test123"
device_id = "DEVICE_TEST"
ip_address = "127.0.0.1"
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

cursor.execute("""
    INSERT INTO attendance (roll, name, subject, session_id, device_id, ip_address, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (roll, name, subject, session_id, device_id, ip_address, timestamp))

conn.commit()
conn.close()

print("✅ Dummy attendance marked.")
