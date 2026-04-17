import sqlite3
from datetime import datetime

conn = sqlite3.connect("attendance.db")
cursor = conn.cursor()

# Pehle ek valid subject_id chahiye
cursor.execute("SELECT id, name, class_id FROM subjects LIMIT 1")
row = cursor.fetchone()

if not row:
    print("❌ Koi subject nahi mila. Pehle subject add karo dashboard se.")
else:
    subject_id, subject_name, class_id = row
    roll = "23BCA001"
    name = "Anshika Bharti"
    session_id = "test123"
    device_id = "DEVICE_TEST"
    ip_address = "127.0.0.1"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor.execute("""
            INSERT INTO attendance 
            (subject_id, subject_name, class_id, session_id, roll, name, device_id, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (subject_id, subject_name, class_id, session_id, roll, name, device_id, ip_address, timestamp))
        conn.commit()
        print(f"✅ Dummy attendance marked for {name} in {subject_name}")
    except sqlite3.IntegrityError:
        print("⚠️ Already exists (duplicate blocked)")

conn.close()