import pg8000.native
import sqlite3
from datetime import datetime
import pandas as pd
import os
import re

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    ""  # Use SQLite locally by default
)

# ── Database type detection ──────────────────────────────────────────────
USE_SQLITE = not DATABASE_URL or os.environ.get("USE_SQLITE", "").lower() in ("1", "true", "yes")
SQLITE_DB = os.environ.get("SQLITE_DB_PATH", "attendance.db")

if USE_SQLITE:
    print("[INFO] Using SQLite for database (local development mode)", flush=True)
else:
    print("[INFO] Using PostgreSQL for database (production mode)", flush=True)

def _parse_url(url):
    """Parse postgresql://user:pass@host:port/dbname"""
    url = url.replace("%40", "@")
    pattern = r"postgresql://([^:]+):(.+)@([^:]+):(\d+)/(.+)"
    m = re.match(pattern, url)
    if not m:
        raise ValueError(f"Cannot parse DATABASE_URL: {url}")
    return {
        "user":     m.group(1),
        "password": m.group(2),
        "host":     m.group(3),
        "port":     int(m.group(4)),
        "database": m.group(5),
    }

class SQLiteConnection:
    """Wrapper to make SQLite behave like pg8000 connection"""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
    def run(self, query, **kwargs):
        """Execute query and return results like pg8000"""
        # Convert PostgreSQL :param syntax to SQLite ?
        sql = query
        params = []
        
        # Find all :param placeholders in order
        import re
        placeholders = re.findall(r':(\w+)', sql)
        
        # Build params list in order of appearance
        for placeholder in placeholders:
            if placeholder in kwargs:
                params.append(kwargs[placeholder])
            else:
                params.append(None)
        
        # Replace :param with ?
        sql = re.sub(r':\w+', '?', sql)
        
        c = self.conn.cursor()
        if params:
            c.execute(sql, params)
        else:
            c.execute(sql)
        self.conn.commit()
        
        # Return results as list of tuples (like pg8000)
        results = c.fetchall()
        return [tuple(row) for row in results]
    
    def close(self):
        self.conn.close()

def get_db():
    """Get database connection (SQLite or PostgreSQL)"""
    if USE_SQLITE:
        return SQLiteConnection(SQLITE_DB)
    else:
        p = _parse_url(DATABASE_URL)
        conn = pg8000.native.Connection(
            user=p["user"],
            password=p["password"],
            host=p["host"],
            port=p["port"],
            database=p["database"],
            ssl_context=True,
        )
        return conn


