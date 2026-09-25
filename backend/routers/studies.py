from fastapi import APIRouter, HTTPException
from typing import List
from backend.services.storage_service import StorageService
from backend.models.schemas import SeriesSummary

router = APIRouter(prefix="/api/studies", tags=["Studies"])
storage = StorageService()

@router.get("/{study_uid}/series", response_model=List[SeriesSummary])
def get_study_series(study_uid: str):
    return storage.get_series_for_study(study_uid)

@router.delete("/{study_uid}")
def delete_study(study_uid: str):
    storage.delete_study(study_uid)
    return {"success": True, "message": f"Examen {study_uid} supprimé avec succès"}
