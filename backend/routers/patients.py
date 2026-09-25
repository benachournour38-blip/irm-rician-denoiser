from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from backend.services.storage_service import StorageService
from backend.models.schemas import PatientSummary, StudySummary

router = APIRouter(prefix="/api/patients", tags=["Patients"])
storage = StorageService()

@router.get("", response_model=List[PatientSummary])
def get_patients(q: Optional[str] = Query(None, description="Recherche par nom ou ID patient")):
    return storage.get_patients(query=q or "")

@router.get("/{patient_id}", response_model=PatientSummary)
def get_patient(patient_id: str):
    patient = storage.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} non trouvé")
    return patient

@router.get("/{patient_id}/studies", response_model=List[StudySummary])
def get_patient_studies(patient_id: str):
    patient = storage.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} non trouvé")
    return storage.get_studies_for_patient(patient_id)

@router.delete("/{patient_id}")
def delete_patient(patient_id: str):
    patient = storage.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} non trouvé")
    storage.delete_patient(patient_id)
    return {"success": True, "message": f"Patient {patient_id} supprimé avec succès"}
