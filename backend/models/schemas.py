from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class InstanceSummary(BaseModel):
    id: str
    instance_uid: str
    instance_number: Optional[int] = 1
    slice_location: Optional[float] = None
    slice_thickness: Optional[float] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    window_center: Optional[float] = None
    window_width: Optional[float] = None
    rescale_intercept: Optional[float] = 0.0
    rescale_slope: Optional[float] = 1.0
    image_position: Optional[List[float]] = None
    image_orientation: Optional[List[float]] = None
    pixel_spacing: Optional[List[float]] = None
    repetition_time: Optional[float] = None
    echo_time: Optional[float] = None
    inversion_time: Optional[float] = None
    magnetic_field_strength: Optional[float] = None

class SeriesSummary(BaseModel):
    id: str
    series_instance_uid: str
    series_number: Optional[int] = 1
    series_description: str = "Série Sans Titre"
    modality: str = "MR"
    body_part: Optional[str] = "LUMBAR SPINE"
    protocol_name: Optional[str] = None
    slice_count: int = 0
    slice_thickness: Optional[float] = None
    pixel_spacing: Optional[List[float]] = None
    repetition_time: Optional[float] = None
    echo_time: Optional[float] = None
    magnetic_field_strength: Optional[float] = None
    manufacturer: Optional[str] = None
    instances: Optional[List[InstanceSummary]] = None

class StudySummary(BaseModel):
    id: str
    study_instance_uid: str
    study_date: Optional[str] = None
    study_time: Optional[str] = None
    study_description: str = "IRM Lombaire"
    accession_number: Optional[str] = None
    series_count: int = 0
    series: Optional[List[SeriesSummary]] = None

class PatientSummary(BaseModel):
    id: str
    patient_id: str
    patient_name: str = "Anonyme"
    patient_sex: Optional[str] = None
    patient_birth_date: Optional[str] = None
    studies_count: int = 0
    studies: Optional[List[StudySummary]] = None

class DicomTagDetail(BaseModel):
    tag: str
    vr: str
    name: str
    value: str

class DicomMetadataResponse(BaseModel):
    instance_id: str
    patient_id: str
    patient_name: str
    study_description: str
    series_description: str
    modality: str
    body_part: str
    study_date: Optional[str] = None
    manufacturer: Optional[str] = None
    magnetic_field_strength: Optional[float] = None
    repetition_time: Optional[float] = None
    echo_time: Optional[float] = None
    flip_angle: Optional[float] = None
    slice_thickness: Optional[float] = None
    pixel_spacing: Optional[List[float]] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    window_center: Optional[float] = None
    window_width: Optional[float] = None
    all_tags: List[DicomTagDetail] = Field(default_factory=list)

class UploadResponse(BaseModel):
    success: bool
    message: str
    imported_patients_count: int = 0
    imported_studies_count: int = 0
    imported_series_count: int = 0
    imported_instances_count: int = 0
    errors: List[str] = Field(default_factory=list)

class DenoiseResponse(BaseModel):
    status: str
    message: str
    series_id: str
    target_architecture: str = "MLflow / ResNet 2D Denoiser"
    details: Dict[str, Any] = Field(default_factory=dict)
