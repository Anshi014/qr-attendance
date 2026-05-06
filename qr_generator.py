import qrcode
import uuid
import os
import secrets
import glob
from datetime import datetime

# FIX: Removed direct sqlite3 import — all DB operations now go through
# database_logic to avoid duplicate/inconsistent cleanup logic.
from database_logic import db_issue_token, db_consume_token, cleanup_expired_tokens


# ══════════════════════════════════════════════════════════════
# QR GENERATION
# ══════════════════════════════════════════════════════════════

def generate_qr(subject_id, subject_name,
                base_url="https://qr-attendance-bgdn.onrender.com"):
    """
    Generate a QR code PNG for one attendance session.
    Cleans up previous QR PNGs for the same subject first.
    Returns (session_id, filename).
    """
    session_id = str(uuid.uuid4())[:8]
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_name = "".join(c for c in subject_name if c.isalnum() or c in "_-")
    filename  = f"{safe_name}_{timestamp}.png"

    folder = os.path.join("static", "qr_codes")
    os.makedirs(folder, exist_ok=True)

    # Remove old QR codes for this subject
    for old_file in glob.glob(os.path.join(folder, f"{safe_name}_*.png")):
        try:
            os.remove(old_file)
        except OSError:
            pass

    content = f"{base_url}/scan?subject_id={subject_id}&session_id={session_id}"
    img = qrcode.make(content)
    img.save(os.path.join(folder, filename))

    return session_id, filename


# ══════════════════════════════════════════════════════════════
# DEVICE TOKEN LIFECYCLE
# ══════════════════════════════════════════════════════════════

def issue_device_token(session_id):
    """
    Called once when a device hits /scan.
    Creates a one-time token, persists it to session_tokens as 'issued'.
    Returns the token string, or None if the DB write failed.
    """
    token = secrets.token_hex(16)
    ok = db_issue_token(session_id, token)
    return token if ok else None


def consume_device_token(session_id, device_token):
    """
    Atomically validates and consumes a device token on form submission.
    Returns (True, None) on success.
    Returns (False, reason) on failure — reason is one of:
        'invalid_session', 'unrecognized_token', 'already_used'
    """
    return db_consume_token(session_id, device_token)


# ══════════════════════════════════════════════════════════════
# TOKEN CLEANUP
# FIX: Delegate to database_logic.cleanup_expired_tokens() which uses
# the expires_at column (24-hour window) instead of a stale 7-day
# created_at window that kept tokens alive far longer than intended.
# ══════════════════════════════════════════════════════════════

def cleanup_old_tokens():
    """Delete expired session tokens. Safe to call on every server start."""
    cleanup_expired_tokens()


# ══════════════════════════════════════════════════════════════
# LEGACY SHIMS  (kept for backward compatibility)
# ══════════════════════════════════════════════════════════════

def generate_device_token():
    """Legacy shim. Returns a raw token not yet tied to any session."""
    return secrets.token_hex(16)


def is_device_allowed(session_id, device_token):
    """
    Legacy shim. True = token has NOT been used yet.
    Checks DB without consuming the token.
    """
    import sqlite3
    DB = os.environ.get("DB_PATH", "attendance.db")
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT status FROM session_tokens WHERE session_id=? AND device_token=?",
        (session_id, device_token)
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return True
    return row[0] == "issued"


def register_device(session_id, device_token):
    """Legacy shim. Marks the token as 'used' in the DB."""
    db_consume_token(session_id, device_token)