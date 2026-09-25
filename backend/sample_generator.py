import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from datetime import datetime
from backend.services.storage_service import StorageService
from backend.config import PATIENTS_STORAGE_DIR

def create_dicom_file_meta() -> FileMetaDataset:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "1.2.826.0.1.3680043.2.1125.1.0"
    file_meta.ImplementationVersionName = "MR_LUMBAR_GEN_1"
    return file_meta

def draw_lumbar_sagittal(slice_idx: int, total_slices: int, sequence_type: str = "T2") -> np.ndarray:
    """
    Renders an anatomically structured sagittal slice of the lumbar spine:
    - Vertebral bodies L1, L2, L3, L4, L5, S1
    - Intervertebral discs (T2 hyperintense nucleus pulposus / annulus)
    - Spinal canal, dural sac & cerebrospinal fluid (CSF bright on T2, dark on T1, bright on STIR)
    - Spinal cord / Cauda equina nerve roots
    - Spinous processes and paraspinal muscles
    - Subcutaneous fat (bright on T1/T2, suppressed/dark on STIR)
    """
    h, w = 384, 384
    img = np.zeros((h, w), dtype=np.float32)

    # Lateral distance from midline (normalized -1 to 1)
    mid_idx = total_slices / 2.0
    lat_dist = abs(slice_idx - mid_idx) / (total_slices / 2.0)
    slice_factor = max(0.2, 1.0 - (lat_dist ** 2) * 0.8)

    # Base background noise (low MRI noise)
    noise = np.random.normal(15, 5, (h, w)).astype(np.float32)
    img += np.clip(noise, 0, 50)

    # Soft tissue / posterior muscular mass
    y, x = np.mgrid[:h, :w]

    # Abdominal / anterior soft tissue
    ant_mask = (x > 60) & (x < 160) & (y > 40) & (y < 350)
    img[ant_mask] += 120 + 30 * np.sin(y[ant_mask] / 20.0)

    # Subcutaneous fat anterior & posterior
    fat_signal = 180 if sequence_type in ["T1", "T2"] else 30  # Fat suppressed on STIR
    post_fat = (x > 290) & (x < 340) & (y > 30) & (y < 360)
    img[post_fat] += fat_signal

    # Spinal Canal & CSF (Thecal Sac)
    # Curved canal from y=40 to y=350, centered around x = 205 + 15*sin(y/100)
    canal_center_x = 210 + 18.0 * np.sin((y - 60) / 100.0)
    canal_width = 16.0 * slice_factor
    canal_mask = (np.abs(x - canal_center_x) < canal_width) & (y > 40) & (y < 340)

    if sequence_type == "T2":
        # CSF is bright hyperintense on T2
        img[canal_mask] = 480 + 30 * np.random.randn(np.sum(canal_mask))
        # Cauda equina fibers inside CSF (dark linear strands)
        nerve_mask = canal_mask & ((x.astype(int) % 4 == 0) | (y > 300))
        img[nerve_mask] -= 160
    elif sequence_type == "T1":
        # CSF is dark hypointense on T1
        img[canal_mask] = 90 + 15 * np.random.randn(np.sum(canal_mask))
    elif sequence_type == "STIR":
        # CSF is very bright on STIR
        img[canal_mask] = 520 + 30 * np.random.randn(np.sum(canal_mask))

    # Vertebrae L1 to L5 + S1
    # Positions of vertebral bodies anterior to spinal canal
    vertebrae = [
        ("L1", 70, 38, 48),
        ("L2", 118, 40, 50),
        ("L3", 168, 42, 52),
        ("L4", 220, 44, 54),
        ("L5", 274, 46, 56),
        ("S1", 330, 50, 60),
    ]

    bone_marrow_signal = 340 if sequence_type == "T1" else 280 if sequence_type == "T2" else 110
    cortical_bone_signal = 40  # Dark cortical rim on all MRI sequences

    for name, cy, vh, vw in vertebrae:
        # Slight lumbar lordosis curve
        cx = 160 + 18.0 * np.sin((cy - 60) / 100.0)
        # Vertebral body rectangle with rounded corners
        vert_mask = (abs(y - cy) < (vh / 2.0)) & (abs(x - cx) < (vw / 2.0) * slice_factor)

        # Cortical rim
        rim_mask = vert_mask & (
            (abs(y - cy) > (vh / 2.0 - 4)) | (abs(x - cx) > (vw / 2.0 * slice_factor - 4))
        )
        img[vert_mask] = bone_marrow_signal + 20 * np.random.randn(np.sum(vert_mask))
        img[rim_mask] = cortical_bone_signal

        # Posterior elements / spinous processes (visible near midline)
        if lat_dist < 0.6:
            post_x = cx + 55 + (name == "L4" or name == "L5") * 10
            post_mask = ((y - (cy + 5)) ** 2 / 100.0 + (x - post_x) ** 2 / 300.0) < 1.0
            img[post_mask] = bone_marrow_signal * 0.8
            img[post_mask & ((x - post_x) ** 2 / 300.0 > 0.6)] = cortical_bone_signal

    # Intervertebral Discs (between L1-L2, L2-L3, L3-L4, L4-L5, L5-S1)
    disc_levels = [
        (94, 14, 44),
        (143, 15, 46),
        (194, 16, 48),
        (247, 17, 50),
        (302, 16, 52),
    ]

    for dcy, dh, dw in disc_levels:
        dcx = 160 + 18.0 * np.sin((dcy - 60) / 100.0)
        disc_mask = (abs(y - dcy) < (dh / 2.0)) & (abs(x - dcx) < (dw / 2.0) * slice_factor)

        if sequence_type == "T2":
            # Nucleus pulposus is hyperintense (bright), annulus fibrosus is darker
            img[disc_mask] = 420
            # Dark outer annulus
            annulus_mask = disc_mask & (
                (abs(y - dcy) > (dh / 2.0 - 3)) | (abs(x - dcx) > (dw / 2.0 * slice_factor - 5))
            )
            img[annulus_mask] = 160
            # Slight disc protrusion at L4-L5 for clinical realism
            if dcy == 247:
                prot_mask = (abs(y - dcy) < 6) & (x >= dcx + dw/2.0 * slice_factor - 3) & (x < dcx + dw/2.0 * slice_factor + 6)
                img[prot_mask] = 220
        elif sequence_type == "T1":
            img[disc_mask] = 130
        elif sequence_type == "STIR":
            img[disc_mask] = 310

    # Gaussian smoothing & realistic MRI texture
    return np.clip(img, 0, 1024).astype(np.uint16)

