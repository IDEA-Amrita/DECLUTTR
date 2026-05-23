import os
import time
import pytest
from PIL import Image
from app.services.storage_service import (
    walk_directory,
    find_exact_duplicates,
    find_large_files,
    find_old_files,
    find_screenshots,
    find_near_duplicates,
)


@pytest.fixture
def dir_with_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"hello world")
    (tmp_path / "b.txt").write_bytes(b"hello world")  # exact dup of a.txt
    (tmp_path / "c.txt").write_bytes(b"different content")
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * (60 * 1024 * 1024))  # 60 MB
    screenshot = tmp_path / "Screenshot 2025-01-01.png"
    screenshot.write_bytes(b"fake png")
    return tmp_path


def test_walk_directory_returns_metadata(dir_with_files):
    files = walk_directory(str(dir_with_files))
    paths = [f["path"] for f in files]
    assert any("a.txt" in p for p in paths)
    assert all("size_bytes" in f for f in files)
    assert all("last_accessed" in f for f in files)


def test_find_exact_duplicates(dir_with_files):
    files = walk_directory(str(dir_with_files))
    dups = find_exact_duplicates(files)
    dup_paths = [d["path"] for d in dups]
    assert len(dup_paths) == 2  # a.txt and b.txt both flagged


def test_find_large_files(dir_with_files):
    files = walk_directory(str(dir_with_files))
    large = find_large_files(files, threshold_mb=50)
    assert any("big.bin" in f["path"] for f in large)
    assert not any("a.txt" in f["path"] for f in large)


def test_find_old_files(tmp_path):
    old = tmp_path / "old.txt"
    old.write_bytes(b"old")
    old_time = time.time() - (400 * 86400)
    os.utime(str(old), (old_time, old_time))
    files = walk_directory(str(tmp_path))
    result = find_old_files(files, days=365)
    assert any("old.txt" in f["path"] for f in result)


def test_find_screenshots(dir_with_files):
    files = walk_directory(str(dir_with_files))
    shots = find_screenshots(files)
    assert any("Screenshot" in f["path"] for f in shots)
    assert not any("a.txt" in f["path"] for f in shots)


def test_post_scan_returns_scan_id(client, tmp_path):
    (tmp_path / "file.txt").write_bytes(b"x" * (60 * 1024 * 1024))
    resp = client.post("/api/storage/scan", json={"directory": str(tmp_path)})
    assert resp.status_code == 200
    assert "scan_id" in resp.json()


def test_get_scan_status(client, tmp_path):
    (tmp_path / "file.txt").write_bytes(b"x")
    scan_id = client.post("/api/storage/scan", json={"directory": str(tmp_path)}).json()["scan_id"]
    resp = client.get(f"/api/storage/scan/{scan_id}/status")
    assert resp.status_code == 200
    assert "status" in resp.json()
