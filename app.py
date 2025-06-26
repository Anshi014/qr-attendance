from database_logic import init_db, seed_students_from_excel
from database_logic import load_student_list
from flask import Flask, render_template, request, redirect, url_for, session
from database_logic import roll_exists
from users import users
    # Redirect to dashboard
from qr_generator import generate_qr
import os
app = Flask(__name__)
app.secret_key = "secretkey123"
init_db() #this creates the attendance table if not already there
seed_students_from_excel()

# Needed to manage sessions
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username]["password"] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))

        return "❌ Invalid login. Try again."

    return render_template("login.html")
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    user = users[session["user"]]
    return render_template(
        "dashboard.html",
        username=session["user"],
        role=user["role"],
        subjects=user["subjects"]
    )
@app.route("/generate_qr/<subject>")
def generate_qr_route(subject):
    if "user" not in session:
        return redirect(url_for("login"))

    session_id, subject, qr_image = generate_qr(subject)
    return render_template("dashboard.html", qr_image=qr_image, session_id=session_id, subject=subject)
@app.route("/scan")
def scan():
    subject = request.args.get("subject", "")
    session_id = request.args.get("session_id", "")

    submitted_roll = session.get(f"submitted_for_{subject}_{session_id}")
    if submitted_roll:
        return render_template("confirm.html", message=f"❌ This device has already submitted attendance for Roll No: {submitted_roll}")

    return render_template("scan.html", subject=subject, session_id=session_id)
from database_logic import has_already_submitted, mark_attendance

@app.route("/submit_attendance", methods=["POST"])
def submit_attendance():
    roll = request.form["roll"].strip().upper()
    subject = request.form["subject"]
    session_id = request.form["session_id"]
    device_id = request.form.get("device_id")
    ip_address = request.remote_addr
    
    #check if roll exists in students table
    if not roll_exists(roll):
        return render_template("confirm.html",message="Roll number not found in student database.")
    
    #optional: Auto-fill name from DB
    import sqlite3
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students WHERE roll = ?",(roll,))
    result = cursor.fetchone()
    conn.close()
    if result:
        name = result[0]

    if has_already_submitted(subject, device_id=device_id):
        return render_template("confirm.html", message="❌ This device already marked attendance for this subject.")
    
    if has_already_submitted(subject, ip_address=ip_address):
        return render_template("confirm.html", message="❌ This IP already submitted attendance for this subject.")
    # Load student list and validate roll

    mark_attendance(subject, session_id, roll, name, device_id, ip_address)
    return render_template("confirm.html", message=f"✅ Attendance marked for {name} ({roll})")
@app.route("/export/<subject>")
def export_subject(subject):
    import pandas as pd
    import sqlite3

    if "user" not in session:
        return redirect(url_for("login"))
    
    user = users.get(session["user"])
    if user["role"] not in ["incharge","cr"]:
        return "Access denied."

    conn = sqlite3.connect("attendance.db")
    df = pd.read_sql_query("SELECT * FROM attendance ", conn)
    conn.close()

    export_folder = "exports"
    os.makedirs(export_folder, exist_ok=True)
    filename = f"{subject}_attendance.xlsx"
    filepath = os.path.join(export_folder, filename)
    df.to_excel(filepath, index=False)

    return redirect(url_for("download_export", filename=filename))

@app.route("/download/<filename>")
def download_export(filename):
    from flask import send_from_directory
    return send_from_directory("exports", filename, as_attachment=True)

@app.route("/students")
def show_students():
    df = load_student_list()
    if df is None:
        return "❌ Could not load student list."

    return df.to_html(index=False)

@app.route("/report/<subject>/<session_id>")
def generate_report(subject, session_id):
    import pandas as pd
    import sqlite3

    # Connect to DB
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Get full student list
    cursor.execute("SELECT roll, name FROM students")
    students = cursor.fetchall()

    # Get attendees for this session
    cursor.execute("""
        SELECT roll FROM attendance
        WHERE subject = ? AND session_id = ?
    """, (subject, session_id))
    present_rolls = set(row[0] for row in cursor.fetchall())

    conn.close()

    # Build DataFrame with 'P' or 'A'
    report = []
    for roll, name in students:
        status = "P" if roll.strip().upper() in present_rolls else "A"
        report.append({"Roll": roll, "Name": name, "Status": status})

    df = pd.DataFrame(report)

    # Save Excel file
    import os
    export_folder = "exports"
    os.makedirs(export_folder, exist_ok=True)
    filename = f"{subject}_{session_id}_report.xlsx"
    filepath = os.path.join(export_folder, filename)
    df.to_excel(filepath, index=False)

    return redirect(url_for("download_export", filename=filename))
@app.route("/get_name", methods=["POST"])
def get_name():
    roll = request.form["roll"].strip().upper()
    import sqlite3
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students WHERE roll = ?", (roll,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "❌ Not found"


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
