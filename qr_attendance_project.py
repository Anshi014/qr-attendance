import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g

from database_logic import (
    init_db, seed_students_from_excel, load_student_list,
    roll_exists, has_already_submitted, mark_attendance, get_student_name,
    add_user, delete_user, get_all_users, get_teachers, get_incharges,
    add_class, delete_class, get_all_classes, assign_incharge_to_class,
    add_subject, delete_subject, assign_teacher_to_subject,
    get_subjects_for_user, get_subject_by_id, get_all_subjects,
    authenticate_user, generate_report_for_subject,
    get_attendance_records,
    get_students_by_class, get_all_students, add_student, delete_student,
    is_device_blocked_for_subject, register_device_for_subject
)
from qr_generator import generate_qr, issue_device_token, consume_device_token, cleanup_old_tokens

app = Flask(__name__)

# Secret key from environment — never hardcode
app.secret_key = os.environ.get("SECRET_KEY", "fallback-only-for-dev")

# DB path from environment (set DB_PATH=/data/attendance.db on Render with Persistent Disk)
DB = os.environ.get("DB_PATH", "attendance.db")

init_db()


def seed_all_classes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id FROM classes")
    class_ids = [row[0] for row in c.fetchall()]
    conn.close()
    for cid in class_ids:
        seed_students_from_excel(class_id=cid)

seed_all_classes()


# ── Per-request DB connection ──────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


# ── DB indexes at startup ──────────────────────────────────────────────────────

