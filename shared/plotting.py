from pathlib import Path


def figure_path(filename: str, root: str | Path = "wheels/figures") -> Path:
    return Path(root) / filename