def draw_lumbar_axial(slice_idx: int, total_slices: int, sequence_type: str = "T2") -> np.ndarray:
    """Renders an axial slice of the lumbar spine at disc / foraminal levels."""
    h, w = 384, 384
    img = np.zeros((h, w), dtype=np.float32)

    # Base noise
    noise = np.random.normal(12, 4, (h, w)).astype(np.float32)
    img += np.clip(noise, 0, 40)

    y, x = np.mgrid[:h, :w]
    cy, cx = 192, 192

    # Abdominal / retroperitoneal cavity (anterior)
    abdo_mask = ((y - 120) ** 2 / 6000.0 + (x - cx) ** 2 / 12000.0) < 1.0
    img[abdo_mask] = 110 + 20 * np.sin((x[abdo_mask] + y[abdo_mask]) / 15.0)

    # Major abdominal vessels: Aorta & Inferior Vena Cava (Flow voids -> dark)
    aorta = ((y - 130) ** 2 + (x - 170) ** 2) < 180
    ivc = ((y - 130) ** 2 + (x - 215) ** 2) < 220
    img[aorta] = 20
    img[ivc] = 25

    # Psoas major muscles (bilateral anterolateral)
    psoas_l = ((y - 175) ** 2 / 800.0 + (x - 135) ** 2 / 400.0) < 1.0
    psoas_r = ((y - 175) ** 2 / 800.0 + (x - 249) ** 2 / 400.0) < 1.0
    img[psoas_l] = 160
    img[psoas_r] = 160

    # Posterior erector spinae / multifidus muscles
    erector_l = ((y - 275) ** 2 / 1400.0 + (x - 140) ** 2 / 900.0) < 1.0
    erector_r = ((y - 275) ** 2 / 1400.0 + (x - 244) ** 2 / 900.0) < 1.0
    img[erector_l] = 175
    img[erector_r] = 175

    # Posterior Subcutaneous fat
    post_fat = (y > 310) & (y < 365) & (abs(x - cx) < 160)
    fat_val = 260 if sequence_type in ["T1", "T2"] else 40
    img[post_fat] = fat_val

    # Vertebral Body or Disc at this axial level
    is_disc_level = (slice_idx % 4 == 0 or slice_idx % 4 == 1)
    vert_body = ((y - 180) ** 2 / 950.0 + (x - cx) ** 2 / 1600.0) < 1.0

    if is_disc_level:
        # Intervertebral disc
        if sequence_type == "T2":
            img[vert_body] = 380  # bright nucleus
            annulus = vert_body & (((y - 180) ** 2 / 950.0 + (x - cx) ** 2 / 1600.0) > 0.65)
            img[annulus] = 140
        else:
            img[vert_body] = 140
    else:
        # Bone body
        bone_val = 320 if sequence_type == "T1" else 260
        img[vert_body] = bone_val
        cortex = vert_body & (((y - 180) ** 2 / 950.0 + (x - cx) ** 2 / 1600.0) > 0.85)
        img[cortex] = 35

    # Posterior neural arch / pedicles & lamina
    pedicle_l = ((y - 220) ** 2 / 200.0 + (x - 150) ** 2 / 80.0) < 1.0
    pedicle_r = ((y - 220) ** 2 / 200.0 + (x - 234) ** 2 / 80.0) < 1.0
    lamina = ((y - 250) ** 2 / 120.0 + (abs(x - cx) - 25) ** 2 / 150.0) < 1.0
    spinous = (abs(x - cx) < 10) & (y >= 250) & (y <= 310)

    neural_arch = pedicle_l | pedicle_r | lamina | spinous
    img[neural_arch] = 240
    img[neural_arch & (((y - 250) ** 2 + (x - cx) ** 2) > 400)] = 200

    # Spinal Canal (Dural Sac) & Foramina
    dural_sac = ((y - 225) ** 2 / 220.0 + (x - cx) ** 2 / 180.0) < 1.0
    if sequence_type == "T2":
        img[dural_sac] = 520
        # Cauda equina rootlets (dots inside CSF)
        roots = dural_sac & ((x.astype(int) % 3 == 0) & (y.astype(int) % 3 == 0) & (y > 222))
        img[roots] = 110
        # Exiting nerve roots in neural foramina
        foram_l = ((y - 215) ** 2 + (x - 165) ** 2) < 35
        foram_r = ((y - 215) ** 2 + (x - 219) ** 2) < 35
        img[foram_l] = 220
        img[foram_r] = 220
    else:
        img[dural_sac] = 100

    return np.clip(img, 0, 1024).astype(np.uint16)

