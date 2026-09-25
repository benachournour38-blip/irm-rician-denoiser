import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
PATIENTS_STORAGE_DIR = STORAGE_DIR / "patients"
TEMP_UPLOADS_DIR = STORAGE_DIR / "temp_uploads"
DB_PATH = STORAGE_DIR / "dicom_index.db"
FRONTEND_DIR = BASE_DIR / "frontend"

# Ensure directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
PATIENTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed formats
ALLOWED_DICOM_EXTENSIONS = {".dcm", ".dicom", ".ima", ""}
ALLOWED_ARCHIVE_EXTENSIONS = {".zip"}

# ====================================================================
# ACCÈS SÉCURISÉ & MOTS DE PASSE (Personnalisables)
# ====================================================================
# Mot de passe pour le médecin / radiologue autorisé
AUTH_PASSWORD = os.getenv("MRI_ACCESS_PASSWORD", "Radiologie2026!")

# Mot de passe administrateur (pour vous-même)
AUTH_ADMIN_PASSWORD = os.getenv("MRI_ADMIN_PASSWORD", "AdminRad2026!")

# Clé secrète de signature des sessions sécurisées
AUTH_SECRET_KEY = os.getenv("MRI_AUTH_SECRET", "mri-lumbar-denoiser-jwt-secret-key-2026-secure")
AUTH_TOKEN_EXPIRY_HOURS = 72  # 3 jours de validité de session
