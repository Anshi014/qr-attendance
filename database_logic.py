import sqlite3
from datetime import datetime
import pandas as pd
import os

DB = os.environ.get("DB_PATH", "attendance.db")


def get_db():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ══════════════════════════════════════════
# INIT — create all tables + indexes
# ══════════════════════════════════════════

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('coordinator','incharge','teacher')),
            full_name TEXT,
            class_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            department TEXT,
            incharge_id INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            teacher_id INTEGER,
            UNIQUE(name, class_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            roll TEXT PRIMARY KEY,
            name TEXT,
            class_id INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            subject_name TEXT,
            class_id INTEGER,
            session_id TEXT,
            roll TEXT,
            name TEXT,
            device_id TEXT,
            ip_address TEXT,
            timestamp TEXT,
            UNIQUE(session_id, roll)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS session_ip_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            ip_address TEXT,
            UNIQUE(session_id, ip_address)
        )
    """)

    # ── Persistent device-token store ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS session_tokens (
            session_id   TEXT NOT NULL,
            device_token TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'issued'
                         CHECK(status IN ('issued','used')),
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at   TEXT NOT NULL
                         DEFAULT (datetime('now', '+24 hours')),
            PRIMARY KEY (session_id, device_token)
        )
    """)

    # ── NEW: one-device-per-subject enforcement ───────────────────────────────
    # Stores a fingerprint (device_id) per subject so the same device cannot
    # mark attendance more than once for the same subject across ALL sessions.
    c.execute("""
        CREATE TABLE IF NOT EXISTS subject_device_log (
            subject_id INTEGER NOT NULL,
            device_id  TEXT NOT NULL,
            timestamp  TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (subject_id, device_id)
        )
    """)

    # ── Performance indexes ───────────────────────────────────────────────────
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_subject   ON attendance(subject_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_sess_roll ON attendance(session_id, roll)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_sess_dev  ON attendance(session_id, device_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_roll      ON attendance(roll)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_students_cls  ON students(class_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tok_sess      ON session_tokens(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tok_expires   ON session_tokens(expires_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_subdev        ON subject_device_log(subject_id, device_id)")

    conn.commit()

    # Default coordinator account (created only on first run)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO users (username, password, role, full_name)
            VALUES ('coordinator', 'coord123', 'coordinator', 'Coordinator')
        """)
        conn.commit()
        print("Default coordinator created — username: coordinator  password: coord123")

    conn.close()


# ══════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════

def get_user_by_username(username):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, username, password, role, full_name, class_id FROM users WHERE username = ?",
        (username,)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "password": row[2],
                "role": row[3], "full_name": row[4], "class_id": row[5]}
    return None


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if user and user["password"] == password:
        return user
    return None


def add_user(username, password, role, full_name="", class_id=None):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password, role, full_name, class_id)
            VALUES (?, ?, ?, ?, ?)
        """, (username, password, role, full_name, class_id))
        conn.commit()
        return True, "User added!"
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def delete_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.role, u.full_name, cl.name
        FROM users u
        LEFT JOIN classes cl ON u.class_id = cl.id
        ORDER BY u.role, u.username
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_teachers():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, full_name FROM users WHERE role = 'teacher' ORDER BY full_name")
    rows = c.fetchall()
    conn.close()
    return rows


def get_incharges():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, full_name FROM users WHERE role = 'incharge' ORDER BY full_name")
    rows = c.fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════
# CLASS MANAGEMENT
# ══════════════════════════════════════════

def add_class(name, department=""):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO classes (name, department) VALUES (?, ?)", (name.strip(), department))
        conn.commit()
        return True, "Class added!"
    except sqlite3.IntegrityError:
        return False, "Class already exists."
    finally:
        conn.close()


def delete_class(class_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()


def get_all_classes():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT cl.id, cl.name, cl.department, u.full_name
        FROM classes cl
        LEFT JOIN users u ON cl.incharge_id = u.id
        ORDER BY cl.name
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def assign_incharge_to_class(class_id, incharge_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE classes SET incharge_id = ? WHERE id = ?", (incharge_id, class_id))
    c.execute("UPDATE users SET class_id = ? WHERE id = ?", (class_id, incharge_id))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════
# SUBJECT MANAGEMENT
# ══════════════════════════════════════════

def add_subject(name, class_id, teacher_id=None):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO subjects (name, class_id, teacher_id) VALUES (?, ?, ?)",
                  (name.strip(), class_id, teacher_id))
        conn.commit()
        return True, "Subject added!"
    except sqlite3.IntegrityError:
        return False, "Subject already exists for this class."
    finally:
        conn.close()


def delete_subject(subject_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()


def assign_teacher_to_subject(subject_id, teacher_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE subjects SET teacher_id = ? WHERE id = ?", (teacher_id, subject_id))
    conn.commit()
    conn.close()


def get_subjects_for_user(user):
    conn = get_db()
    c = conn.cursor()
    if user["role"] == "coordinator":
        c.execute("""
            SELECT s.id, s.name, cl.name, u.full_name
            FROM subjects s
            JOIN classes cl ON s.class_id = cl.id
            LEFT JOIN users u ON s.teacher_id = u.id
            ORDER BY cl.name, s.name
        """)
    elif user["role"] == "incharge":
        c.execute("""
            SELECT s.id, s.name, cl.name, u.full_name
            FROM subjects s
            JOIN classes cl ON s.class_id = cl.id
            LEFT JOIN users u ON s.teacher_id = u.id
            WHERE s.class_id = ?
            ORDER BY s.name
        """, (user["class_id"],))
    else:  # teacher
        c.execute("""
            SELECT s.id, s.name, cl.name, u.full_name
            FROM subjects s
            JOIN classes cl ON s.class_id = cl.id
            LEFT JOIN users u ON s.teacher_id = u.id
            WHERE s.teacher_id = ?
            ORDER BY s.name
        """, (user["id"],))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "class_name": r[2], "teacher_name": r[3]} for r in rows]


def get_subject_by_id(subject_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, s.class_id, cl.name
        FROM subjects s JOIN classes cl ON s.class_id = cl.id
        WHERE s.id = ?
    """, (subject_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "class_id": row[2], "class_name": row[3]}
    return None


def get_all_subjects():
    """Return all subjects with class and teacher info — used by coordinator."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, cl.name AS class_name, u.full_name AS teacher_name,
               s.class_id, s.teacher_id
        FROM subjects s
        JOIN classes cl ON s.class_id = cl.id
        LEFT JOIN users u ON s.teacher_id = u.id
        ORDER BY cl.name, s.name
    """)
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "class_name": r[2],
             "teacher_name": r[3], "class_id": r[4], "teacher_id": r[5]}
            for r in rows]


# ══════════════════════════════════════════
# STUDENT MANAGEMENT
# ══════════════════════════════════════════

def get_students_by_class(class_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT roll, name, class_id FROM students WHERE class_id = ? ORDER BY roll",
              (class_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_students():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.roll, s.name, s.class_id, cl.name
        FROM students s
        LEFT JOIN classes cl ON s.class_id = cl.id
        ORDER BY cl.name, s.roll
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def add_student(roll, name, class_id):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO students (roll, name, class_id) VALUES (?, ?, ?)
            ON CONFLICT(roll) DO UPDATE SET name=excluded.name, class_id=excluded.class_id
        """, (roll.strip().upper(), name.strip(), class_id))
        conn.commit()
        return True, "Student added!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_student(roll):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE roll = ?", (roll.upper(),))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ══════════════════════════════════════════
# SESSION TOKEN MANAGEMENT  (DB-persisted)
# ══════════════════════════════════════════

def db_issue_token(session_id, device_token):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO session_tokens (session_id, device_token, status)
            VALUES (?, ?, 'issued')
            ON CONFLICT(session_id, device_token) DO NOTHING
        """, (session_id, device_token))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def db_consume_token(session_id, device_token):
    """
    Atomically check that the token is 'issued' then flip it to 'used'.
    Returns (True, None) on success.
    Returns (False, reason) on failure.
    """
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT status FROM session_tokens WHERE session_id=? AND device_token=?",
            (session_id, device_token)
        )
        row = c.fetchone()

        if row is None:
            c.execute("SELECT 1 FROM session_tokens WHERE session_id=?", (session_id,))
            if c.fetchone() is None:
                return False, "invalid_session"
            return False, "unrecognized_token"

        if row[0] == "used":
            return False, "already_used"

        c.execute(
            "UPDATE session_tokens SET status='used' WHERE session_id=? AND device_token=?",
            (session_id, device_token)
        )
        conn.commit()
        return True, None
    finally:
        conn.close()


def cleanup_expired_tokens():
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM session_tokens WHERE expires_at < datetime('now')")
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted


# ══════════════════════════════════════════
# ONE DEVICE PER SUBJECT  (new feature)
# ══════════════════════════════════════════

def is_device_blocked_for_subject(subject_id, device_id):
    """
    Returns True if this device has already marked attendance for this
    subject in ANY previous session.  Blocks repeat scanning across sessions.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM subject_device_log WHERE subject_id=? AND device_id=?",
        (subject_id, device_id)
    )
    found = c.fetchone() is not None
    conn.close()
    return found


def register_device_for_subject(subject_id, device_id):
    """
    Record that this device has marked attendance for this subject.
    Called after successful mark_attendance().
    """
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO subject_device_log (subject_id, device_id) VALUES (?, ?)",
            (subject_id, device_id)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════

def has_already_submitted(session_id, device_id=None, roll=None, ip_address=None):
    conn = get_db()
    c = conn.cursor()
    if roll:
        c.execute("SELECT 1 FROM attendance WHERE session_id = ? AND roll = ?",
                  (session_id, roll.upper()))
        if c.fetchone():
            conn.close()
            return True, "roll"
    if device_id:
        c.execute("SELECT 1 FROM attendance WHERE session_id = ? AND device_id = ?",
                  (session_id, device_id))
        if c.fetchone():
            conn.close()
            return True, "device"
    if ip_address:
        c.execute("SELECT 1 FROM session_ip_log WHERE session_id = ? AND ip_address = ?",
                  (session_id, ip_address))
        if c.fetchone():
            conn.close()
            return True, "ip"
    conn.close()
    return False, None


def roll_exists(roll, class_id=None):
    conn = get_db()
    c = conn.cursor()
    if class_id:
        c.execute("SELECT 1 FROM students WHERE roll = ? AND class_id = ?",
                  (roll.upper(), class_id))
    else:
        c.execute("SELECT 1 FROM students WHERE roll = ?", (roll.upper(),))
    result = c.fetchone()
    conn.close()
    return result is not None


def mark_attendance(subject_id, subject_name, class_id, session_id,
                    roll, name, device_id, ip_address):
    conn = get_db()
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        c.execute("""
            INSERT INTO attendance
            (subject_id, subject_name, class_id, session_id, roll, name,
             device_id, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (subject_id, subject_name, class_id, session_id,
              roll.upper(), name, device_id, ip_address, timestamp))
        c.execute(
            "INSERT OR IGNORE INTO session_ip_log (session_id, ip_address) VALUES (?, ?)",
            (session_id, ip_address)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_student_name(roll):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM students WHERE roll = ?", (roll.upper(),))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_attendance_records(subject_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT a.roll,
               COALESCE(s.name, a.name, a.roll) AS student_name,
               a.session_id,
               a.timestamp,
               a.ip_address
        FROM attendance a
        LEFT JOIN students s ON a.roll = s.roll
        WHERE a.subject_id = ?
        ORDER BY a.timestamp DESC
    """, (subject_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════
# ATTENDANCE VIEW — per-student summary
# ══════════════════════════════════════════

def get_attendance_summary(subject_id, class_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT roll, name FROM students WHERE class_id=? ORDER BY roll", (class_id,))
    students = c.fetchall()

    c.execute("""
        SELECT roll, DATE(timestamp) AS date
        FROM attendance
        WHERE subject_id=?
        ORDER BY date, roll
    """, (subject_id,))
    records = c.fetchall()
    conn.close()

    if not students:
        return [], []

    all_dates = sorted({r[1] for r in records})
    total_classes = len(all_dates)

    present_map = {}
    for roll, date in records:
        present_map.setdefault(roll, set()).add(date)

    summary = []
    for roll, name in students:
        dates_present = present_map.get(roll, set())
        classes_present = len(dates_present)
        pct = round(classes_present / total_classes * 100, 1) if total_classes else 0.0
        date_status = {d: ("P" if d in dates_present else "A") for d in all_dates}
        summary.append({
            "roll": roll,
            "name": name,
            "classes_present": classes_present,
            "total_classes": total_classes,
            "pct": pct,
            "dates": date_status,
        })

    return summary, all_dates


# ══════════════════════════════════════════
# STUDENTS — Excel seed
# ══════════════════════════════════════════

def seed_students_from_excel(class_id=None):
    """
    Seed students from student_list.xlsx.
    Required columns: roll, name, class_id
    Column names are stripped + lowercased automatically.
    """
    xlsx_path = "student_list.xlsx"
    if not os.path.exists(xlsx_path):
        print("student_list.xlsx not found — skipping seed.")
        return

    try:
        df = pd.read_excel(xlsx_path)
        # Strip whitespace from column names (fixes 'roll ' bug found in your file)
        df.rename(columns=lambda x: x.strip().lower(), inplace=True)
        df["roll"] = df["roll"].astype(str).str.strip().str.upper()
        df["name"] = df["name"].astype(str).str.strip()

        has_class_col = "class_id" in df.columns

        conn = get_db()
        c = conn.cursor()
        count = skipped = 0

        for _, row in df.iterrows():
            if has_class_col and pd.notna(row.get("class_id")):
                eff_class_id = int(row["class_id"])
            elif class_id is not None:
                eff_class_id = class_id
            else:
                skipped += 1
                continue

            c.execute("""
                INSERT INTO students (roll, name, class_id) VALUES (?, ?, ?)
                ON CONFLICT(roll) DO UPDATE
                SET name=excluded.name, class_id=excluded.class_id
            """, (row["roll"], row["name"], eff_class_id))
            count += 1

        conn.commit()
        conn.close()
        msg = f"Seeded {count} students."
        if skipped:
            msg += f" Skipped {skipped} rows with no class_id."
        print(msg)
    except Exception as e:
        print(f"Error seeding students: {e}")


def load_student_list():
    try:
        return pd.read_excel("student_list.xlsx")
    except Exception as e:
        print(f"Could not load student_list.xlsx: {e}")
        return None


# ══════════════════════════════════════════
# REPORT — date-wise + percentage (Excel download)
# ══════════════════════════════════════════

def generate_report_for_subject(subject_id, class_id):
    """
    Build a DataFrame with one row per student showing:
      Roll | Name | <date1> | <date2> | ... | Total Classes | Classes Present | Attendance %

    P = present on that date, A = absent.
    """
    conn = get_db()
    c = conn.cursor()

    # All students in this class
    c.execute("SELECT roll, name FROM students WHERE class_id = ? ORDER BY roll", (class_id,))
    students = c.fetchall()

    # All attendance records for this subject
    # Use session_id to count UNIQUE class sessions (one session = one class held)
    c.execute("""
        SELECT roll, DATE(timestamp) AS date, session_id
        FROM attendance
        WHERE subject_id = ?
        ORDER BY date, roll
    """, (subject_id,))
    records = c.fetchall()
    conn.close()

    student_df = pd.DataFrame(students, columns=["Roll", "Name"])
    if student_df.empty:
        return student_df, []

    if not records:
        student_df["Total Classes"] = 0
        student_df["Classes Present"] = 0
        student_df["Attendance %"] = 0.0
        return student_df, []

    att_df = pd.DataFrame(records, columns=["Roll", "Date", "Session"])
    # One record per student per date (in case of duplicates)
    att_df = att_df.drop_duplicates(subset=["Roll", "Date"])
    att_df["Status"] = "P"

    # Pivot: rows=Roll, columns=Date, values=P
    pivot = att_df.pivot_table(
        index="Roll", columns="Date",
        values="Status", aggfunc="first"
    )
    pivot.reset_index(inplace=True)

    # Merge all students (left join so absent students appear with A)
    final_df = pd.merge(student_df, pivot, on="Roll", how="left")
    date_cols = [col for col in final_df.columns if col not in ["Roll", "Name"]]

    # Fill NaN with "A" for students who didn't attend
    for col in date_cols:
        final_df[col] = final_df[col].fillna("A")

    total_classes = len(date_cols)
    final_df["Total Classes"] = total_classes
    final_df["Classes Present"] = final_df[date_cols].apply(
        lambda row: sum(str(x) == "P" for x in row), axis=1
    )
    final_df["Attendance %"] = (
        (final_df["Classes Present"] / total_classes * 100).round(2)
        if total_classes > 0 else 0.0
    )

    return final_df, date_cols