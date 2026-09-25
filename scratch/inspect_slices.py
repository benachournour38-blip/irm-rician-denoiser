import sqlite3
import pydicom

conn = sqlite3.connect('storage/dicom_index.db')
c = conn.cursor()
c.execute("""
    SELECT i.file_path, i.instance_uid, i.instance_number, i.slice_location
    FROM instances i
    JOIN series ser ON i.series_instance_uid = ser.series_instance_uid
    WHERE ser.study_instance_uid = '202612543.170004'
""")
rows = c.fetchall()
print(f"Total instances for 202612543.170004: {len(rows)}")

for idx, (path, uid, inst_num, sl_loc) in enumerate(rows[:5]):
    ds = pydicom.dcmread(path, stop_before_pixels=True)
    print(f"\n--- Slice {idx+1} ---")
    print(f"File: {path}")
    print(f"InstanceNumber: {getattr(ds, 'InstanceNumber', None)}")
    print(f"SliceLocation: {getattr(ds, 'SliceLocation', None)}")
    print(f"ImagePosition: {getattr(ds, 'ImagePositionPatient', None)}")
    print(f"AcquisitionNumber: {getattr(ds, 'AcquisitionNumber', None)}")
    print(f"TemporalPosition: {getattr(ds, 'TemporalPositionIdentifier', None)}")
    print(f"ContentTime: {getattr(ds, 'ContentTime', None)}")
    print(f"AcquisitionTime: {getattr(ds, 'AcquisitionTime', None)}")
