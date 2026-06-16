# QR Attendance System

A web-based attendance tracking system for educational institutions. Teachers generate a QR code for each class session; students scan it with their phones to mark themselves present. The system prevents duplicate submissions and supports Excel-based student rosters, role-based access, and exportable attendance reports.

---

## Features

- **QR-based attendance** — Teachers generate a per-session QR code; students scan it once to submit their roll number and mark attendance.
- **Anti-fraud controls** — Each device is issued a one-time token on scan. Duplicate device submissions and duplicate IP addresses within the same session are detected and rejected.
- **Role-based access** — Three roles (Coordinator, Incharge, Teacher) with scoped permissions across all actions.
- **Student management** — Add/remove students manually or bulk-seed from an Excel file (`student_list.xlsx`).
- **Attendance reports** — View and export subject-wise, class-wise, or institution-wide attendance as color-coded Excel files.
- **Dual database support** — SQLite for local development; PostgreSQL for production (auto-detected via `DATABASE_URL`).
- **Deployable on Render** — Includes a `Procfile` for one-click deployment using Gunicorn.

---

## Roles

| Role | Permissions |
|---|---|
| **Coordinator** | Full access — manages users, classes, subjects, students, and all reports |
| **Incharge** | Manages subjects, students, and teachers within their assigned class |
| **Teacher** | Generates QR codes for their assigned subjects; views attendance for those subjects |

---

## Project Structure

```
qr-attendance-main/
├── qr_attendance_project.py  # Flask app — all routes and role enforcement
├── database_logic.py         # All DB operations (SQLite + PostgreSQL compatible)
├── qr_generator.py           # QR code generation and device token lifecycle
├── users.py                  # Static user lookup helper (local dev)
├── seed_attendance.py        # Script to seed dummy attendance data
├── check_data.py             # Script to inspect current DB records
├── view_attendance.py        # CLI script to print attendance records
├── test_app.py               # Pytest test suite
├── requirements.txt          # Python dependencies
├── Procfile                  # Gunicorn startup command for Render
├── TEST_GUIDE.md             # Manual testing checklist
└── templates/
    ├── login.html            # Login page
    ├── dashboard.html        # Main dashboard (varies by role)
    ├── students.html         # Student list management
    ├── qr_display.html       # QR code display for teachers
    ├── scan.html             # Student-facing scan/submit page
    ├── confirm.html          # Attendance confirmation page
    └── view_attendance.html  # Attendance records and export
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd qr-attendance-main

# Install dependencies
pip install flask qrcode pillow pandas openpyxl pg8000 gunicorn
# Or use the requirements file:
pip install -r requirements.txt
```

### Run Locally (SQLite)

```bash
python qr_attendance_project.py
```

The app will start at `http://localhost:5000`. On first run, it initializes the SQLite database (`attendance.db`) automatically.

### Seed Students from Excel

Place a file named `student_list.xlsx` in the project root with columns `roll` and `name`. The app will auto-seed students into all existing classes on startup.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret key | `fallback-only-for-dev` |
| `DATABASE_URL` | PostgreSQL connection URL (`postgresql://user:pass@host:port/db`) | *(empty — uses SQLite)* |
| `USE_SQLITE` | Force SQLite even if `DATABASE_URL` is set (`1` / `true`) | — |
| `SQLITE_DB_PATH` | Path for the SQLite database file | `attendance.db` |

---

## Deployment (Render)

1. Push the project to a GitHub repository.
2. Create a new **Web Service** on [Render](https://render.com) and connect the repo.
3. Set the following environment variables in the Render dashboard:
   - `SECRET_KEY` — a long random string
   - `DATABASE_URL` — your PostgreSQL connection string (Render provides this if you add a PostgreSQL database)
4. Render will detect the `Procfile` and start the app with Gunicorn automatically.

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | Stores coordinators, incharges, and teachers with roles |
| `classes` | Class/section records |
| `subjects` | Subjects linked to a class and assigned teacher |
| `students` | Students with roll numbers linked to a class |
| `attendance` | Attendance records (roll, subject, session, timestamp) |
| `session_ip_log` | Tracks IPs per session for duplicate detection |
| `session_tokens` | One-time device tokens issued per scan session |
| `subject_device_log` | Tracks devices per subject to prevent re-scanning |

---

## Running Tests

```bash
pip install pytest
pytest test_app.py -v
```

The test suite covers login, dashboard access, QR generation, attendance submission, duplicate rejection, report export, and route protection.

---

## Tech Stack

- **Backend** — Python, Flask
- **Database** — SQLite (dev) / PostgreSQL via pg8000 (prod)
- **QR Codes** — `qrcode` + `Pillow`
- **Excel Export** — `pandas` + `openpyxl`
- **Server** — Gunicorn
- **Frontend** — Jinja2 templates (HTML/CSS/JS, no frontend framework)

---

## License

This project is intended for institutional use. Please check with the author before redistributing or deploying commercially.
