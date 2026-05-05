import qrcode
import uuid
import os
import secrets
import glob
import sqlite3
from datetime import datetime

# ── DB path — mirrors qr_attendance_project.py so both use the same file ─────
DB = os.environ.get("DB_PATH", "attendance.db")

# ── Import DB token helpers (avoids circular import by importing lazily) ──────
def _db():
    from database_logic import db_issue_token, db_consume_token
    return db_issue_token, db_consume_token


# ══════════════════════════════════════════════════════════════
# QR GENERATION
# ══════════════════════════════════════════════════════════════

def generate_qr(subject_id, subject_name,
                base_url="https://qr-attendance-bgdn.onrender.com"):
    """
    Generate a QR code PNG for one attendance session.

    Cleans up previous QR PNGs for the same subject first so the
    static/qr_codes folder never fills up.  (Issue 4b fix)

    Returns (session_id, filename).
    """
    session_id = str(uuid.uuid4())[:8]
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_name = "".join(c for c in subject_name if c.isalnum() or c in "_-")
    filename  = f"{safe_name}_{timestamp}.png"

    folder = os.path.join("static", "qr_codes")
    os.makedirs(folder, exist_ok=True)

    # ── Issue 4b: Remove old QR codes for this subject (keeps disk tidy) ──
    for old_file in glob.glob(os.path.join(folder, f"{safe_name}_*.png")):
        try:
            os.remove(old_file)
        except OSError:
            pass  # File in use or already gone — not fatal

    content = f"{base_url}/scan?subject_id={subject_id}&session_id={session_id}"
    img = qrcode.make(content)
    img.save(os.path.join(folder, filename))

    return session_id, filename


# ══════════════════════════════════════════════════════════════
# DEVICE TOKEN LIFECYCLE  (DB-backed — survives server restarts)
# ══════════════════════════════════════════════════════════════

def issue_device_token(session_id):
    """
    Called once when a device hits /scan.

    Creates a cryptographically random one-time token, persists it to the
    session_tokens table as 'issued', and returns it.

    Returns the token string, or None if the DB write failed.
    """
    token = secrets.token_hex(16)
    db_issue, _ = _db()
    ok = db_issue(session_id, token)
    return token if ok else None


def consume_device_token(session_id, device_token):
    """
    Atomically validates and consumes a device token on form submission.

    Returns (True, None) when the token is valid and not yet used.
    Returns (False, reason) otherwise — reason is one of:
        'invalid_session'    — session_id unknown
        'unrecognized_token' — token was never issued for this session
        'already_used'       — token already consumed (duplicate submit)
    """
    _, db_consume = _db()
    return db_consume(session_id, device_token)


# ══════════════════════════════════════════════════════════════
# TOKEN CLEANUP  (Issue 1 fix — called once at server startup)
# ══════════════════════════════════════════════════════════════

def cleanup_old_tokens():
    """
    Delete session tokens older than 7 days so the session_tokens table
    doesn't grow indefinitely.  Safe to call on every server start.
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM session_tokens WHERE created_at < datetime('now', '-7 days')")
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
# LEGACY SHIMS  (kept so existing routes don't break immediately)
# ══════════════════════════════════════════════════════════════

def generate_device_token():
    """
    Legacy shim.  Returns a raw token (not yet tied to any session).
    Prefer issue_device_token(session_id) for new code.
    """
    return secrets.token_hex(16)


def is_device_allowed(session_id, device_token):
    """
    Legacy shim.  True = token has NOT been used yet (allowed to proceed).
    Checks the DB directly without consuming the token.
    """
    from database_logic import get_db
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT status FROM session_tokens WHERE session_id=? AND device_token=?",
        (session_id, device_token)
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return True            # Token not in DB yet — allow
    return row[0] == "issued"  # False if already 'used'


def register_device(session_id, device_token):
    """
    Legacy shim.  Marks the token as 'used' in the DB.
    """
    from database_logic import db_consume_token
    db_consume_token(session_id, device_token)