from flask import Flask, render_template, request, redirect, url_for, session
from users import users
    # Redirect to dashboard
from qr_generator import generate_qr
from save_attendance import mark_attendance
import os
app = Flask(__name__)
app.secret_key = "secretkey123"  # Needed to manage sessions
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
    return render_template("scan.html", subject=subject, session_id=session_id)
@app.route("/submit_attendance", methods=["POST"])
def submit_attendance():
    name = request.form["name"]
    roll = request.form["roll"]
    subject = request.form["subject"]
    session_id = request.form["session_id"]

    result = mark_attendance(subject, name, roll, session_id)
    return render_template("confirm.html", message=result)
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
