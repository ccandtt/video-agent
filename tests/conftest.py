"""Keep test scratch directories inside the project, including fresh clones."""
from pathlib import Path
import pytest

@pytest.fixture(scope="session", autouse=True)
def project_test_directories():
    root = Path(__file__).resolve().parents[1]
    for relative in (".cache", "tmp", "data/processed"):
        (root / relative).mkdir(parents=True, exist_ok=True)
