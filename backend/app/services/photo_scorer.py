import os
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter
from scipy.signal import convolve2d

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

_LAPLACIAN = np.array([
    [0,  1, 0],
    [1, -4, 1],
    [0,  1, 0],
], dtype=float)


def sharpness_score(path: str) -> float:
    try:
        img = Image.open(path).convert("L").resize((256, 256))
        arr = np.array(img, dtype=float)
        filtered = convolve2d(arr, _LAPLACIAN, mode="valid")
        variance = float(np.var(filtered))
        return min(100.0, variance / 10.0)
    except Exception:
        return 0.0


def brightness_score(path: str) -> float:
    try:
        img = Image.open(path).convert("L").resize((256, 256))
        mean = float(np.mean(np.array(img)))
        if mean < 30 or mean > 220:
            return max(0.0, 100.0 - abs(mean - 128) * 1.5)
        return max(0.0, 100.0 - abs(mean - 128) * 0.5)
    except Exception:
        return 0.0


def composition_score(path: str) -> float:
    try:
        img = Image.open(path).convert("L").resize((300, 300))
        edges = img.filter(ImageFilter.FIND_EDGES)
        arr = np.array(edges, dtype=float)
        h, w = arr.shape
        h3, w3 = h // 3, w // 3
        third_regions = [
            arr[h3:2*h3, w3:2*w3],
            arr[:h3, :w3], arr[:h3, 2*w3:],
            arr[2*h3:, :w3], arr[2*h3:, 2*w3:],
        ]
        densities = [float(np.mean(r)) for r in third_regions]
        centre_density = densities[0]
        corner_density = sum(densities[1:]) / 4
        score = min(100.0, corner_density / max(centre_density + 1, 1) * 50 + corner_density * 0.3)
        return max(0.0, score)
    except Exception:
        return 0.0


def combined_score(path: str) -> float:
    s = sharpness_score(path)
    b = brightness_score(path)
    c = composition_score(path)
    return round(s * 0.4 + b * 0.3 + c * 0.3, 2)


def score_directory(directory: str) -> list[dict]:
    results = []
    for name in os.listdir(directory):
        full = os.path.join(directory, name)
        if not os.path.isfile(full):
            continue
        if Path(name).suffix.lower() not in IMAGE_EXTS:
            continue
        results.append({
            "path": full,
            "score": combined_score(full),
            "sharpness": sharpness_score(full),
            "brightness": brightness_score(full),
            "composition": composition_score(full),
            "reason": None,
        })
    return sorted(results, key=lambda x: x["score"], reverse=True)
