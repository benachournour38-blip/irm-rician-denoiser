import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import FRONTEND_DIR, DB_PATH
from backend.routers import (
    patients_router,
    studies_router,
    series_router,
    instances_router,
    upload_router,
    denoising_router,
    auth_router
)
from backend.services.storage_service import StorageService

app = FastAPI(
    title="IRM Denoising Viewer - API Radiologue",
    description="Backend médical pour l'organisation, la visualisation et la comparaison d'IRM lombaires DICOM",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(studies_router)
app.include_router(series_router)
app.include_router(instances_router)
app.include_router(upload_router)
app.include_router(denoising_router)

@app.on_event("startup")
def on_startup():
    storage = StorageService()
    # Check if there are any patients in the database
    patients = storage.get_patients()
    if not patients:
        print("💡 Base de données vide. Initialisation avec les études de démonstration IRM lombaire...")
        from backend.sample_generator import generate_sample_lumbar_studies
        generate_sample_lumbar_studies()

    try:
        from backend.services.denoising_service import DenoisingService
        print("⚡ Préchauffage du modèle IA ResNet 2D...")
        DenoisingService.get_model()
        print("✅ Modèle IA ResNet 2D préchauffé et prêt en mémoire.")
    except Exception as e:
        print(f"⚠️ Erreur préchauffage IA: {e}")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "IRM Lumbar DICOM Viewer Backend",
        "version": "1.0.0",
        "ai_integration_target": "ResNet 2D Denoiser via MLflow"
    }

@app.get("/favicon.ico")
def serve_favicon():
    fav_path = FRONTEND_DIR / "assets" / "favicon.svg"
    if fav_path.exists():
        return FileResponse(str(fav_path), media_type="image/svg+xml")
    return FileResponse(str(FRONTEND_DIR / "index.html"))

# Mount static files for frontend
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_frontend_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend en cours d'initialisation..."}
