import sqlite3

# Static credentials — subjects ab DB se aayenge
users = {
    "incharge": {"password": "admin123", "role": "incharge"},
    "cr":       {"password": "cr123",    "role": "cr"},
    "teacher1": {"password": "teach123", "role": "teacher"},
}

def get_user_subjects(username):
    """DB se is user ke subjects fetch karo."""
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    role = users.get(username, {}).get("role", "")

    if role in ["incharge", "cr"]:
        # incharge/cr ko saare subjects dikhte hain
        cursor.execute("SELECT name FROM subjects ORDER BY name")
    else:
        # teacher ko sirf apne subjects
        cursor.execute(
            "SELECT name FROM subjects WHERE teacher_username = ? ORDER BY name",
            (username,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]