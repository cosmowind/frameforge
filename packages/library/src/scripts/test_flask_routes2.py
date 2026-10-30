"""Extended Flask tests - test write/scan/delete routes"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from app import app as flask_app
from config import CSV_PATH, CONFIG_PATH

print(f"CSV_PATH: {CSV_PATH} (exists: {os.path.exists(CSV_PATH)})")
print(f"CONFIG_PATH: {CONFIG_PATH} (exists: {os.path.exists(CONFIG_PATH)})")

with flask_app.test_client() as client:
    # Test 15: Save data (dry run - just verify endpoint responds)
    test_data = {"fieldnames": ["path"], "data": []}
    resp = client.post('/api/save', json=test_data)
    print(f"Test 15: POST /api/save -> {resp.status_code}")

    # Test 16: Estimate endpoint
    resp = client.get('/api/estimate')
    print(f"Test 16: GET /api/estimate -> {resp.status_code}")

    # Test 17: Export endpoint
    resp = client.post('/api/export', json={"type": "txt"})
    print(f"Test 17: POST /api/export -> {resp.status_code}")

    # Test 18: Scan endpoint   
    resp = client.post('/api/scan', json={"directory": "/media"})
    print(f"Test 18: POST /api/scan -> {resp.status_code}")

    # Test 19: Dim editable options
    resp = client.get('/api/dim-editable-options')
    print(f"Test 19: GET /api/dim-editable-options -> {resp.status_code}")

    # Test 20: Tasks diff defaults
    resp = client.get('/api/dim/tasks/difficulty-defaults')
    data = json.loads(resp.data)
    print(f"Test 20: GET /api/dim/tasks/difficulty-defaults -> {resp.status_code}, data: {data}")

    # Test 21: Tasks with usage
    resp = client.get('/api/dim/tasks/with-usage')
    print(f"Test 21: GET /api/dim/tasks/with-usage -> {resp.status_code}")

    # Test 22: Pick directory
    resp = client.post('/api/pick-directory')
    print(f"Test 22: POST /api/pick-directory -> {resp.status_code}")

    # Test 23: Resume monitor
    resp = client.post('/api/resume-monitor')
    print(f"Test 23: POST /api/resume-monitor -> {resp.status_code}")

    # Test 24: HMD endpoints
    resp = client.post('/api/hmd/scan', json={"directory": "/media"})
    print(f"Test 24: POST /api/hmd/scan -> {resp.status_code}")

    # Test 25: Thumbnail endpoint (no path = 400)
    resp = client.get('/api/thumbnail')
    print(f"Test 25: GET /api/thumbnail (no param) -> {resp.status_code}")

    # Test 26: Video endpoint (no path = 400)
    resp = client.get('/api/video')
    print(f"Test 26: GET /api/video (no param) -> {resp.status_code}")

    # Test 27: Upload run cmd
    resp = client.post('/api/upload-run-cmd', json={"row_index": 0})
    print(f"Test 27: POST /api/upload-run-cmd -> {resp.status_code}")

    # Test 28: Fix dates
    resp = client.post('/api/fix-dates')
    print(f"Test 28: POST /api/fix-dates -> {resp.status_code}")

    # Test 29: Clean orphan cache
    resp = client.post('/api/clean-orphan-cache')
    print(f"Test 29: POST /api/clean-orphan-cache -> {resp.status_code}")

print("\n=== ALL EXTENDED TESTS COMPLETED ===")
