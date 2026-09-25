import os
import shutil
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.config import PATIENTS_STORAGE_DIR, DB_PATH, BASE_DIR, STORAGE_DIR
from backend.services.dicom_service import DicomService

class StorageService:
    def __init__(self):
        self.init_db()

    @staticmethod
    def resolve_file_path(file_path: Optional[str]) -> str:
        if not file_path:
            return ""
        p = Path(file_path)
        if p.is_file():
            return str(p.resolve())

        base_cand = (BASE_DIR / file_path).resolve()
        if base_cand.is_file():
            return str(base_cand)

        norm_path = file_path.replace("\\", "/")
        if "storage/patients/" in norm_path:
            rel = norm_path.split("storage/patients/")[-1]
            cand = (PATIENTS_STORAGE_DIR / rel).resolve()
            if cand.is_file():
                return str(cand)

        if "storage/" in norm_path:
            rel = norm_path.split("storage/")[-1]
            cand = (STORAGE_DIR / rel).resolve()
            if cand.is_file():
                return str(cand)

        filename = Path(norm_path).name
        matches = list(PATIENTS_STORAGE_DIR.rglob(filename))
        if matches:
            return str(matches[0].resolve())

        return str((BASE_DIR / file_path).resolve())


    def get_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                patient_id TEXT UNIQUE,
                patient_name TEXT,
                patient_sex TEXT,
                patient_birth_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS studies (
                id TEXT PRIMARY KEY,
                patient_id TEXT,
                study_instance_uid TEXT UNIQUE,
                study_date TEXT,
                study_time TEXT,
                study_description TEXT,
                accession_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id TEXT PRIMARY KEY,
                study_instance_uid TEXT,
                series_instance_uid TEXT UNIQUE,
                series_number INTEGER,
                series_description TEXT,
                modality TEXT,
                body_part TEXT,
                protocol_name TEXT,
                slice_thickness REAL,
                pixel_spacing TEXT,
                repetition_time REAL,
                echo_time REAL,
                inversion_time REAL,
                magnetic_field_strength REAL,
                manufacturer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (study_instance_uid) REFERENCES studies (study_instance_uid) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS instances (
                id TEXT PRIMARY KEY,
                series_instance_uid TEXT,
                instance_uid TEXT UNIQUE,
                instance_number INTEGER,
                slice_location REAL,
                slice_thickness REAL,
                rows INTEGER,
                columns INTEGER,
                window_center REAL,
                window_width REAL,
                rescale_intercept REAL,
                rescale_slope REAL,
                image_position TEXT,
                image_orientation TEXT,
                pixel_spacing TEXT,
                repetition_time REAL,
                echo_time REAL,
                inversion_time REAL,
                magnetic_field_strength REAL,
                file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (series_instance_uid) REFERENCES series (series_instance_uid) ON DELETE CASCADE
            );
            """)

            # Auto-migrate legacy absolute paths to portable relative paths
            cursor.execute("SELECT id, file_path FROM instances WHERE file_path LIKE 'C:%'")
            for inst_id, fp in cursor.fetchall():
                norm = fp.replace("\\", "/")
                if "storage/patients/" in norm:
                    rel = "storage/patients/" + norm.split("storage/patients/")[-1]
            # Clean phantom empty series
            cursor.execute("DELETE FROM series WHERE series_instance_uid NOT IN (SELECT DISTINCT series_instance_uid FROM instances)")

            conn.commit()

    def index_dicom_file(self, src_file_path: str, move_file: bool = False, is_single_file_test: bool = False, test_name: str = None) -> Dict[str, Any]:
        """Parses a DICOM file, organizes it into the patient directory tree and records it in SQLite."""
        meta = DicomService.parse_dicom(src_file_path)

        p_info = meta["patient"]
        s_info = meta["study"]
        ser_info = meta["series"]
        inst_info = meta["instance"]

        clean_patient_id = "".join([c if c.isalnum() or c in "-_" else "_" for c in p_info["patient_id"]])

        # If testing a single file, isolate it so it never gets attached to an existing multi-slice folder
        if is_single_file_test:
            import time
            ts = int(time.time() * 1000)
            orig_name = test_name or Path(src_file_path).stem
            p_info["patient_id"] = f"TEST_{clean_patient_id}_{ts}"
            p_info["patient_name"] = f"Test Solo: {orig_name}"
            s_info["study_instance_uid"] = f"study_solo_{ts}"
            s_info["study_description"] = f"Test Unitaire - {orig_name}"
            ser_info["series_instance_uid"] = f"ser_solo_{ts}"
            ser_info["series_description"] = "Coupe Unique"
            clean_patient_id = p_info["patient_id"]

        # Safe directory path with compact hashes to avoid Windows MAX_PATH limits
        import hashlib
        study_hash = hashlib.md5(s_info["study_instance_uid"].encode()).hexdigest()[:12]
        series_hash = hashlib.md5(ser_info["series_instance_uid"].encode()).hexdigest()[:12]
        inst_hash = hashlib.md5(inst_info["instance_uid"].encode()).hexdigest()[:16]

        target_dir = PATIENTS_STORAGE_DIR / clean_patient_id / f"st_{study_hash}" / f"se_{series_hash}"
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_file_path = target_dir / f"{inst_hash}.dcm"

        if move_file:
            shutil.move(src_file_path, str(dest_file_path))
        else:
            shutil.copy2(src_file_path, str(dest_file_path))

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Insert or update patient
            cursor.execute("""
                INSERT INTO patients (id, patient_id, patient_name, patient_sex, patient_birth_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    patient_name = COALESCE(excluded.patient_name, patient_name),
                    patient_sex = COALESCE(excluded.patient_sex, patient_sex),
                    patient_birth_date = COALESCE(excluded.patient_birth_date, patient_birth_date)
            """, (p_info["patient_id"], p_info["patient_id"], p_info["patient_name"], p_info["patient_sex"], p_info["patient_birth_date"]))

            # Insert or update study
            cursor.execute("""
                INSERT INTO studies (id, patient_id, study_instance_uid, study_date, study_time, study_description, accession_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(study_instance_uid) DO UPDATE SET
                    study_description = COALESCE(excluded.study_description, study_description),
                    study_date = COALESCE(excluded.study_date, study_date)
            """, (s_info["study_instance_uid"], p_info["patient_id"], s_info["study_instance_uid"], s_info["study_date"], s_info["study_time"], s_info["study_description"], s_info["accession_number"]))

            # Insert or update series
            ps_json = json.dumps(ser_info["pixel_spacing"]) if ser_info["pixel_spacing"] else None
            cursor.execute("""
                INSERT INTO series (id, study_instance_uid, series_instance_uid, series_number, series_description, modality, body_part, protocol_name, slice_thickness, pixel_spacing, repetition_time, echo_time, inversion_time, magnetic_field_strength, manufacturer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(series_instance_uid) DO UPDATE SET
                    series_description = COALESCE(excluded.series_description, series_description),
                    slice_thickness = COALESCE(excluded.slice_thickness, slice_thickness),
                    repetition_time = COALESCE(excluded.repetition_time, repetition_time),
                    echo_time = COALESCE(excluded.echo_time, echo_time)
            """, (
                ser_info["series_instance_uid"], s_info["study_instance_uid"], ser_info["series_instance_uid"],
                ser_info["series_number"], ser_info["series_description"], ser_info["modality"],
                ser_info["body_part"], ser_info["protocol_name"], ser_info["slice_thickness"],
                ps_json, ser_info["repetition_time"], ser_info["echo_time"],
                ser_info["inversion_time"], ser_info["magnetic_field_strength"], ser_info["manufacturer"]
            ))

            # Insert or update instance
            img_pos_json = json.dumps(inst_info["image_position"]) if inst_info["image_position"] else None
            img_ori_json = json.dumps(inst_info["image_orientation"]) if inst_info["image_orientation"] else None
            inst_ps_json = json.dumps(inst_info["pixel_spacing"]) if inst_info["pixel_spacing"] else None

            cursor.execute("""
                INSERT INTO instances (id, series_instance_uid, instance_uid, instance_number, slice_location, slice_thickness, rows, columns, window_center, window_width, rescale_intercept, rescale_slope, image_position, image_orientation, pixel_spacing, repetition_time, echo_time, inversion_time, magnetic_field_strength, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_uid) DO UPDATE SET
                    slice_location = excluded.slice_location,
                    instance_number = excluded.instance_number,
                    file_path = excluded.file_path,
                    window_center = excluded.window_center,
                    window_width = excluded.window_width
            """, (
                inst_info["instance_uid"], ser_info["series_instance_uid"], inst_info["instance_uid"],
                inst_info["instance_number"], inst_info["slice_location"], inst_info["slice_thickness"],
                inst_info["rows"], inst_info["columns"], inst_info["window_center"], inst_info["window_width"],
                inst_info["rescale_intercept"], inst_info["rescale_slope"],
                img_pos_json, img_ori_json, inst_ps_json,
                inst_info["repetition_time"], inst_info["echo_time"],
                inst_info["inversion_time"], inst_info["magnetic_field_strength"],
                str(dest_file_path)
            ))
            conn.commit()

        return meta

    def get_patients(self, query: str = "") -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if query:
                like_str = f"%{query}%"
                cursor.execute("""
                    SELECT p.*, COUNT(DISTINCT s.id) as studies_count
                    FROM patients p
                    LEFT JOIN studies s ON p.patient_id = s.patient_id
                    WHERE p.patient_id LIKE ? OR p.patient_name LIKE ?
                    GROUP BY p.patient_id
                    ORDER BY p.patient_name ASC
                """, (like_str, like_str))
            else:
                cursor.execute("""
                    SELECT p.*, COUNT(DISTINCT s.id) as studies_count
                    FROM patients p
                    LEFT JOIN studies s ON p.patient_id = s.patient_id
                    GROUP BY p.patient_id
                    ORDER BY p.created_at DESC
                """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
            row = cursor.fetchone()
            if not row:
                return None
            patient_dict = dict(row)
            patient_dict["studies"] = self.get_studies_for_patient(patient_id)
            return patient_dict

    def get_studies_for_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, COUNT(DISTINCT ser.id) as series_count
                FROM studies s
                LEFT JOIN series ser ON s.study_instance_uid = ser.study_instance_uid
                WHERE s.patient_id = ?
                GROUP BY s.study_instance_uid
                ORDER BY s.study_date DESC, s.study_time DESC
            """, (patient_id,))
            studies = [dict(row) for row in cursor.fetchall()]
            for st in studies:
                st["series"] = self.get_series_for_study(st["study_instance_uid"])
            return studies

    def get_series_for_study(self, study_uid: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ser.*, COUNT(DISTINCT i.id) as slice_count
                FROM series ser
                LEFT JOIN instances i ON ser.series_instance_uid = i.series_instance_uid
                WHERE ser.study_instance_uid = ?
                GROUP BY ser.series_instance_uid
                HAVING COUNT(DISTINCT i.id) > 0
                ORDER BY ser.series_number ASC
            """, (study_uid,))
            series_rows = [dict(row) for row in cursor.fetchall()]
            for s in series_rows:
                if s.get("pixel_spacing"):
                    try:
                        s["pixel_spacing"] = json.loads(s["pixel_spacing"])
                    except Exception:
                        pass
            return series_rows

    def get_series(self, series_uid: str, include_instances: bool = True) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM series WHERE series_instance_uid = ?", (series_uid,))
            row = cursor.fetchone()
            if not row:
                return None
            ser_dict = dict(row)
            if ser_dict.get("pixel_spacing"):
                try:
                    ser_dict["pixel_spacing"] = json.loads(ser_dict["pixel_spacing"])
                except Exception:
                    pass
            if include_instances:
                ser_dict["instances"] = self.get_instances_for_series(series_uid)
                ser_dict["slice_count"] = len(ser_dict["instances"])
            return ser_dict

    def get_instances_for_series(self, series_uid: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM instances
                WHERE series_instance_uid = ?
                ORDER BY
                    CASE WHEN slice_location IS NOT NULL THEN slice_location ELSE instance_number END ASC,
                    instance_number ASC
            """, (series_uid,))
            rows = cursor.fetchall()
            instances = []
            for r in rows:
                d = dict(r)
                if d.get("image_position"):
                    try:
                        d["image_position"] = json.loads(d["image_position"])
                    except Exception:
                        pass
                if d.get("image_orientation"):
                    try:
                        d["image_orientation"] = json.loads(d["image_orientation"])
                    except Exception:
                        pass
                if d.get("pixel_spacing"):
                    try:
                        d["pixel_spacing"] = json.loads(d["pixel_spacing"])
                    except Exception:
                        pass
                if d.get("file_path"):
                    d["file_path"] = self.resolve_file_path(d["file_path"])
                instances.append(d)
            return instances

    def get_instance(self, instance_uid: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM instances WHERE instance_uid = ?", (instance_uid,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            for k in ["image_position", "image_orientation", "pixel_spacing"]:
                if d.get(k):
                    try:
                        d[k] = json.loads(d[k])
                    except Exception:
                        pass
            if d.get("file_path"):
                d["file_path"] = self.resolve_file_path(d["file_path"])
            return d

    def delete_patient(self, patient_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
            conn.commit()
        # Clean filesystem
        clean_patient_id = "".join([c if c.isalnum() or c in "-_" else "_" for c in patient_id])
        p_dir = PATIENTS_STORAGE_DIR / clean_patient_id
        if p_dir.exists():
            shutil.rmtree(p_dir, ignore_errors=True)
        return True

    def delete_study(self, study_uid: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM studies WHERE study_instance_uid = ?", (study_uid,))
            conn.commit()
        return True

    def consolidate_study_series(self, study_uid: str):
        """Intelligently detects when an exported/anonymized dataset split a single acquisition volume
        into individual 1-slice series and consolidates them into a unified multi-slice series."""
        with self.get_connection() as conn:
            c = conn.cursor()
            # Check if this study has multiple series that all have only 1 instance
            c.execute("""
                SELECT count(distinct ser.series_instance_uid) as num_series, count(i.id) as num_instances
                FROM series ser
                JOIN instances i ON ser.series_instance_uid = i.series_instance_uid
                WHERE ser.study_instance_uid = ?
            """, (study_uid,))
            row = c.fetchone()
            if not row:
                return

            num_series, num_instances = row[0], row[1]
            if num_series > 1:
                # Consolidate all instances in this study into one unified multi-slice series
                c.execute("""
                    SELECT i.id as inst_id, i.file_path, i.instance_uid, ser.modality, ser.slice_thickness, ser.pixel_spacing
                    FROM instances i
                    JOIN series ser ON i.series_instance_uid = ser.series_instance_uid
                    WHERE ser.study_instance_uid = ?
                    ORDER BY
                        CASE WHEN i.slice_location IS NOT NULL THEN i.slice_location ELSE i.instance_number END ASC,
                        i.file_path ASC, i.created_at ASC
                """, (study_uid,))
                instances = [dict(r) for r in c.fetchall()]
                if not instances:
                    return

                master_series_uid = f"ser_{study_uid}.1"
                first_inst = instances[0]

                c.execute("""
                    INSERT INTO series (id, study_instance_uid, series_instance_uid, series_number, series_description, modality, body_part, slice_thickness, pixel_spacing)
                    VALUES (?, ?, ?, 1, 'IRM Rachis Lombaire (Coupes Sagittales)', ?, 'LUMBAR SPINE', ?, ?)
                    ON CONFLICT(series_instance_uid) DO UPDATE SET
                        series_description = 'IRM Rachis Lombaire (Coupes Sagittales)'
                """, (
                    master_series_uid, study_uid, master_series_uid,
                    first_inst.get("modality", "MR") or "MR",
                    first_inst.get("slice_thickness", 3.0) or 3.0,
                    first_inst.get("pixel_spacing")
                ))

                for idx, inst in enumerate(instances, start=1):
                    c.execute("""
                        UPDATE instances
                        SET series_instance_uid = ?,
                            instance_number = ?,
                            slice_location = COALESCE(slice_location, ?)
                        WHERE id = ?
                    """, (master_series_uid, idx, float(idx * 3.0), inst["inst_id"]))

                c.execute("""
                    DELETE FROM series
                    WHERE study_instance_uid = ? AND series_instance_uid != ?
                """, (study_uid, master_series_uid))

                c.execute("DELETE FROM series WHERE series_instance_uid NOT IN (SELECT distinct series_instance_uid FROM instances)")

                conn.commit()
