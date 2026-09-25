from fastapi import APIRouter, HTTPException
from typing import List
from backend.services.storage_service import StorageService
from backend.models.schemas import SeriesSummary, InstanceSummary

router = APIRouter(prefix="/api/series", tags=["Series"])
storage = StorageService()

@router.get("/{series_uid}", response_model=SeriesSummary)
def get_series_detail(series_uid: str):
    series = storage.get_series(series_uid, include_instances=True)
    if not series:
        raise HTTPException(status_code=404, detail=f"Série {series_uid} non trouvée")
    return series

@router.get("/{series_uid}/instances", response_model=List[InstanceSummary])
def get_series_instances(series_uid: str):
    instances = storage.get_instances_for_series(series_uid)
    return instances

@router.get("/{series_uid}/export_denoised")
def export_series_denoised_zip(series_uid: str):
    series = storage.get_series(series_uid, include_instances=True)
    if not series or not series.get("instances"):
        raise HTTPException(status_code=404, detail=f"Série {series_uid} non trouvée")

    import io
    import zipfile
    import pydicom
    import numpy as np
    from fastapi.responses import Response
    from backend.services.dicom_service import DicomService
    from backend.services.denoising_service import DenoisingService

    instances = series["instances"]
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, inst in enumerate(instances, 1):
            file_path = inst.get("file_path")
            if file_path and os.path.exists(file_path):
                ds = pydicom.dcmread(file_path, force=True)
                raw_pixels = ds.pixel_array.astype(np.float32)
                slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
                intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
                if slope != 1.0 or intercept != 0.0:
                    raw_pixels = raw_pixels * slope + intercept
                denoised_pixels = DenoisingService.denoise_pixel_array(raw_pixels)
                dcm_bytes = DicomService.create_denoised_dicom_bytes(file_path, denoised_pixels)
                inst_name = f"DENOISED_{series['series_description'][:20].replace(' ', '_')}_{idx:03d}.dcm"
                zf.writestr(inst_name, dcm_bytes)

    zip_buffer.seek(0)
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in series.get("series_description", "IRM"))
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="DENOISED_{safe_title}.zip"'}
    )
