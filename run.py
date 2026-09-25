import os
import sys
import socket
import uvicorn

# Force UTF-8 on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 72)
    print("  [OK] IRM DENOISING VIEWER - SERVEUR ACTIF (ACCES SECURISE)")
    print("=" * 72)
    print(f"  [URL Locale]  Sur votre PC :                 http://127.0.0.1:8000")
    print(f"  [URL Reseau]  Sur le PC du Medecin (Wi-Fi) : http://{local_ip}:8000")
    print(f"  [DOCS API]    Documentation Swagger :        http://127.0.0.1:8000/docs")
    print("=" * 72)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
