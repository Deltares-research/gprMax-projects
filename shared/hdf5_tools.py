from pathlib import Path


def output_path(filename: str, root: str | Path = "outputs") -> Path:
    return Path(root) / filename
