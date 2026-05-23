import pytest
from PIL import Image


@pytest.fixture
def sample_image(tmp_path):
    img = Image.new("RGB", (400, 300), color=(128, 128, 128))
    path = tmp_path / "sample.jpg"
    img.save(str(path))
    return str(path)


def test_sharpness_score_returns_0_to_100(sample_image):
    from app.services.photo_scorer import sharpness_score
    s = sharpness_score(sample_image)
    assert 0 <= s <= 100


def test_brightness_score_returns_0_to_100(sample_image):
    from app.services.photo_scorer import brightness_score
    s = brightness_score(sample_image)
    assert 0 <= s <= 100


def test_combined_score_returns_0_to_100(sample_image):
    from app.services.photo_scorer import combined_score
    s = combined_score(sample_image)
    assert 0 <= s <= 100


def test_score_directory_returns_sorted_list(tmp_path):
    from app.services.photo_scorer import score_directory
    for i in range(3):
        img = Image.new("RGB", (400, 300), color=(i * 80, i * 80, i * 80))
        img.save(str(tmp_path / f"img{i}.jpg"))
    results = score_directory(str(tmp_path))
    assert len(results) == 3
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
