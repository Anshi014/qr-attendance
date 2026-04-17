import qrcode
import uuid
import os
import secrets
from datetime import datetime

# In-memory store: session_id -> set of used device tokens
# Resets on server restart — use Redis/DB for production
session_device_store = {}

def generate_qr(subject_id, subject_name, base_url="https://qr-attendance-bgdn.onrender.com"):
    """
    Generate a QR code for a subject session.
    URL format: /scan?subject_id=5&session_id=abc12345
    """
    session_id = str(uuid.uuid4())[:8]
    timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Clean subject name for filename
    safe_name = "".join(c for c in subject_name if c.isalnum() or c in "_-")
    filename  = f"{safe_name}_{timestamp}.png"

    content = f"{base_url}/scan?subject_id={subject_id}&session_id={session_id}"

    folder = os.path.join("static", "qr_codes")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)

    img = qrcode.make(content)
    img.save(path)

    # Initialize empty device set for this session
    session_device_store[session_id] = set()

    return session_id, filename

def generate_device_token():
    """Server-side one-time device token — cannot be spoofed."""
    return secrets.token_hex(16)

def is_device_allowed(session_id, device_token):
    """Return True if device token has NOT been used for this session yet."""
    if session_id not in session_device_store:
        session_device_store[session_id] = set()
    return device_token not in session_device_store[session_id]

def register_device(session_id, device_token):
    """Mark device token as used for this session."""
    if session_id not in session_device_store:
        session_device_store[session_id] = set()
    session_device_store[session_id].add(device_token)