def generate_sample_lumbar_studies():
    """Generates complete sample Lumbar MRI studies with T1, T2, and STIR sequences."""
    storage = StorageService()
    study_date = datetime.now().strftime("%Y%m%d")
    study_time = "103000"

    samples_config = [
        {
            "patient_id": "LUMBAR-001",
            "patient_name": "DUPONT^Jean",
            "patient_sex": "M",
            "patient_birth_date": "19780415",
            "study_desc": "IRM Rachis Lombaire - Bilan Lomboradiculalgie L5",
            "series_list": [
                {
                    "desc": "T2 TSE Sagittal Rachis Lombaire",
                    "type": "T2",
                    "plane": "sagittal",
                    "slices": 15,
                    "tr": 3500.0,
                    "te": 105.0,
                    "thick": 3.0,
                    "spacing": [0.65, 0.65],
                    "wc": 300,
                    "ww": 650,
                },
                {
                    "desc": "T1 SE Sagittal Rachis Lombaire",
                    "type": "T1",
                    "plane": "sagittal",
                    "slices": 15,
                    "tr": 650.0,
                    "te": 12.0,
                    "thick": 3.0,
                    "spacing": [0.65, 0.65],
                    "wc": 220,
                    "ww": 500,
                },
                {
                    "desc": "T2 TSE Axial Disques L3-L4 / L4-L5 / L5-S1",
                    "type": "T2",
                    "plane": "axial",
                    "slices": 16,
                    "tr": 4200.0,
                    "te": 110.0,
                    "thick": 3.5,
                    "spacing": [0.55, 0.55],
                    "wc": 320,
                    "ww": 680,
                },
                {
                    "desc": "STIR T2 FatSat Sagittal Rachis Lombaire",
                    "type": "STIR",
                    "plane": "sagittal",
                    "slices": 15,
                    "tr": 4000.0,
                    "te": 60.0,
                    "thick": 3.5,
                    "spacing": [0.70, 0.70],
                    "wc": 280,
                    "ww": 600,
                }
            ]
        },
        {
            "patient_id": "LUMBAR-002",
            "patient_name": "MARTIN^Claire",
            "patient_sex": "F",
            "patient_birth_date": "19851122",
            "study_desc": "IRM Rachis Lombaire & Jonction Lombo-Sacrée",
            "series_list": [
                {
                    "desc": "T2 TSE Sagittal Haute Résolution",
                    "type": "T2",
                    "plane": "sagittal",
                    "slices": 15,
                    "tr": 3600.0,
                    "te": 102.0,
                    "thick": 3.0,
                    "spacing": [0.60, 0.60],
                    "wc": 310,
                    "ww": 660,
                },
                {
                    "desc": "T1 SE Sagittal",
                    "type": "T1",
                    "plane": "sagittal",
                    "slices": 15,
                    "tr": 620.0,
                    "te": 11.0,
                    "thick": 3.0,
                    "spacing": [0.60, 0.60],
                    "wc": 210,
                    "ww": 480,
                },
                {
                    "desc": "T2 TSE Axial L4-L5 / L5-S1",
                    "type": "T2",
                    "plane": "axial",
                    "slices": 12,
                    "tr": 3800.0,
                    "te": 105.0,
                    "thick": 3.0,
                    "spacing": [0.55, 0.55],
                    "wc": 330,
                    "ww": 700,
                }
            ]
        }
    ]

    temp_gen_dir = PATIENTS_STORAGE_DIR.parent / "temp_generator"
    temp_gen_dir.mkdir(parents=True, exist_ok=True)

    print("[INFO] Generation des etudes IRM lombaire de demonstration...")

    for p in samples_config:
        study_uid = generate_uid()
        for ser_idx, ser in enumerate(p["series_list"], 1):
            ser_uid = generate_uid()
            num_slices = ser["slices"]
            plane = ser["plane"]
            seq_type = ser["type"]

            for slice_i in range(1, num_slices + 1):
                sop_uid = generate_uid()

                # Generate image pixel matrix
                if plane == "sagittal":
                    pixels = draw_lumbar_sagittal(slice_i, num_slices, seq_type)
                    slice_loc = -((num_slices / 2.0) - slice_i) * ser["thick"]
                    img_pos = [slice_loc, -100.0, 0.0]
                    img_ori = [0.0, 1.0, 0.0, 0.0, 0.0, -1.0]
                else:
                    pixels = draw_lumbar_axial(slice_i, num_slices, seq_type)
                    slice_loc = -((num_slices / 2.0) - slice_i) * ser["thick"]
                    img_pos = [-100.0, -100.0, slice_loc]
                    img_ori = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

                # Create Dataset
                file_meta = create_dicom_file_meta()
                file_meta.MediaStorageSOPInstanceUID = sop_uid

                ds = Dataset()
                ds.file_meta = file_meta
                ds.is_little_endian = True
                ds.is_implicit_VR = False

                # Patient tags
                ds.PatientID = p["patient_id"]
                ds.PatientName = p["patient_name"]
                ds.PatientSex = p["patient_sex"]
                ds.PatientBirthDate = p["patient_birth_date"]

                # Study tags
                ds.StudyInstanceUID = study_uid
                ds.StudyDate = study_date
                ds.StudyTime = study_time
                ds.StudyDescription = p["study_desc"]
                ds.AccessionNumber = f"ACC-{p['patient_id'][-3:]}001"
                ds.StudyID = "1"

                # Series tags
                ds.SeriesInstanceUID = ser_uid
                ds.SeriesNumber = ser_idx
                ds.SeriesDescription = ser["desc"]
                ds.Modality = "MR"
                ds.BodyPartExamined = "LUMBAR SPINE"
                ds.ProtocolName = ser["desc"]
                ds.Manufacturer = "SIEMENS"
                ds.ManufacturerModelName = "MAGNETOM Vida 3T"
                ds.MagneticFieldStrength = 3.0
                ds.RepetitionTime = ser["tr"]
                ds.EchoTime = ser["te"]
                if seq_type == "STIR":
                    ds.InversionTime = 160.0
                ds.FlipAngle = 150.0

                # Instance tags
                ds.SOPClassUID = pydicom.uid.MRImageStorage
                ds.SOPInstanceUID = sop_uid
                ds.InstanceNumber = slice_i
                ds.SliceLocation = slice_loc
                ds.SliceThickness = ser["thick"]
                ds.PixelSpacing = ser["spacing"]
                ds.ImagePositionPatient = img_pos
                ds.ImageOrientationPatient = img_ori
                ds.SamplesPerPixel = 1
                ds.PhotometricInterpretation = "MONOCHROME2"
                ds.Rows = pixels.shape[0]
                ds.Columns = pixels.shape[1]
                ds.BitsAllocated = 16
                ds.BitsStored = 12
                ds.HighBit = 11
                ds.PixelRepresentation = 0
                ds.WindowCenter = ser["wc"]
                ds.WindowWidth = ser["ww"]
                ds.RescaleIntercept = 0.0
                ds.RescaleSlope = 1.0

                # Pixel Data
                ds.PixelData = pixels.tobytes()

                # Save temporary DCM file and index
                tmp_file = temp_gen_dir / f"tmp_{slice_i}_{sop_uid[-12:]}.dcm"
                ds.save_as(str(tmp_file), write_like_original=False)
                storage.index_dicom_file(str(tmp_file), move_file=True)

    print("[SUCCESS] Etudes IRM Lombaire generees et indexees avec succes.")

if __name__ == "__main__":
    generate_sample_lumbar_studies()