def ensure_indexes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_subject        ON attendance(subject_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_session_roll   ON attendance(session_id, roll)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_att_session_device ON attendance(session_id, device_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_students_class     ON students(class_id)")
    conn.commit()
    conn.close()

ensure_indexes()
cleanup_old_tokens()


# ── Role helpers ───────────────────────────────────────────────────────────────

def current_user():
    return session.get("user_data")

def require_login():
    if not current_user():
        return redirect(url_for("login"))
    return None

def require_role(*roles):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if user["role"] not in roles:
        return "❌ Access denied.", 403
    return None


# ─────────────────────────────────────────────
# LOGIN / LOGOUT
# ─────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = authenticate_user(username, password)
        if user:
            session["user_data"] = user
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="❌ Invalid username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────
# DASHBOARD
# Permissions:
#   coordinator — sees everything, manages users/classes/subjects/teachers
#   incharge    — sees their class subjects, can add subjects, assign teachers
#   teacher     — sees only their assigned subjects, can generate QR & reports
# ─────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    redir = require_login()
    if redir: return redir
    user      = current_user()
    subjects  = get_subjects_for_user(user)
    classes   = get_all_classes() if user["role"] in ["coordinator", "incharge"] else []
    all_users = get_all_users()   if user["role"] == "coordinator" else []
    teachers  = get_teachers()
    incharges = get_incharges()
    # All subjects list for the assign-teacher panel (coordinator only)
    all_subjects = get_all_subjects() if user["role"] == "coordinator" else []
    return render_template("dashboard.html",
        user=user,
        subjects=subjects,
        classes=classes,
        all_users=all_users,
        teachers=teachers,
        incharges=incharges,
        all_subjects=all_subjects
    )


# ─────────────────────────────────────────────
# USER MANAGEMENT  (coordinator only)
# ─────────────────────────────────────────────

@app.route("/add_user", methods=["POST"])
def add_user_route():
    err = require_role("coordinator")
    if err: return err
    username  = request.form.get("username", "").strip()
    password  = request.form.get("password", "").strip()
    role      = request.form.get("role", "")
    full_name = request.form.get("full_name", "").strip()
    class_id  = request.form.get("class_id") or None
    if class_id:
        class_id = int(class_id)
    add_user(username, password, role, full_name, class_id)
    return redirect(url_for("dashboard"))

@app.route("/delete_user/<int:uid>")
def delete_user_route(uid):
    err = require_role("coordinator")
    if err: return err
    delete_user(uid)
    return redirect(url_for("dashboard"))


# ─────────────────────────────────────────────
# CLASS MANAGEMENT  (coordinator only)
# ─────────────────────────────────────────────

@app.route("/add_class", methods=["POST"])
def add_class_route():
    err = require_role("coordinator")
    if err: return err
    name = request.form.get("class_name", "").strip()
    dept = request.form.get("department", "").strip()
    add_class(name, dept)
    return redirect(url_for("dashboard"))

@app.route("/delete_class/<int:cid>")
def delete_class_route(cid):
    err = require_role("coordinator")
    if err: return err
    delete_class(cid)
    return redirect(url_for("dashboard"))

@app.route("/assign_incharge", methods=["POST"])
def assign_incharge_route():
    err = require_role("coordinator")
    if err: return err
    class_id    = int(request.form.get("class_id"))
    incharge_id = int(request.form.get("incharge_id"))
    assign_incharge_to_class(class_id, incharge_id)
    return redirect(url_for("dashboard"))


# ─────────────────────────────────────────────
# SUBJECT MANAGEMENT  (coordinator + incharge)
# ─────────────────────────────────────────────

@app.route("/add_subject", methods=["POST"])
def add_subject_route():
    err = require_role("coordinator", "incharge")
    if err: return err
    user       = current_user()
    name       = request.form.get("subject_name", "").strip()
    class_id   = request.form.get("class_id") or user.get("class_id")
    teacher_id = request.form.get("teacher_id") or None
    if class_id:
        add_subject(name, int(class_id), int(teacher_id) if teacher_id else None)
    return redirect(url_for("dashboard"))

@app.route("/delete_subject/<int:sid>")
def delete_subject_route(sid):
    err = require_role("coordinator", "incharge")
    if err: return err
    delete_subject(sid)
    return redirect(url_for("dashboard"))

# ── Assign teacher to existing subject ────────────────────────────────────────
# This route handles the "Assign Teacher" form on the dashboard.
# Coordinator can assign any teacher to any subject.
# Incharge can assign teachers to subjects in their own class only.
@app.route("/assign_teacher", methods=["POST"])
def assign_teacher_route():
    err = require_role("coordinator", "incharge")
    if err: return err
    user       = current_user()
    subject_id = int(request.form.get("subject_id"))
    teacher_id = int(request.form.get("teacher_id"))

    # Incharge guard — can only assign teachers to their own class subjects
    if user["role"] == "incharge":
        subject = get_subject_by_id(subject_id)
        if not subject or subject["class_id"] != user["class_id"]:
            return "❌ Access denied — subject not in your class.", 403

    assign_teacher_to_subject(subject_id, teacher_id)
    return redirect(url_for("dashboard"))


# ─────────────────────────────────────────────
# STUDENT MANAGEMENT
# ─────────────────────────────────────────────

@app.route("/students")
def show_students():
    redir = require_login()
    if redir: return redir
    user    = current_user()
    classes = get_all_classes()

    class_id = request.args.get("class_id")
    if class_id:
        class_id = int(class_id)
        students = get_students_by_class(class_id)
    elif user["role"] == "coordinator":
        students = get_all_students()
        class_id = None
    else:
        class_id = user.get("class_id")
        students = get_students_by_class(class_id) if class_id else []

    return render_template("students.html",
        user=user,
        students=students,
        classes=classes,
        selected_class_id=class_id
    )

@app.route("/add_student", methods=["POST"])
def add_student_route():
    err = require_role("coordinator", "incharge")
    if err: return err
    roll     = request.form.get("roll", "").strip()
    name     = request.form.get("name", "").strip()
    class_id = request.form.get("class_id", "")
    if not roll or not name or not class_id:
        return redirect(url_for("show_students"))
    add_student(roll, name, int(class_id))
    return redirect(url_for("show_students", class_id=class_id))

@app.route("/delete_student/<roll>")
def delete_student_route(roll):
    err = require_role("coordinator", "incharge")
    if err: return err
    class_id = request.args.get("class_id", "")
    delete_student(roll)
    return redirect(url_for("show_students", class_id=class_id))


# ─────────────────────────────────────────────
# QR GENERATION
# Only coordinator, incharge, and teacher can generate QR.
# Teacher can only generate QR for their own assigned subjects.
# ─────────────────────────────────────────────

@app.route("/generate_qr/<int:subject_id>")
def generate_qr_route(subject_id):
    redir = require_login()
    if redir: return redir
    user    = current_user()
    subject = get_subject_by_id(subject_id)
    if not subject:
        return "❌ Subject not found."

    # Teacher permission check
    if user["role"] == "teacher":
        my_subjects = get_subjects_for_user(user)
        if not any(s["id"] == subject_id for s in my_subjects):
            return "❌ Access denied — not your subject.", 403

    session_id, qr_image = generate_qr(subject["id"], subject["name"])
    return render_template("qr_display.html",
        subject=subject,
        session_id=session_id,
        qr_image=qr_image
    )

@app.route("/refresh_qr/<int:subject_id>")
def refresh_qr(subject_id):
    redir = require_login()
    if redir: return jsonify({"error": "Not logged in"}), 401
    subject = get_subject_by_id(subject_id)
    if not subject:
        return jsonify({"error": "Subject not found"}), 404
    session_id, qr_image = generate_qr(subject["id"], subject["name"])
    return jsonify({"session_id": session_id, "qr_image": qr_image})


# ─────────────────────────────────────────────
# SCAN (student side)
# ─────────────────────────────────────────────

@app.route("/scan")
def scan():
    subject_id = request.args.get("subject_id", "")
    session_id = request.args.get("session_id", "")

    subject = get_subject_by_id(int(subject_id)) if subject_id else None
    if not subject:
        return render_template("confirm.html",
            message="❌ Invalid QR code.", session_id="")

    device_token = issue_device_token(session_id)
    if not device_token:
        return render_template("confirm.html",
            message="❌ Invalid or expired session. Ask your teacher to refresh the QR.",
            session_id=session_id)

    session["device_token"]    = device_token
    session["scan_subject_id"] = subject_id
    session["scan_session_id"] = session_id

    return render_template("scan.html",
        subject=subject,
        session_id=session_id,
        device_token=device_token
    )


@app.route("/submit_attendance", methods=["POST"])
def submit_attendance():
    roll       = request.form.get("roll", "").strip().upper()
    subject_id = request.form.get("subject_id", "")
    session_id = request.form.get("session_id", "")
    ip_address = request.remote_addr

    device_token = session.get("device_token")
    if not device_token:
        return render_template("confirm.html",
            message="❌ Invalid session. Please scan the QR code again.",
            session_id=session_id)

    # ── Step 1: Consume the one-time session token ─────────────────────────
    allowed, reason = consume_device_token(session_id, device_token)
    if not allowed:
        error_messages = {
            "invalid_session":    "❌ Session expired. Ask your teacher to refresh the QR.",
            "unrecognized_token": "❌ Invalid token. Please scan the QR code again.",
            "already_used":       "❌ This device has already submitted for this session.",
        }
        return render_template("confirm.html",
            message=error_messages.get(reason, "❌ Already submitted."),
            session_id=session_id)

    subject = get_subject_by_id(int(subject_id)) if subject_id else None
    if not subject:
        return render_template("confirm.html",
            message="❌ Invalid subject.", session_id=session_id)

    # ── Step 2: One device per subject (across ALL sessions) ───────────────
    # This is the new unique feature — a device can only ever mark attendance
    # once for a given subject, even if the QR is refreshed.
    if is_device_blocked_for_subject(subject["id"], device_token):
        return render_template("confirm.html",
            message="❌ This device has already marked attendance for this subject.",
            session_id=session_id)

    # ── Step 3: Validate roll number ───────────────────────────────────────
    # FIX: use subject["class_id"] so roll is checked against the correct class
    if not roll_exists(roll, subject["class_id"]):
        return render_template("confirm.html",
            message=f"❌ Roll number '{roll}' not found in this class. Check and try again.",
            session_id=session_id)

    # ── Step 4: Check for duplicate within this session ────────────────────
    already, reason = has_already_submitted(
        session_id, device_id=device_token, roll=roll, ip_address=ip_address)
    if already:
        msgs = {
            "roll":   "❌ Attendance already marked for this roll number.",
            "device": "❌ This device has already marked attendance.",
            "ip":     "❌ Attendance already marked from this network.",
        }
        return render_template("confirm.html",
            message=msgs.get(reason, "❌ Already submitted."), session_id=session_id)

    # ── Step 5: Mark attendance ────────────────────────────────────────────
    name = get_student_name(roll) or "Unknown"
    success = mark_attendance(
        subject["id"], subject["name"], subject["class_id"],
        session_id, roll, name, device_token, ip_address
    )

    session.pop("device_token", None)

    if not success:
        return render_template("confirm.html",
            message="❌ Already submitted (duplicate blocked).", session_id=session_id)

    # ── Step 6: Register device for this subject (one-device-per-subject) ──
    register_device_for_subject(subject["id"], device_token)

    return render_template("confirm.html",
        message=f"✅ Attendance marked for {name} ({roll})",
        session_id=session_id)


# ─────────────────────────────────────────────
# VIEW ATTENDANCE
# ─────────────────────────────────────────────

@app.route("/view_attendance/<int:subject_id>")
def view_attendance(subject_id):
    redir = require_login()
    if redir: return redir

    subject = get_subject_by_id(subject_id)
    if not subject:
        return "❌ Subject not found."

    final_df, date_cols = generate_report_for_subject(subject_id, subject["class_id"])
    students_data = final_df.to_dict(orient="records") if not final_df.empty else []

    return render_template("view_attendance.html",
        subject=subject,
        students_data=students_data,
        date_cols=date_cols,
        total_students=len(students_data),
        message="" if students_data else "⚠️ No attendance records found for this subject yet."
    )


# ─────────────────────────────────────────────
# REPORTS
# coordinator — all subjects/classes
# incharge    — their class only
# teacher     — their assigned subjects only
# ─────────────────────────────────────────────

@app.route("/report/<int:subject_id>")
def report(subject_id):
    redir = require_login()
    if redir: return redir
    user    = current_user()
    subject = get_subject_by_id(subject_id)
    if not subject:
        return "❌ Subject not found."

    if user["role"] == "teacher":
        my_subjects = get_subjects_for_user(user)
        if not any(s["id"] == subject_id for s in my_subjects):
            return "❌ Access denied."
    elif user["role"] == "incharge":
        if subject["class_id"] != user["class_id"]:
            return "❌ Access denied."

    from datetime import datetime as dt
    import pandas as pd

    final_df, date_cols = generate_report_for_subject(subject_id, subject["class_id"])

    os.makedirs("exports", exist_ok=True)
    month_str = dt.now().strftime("%B_%Y")
    filename  = f"{subject['class_name']}_{subject['name']}_{month_str}.xlsx"
    filepath  = os.path.join("exports", filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="Attendance", index=False)

    _apply_colors(filepath, date_cols)
    return redirect(url_for("download_export", filename=filename))


@app.route("/report/class/<int:class_id>")
def report_class(class_id):
    redir = require_login()
    if redir: return redir
    user = current_user()
    if user["role"] == "teacher":
        return "❌ Access denied."
    if user["role"] == "incharge" and user["class_id"] != class_id:
        return "❌ Access denied."

    from datetime import datetime as dt
    import pandas as pd

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, name FROM subjects WHERE class_id = ?", (class_id,))
    subs = c.fetchall()
    c.execute("SELECT name FROM classes WHERE id = ?", (class_id,))
    cls_row = c.fetchone()
    conn.close()

    if not subs:
        return "⚠️ No subjects found for this class."

    class_name = cls_row[0] if cls_row else f"Class_{class_id}"
    os.makedirs("exports", exist_ok=True)
    filename = f"{class_name}_Full_Report_{dt.now().strftime('%B_%Y')}.xlsx"
    filepath = os.path.join("exports", filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sub_id, sub_name in subs:
            final_df, date_cols = generate_report_for_subject(sub_id, class_id)
            sheet_name = sub_name[:31]
            final_df.to_excel(writer, sheet_name=sheet_name, index=False)

    _apply_colors(filepath)
    return redirect(url_for("download_export", filename=filename))


@app.route("/report/all")
def report_all():
    err = require_role("coordinator")
    if err: return err

    from datetime import datetime as dt
    import pandas as pd

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, name FROM classes ORDER BY name")
    classes = c.fetchall()
    conn.close()

    os.makedirs("exports", exist_ok=True)
    filename = f"All_Classes_Report_{dt.now().strftime('%B_%Y')}.xlsx"
    filepath = os.path.join("exports", filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for cls_id, cls_name in classes:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("SELECT id, name FROM subjects WHERE class_id = ?", (cls_id,))
            subs = c.fetchall()
            conn.close()
            for sub_id, sub_name in subs:
                sheet = f"{cls_name}-{sub_name}"[:31]
                final_df, _ = generate_report_for_subject(sub_id, cls_id)
                final_df.to_excel(writer, sheet_name=sheet, index=False)

    _apply_colors(filepath)
    return redirect(url_for("download_export", filename=filename))


def _apply_colors(filepath, date_cols=None):
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    wb = load_workbook(filepath)
    green       = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red         = PatternFill(start_color="F2DCDB", end_color="F2DCDB", fill_type="solid")
    yellow      = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    header_fill = PatternFill(start_color="1A3A6B", end_color="1A3A6B", fill_type="solid")

    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font      = Font(bold=True, color="FFFFFF")
            cell.fill      = header_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        header_vals = [cell.value for cell in ws[1]]

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                col_name = header_vals[cell.column - 1] if cell.column <= len(header_vals) else ""
                if cell.value == "P":
                    cell.fill      = green
                    cell.alignment = Alignment(horizontal="center")
                elif cell.value == "A":
                    cell.fill      = red
                    cell.alignment = Alignment(horizontal="center")
                elif col_name == "Attendance %":
                    try:
                        pct = float(cell.value)
                        if pct >= 75:
                            cell.fill = green
                        elif pct >= 60:
                            cell.fill = yellow
                        else:
                            cell.fill = red
                    except (TypeError, ValueError):
                        pass
                    cell.alignment = Alignment(horizontal="center")

        for col in ws.columns:
            max_len    = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 4, 20)

    wb.save(filepath)


# ─────────────────────────────────────────────
# MISC
# ─────────────────────────────────────────────

@app.route("/download/<filename>")
def download_export(filename):
    from flask import send_from_directory
    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    return send_from_directory(exports_dir, filename, as_attachment=True)

@app.route("/refresh_students")
def refresh_students():
    err = require_role("coordinator", "incharge")
    if err: return err
    user     = current_user()
    class_id = request.args.get("class_id") or user.get("class_id")
    if class_id:
        seed_students_from_excel(class_id=int(class_id))
    else:
        seed_all_classes()
    return redirect(url_for("dashboard"))

@app.route("/get_name", methods=["POST"])
def get_name():
    roll = request.form["roll"].strip().upper()
    name = get_student_name(roll)
    return name if name else "❌ Not found"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)