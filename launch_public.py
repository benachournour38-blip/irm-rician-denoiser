import os
import sys
import time
import re
import socket
import threading
import subprocess

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
BIN_DIR = os.path.join(BASE_DIR, "bin")

NGROK_EXE = os.path.join(BIN_DIR, "ngrok.exe")
NGROK_STATIC_DOMAIN = "lunchroom-briar-tacking.ngrok-free.dev"
NGROK_LOG_FILE = os.path.join(STORAGE_DIR, "ngrok.log")

CLOUDFLARED_EXE = os.path.join(BIN_DIR, "cloudflared.exe")
TUNNEL_LOG_FILE = os.path.join(STORAGE_DIR, "cloudflared.log")
PUBLIC_LINK_FILE = os.path.join(STORAGE_DIR, "PUBLIC_LINK.txt")

os.makedirs(STORAGE_DIR, exist_ok=True)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_backend_server():
    """Démarre le serveur FastAPI."""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

def start_permanent_ngrok_tunnel():
    """Démarre le tunnel permanent ngrok avec domaine fixe réservé."""
    if not os.path.exists(NGROK_EXE):
        return None, None

    if os.path.exists(NGROK_LOG_FILE):
        try:
            os.remove(NGROK_LOG_FILE)
        except Exception:
            pass

    proc = subprocess.Popen(
        [
            NGROK_EXE, "http", "8000",
            "--url", f"https://{NGROK_STATIC_DOMAIN}",
            "--log", NGROK_LOG_FILE,
            "--log-format", "json"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    public_url = None
    for _ in range(40):
        time.sleep(0.3)
        if os.path.exists(NGROK_LOG_FILE):
            try:
                with open(NGROK_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if NGROK_STATIC_DOMAIN in content or "client session established" in content:
                        public_url = f"https://{NGROK_STATIC_DOMAIN}"
                        break
            except Exception:
                pass

    return proc, public_url

def start_cloudflare_tunnel():
    """Démarre le tunnel Cloudflare de secours si besoin."""
    if not os.path.exists(CLOUDFLARED_EXE):
        return None, None

    if os.path.exists(TUNNEL_LOG_FILE):
        try:
            os.remove(TUNNEL_LOG_FILE)
        except Exception:
            pass

    proc = subprocess.Popen(
        [
            CLOUDFLARED_EXE, "tunnel",
            "--url", "http://127.0.0.1:8000",
            "--logfile", TUNNEL_LOG_FILE,
            "--no-autoupdate"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    public_url = None
    for _ in range(50):
        time.sleep(0.3)
        if os.path.exists(TUNNEL_LOG_FILE):
            try:
                with open(TUNNEL_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', content)
                    if match:
                        public_url = match.group(1)
                        break
            except Exception:
                pass

    return proc, public_url

if __name__ == "__main__":
    local_ip = get_local_ip()

    print("=" * 76)
    print("  🏥 IRM DENOISING VIEWER — STATION MÉDICALE SÉCURISÉE")
    print("=" * 76)
    print("  [1/2] Démarrage du serveur IA GPU (CUDA RTX 5060)...")

    # Start FastAPI server in background thread
    server_thread = threading.Thread(target=start_backend_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    print("  [2/2] Activation du tunnel permanent à domaine fixe HTTPS...")
    tunnel_proc, public_url = start_permanent_ngrok_tunnel()

    if not public_url:
        print("  [Secours] Démarrage du tunnel Cloudflare...")
        tunnel_proc, public_url = start_cloudflare_tunnel()

    print("\n" + "=" * 76)
    print("  🚀 STATION EN LIGNE ET PRÊTE POUR LE MÉDECIN")
    print("=" * 76)
    if public_url:
        print(f"\n  🌍 LIEN PUBLIC FIXE DÉFINITIF (NE CHANGE JAMAIS) :")
        print(f"     👉 {public_url}")
        print(f"\n  💻 LIEN LOCAL (VOTRE ORDINATEUR) :")
        print(f"     👉 http://127.0.0.1:8000")
        print(f"\n  📡 LIEN RÉSEAU LOCAL (MÊME WI-FI) :")
        print(f"     👉 http://{local_ip}:8000")
        print(f"\n  🔑 MOT DE PASSE MÉDECIN :")
        print(f"     👉 Radiologie2026!")

        with open(PUBLIC_LINK_FILE, "w", encoding="utf-8") as f:
            f.write(f"LIEN PUBLIC PERMANENT : {public_url}\nMOT DE PASSE : Radiologie2026!\nDOMAINE FIXE : {NGROK_STATIC_DOMAIN}\n")
    else:
        print("  ⚠️ Le tunnel public n'a pas pu être initialisé. Utilisation en réseau local :")
        print(f"  👉 http://{local_ip}:8000")
    print("=" * 76)
    print("  💡 Laissez cette fenêtre ouverte tant que le médecin utilise l'application.")
    print("  Appuyez sur Ctrl + C pour arrêter le serveur.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt de la station...")
        if tunnel_proc:
            tunnel_proc.terminate()
        sys.exit(0)
