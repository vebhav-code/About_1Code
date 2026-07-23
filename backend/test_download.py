import sys
import zipfile
import io
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

for slug in ["authentication-debug", "test-challenge"]:
    print(f"Testing {slug}...")
    res = client.get(f"/challenge/{slug}/download")
    print("STATUS:", res.status_code)
    if res.status_code == 200:
        buf = io.BytesIO(res.content)
        with zipfile.ZipFile(buf, "r") as zf:
            files = zf.namelist()
            print("FILES IN ZIP:", files)
            print("Contains official solution?", any("official_solution" in f for f in files))
    print("-------------------------")
