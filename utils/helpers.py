import io
import re
import qrcode
from typing import Dict, Optional
from datetime import datetime

def generate_upi_qr(upi_id: str, payee_name: str, amount: Optional[int] = None) -> io.BytesIO:
    """Generate in-memory UPI QR Code image buffer"""
    params = f"pa={upi_id}&pn={payee_name}&cu=INR"
    if amount and amount > 0:
        params += f"&am={amount}"
    upi_url = f"upi://pay?{params}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def format_status_badge(status: str) -> str:
    s = (status or "").lower()
    if s in ["running", "up", "active"]:
        return "🟢 Running (24/7)"
    elif s in ["stopped", "crashed", "down", "idle"]:
        return "🔴 Stopped"
    elif s in ["building", "deploying"]:
        return "🔄 Building / Deploying"
    return f"⚪ {status.capitalize()}"

def parse_config_vars_text(text: str) -> Dict[str, str]:
    """Parse text with lines of KEY=VALUE or KEY = VALUE"""
    result = {}
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            parts = line.split("=", 1)
            key = parts[0].strip().upper()
            val = parts[1].strip()
            # remove surrounding quotes if any
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if key:
                result[key] = val
    return result

def github_repo_to_tarball(url: str) -> Optional[str]:
    """Convert standard GitHub repo URL to a downloadable tarball URL"""
    url = url.strip().rstrip("/")
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
    if not match:
        return None
    user, repo = match.group(1), match.group(2)
    # Remove .git suffix if present
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"https://codeload.github.com/{user}/{repo}/tar.gz/main"
