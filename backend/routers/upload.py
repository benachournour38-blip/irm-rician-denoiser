import os
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.services.storage_service import StorageService
from backend.models.schemas import UploadResponse
from backend.config import TEMP_UPLOADS_DIR

router = APIRouter(prefix="/api/dicom", tags=["Upload"])
storage = StorageService()

@router.post("/upload", response_model=UploadResponse)
async def upload_dicom_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni pour l'import")

    imported_patients = set()
    imported_studies = set()
    imported_series = set()
    imported_instances_count = 0
    errors = []

    temp_dir = Path(tempfile.mkdtemp(dir=TEMP_UPLOADS_DIR))

    try:
        # Save all uploaded files to temp directory
        for file in files:
            file_path = temp_dir / file.filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # If it's a zip file, extract it
            if file.filename.lower().endswith(".zip") or zipfile.is_zipfile(file_path):
                extract_target = temp_dir / f"extracted_{file.filename}"
                extract_target.mkdir(parents=True, exist_ok=True)
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_target)
                except Exception as ze:
                    errors.append(f"Erreur d'extraction ZIP {file.filename}: {str(ze)}")

        # Recursively search for all files in temp_dir
        all_candidate_files = []
        for root, _, filenames in os.walk(temp_dir):
            for fname in filenames:
                candidate = Path(root) / fname
                if not candidate.name.lower().endswith(".zip") and candidate.is_file():
                    all_candidate_files.append(candidate)

        is_single_file_test = (len(all_candidate_files) == 1)

        for candidate in all_candidate_files:
            try:
                meta = storage.index_dicom_file(
                    str(candidate),
                    move_file=False,
                    is_single_file_test=is_single_file_test,
                    test_name=candidate.name if is_single_file_test else None
                )
                imported_patients.add(meta["patient"]["patient_id"])
                imported_studies.add(meta["study"]["study_instance_uid"])
                imported_series.add(meta["series"]["series_instance_uid"])
                imported_instances_count += 1
            except Exception as e:
                # Some files might not be DICOM (e.g. .DS_Store, readme, etc.), record error only if relevant
                if candidate.suffix.lower() in [".dcm", ".ima", ".dicom"] or "dicom" in candidate.name.lower():
                    errors.append(f"{candidate.name}: {str(e)}")

        if imported_instances_count == 0 and not errors:
            errors.append("Aucun fichier DICOM valide n'a été détecté dans les fichiers téléversés.")

        # Consolidate any fragmented sequences into unified multi-slice series for patient folders
        if not is_single_file_test:
            for st_uid in imported_studies:
                try:
                    storage.consolidate_study_series(st_uid)
                except Exception as ce:
                    print(f"Erreur consolidation étude {st_uid}: {ce}")

    finally:
        # Cleanup temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)

    success = imported_instances_count > 0
    message = (
        f"Import réussi : {imported_instances_count} coupe(s) DICOM importée(s) pour {len(imported_patients)} patient(s)."
        if success else "Échec de l'import : aucun fichier DICOM valide trouvé."
    )

    return UploadResponse(
        success=success,
        message=message,
        imported_patients_count=len(imported_patients),
        imported_studies_count=len(imported_studies),
        imported_series_count=len(imported_series),
        imported_instances_count=imported_instances_count,
        errors=errors
    )
