import qrcode, uuid, os
from datetime import datetime

def generate_qr(subject):
    session_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    content = f"http://192.168.64.94:5000/scan?subject=AI&session_id=abc123"
    filename = f"{subject}_{timestamp}.png"
    
    folder = os.path.join("static", "qr_codes")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)

    img = qrcode.make(content)
    img.save(path)
    return session_id, subject, filename
