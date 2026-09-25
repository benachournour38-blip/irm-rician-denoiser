import urllib.request
import urllib.parse
import os
import json

test_file = r"C:\Users\benac\Documents\Version-02\Sequence_T2W_TSE_sag - 301\bruitée\P_23\IM-0001-0001-0001.dcm"
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

with open(test_file, "rb") as f:
    file_bytes = f.read()

body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="files"; filename="IM-0001-0001-0001.dcm"\r\n'
    f"Content-Type: application/dicom\r\n\r\n"
).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/dicom/upload",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
)

res = urllib.request.urlopen(req)
resp_json = json.loads(res.read().decode())
print("Upload Result:", resp_json)
