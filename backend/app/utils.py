from pathlib import Path


def ensure_upload_dir() -> None:
    Path("./uploads").mkdir(parents=True, exist_ok=True)

