import os
import io
import numpy as np
import pydicom
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
from typing import Optional
from backend.services.storage_service import StorageService
from backend.services.dicom_service import DicomService
from backend.models.schemas import InstanceSummary, DicomMetadataResponse

router = APIRouter(prefix="/api/instances", tags=["Instances"])
storage = StorageService()

@router.get("/{instance_uid}", response_model=InstanceSummary)
def get_instance_detail(instance_uid: str):
    instance = storage.get_instance(instance_uid)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Coupe DICOM {instance_uid} non trouvée")
    return instance

@router.get("/{instance_uid}/image")
def get_instance_rendered_image(
    instance_uid: str,
    wc: Optional[float] = Query(None, description="Window Center personnalisé"),
    ww: Optional[float] = Query(None, description="Window Width personnalisé"),
    invert: bool = Query(False, description="Inversion des niveaux de gris")
):
    instance = storage.get_instance(instance_uid)
    if not instance or not instance.get("file_path"):
        raise HTTPException(status_code=404, detail=f"Coupe {instance_uid} introuvable")

    file_path = instance["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier DICOM manquant sur le disque")

    try:
        png_bytes = DicomService.render_slice_png(
            file_path=file_path,
            custom_wc=wc,
            custom_ww=ww,
            invert=invert
        )
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Window-Center": str(wc or instance.get("window_center") or ""),
                "X-Window-Width": str(ww or instance.get("window_width") or "")
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de rendu de l'image DICOM: {str(e)}")

@router.get("/{instance_uid}/image_denoised")
def get_instance_denoised_image(
    instance_uid: str,
    wc: Optional[float] = Query(None, description="Window Center personnalisé"),
    ww: Optional[float] = Query(None, description="Window Width personnalisé"),
    invert: bool = Query(False, description="Inversion des niveaux de gris")
):
    instance = storage.get_instance(instance_uid)
    if not instance or not instance.get("file_path"):
        raise HTTPException(status_code=404, detail=f"Coupe {instance_uid} introuvable")

    file_path = instance["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier DICOM manquant sur le disque")

    try:
        from backend.services.denoising_service import DenoisingService
        png_bytes = DenoisingService.render_denoised_slice_png(
            file_path=file_path,
            custom_wc=wc,
            custom_ww=ww,
            invert=invert
        )
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Denoised-Model": "ResNet 2D Denoiser (Fold 2 / MLflow)",
                "X-Window-Center": str(wc or instance.get("window_center") or ""),
                "X-Window-Width": str(ww or instance.get("window_width") or "")
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de débruitage de l'image: {str(e)}")

@router.get("/{instance_uid}/metrics")
def get_instance_restoration_metrics(instance_uid: str):
    instance = storage.get_instance(instance_uid)
    if not instance or not instance.get("file_path"):
        raise HTTPException(status_code=404, detail="Coupe non trouvée")

    file_path = instance["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    try:
        from backend.services.denoising_service import DenoisingService
        return DenoisingService.calculate_slice_metrics(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de calcul des métriques: {e}")

@router.get("/{instance_uid}/dicom")
def get_raw_dicom(instance_uid: str):
    instance = storage.get_instance(instance_uid)
    if not instance or not instance.get("file_path"):
        raise HTTPException(status_code=404, detail="Coupe non trouvée")

    file_path = instance["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return FileResponse(
        path=file_path,
        media_type="application/dicom",
        filename=f"{instance_uid}.dcm"
    )

@router.get("/{instance_uid}/dicom_denoised")
def get_denoised_dicom_file(instance_uid: str):
    instance = storage.get_instance(instance_uid)
    if not instance or not instance.get("file_path"):
        raise HTTPException(status_code=404, detail="Coupe non trouvée")

    file_path = instance["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    try:
        from backend.services.denoising_service import DenoisingService
        ds = pydicom.dcmread(file_path, force=True)
        raw_pixels = ds.pixel_array.astype(np.float32)
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        if slope != 1.0 or intercept != 0.0:
            raw_pixels = raw_pixels * slope + intercept
        denoised_pixels = DenoisingService.denoise_pixel_array(raw_pixels)
        dcm_bytes = DicomService.create_denoised_dicom_bytes(file_path, denoised_pixels)
        return Response(
            content=dcm_bytes,
            media_type="application/dicom",
            headers={"Content-Disposition": f'attachment; filename="DENOISED_{instance_uid}.dcm"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur export DICOM débruité: {e}")

@router.get("/{instance_uid}/metadata", response_model=DicomMetadataResponse)
def get_instance_metadata(instance_uid: str):
    instance = storage.get_instance(instance_uid)
    if not instance or not instance.get("file_path"):
        raise HTTPException(status_code=404, detail="Coupe non trouvée")

    file_path = instance["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier DICOM introuvable")

    try:
        parsed = DicomService.parse_dicom(file_path)
        all_tags = DicomService.get_full_tags(file_path)

        p = parsed["patient"]
        s = parsed["study"]
        ser = parsed["series"]
        inst = parsed["instance"]

        return DicomMetadataResponse(
            instance_id=instance_uid,
            patient_id=p["patient_id"],
            patient_name=p["patient_name"],
            study_description=s["study_description"],
            series_description=ser["series_description"],
            modality=ser["modality"],
            body_part=ser["body_part"],
            study_date=s["study_date"],
            manufacturer=ser["manufacturer"],
            magnetic_field_strength=ser["magnetic_field_strength"],
            repetition_time=ser["repetition_time"],
            echo_time=ser["echo_time"],
            flip_angle=inst.get("flip_angle"),
            slice_thickness=inst["slice_thickness"],
            pixel_spacing=inst["pixel_spacing"],
            rows=inst["rows"],
            columns=inst["columns"],
            window_center=inst["window_center"],
            window_width=inst["window_width"],
            all_tags=all_tags
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'extraction des métadonnées: {str(e)}")