# ══════════════════════════════════════════
# INIT — create all tables + indexes
# ══════════════════════════════════════════
def init_db():
    conn = get_db()
    
    if USE_SQLITE:
        # SQLite schema
        conn.run("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT,
                class_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                department TEXT,
                incharge_id INTEGER
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                teacher_id INTEGER,
                UNIQUE(name, class_id)
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS students (
                roll TEXT PRIMARY KEY,
                name TEXT,
                class_id INTEGER
            )
        """)
        conn.run("""
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
        conn.run("""
            CREATE TABLE IF NOT EXISTS session_ip_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ip_address TEXT,
                UNIQUE(session_id, ip_address)
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS session_tokens (
                session_id TEXT NOT NULL,
                device_token TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'issued',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL DEFAULT (datetime('now', '+24 hours')),
                PRIMARY KEY (session_id, device_token)
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS subject_device_log (
                subject_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (subject_id, device_id)
            )
        """)
    else:
        # PostgreSQL schema
        conn.run("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('coordinator','incharge','teacher')),
                full_name TEXT,
                class_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS classes (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                department TEXT,
                incharge_id INTEGER
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                teacher_id INTEGER,
                UNIQUE(name, class_id)
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS students (
                roll TEXT PRIMARY KEY,
                name TEXT,
                class_id INTEGER
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
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
        conn.run("""
            CREATE TABLE IF NOT EXISTS session_ip_log (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                ip_address TEXT,
                UNIQUE(session_id, ip_address)
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS session_tokens (
                session_id TEXT NOT NULL,
                device_token TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'issued'
                       CHECK(status IN ('issued','used')),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
                PRIMARY KEY (session_id, device_token)
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS subject_device_log (
                subject_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (subject_id, device_id)
            )
        """)

    # Create indexes (same for both)
    conn.run("CREATE INDEX IF NOT EXISTS idx_att_subject   ON attendance(subject_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_att_sess_roll ON attendance(session_id, roll)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_att_sess_dev  ON attendance(session_id, device_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_att_roll      ON attendance(roll)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_students_cls  ON students(class_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_tok_sess      ON session_tokens(session_id)")
    if not USE_SQLITE:
        conn.run("CREATE INDEX IF NOT EXISTS idx_tok_expires   ON session_tokens(expires_at)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_subdev        ON subject_device_log(subject_id, device_id)")

    # Check if we need to seed default coordinator
    rows = conn.run("SELECT COUNT(*) FROM users")
    if rows[0][0] == 0:
        conn.run("""
            INSERT INTO users (username, password, role, full_name)
            VALUES (:u, :p, :r, :f)
        """, u="coordinator", p="coord123", r="coordinator", f="Coordinator")
        print("Default coordinator created — username: coordinator  password: coord123", flush=True)

    conn.close()


# ══════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════

def get_user_by_username(username):
    conn = get_db()
    rows = conn.run(
        "SELECT id, username, password, role, full_name, class_id FROM users WHERE username = :u",
        u=username
    )
    conn.close()
    if rows:
        r = rows[0]
        return {"id": r[0], "username": r[1], "password": r[2],
                "role": r[3], "full_name": r[4], "class_id": r[5]}
    return None

def authenticate_user(username, password):
    user = get_user_by_username(username)
    if user and user["password"] == password:
        return user
    return None

def add_user(username, password, role, full_name="", class_id=None):
    conn = get_db()
    try:
        conn.run("""
            INSERT INTO users (username, password, role, full_name, class_id)
            VALUES (:u, :p, :r, :f, :c)
        """, u=username, p=password, r=role, f=full_name, c=class_id)
        conn.close()
        return True, "User added!"
    except Exception:
        conn.close()
        return False, "Username already exists."

def delete_user(user_id):
    conn = get_db()
    conn.run("DELETE FROM users WHERE id = :i", i=user_id)
    conn.close()

def get_all_users():
    conn = get_db()
    rows = conn.run("""
        SELECT u.id, u.username, u.role, u.full_name, cl.name
        FROM users u
        LEFT JOIN classes cl ON u.class_id = cl.id
        ORDER BY u.role, u.username
    """)
    conn.close()
    return rows

def get_teachers():
    conn = get_db()
    rows = conn.run("SELECT id, username, full_name FROM users WHERE role = 'teacher' ORDER BY full_name")
    conn.close()
    return rows

def get_incharges():
    conn = get_db()
    rows = conn.run("SELECT id, username, full_name FROM users WHERE role = 'incharge' ORDER BY full_name")
    conn.close()
    return rows


# ══════════════════════════════════════════
# CLASS MANAGEMENT
# ══════════════════════════════════════════

def add_class(name, department=""):
    conn = get_db()
    try:
        conn.run("INSERT INTO classes (name, department) VALUES (:n, :d)", n=name.strip(), d=department)
        conn.close()
        return True, "Class added!"
    except Exception:
        conn.close()
        return False, "Class already exists."

def delete_class(class_id):
    conn = get_db()
    conn.run("DELETE FROM classes WHERE id = :i", i=class_id)
    conn.close()

def get_all_classes():
    conn = get_db()
    rows = conn.run("""
        SELECT cl.id, cl.name, cl.department, u.full_name
        FROM classes cl
        LEFT JOIN users u ON cl.incharge_id = u.id
        ORDER BY cl.name
    """)
    conn.close()
    return rows

def assign_incharge_to_class(class_id, incharge_id):
    conn = get_db()
    conn.run("UPDATE classes SET incharge_id = :i WHERE id = :c", i=incharge_id, c=class_id)
    conn.run("UPDATE users SET class_id = :c WHERE id = :i", c=class_id, i=incharge_id)
    conn.close()


# ══════════════════════════════════════════
# SUBJECT MANAGEMENT
# ══════════════════════════════════════════

def add_subject(name, class_id, teacher_id=None):
    conn = get_db()
    try:
        conn.run("INSERT INTO subjects (name, class_id, teacher_id) VALUES (:n, :c, :t)",
                 n=name.strip(), c=class_id, t=teacher_id)
        conn.close()
        return True, "Subject added!"
    except Exception:
        conn.close()
        return False, "Subject already exists for this class."

def delete_subject(subject_id):
    conn = get_db()
    conn.run("DELETE FROM subjects WHERE id = :i", i=subject_id)
    conn.close()

def assign_teacher_to_subject(subject_id, teacher_id):
    conn = get_db()
    conn.run("UPDATE subjects SET teacher_id = :t WHERE id = :s", t=teacher_id, s=subject_id)
    conn.close()

def get_subjects_for_user(user):
    conn = get_db()
    if user["role"] == "coordinator":
        rows = conn.run("""
            SELECT s.id, s.name, cl.name, u.full_name
            FROM subjects s
            JOIN classes cl ON s.class_id = cl.id
            LEFT JOIN users u ON s.teacher_id = u.id
            ORDER BY cl.name, s.name
        """)
    elif user["role"] == "incharge":
        rows = conn.run("""
            SELECT s.id, s.name, cl.name, u.full_name
            FROM subjects s
            JOIN classes cl ON s.class_id = cl.id
            LEFT JOIN users u ON s.teacher_id = u.id
            WHERE s.class_id = :c
            ORDER BY s.name
        """, c=user["class_id"])
    else:
        rows = conn.run("""
            SELECT s.id, s.name, cl.name, u.full_name
            FROM subjects s
            JOIN classes cl ON s.class_id = cl.id
            LEFT JOIN users u ON s.teacher_id = u.id
            WHERE s.teacher_id = :t
            ORDER BY s.name
        """, t=user["id"])
    conn.close()
    return [{"id": r[0], "name": r[1], "class_name": r[2], "teacher_name": r[3]} for r in rows]

def get_subject_by_id(subject_id):
    conn = get_db()
    rows = conn.run("""
        SELECT s.id, s.name, s.class_id, cl.name
        FROM subjects s JOIN classes cl ON s.class_id = cl.id
        WHERE s.id = :i
    """, i=subject_id)
    conn.close()
    if rows:
        r = rows[0]
        return {"id": r[0], "name": r[1], "class_id": r[2], "class_name": r[3]}
    return None

def get_all_subjects():
    conn = get_db()
    rows = conn.run("""
        SELECT s.id, s.name, cl.name AS class_name, u.full_name AS teacher_name,
               s.class_id, s.teacher_id
        FROM subjects s
        JOIN classes cl ON s.class_id = cl.id
        LEFT JOIN users u ON s.teacher_id = u.id
        ORDER BY cl.name, s.name
    """)
    conn.close()
    return [{"id": r[0], "name": r[1], "class_name": r[2],
             "teacher_name": r[3], "class_id": r[4], "teacher_id": r[5]}
            for r in rows]


# ══════════════════════════════════════════
# STUDENT MANAGEMENT
# ══════════════════════════════════════════

def get_students_by_class(class_id):
    conn = get_db()
    rows = conn.run("SELECT roll, name, class_id FROM students WHERE class_id = :c ORDER BY roll", c=class_id)
    conn.close()
    return rows

def get_all_students():
    conn = get_db()
    rows = conn.run("""
        SELECT s.roll, s.name, s.class_id, cl.name
        FROM students s
        LEFT JOIN classes cl ON s.class_id = cl.id
        ORDER BY cl.name, s.roll
    """)
    conn.close()
    return rows

def add_student(roll, name, class_id):
    conn = get_db()
    try:
        conn.run("""
            INSERT INTO students (roll, name, class_id) VALUES (:r, :n, :c)
            ON CONFLICT(roll) DO UPDATE SET name=EXCLUDED.name, class_id=EXCLUDED.class_id
        """, r=roll.strip().upper(), n=name.strip(), c=class_id)
        conn.close()
        return True, "Student added!"
    except Exception as e:
        conn.close()
        return False, str(e)

def delete_student(roll):
    conn = get_db()
    conn.run("DELETE FROM students WHERE roll = :r", r=roll.upper())
    conn.close()
    return True


# ══════════════════════════════════════════
# SESSION TOKEN MANAGEMENT
# ══════════════════════════════════════════

def db_issue_token(session_id, device_token):
    conn = get_db()
    try:
        conn.run("""
            INSERT INTO session_tokens (session_id, device_token, status)
            VALUES (:s, :d, 'issued')
            ON CONFLICT(session_id, device_token) DO NOTHING
        """, s=session_id, d=device_token)
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def db_consume_token(session_id, device_token):
    conn = get_db()
    try:
        rows = conn.run(
            "SELECT status FROM session_tokens WHERE session_id=:s AND device_token=:d",
            s=session_id, d=device_token
        )
        if not rows:
            check = conn.run("SELECT 1 FROM session_tokens WHERE session_id=:s", s=session_id)
            conn.close()
            if not check:
                return False, "invalid_session"
            return False, "unrecognized_token"
        if rows[0][0] == "used":
            conn.close()
            return False, "already_used"
        conn.run(
            """UPDATE session_tokens SET status='used'
               WHERE session_id=:s AND device_token=:d AND status='issued'""",
            s=session_id, d=device_token
        )
        conn.close()
        return True, None
    except Exception:
        conn.close()
        return False, "invalid_session"

def cleanup_expired_tokens():
    conn = get_db()
    if USE_SQLITE:
        conn.run("DELETE FROM session_tokens WHERE expires_at < datetime('now')")
    else:
        conn.run("DELETE FROM session_tokens WHERE expires_at < NOW()")
    conn.close()
    return 0


# ══════════════════════════════════════════
# ONE DEVICE PER SUBJECT
# ══════════════════════════════════════════

def is_device_blocked_for_subject(subject_id, device_id):
    conn = get_db()
    rows = conn.run(
        "SELECT 1 FROM subject_device_log WHERE subject_id=:s AND device_id=:d",
        s=subject_id, d=device_id
    )
    conn.close()
    return len(rows) > 0

def register_device_for_subject(subject_id, device_id):
    conn = get_db()
    try:
        conn.run(
            "INSERT INTO subject_device_log (subject_id, device_id) VALUES (:s, :d) ON CONFLICT DO NOTHING",
            s=subject_id, d=device_id
        )
    finally:
        conn.close()


# ══════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════

def has_already_submitted(session_id, device_id=None, roll=None, ip_address=None):
    conn = get_db()
    if roll:
        rows = conn.run(
            "SELECT 1 FROM attendance WHERE session_id = :s AND roll = :r",
            s=session_id, r=roll.upper()
        )
        if rows:
            conn.close()
            return True, "roll"
    if device_id:
        rows = conn.run(
            "SELECT 1 FROM attendance WHERE session_id = :s AND device_id = :d",
            s=session_id, d=device_id
        )
        if rows:
            conn.close()
            return True, "device"
    conn.close()
    return False, None

def roll_exists(roll, class_id=None):
    conn = get_db()
    if class_id:
        rows = conn.run(
            "SELECT 1 FROM students WHERE roll = :r AND class_id = :c",
            r=roll.upper(), c=class_id
        )
    else:
        rows = conn.run("SELECT 1 FROM students WHERE roll = :r", r=roll.upper())
    conn.close()
    return len(rows) > 0

def mark_attendance(subject_id, subject_name, class_id, session_id,
                    roll, name, device_id, ip_address):
    conn = get_db()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[DEBUG] Inserting attendance: subject_id={subject_id}, session_id={session_id}, roll={roll.upper()}, timestamp={timestamp}", flush=True)
        conn.run("""
            INSERT INTO attendance
            (subject_id, subject_name, class_id, session_id, roll, name,
             device_id, ip_address, timestamp)
            VALUES (:sid, :sn, :cid, :sess, :r, :n, :dev, :ip, :ts)
        """, sid=subject_id, sn=subject_name, cid=class_id, sess=session_id,
             r=roll.upper(), n=name, dev=device_id, ip=ip_address, ts=timestamp)
        print(f"[DEBUG] Attendance inserted successfully", flush=True)
        conn.run(
            "INSERT INTO session_ip_log (session_id, ip_address) VALUES (:s, :i) ON CONFLICT DO NOTHING",
            s=session_id, i=ip_address
        )
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] mark_attendance failed: {e}", flush=True)
        conn.close()
        return False

def get_student_name(roll):
    conn = get_db()
    rows = conn.run("SELECT name FROM students WHERE roll = :r", r=roll.upper())
    conn.close()
    return rows[0][0] if rows else None

def get_attendance_records(subject_id):
    conn = get_db()
    rows = conn.run("""
        SELECT a.roll,
               COALESCE(s.name, a.name, a.roll) AS student_name,
               a.session_id,
               a.timestamp,
               a.ip_address
        FROM attendance a
        LEFT JOIN students s ON a.roll = s.roll
        WHERE a.subject_id = :sid
        ORDER BY a.timestamp DESC
    """, sid=subject_id)
    conn.close()
    return rows


# ══════════════════════════════════════════
# ATTENDANCE VIEW — per-student summary
# ══════════════════════════════════════════

def get_attendance_summary(subject_id, class_id):
    conn = get_db()
    students = conn.run(
        "SELECT roll, name FROM students WHERE class_id=:c ORDER BY roll", c=class_id
    )
    records = conn.run("""
        SELECT roll, session_id, SUBSTR("timestamp", 1, 10) AS att_date
        FROM attendance
        WHERE subject_id=:sid
        ORDER BY att_date, roll
    """, sid=subject_id)
    conn.close()

    if not students:
        return [], []

    seen_dates = {}
    session_labels = {}
    for roll, session_id, date in records:
        date_str = str(date)
        if session_id not in session_labels:
            count = seen_dates.get(date_str, 0) + 1
            seen_dates[date_str] = count
            label = date_str if count == 1 else f"{date_str} #{count}"
            session_labels[session_id] = label

    all_sessions  = list(session_labels.keys())
    all_labels    = [session_labels[s] for s in all_sessions]
    total_classes = len(all_sessions)

    present_map = {}
    for roll, session_id, date in records:
        present_map.setdefault(roll, set()).add(session_id)

    summary = []
    for roll, name in students:
        sessions_present = present_map.get(roll, set())
        classes_present  = len(sessions_present)
        pct = round(classes_present / total_classes * 100, 1) if total_classes else 0.0
        session_status = {
            lbl: ("P" if sid in sessions_present else "A")
            for sid, lbl in session_labels.items()
        }
        summary.append({
            "roll": roll,
            "name": name,
            "classes_present": classes_present,
            "total_classes": total_classes,
            "pct": pct,
            "dates": session_status,
        })
    return summary, all_labels


# ══════════════════════════════════════════
# STUDENTS — Excel seed
# ══════════════════════════════════════════

def seed_students_from_excel(class_id=None):
    xlsx_path = "student_list.xlsx"
    if not os.path.exists(xlsx_path):
        print("student_list.xlsx not found — skipping seed.")
        return
    try:
        df = pd.read_excel(xlsx_path)
        df.rename(columns=lambda x: x.strip().lower(), inplace=True)
        df["roll"] = df["roll"].astype(str).str.strip().str.upper()
        df["name"] = df["name"].astype(str).str.strip()
        has_class_col = "class_id" in df.columns
        conn = get_db()
        count = skipped = 0
        for _, row in df.iterrows():
            if has_class_col and pd.notna(row.get("class_id")):
                eff_class_id = int(row["class_id"])
            elif class_id is not None:
                eff_class_id = class_id
            else:
                skipped += 1
                continue
            conn.run("""
                INSERT INTO students (roll, name, class_id) VALUES (:r, :n, :c)
                ON CONFLICT(roll) DO UPDATE
                SET name=EXCLUDED.name, class_id=EXCLUDED.class_id
            """, r=row["roll"], n=row["name"], c=eff_class_id)
            count += 1
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
# REPORT
# ══════════════════════════════════════════

def generate_report_for_subject(subject_id, class_id):
    conn = get_db()
    students = conn.run(
        "SELECT roll, name FROM students WHERE class_id = :c ORDER BY roll", c=class_id
    )
    records = conn.run("""
        SELECT roll, SUBSTR("timestamp", 1, 10) AS att_date, session_id
        FROM attendance
        WHERE subject_id = :sid
        ORDER BY att_date, roll
    """, sid=subject_id)
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
    att_df["Date"] = att_df["Date"].astype(str)

    seen_dates = {}
    session_label_map = {}
    for _, row in att_df.drop_duplicates("Session").iterrows():
        date  = row["Date"]
        sid   = row["Session"]
        count = seen_dates.get(date, 0) + 1
        seen_dates[date] = count
        session_label_map[sid] = date if count == 1 else f"{date} #{count}"

    att_df["Label"]  = att_df["Session"].map(session_label_map)
    att_df = att_df.drop_duplicates(subset=["Roll", "Session"])
    att_df["Status"] = "P"

    pivot = att_df.pivot_table(
        index="Roll", columns="Label",
        values="Status", aggfunc="first"
    )
    pivot.reset_index(inplace=True)

    final_df  = pd.merge(student_df, pivot, on="Roll", how="left")
    date_cols = [col for col in final_df.columns if col not in ["Roll", "Name"]]

    for col in date_cols:
        final_df[col] = final_df[col].fillna("A")

    total_classes = len(date_cols)
    final_df["Total Classes"]   = total_classes
    final_df["Classes Present"] = final_df[date_cols].apply(
        lambda row: sum(str(x) == "P" for x in row), axis=1
    )
    final_df["Attendance %"] = (
        (final_df["Classes Present"] / total_classes * 100).round(2)
        if total_classes > 0 else 0.0
    )
    return final_df, date_cols