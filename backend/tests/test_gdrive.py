import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sqlmodel import Session
from app.models.gdrive_schemas import DriveToken, DriveScanJob, DriveFileRecord

def test_gdrive_auth_status_empty(client):
    resp = client.get("/api/gdrive/auth/status")
    assert resp.status_code == 200
    assert resp.json()["linked"] is False
    assert resp.json()["email"] is None

def test_gdrive_auth_status_linked(client, session: Session):
    token = DriveToken(
        email="user@gmail.com",
        access_token="fake_access",
        refresh_token="fake_refresh"
    )
    session.add(token)
    session.commit()
    
    resp = client.get("/api/gdrive/auth/status")
    assert resp.status_code == 200
    assert resp.json()["linked"] is True
    assert resp.json()["email"] == "user@gmail.com"

def test_gdrive_scan_without_link(client):
    resp = client.post("/api/gdrive/scan")
    assert resp.status_code == 404

@patch("app.services.drive_scanner.build")
@patch("fastapi.BackgroundTasks.add_task")
@patch("app.routers.gdrive._build_service")
def test_gdrive_scan_and_flow(mock_build_service, mock_add_task, mock_scanner_build, client, session: Session):
    from datetime import timedelta
    token = DriveToken(
        email="user@gmail.com",
        access_token="fake_access",
        refresh_token="fake_refresh",
        token_expiry=datetime.utcnow() + timedelta(days=1)
    )
    session.add(token)
    session.commit()

    # Mock the Google Drive service
    mock_service = MagicMock()
    mock_build_service.return_value = mock_service
    mock_scanner_build.return_value = mock_service
    
    # Mock files().list().execute()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "file1", "name": "photo.jpg", "mimeType": "image/jpeg", "size": "1024", "md5Checksum": "abc"},
            {"id": "file2", "name": "photo_copy.jpg", "mimeType": "image/jpeg", "size": "1024", "md5Checksum": "abc"},
            {"id": "file3", "name": "large.zip", "mimeType": "application/zip", "size": str(60 * 1024 * 1024)},
        ]
    }

    # Start scan
    resp = client.post("/api/gdrive/scan")
    assert resp.status_code == 200
    scan_id = resp.json()["scan_id"]
    
    # Run the DriveScanner direct mapping using the mock
    from app.services.drive_scanner import DriveScanner
    scanner = DriveScanner(session, token)
    scanner.run_scan(scan_id)
    
    # Check scan status
    status_resp = client.get(f"/api/gdrive/scan/{scan_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "done"
    assert status_resp.json()["progress"] == 100
    
    # Check scan files
    files_resp = client.get(f"/api/gdrive/scan/{scan_id}/files")
    assert files_resp.status_code == 200
    files = files_resp.json()
    assert len(files) == 3
    
    # Spot check mapped fields
    large_file = next(f for f in files if f["name"] == "large.zip")
    assert large_file["category"] == "large"
    
    dupe_file = next(f for f in files if f["name"] == "photo_copy.jpg")
    assert dupe_file["category"] == "duplicate"
    assert dupe_file["in_deletion_list"] == 1
    
    # Flag file (POST /api/gdrive/files/{id}/flag)
    flag_resp = client.post(f"/api/gdrive/files/file3/flag", json={"description": "Keep this archive"})
    assert flag_resp.status_code == 200
    
    # Verify it updated
    files_resp = client.get(f"/api/gdrive/scan/{scan_id}/files")
    files = files_resp.json()
    large_file = next(f for f in files if f["name"] == "large.zip")
    assert large_file["is_flagged"] == 1
    assert large_file["description"] == "Keep this archive"

    # Get deletion list
    del_resp = client.get(f"/api/gdrive/scan/{scan_id}/deletion-list")
    assert del_resp.status_code == 200
    assert len(del_resp.json()) == 1  # only photo_copy.jpg
    
    # Approve deletion
    app_del_resp = client.post(f"/api/gdrive/scan/{scan_id}/approve-deletion")
    assert app_del_resp.status_code == 200
    assert app_del_resp.json()["deleted"] == 1
