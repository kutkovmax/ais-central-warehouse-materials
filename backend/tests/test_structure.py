from pathlib import Path


def test_backend_structure_exists() -> None:
    root = Path(__file__).parents[1]
    assert (root / "app" / "main.py").exists()
    assert (root / "app" / "models.py").exists()
