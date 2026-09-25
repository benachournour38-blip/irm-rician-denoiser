import sqlite3
import json

def consolidate_fragmented_series():
    conn = sqlite3.connect('storage/dicom_index.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Find studies where every series has only 1 instance
    c.execute("""
        SELECT s.study_instance_uid, s.patient_id, count(distinct ser.series_instance_uid) as num_series, count(i.id) as num_instances
        FROM studies s
        JOIN series ser ON s.study_instance_uid = ser.study_instance_uid
        JOIN instances i ON ser.series_instance_uid = i.series_instance_uid
        GROUP BY s.study_instance_uid
        HAVING num_series > 1 AND num_series = num_instances
    """)
    fragmented_studies = [dict(r) for r in c.fetchall()]
    print(f"Found {len(fragmented_studies)} fragmented studies to consolidate:")

    for st in fragmented_studies:
        study_uid = st["study_instance_uid"]
        patient_id = st["patient_id"]
        total_slices = st["num_instances"]
        print(f"\nConsolidating Patient {patient_id} ({total_slices} slices)...")

        # Get all series and instances for this study
        c.execute("""
            SELECT i.id as inst_id, i.file_path, i.instance_uid, ser.series_instance_uid, ser.modality, ser.slice_thickness, ser.pixel_spacing
            FROM instances i
            JOIN series ser ON i.series_instance_uid = ser.series_instance_uid
            WHERE ser.study_instance_uid = ?
            ORDER BY i.file_path ASC, i.created_at ASC
        """, (study_uid,))
        instances = [dict(r) for r in c.fetchall()]

        if not instances:
            continue

        # Choose the master series UID (use the first one, or a canonical one)
        master_series_uid = f"ser_{study_uid}.1"
        first_inst = instances[0]

        # Insert or update master series
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

        # Reassign all instances to this master series and assign sequential instance numbers
        for idx, inst in enumerate(instances, start=1):
            c.execute("""
                UPDATE instances
                SET series_instance_uid = ?,
                    instance_number = ?,
                    slice_location = COALESCE(slice_location, ?)
                WHERE id = ?
            """, (master_series_uid, idx, float(idx * 3.0), inst["inst_id"]))

        # Delete the old orphaned 1-slice series
        c.execute("""
            DELETE FROM series
            WHERE study_instance_uid = ? AND series_instance_uid != ?
        """, (study_uid, master_series_uid))

        print(f"  -> Successfully unified into series '{master_series_uid}' with {len(instances)} coupes!")

    conn.commit()
    conn.close()
    print("\nConsolidation complete!")

if __name__ == "__main__":
    consolidate_fragmented_series()
