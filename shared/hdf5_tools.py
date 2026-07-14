from pathlib import Path


def output_path(filename: str, root: str | Path = "wheels/outputs") -> Path:
    return Path(root) / filename
