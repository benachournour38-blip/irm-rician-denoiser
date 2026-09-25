import os
import io
import math
from typing import Dict, Any, List, Optional, Tuple
import pydicom
from pydicom.dataset import Dataset
from pydicom.tag import Tag
import numpy as np
from PIL import Image

class DicomService:
    @staticmethod
    def parse_dicom(file_path: str) -> Dict[str, Any]:
        """Reads a DICOM file and extracts normalized medical metadata."""
        try:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        except Exception as e:
            raise ValueError(f"Erreur de lecture DICOM pour {file_path}: {e}")

        # Basic verification: ensure it has standard DICOM elements or image headers
        sop_instance_uid = str(getattr(ds, "SOPInstanceUID", os.path.splitext(os.path.basename(file_path))[0]))
        series_instance_uid = str(getattr(ds, "SeriesInstanceUID", "1.2.826.0.1.3680043.2.1125.1"))
        study_instance_uid = str(getattr(ds, "StudyInstanceUID", "1.2.826.0.1.3680043.2.1125.0"))
        patient_id = str(getattr(ds, "PatientID", "ANON_PATIENT")).strip() or "ANON_PATIENT"

        # Patient Name cleaning
        raw_patient_name = getattr(ds, "PatientName", "Patient Anonymisé")
        patient_name = str(raw_patient_name).replace("^", " ").strip() if raw_patient_name else "Patient Anonymisé"

        # Modality and Descriptions
        modality = str(getattr(ds, "Modality", "MR")).strip()
        body_part = str(getattr(ds, "BodyPartExamined", "LUMBAR SPINE")).strip() or "LUMBAR SPINE"
        study_desc = str(getattr(ds, "StudyDescription", "IRM Rachis Lombaire")).strip() or "IRM Rachis Lombaire"
        series_desc = str(getattr(ds, "SeriesDescription", "Série IRM Lombaire")).strip() or "Série IRM Lombaire"
        protocol_name = str(getattr(ds, "ProtocolName", "")).strip()

        # Dates & Times
        study_date = str(getattr(ds, "StudyDate", "")).strip()
        study_time = str(getattr(ds, "StudyTime", "")).strip()
        patient_birth_date = str(getattr(ds, "PatientBirthDate", "")).strip()
        patient_sex = str(getattr(ds, "PatientSex", "O")).strip()

        # Technical MRI parameters
        def safe_float(val, default=None):
            if val is None or val == "":
                return default
            try:
                if isinstance(val, (list, pydicom.multival.MultiValue)):
                    return float(val[0])
                return float(val)
            except Exception:
                return default

        def safe_int(val, default=None):
            if val is None or val == "":
                return default
            try:
                if isinstance(val, (list, pydicom.multival.MultiValue)):
                    return int(val[0])
                return int(val)
            except Exception:
                return default

        instance_num = safe_int(getattr(ds, "InstanceNumber", None), 1)
        slice_loc = safe_float(getattr(ds, "SliceLocation", None))
        slice_thick = safe_float(getattr(ds, "SliceThickness", None))
        rows = safe_int(getattr(ds, "Rows", None))
        cols = safe_int(getattr(ds, "Columns", None))

        tr = safe_float(getattr(ds, "RepetitionTime", None))
        te = safe_float(getattr(ds, "EchoTime", None))
        ti = safe_float(getattr(ds, "InversionTime", None))
        flip_angle = safe_float(getattr(ds, "FlipAngle", None))
        b_field = safe_float(getattr(ds, "MagneticFieldStrength", None))
        manufacturer = str(getattr(ds, "Manufacturer", "Fabricant IRM")).strip()

        wc = safe_float(getattr(ds, "WindowCenter", None))
        ww = safe_float(getattr(ds, "WindowWidth", None))
        rescale_intercept = safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
        rescale_slope = safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)

        # Image Position and Orientation
        img_pos = None
        if hasattr(ds, "ImagePositionPatient"):
            try:
                img_pos = [float(x) for x in ds.ImagePositionPatient]
                if slice_loc is None and len(img_pos) >= 3:
                    slice_loc = img_pos[2]
            except Exception:
                pass

        img_ori = None
        if hasattr(ds, "ImageOrientationPatient"):
            try:
                img_ori = [float(x) for x in ds.ImageOrientationPatient]
            except Exception:
                pass

        pixel_spacing = None
        if hasattr(ds, "PixelSpacing"):
            try:
                pixel_spacing = [float(x) for x in ds.PixelSpacing]
            except Exception:
                pass

        return {
            "patient": {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "patient_sex": patient_sex,
                "patient_birth_date": patient_birth_date,
            },
            "study": {
                "study_instance_uid": study_instance_uid,
                "study_date": study_date,
                "study_time": study_time,
                "study_description": study_desc,
                "accession_number": str(getattr(ds, "AccessionNumber", "")).strip(),
            },
            "series": {
                "series_instance_uid": series_instance_uid,
                "series_number": safe_int(getattr(ds, "SeriesNumber", 1), 1),
                "series_description": series_desc,
                "modality": modality,
                "body_part": body_part,
                "protocol_name": protocol_name,
                "slice_thickness": slice_thick,
                "pixel_spacing": pixel_spacing,
                "repetition_time": tr,
                "echo_time": te,
                "inversion_time": ti,
                "magnetic_field_strength": b_field,
                "manufacturer": manufacturer,
            },
            "instance": {
                "instance_uid": sop_instance_uid,
                "instance_number": instance_num,
                "slice_location": slice_loc,
                "slice_thickness": slice_thick,
                "rows": rows,
                "columns": cols,
                "window_center": wc,
                "window_width": ww,
                "rescale_intercept": rescale_intercept,
                "rescale_slope": rescale_slope,
                "image_position": img_pos,
                "image_orientation": img_ori,
                "pixel_spacing": pixel_spacing,
                "repetition_time": tr,
                "echo_time": te,
                "inversion_time": ti,
                "magnetic_field_strength": b_field,
            }
        }

    @staticmethod
    def render_slice_png(file_path: str, custom_wc: Optional[float] = None, custom_ww: Optional[float] = None, invert: bool = False) -> bytes:
        """Converts DICOM raw pixel data into an optimized high-contrast grayscale PNG byte buffer."""
        ds = pydicom.dcmread(file_path, force=True)
        pixel_array = ds.pixel_array.astype(np.float32)

        # Apply Rescale Slope & Intercept if present
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        if slope != 1.0 or intercept != 0.0:
            pixel_array = pixel_array * slope + intercept

        # Handle Photometric Interpretation
        photometric = getattr(ds, "PhotometricInterpretation", "MONOCHROME2")
        is_monochrome1 = (photometric == "MONOCHROME1")

        # Determine Window Center (WC) and Window Width (WW)
        wc = custom_wc
        ww = custom_ww

        if wc is None or ww is None:
            dicom_wc = getattr(ds, "WindowCenter", None)
            dicom_ww = getattr(ds, "WindowWidth", None)
            if isinstance(dicom_wc, (list, pydicom.multival.MultiValue)):
                dicom_wc = dicom_wc[0]
            if isinstance(dicom_ww, (list, pydicom.multival.MultiValue)):
                dicom_ww = dicom_ww[0]

            if dicom_wc is not None and dicom_ww is not None and float(dicom_ww) > 0:
                wc = float(dicom_wc)
                ww = float(dicom_ww)
            else:
                # Auto-calculate optimal percentile Window/Level for MRI
                p_low, p_high = np.percentile(pixel_array, (1.0, 99.5))
                if p_high <= p_low:
                    p_high = p_low + 1.0
                ww = p_high - p_low
                wc = p_low + ww / 2.0

        if ww <= 0:
            ww = 1.0

        # Standard DICOM linear VOI LUT transformation:
        # y = ((x - (c - 0.5)) / (w - 1) + 0.5) * (ymax - ymin) + ymin
        min_val = wc - 0.5 - (ww - 1) / 2.0
        max_val = wc - 0.5 + (ww - 1) / 2.0

        normalized = np.clip((pixel_array - min_val) / (max_val - min_val), 0.0, 1.0)
        scaled_8bit = (normalized * 255.0).astype(np.uint8)

        # Invert if MONOCHROME1 or user requested invert
        if is_monochrome1 ^ invert:
            scaled_8bit = 255 - scaled_8bit

        # Convert to PNG buffer
        img = Image.fromarray(scaled_8bit, mode='L')
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    @staticmethod
    def create_denoised_dicom_bytes(file_path: str, denoised_pixels: np.ndarray) -> bytes:
        """Creates a standard compliant DICOM file containing the denoised pixel array and updated metadata."""
        ds = pydicom.dcmread(file_path, force=True)
        
        # Clip and convert to original pixel representation
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        
        # Invert rescale: raw_stored = (pixel_val - intercept) / slope
        stored_pixels = (denoised_pixels - intercept) / slope
        
        bits_allocated = getattr(ds, "BitsAllocated", 16)
        if bits_allocated == 16:
            dtype = np.uint16 if getattr(ds, "PixelRepresentation", 0) == 0 else np.int16
            clamped = np.clip(stored_pixels, 0, 65535 if dtype == np.uint16 else 32767).astype(dtype)
        else:
            clamped = np.clip(stored_pixels, 0, 255).astype(np.uint8)

        ds.PixelData = clamped.tobytes()

        # Update Series & Instance Descriptions
        orig_series_desc = getattr(ds, "SeriesDescription", "IRM Lombaire")
        ds.SeriesDescription = f"[DÉBRUITÉ IA] {orig_series_desc}"
        ds.DerivationDescription = "Débruitage haute fidélité par Réseau ResNet 2D (MLflow Best Fold 2 / CUDA)"
        ds.SoftwareVersions = "ResNet2D-Denoiser-1.0.0"

        buffer = io.BytesIO()
        ds.save_as(buffer, write_like_original=False)
        return buffer.getvalue()

    @staticmethod
    def get_full_tags(file_path: str) -> List[Dict[str, str]]:
        """Returns the full list of tags in a readable format for the metadata dictionary modal."""
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        tag_list = []
        for elem in ds:
            if elem.tag.is_private:
                continue
            group = f"{elem.tag.group:04X}"
            element = f"{elem.tag.element:04X}"
            tag_str = f"({group},{element})"
            name = elem.name
            vr = elem.VR
            val_str = str(elem.value)
            if len(val_str) > 120:
                val_str = val_str[:120] + "..."
            tag_list.append({
                "tag": tag_str,
                "vr": vr,
                "name": name,
                "value": val_str
            })
        return tag_list
