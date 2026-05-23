import hashlib
import os
import time
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic"}
SCREENSHOT_PREFIXES = ("screenshot", "screen ", "img_", "capture")


def walk_directory(path: str) -> list[dict[str, Any]]:
    results = []
    for root, _, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                stat = os.stat(full)
                results.append({
                    "path": full,
                    "name": name,
                    "size_bytes": stat.st_size,
                    "last_accessed": int(stat.st_atime),
                    "ext": Path(name).suffix.lower(),
                })
            except (PermissionError, FileNotFoundError):
                continue
    return results


def _sha256(path: str) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, FileNotFoundError):
        return None


def find_exact_duplicates(files: list[dict]) -> list[dict]:
    hash_map: dict[str, list[dict]] = {}
    for f in files:
        h = _sha256(f["path"])
        if h:
            hash_map.setdefault(h, []).append(f)
    result = []
    for group in hash_map.values():
        if len(group) > 1:
            result.extend(group)
    return result


def find_near_duplicates(files: list[dict], threshold: int = 8) -> list[dict]:
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        return []

    image_files = [f for f in files if f["ext"] in IMAGE_EXTS]
    hashes: list[tuple[Any, dict]] = []
    for f in image_files:
        try:
            img = Image.open(f["path"])
            h = imagehash.phash(img)
            hashes.append((h, f))
        except Exception:
            continue

    flagged: set[str] = set()
    near_dups = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            if abs(hashes[i][0] - hashes[j][0]) <= threshold:
                for _, f in (hashes[i], hashes[j]):
                    if f["path"] not in flagged:
                        flagged.add(f["path"])
                        near_dups.append(f)
    return near_dups


def find_large_files(files: list[dict], threshold_mb: float = 50) -> list[dict]:
    threshold_bytes = int(threshold_mb * 1024 * 1024)
    return [f for f in files if f["size_bytes"] >= threshold_bytes]


def find_old_files(files: list[dict], days: int = 365) -> list[dict]:
    cutoff = time.time() - days * 86400
    return [f for f in files if f["last_accessed"] < cutoff]


def find_screenshots(files: list[dict]) -> list[dict]:
    result = []
    for f in files:
        name_lower = f["name"].lower()
        if any(name_lower.startswith(p) for p in SCREENSHOT_PREFIXES) and f["ext"] in IMAGE_EXTS | {".png"}:
            result.append(f)
    return result


def run_full_scan(directory: str, rules: list[dict] | None = None) -> list[dict]:
    from app.services.protected_service import is_protected
    files = walk_directory(directory)
    rules = rules or []

    seen: set[str] = set()
    suggestions = []

    def add(file: dict, stype: str, confidence: float):
        p = file["path"]
        if p not in seen and not is_protected(p, rules):
            seen.add(p)
            suggestions.append({**file, "type": stype, "confidence": confidence})

    for f in find_exact_duplicates(files):
        add(f, "duplicate", 0.99)
    for f in find_near_duplicates(files):
        add(f, "near_duplicate", 0.80)
    for f in find_large_files(files):
        add(f, "large_file", 0.90)
    for f in find_old_files(files):
        add(f, "old_file", 0.75)
    for f in find_screenshots(files):
        add(f, "screenshot", 0.85)

    return suggestions
