from fastapi import APIRouter, HTTPException
from backend.services.denoising_service import DenoisingService
from backend.services.storage_service import StorageService

router = APIRouter(prefix="/api", tags=["Denoising AI"])
storage = StorageService()

@router.get("/denoise/status")
def get_denoising_service_status():
    """Vérifie la disponibilité et les métadonnées du modèle ResNet 2D Denoiser actif sur GPU CUDA."""
    return DenoisingService.get_model_info()

@router.post("/series/{series_uid}/denoise")
def trigger_series_denoising(series_uid: str):
    """
    Déclenche le pré-calcul de débruitage sur GPU pour toutes les coupes d'une série.
    """
    instances = storage.get_instances_for_series(series_uid)
    if not instances:
        raise HTTPException(status_code=404, detail=f"Série {series_uid} non trouvée ou vide")

    processed = 0
    start_time = None
    import time
    start_time = time.time()

    for inst in instances:
        file_path = inst.get("file_path")
        if file_path:
            try:
                # Pré-rendu et mise en cache GPU
                _ = DenoisingService.render_denoised_slice_png(file_path)
                processed += 1
            except Exception as e:
                print(f"Erreur sur {file_path}: {e}")

    elapsed = time.time() - start_time
    return {
        "status": "completed",
        "message": f"Débruitage terminé sur GPU CUDA : {processed}/{len(instances)} coupes traitées en {elapsed:.2f}s.",
        "series_id": series_uid,
        "processed_slices": processed,
        "elapsed_seconds": round(elapsed, 3),
        "target_architecture": "MLflow / ResNet 2D Denoiser (Fold 2)"
    }
