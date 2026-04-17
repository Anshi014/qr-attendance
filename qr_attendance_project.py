from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database_logic import (
    init_db, seed_students_from_excel, load_student_list,
    roll_exists, has_already_submitted, mark_attendance, get_student_name,
    add_user, delete_user, get_all_users, get_teachers, get_incharges,
    add_class, delete_class, get_all_classes, assign_incharge_to_class,
    add_subject, delete_subject, assign_teacher_to_subject,
    get_subjects_for_user, get_subject_by_id,
    authenticate_user, generate_report_for_subject
)
from qr_generator import generate_qr, generate_device_token, is_device_allowed, register_device
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "rbu_qr_secret_2024"

init_db()

# ✅ FIX: Startup pe sabhi classes ke liye students seed karo
def seed_all_classes():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("SELECT id FROM classes")
    class_ids = [row[0] for row in c.fetchall()]
    conn.close()
    for cid in class_ids:
        seed_students_from_excel(class_id=cid)

seed_all_classes()

# ── helpers ──
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
# ─────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    redir = require_login()
    if redir: return redir
    user      = current_user()
    subjects  = get_subjects_for_user(user)
    classes   = get_all_classes() if user["role"] == "coordinator" else []
    all_users = get_all_users()   if user["role"] == "coordinator" else []
    teachers  = get_teachers()
    incharges = get_incharges()
    return render_template("dashboard.html",
        user=user,
        subjects=subjects,
        classes=classes,
        all_users=all_users,
        teachers=teachers,
        incharges=incharges
    )

# ─────────────────────────────────────────────
# USER MANAGEMENT (coordinator only)
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
# CLASS MANAGEMENT (coordinator only)
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
# SUBJECT MANAGEMENT (coordinator + incharge)
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

@app.route("/assign_teacher", methods=["POST"])
def assign_teacher_route():
    err = require_role("coordinator", "incharge")
    if err: return err
    subject_id = int(request.form.get("subject_id"))
    teacher_id = int(request.form.get("teacher_id"))
    assign_teacher_to_subject(subject_id, teacher_id)
    return redirect(url_for("dashboard"))

# ─────────────────────────────────────────────
# QR GENERATION
# ─────────────────────────────────────────────

@app.route("/generate_qr/<int:subject_id>")
def generate_qr_route(subject_id):
    redir = require_login()
    if redir: return redir
    subject = get_subject_by_id(subject_id)
    if not subject:
        return "❌ Subject not found."
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
        return "❌ Invalid QR code."
    device_token = generate_device_token()
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

    if not is_device_allowed(session_id, device_token):
        return render_template("confirm.html",
            message="❌ This device already marked attendance.",
            session_id=session_id)

    subject = get_subject_by_id(int(subject_id)) if subject_id else None
    if not subject:
        return render_template("confirm.html",
            message="❌ Invalid subject.", session_id=session_id)

    if not roll_exists(roll, subject["class_id"]):
        return render_template("confirm.html",
            message="❌ Roll number not found in this class.", session_id=session_id)

    already, reason = has_already_submitted(
        session_id, device_id=device_token, roll=roll, ip_address=ip_address)
    if already:
        msgs = {
            "roll":   "❌ Attendance already marked for this roll number.",
            "device": "❌ This device already marked attendance.",
            "ip":     "❌ Attendance already marked from this network."
        }
        return render_template("confirm.html",
            message=msgs.get(reason, "❌ Already submitted."), session_id=session_id)

    name = get_student_name(roll) or "Unknown"
    success = mark_attendance(
        subject["id"], subject["name"], subject["class_id"],
        session_id, roll, name, device_token, ip_address
    )
    if not success:
        return render_template("confirm.html",
            message="❌ Already submitted (duplicate blocked).", session_id=session_id)

    register_device(session_id, device_token)
    session.pop("device_token", None)
    return render_template("confirm.html",
        message=f"✅ Attendance marked for {name} ({roll})",
        session_id=session_id)

# ─────────────────────────────────────────────
# REPORTS
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
    if not date_cols and len(final_df.columns) == 2:
        return f"⚠️ No attendance data for {subject['name']} yet."

    os.makedirs("exports", exist_ok=True)
    month_str = dt.now().strftime("%B_%Y")
    filename  = f"{subject['class_name']}_{subject['name']}_{month_str}.xlsx"
    filepath  = os.path.join("exports", filename)
    final_df.to_excel(filepath, index=False)
    _apply_colors(filepath)
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

    conn = sqlite3.connect("attendance.db")
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
            final_df, _ = generate_report_for_subject(sub_id, class_id)
            final_df.to_excel(writer, sheet_name=sub_name[:31], index=False)

    _apply_colors(filepath)
    return redirect(url_for("download_export", filename=filename))

@app.route("/report/all")
def report_all():
    err = require_role("coordinator")
    if err: return err

    from datetime import datetime as dt
    import pandas as pd

    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM classes ORDER BY name")
    classes = c.fetchall()
    conn.close()

    os.makedirs("exports", exist_ok=True)
    filename = f"All_Classes_Report_{dt.now().strftime('%B_%Y')}.xlsx"
    filepath = os.path.join("exports", filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for cls_id, cls_name in classes:
            conn = sqlite3.connect("attendance.db")
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

def _apply_colors(filepath):
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill, Font
    wb    = load_workbook(filepath)
    green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red   = PatternFill(start_color="F2DCDB", end_color="F2DCDB", fill_type="solid")
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in ws.iter_rows(min_row=2, min_col=3, max_col=ws.max_column - 3):
            for cell in row:
                if cell.value == "P":   cell.fill = green
                elif cell.value == "A": cell.fill = red
    wb.save(filepath)

# ─────────────────────────────────────────────
# MISC
# ─────────────────────────────────────────────

@app.route("/download/<filename>")
def download_export(filename):
    from flask import send_from_directory
    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    return send_from_directory(exports_dir, filename, as_attachment=True)

@app.route("/students")
def show_students():
    redir = require_login()
    if redir: return redir
    df = load_student_list()
    if df is None:
        return "❌ Could not load student list."
    return df.to_html(index=False)

# ✅ FIX: class_id parameter support added
@app.route("/refresh_students")
def refresh_students():
    err = require_role("coordinator", "incharge")
    if err: return err
    user = current_user()
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


@app.route("/view_attendance/<int:subject_id>")
def view_attendance(subject_id):
    redir = require_login()
    if redir: return redir
    
    # Fetch subject details
    subject = get_subject_by_id(subject_id)
    if not subject:
        return "❌ Subject not found."
    
    # Fetch attendance records
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT roll, name, session_id, timestamp, ip_address FROM attendance WHERE subject_id = ? ORDER BY timestamp DESC", (subject_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return render_template("view_attendance.html", 
            subject=subject,
            records=[], 
            message="⚠️ No attendance records found for this subject yet.",
            total_students=0,
            total_present=0)
    
    # Calculate statistics
    total_present = len(set(row[0] for row in rows))  # Count unique rolls marked present
    # Get total students in the class
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students WHERE class_id = ?", (subject["class_id"],))
    total_students = cursor.fetchone()[0]
    conn.close()
    
    return render_template("view_attendance.html", 
        subject=subject,
        records=rows,
        total_students=total_students,
        total_present=total_present)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)